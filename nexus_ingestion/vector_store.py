import os
import re
import uuid
from typing import List, Dict, Any, Optional, Set
import lancedb
import pandas as pd
import pyarrow as pa

# Lista blanca estricta de columnas permitidas para filtrado de metadatos (Mitigación SQL/DataFusion Injection)
ALLOWED_FILTER_COLUMNS: Set[str] = {
    "id",
    "documento",
    "categoria",
    "subcategoria",
    "carrera",
    "periodo",
    "articulo",
}

_SAFE_VALUE_REGEX = re.compile(r"^[\w\s\-\.\,\(\)\/áéíóúÁÉÍÓÚñÑüÜ]+$")


def build_safe_where_clause(filter_dict: Dict[str, str]) -> str:
    """
    Construye una cláusula WHERE parametrizada y validada contra inyección de predicados
    en LanceDB / Apache Arrow DataFusion.
    """
    clauses = []
    for col, val in filter_dict.items():
        if col not in ALLOWED_FILTER_COLUMNS:
            raise ValueError(
                f"Columna de filtrado no permitida: '{col}'. "
                f"Permitidas: {sorted(ALLOWED_FILTER_COLUMNS)}"
            )
        if not isinstance(val, str):
            val = str(val)
        val = val.strip()
        if not val:
            continue
        if any(ord(ch) < 32 for ch in val) or "--" in val or ";" in val or "/*" in val:
            raise ValueError(f"Valor de filtro rechazado por contener caracteres no seguros: '{val}'")
        if not _SAFE_VALUE_REGEX.match(val):
            raise ValueError(f"Formato de valor de filtro no válido para '{col}': '{val}'")
        escaped_val = val.replace("'", "''")
        clauses.append(f"{col} = '{escaped_val}'")
    return " AND ".join(clauses)


# ---------------------------------------------------------------------------
# Coincidencia exacta de términos poco comunes (complemento de RF13)
# Las preguntas muy cortas sobre un nombre propio («¿Qué es Potropath?») dan una similitud
# coseno baja aunque el fragmento correcto salga primero. Si la pregunta contiene una palabra
# que aparece en muy pocos fragmentos del acervo y un candidato la contiene tal cual, se acepta
# aunque quede bajo el umbral, siempre que supere un piso mínimo. Las preguntas fuera de tema
# no se ven afectadas: sus palabras no aparecen en el acervo.
# ---------------------------------------------------------------------------
TERMINO_MIN_LETRAS = 5
TERMINO_MAX_FRAGMENTOS = 5      # una palabra es «poco común» si aparece en 5 fragmentos o menos
SIMILITUD_MINIMA_TERMINO = 0.30
CANDIDATOS_TERMINO = 10

_PALABRAS_COMUNES: Set[str] = {
    "cuales", "cuando", "donde", "quien", "quienes", "puedo", "podria", "tengo", "tiene", "tienen",
    "sobre", "entre", "hacer", "hacen", "necesito", "debo", "deben", "existe", "existen", "informacion",
    "facultad", "ingenieria", "computacion", "uaemex", "alumno", "alumnos", "estudiante", "estudiantes",
    "tramite", "tramites", "requisitos", "semestre", "materia", "materias", "horario", "horarios",
}


def _normalizar(texto: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _palabras(texto: str) -> Set[str]:
    return {p for p in re.findall(r"[a-z0-9]+", _normalizar(texto))
            if len(p) >= TERMINO_MIN_LETRAS and p not in _PALABRAS_COMUNES and not p.isdigit()}


# ---------------------------------------------------------------------------
# Fragmentos casi duplicados (plan de implementación, ajuste de F2)
#
# Muchos temarios traen incrustada la misma página del mapa curricular, extraída como una
# lista de materias revuelta. Varias copias de ese texto llegaban a ocupar todas las fuentes
# de una respuesta, dejaban fuera el documento correcto (p. ej. el horario del semestre) y el
# LLM armaba listas de materias inventadas. Se descartan los candidatos que comparten casi
# todas sus palabras con uno mejor clasificado. Los textos muy cortos no se comparan: con
# pocas palabras, dos fragmentos distintos («Laboratorio 1», «Laboratorio 2») se parecen mucho.
# ---------------------------------------------------------------------------
UMBRAL_DUPLICADO = 0.80          # índice de Jaccard sobre el conjunto de palabras
MIN_PALABRAS_DUPLICADO = 30      # solo se comparan fragmentos con al menos tantas palabras distintas
FACTOR_CANDIDATOS = 3            # candidatos por cada resultado pedido, para reponer los descartados
MIN_CANDIDATOS = 12
_ENCABEZADO = re.compile(r"^\s*\[DOCUMENTO:[^\]]*\]")


def _huella(texto: str) -> Set[str]:
    """Conjunto de palabras del fragmento sin su encabezado [DOCUMENTO: ...]."""
    return set(re.findall(r"[a-z0-9]+", _normalizar(_ENCABEZADO.sub("", texto or ""))))


def es_casi_duplicado(huella: Set[str], elegidas: List[Set[str]]) -> bool:
    if len(huella) < MIN_PALABRAS_DUPLICADO:
        return False
    for otra in elegidas:
        if len(otra) < MIN_PALABRAS_DUPLICADO:
            continue
        if len(huella & otra) / len(huella | otra) >= UMBRAL_DUPLICADO:
            return True
    return False


# ---------------------------------------------------------------------------
# Preguntas de trámite que no encuentran su norma (defecto D-02)
#
# «¿Qué opciones de titulación tengo en ICO?» no recuperaba el Reglamento de Evaluación
# Profesional: la norma no usa la palabra «titulación», y «Ingeniería en Computación», «ICO» o
# «créditos» acercan la pregunta a los programas de materia, que llenaban los 4 lugares.
# Tres medidas, medidas el 23/11/2026 sobre 28 preguntas (de 18 a 25 aciertos, sin retrocesos):
#   1. Glosario: al texto que se vectoriza se le agrega el nombre de la norma del tema. Solo
#      donde la norma usa otras palabras que la pregunta («titulación» frente a «evaluación
#      profesional»); en servicio social reordenaba el reglamento y dejaba fuera el art. 16 (480 h).
#   2. Refuerzo por título: los fragmentos de esa norma suman REFUERZO_TITULO al puntaje con
#      que se ordenan y se comparan con el umbral; la similitud que se informa es la real.
#   3. Diversidad: como máximo MAX_POR_DOCUMENTO fragmentos de un mismo documento, salvo la
#      norma reforzada, que puede ocupar todos los lugares.
# Solo se activan con preguntas del tema; las fuera de tema no cambian.
# Cada entrada: (patrón en la pregunta normalizada, texto del glosario o None, patrón en el nombre del documento)
# ---------------------------------------------------------------------------
TEMAS_NORMATIVOS = [
    (r"titula", "Reglamento de Evaluación Profesional: modalidades u opciones de evaluación profesional",
     r"evaluacion profesional"),
    (r"servicio social", None, r"servicio social"),
    (r"practicas? profesional", None, r"practicas? profesional"),
    (r"movilidad", None, r"movilidad"),
]
REFUERZO_TITULO = 0.06
MAX_POR_DOCUMENTO = 2
CANDIDATOS_REFUERZO = 20         # candidatos que se piden aparte a los documentos reforzados
MIN_CANDIDATOS_TOPE = 40         # candidatos mínimos cuando se limita el número por documento


def _temas(texto: str) -> list:
    t = _normalizar(texto)
    return [tema for tema in TEMAS_NORMATIVOS if re.search(tema[0], t)]


def expandir_consulta(texto: str) -> str:
    """Texto que se vectoriza: la pregunta más el nombre de la norma de cada tema que toca."""
    extra = [glosa for _, glosa, _ in _temas(texto) if glosa]
    return f"{texto} ({'; '.join(extra)})" if extra else texto


def get_vector_schema(embedding_dim: int = 1536) -> pa.Schema:
    """Esquema explícito Apache Arrow para garantizar consistencia de tipos en LanceDB."""
    return pa.schema([
        pa.field("id", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), embedding_dim)),
        pa.field("text", pa.string()),
        pa.field("raw_text", pa.string()),
        pa.field("documento", pa.string()),
        pa.field("categoria", pa.string()),
        pa.field("subcategoria", pa.string()),
        pa.field("carrera", pa.string()),
        pa.field("periodo", pa.string()),
        pa.field("articulo", pa.string()),
        pa.field("pagina_inicio", pa.int64()),
        pa.field("pagina_fin", pa.int64()),
    ])


class LanceDBVectorStore:
    """
    Gestor de base de datos vectorial sobre LanceDB (compatible con local, caché efímero y S3).
    Incluye upsert idempotente por documento, pre-filtrado seguro contra inyecciones y umbral RF13.
    """

    def __init__(
        self,
        uri: str = "./data/lancedb",
        table_name: str = "nexus_documents",
        embedding_dim: int = 1536,
        local_cache_dir: str = "",
    ):
        self.uri = uri
        self.table_name = table_name
        self.embedding_dim = embedding_dim
        self.local_cache_dir = local_cache_dir

        # Si se configura un directorio de caché local para S3 y ya existe en disco, priorizarlo en lectura
        effective_uri = self.uri
        if self.uri.startswith("s3://") and self.local_cache_dir and os.path.exists(self.local_cache_dir):
            effective_uri = self.local_cache_dir
        elif not self.uri.startswith("s3://"):
            os.makedirs(self.uri, exist_ok=True)

        self.db = lancedb.connect(effective_uri)
        self.table = None
        self._init_table()

    def _init_table(self):
        """Abre la tabla si existe en el catálogo actual."""
        existing_tables = self.db.table_names()
        if self.table_name in existing_tables:
            self.table = self.db.open_table(self.table_name)

    def save_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        mode: str = "upsert",
    ):
        """
        Inserta o actualiza chunks vectorizados de forma idempotente:
        - mode='overwrite': Recrea la tabla completa desde cero.
        - mode='upsert': Elimina previamente los chunks antiguos de los mismos documentos
          antes de insertar los nuevos, evitando duplicados en actualizaciones parciales.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("El número de chunks y de embeddings no coincide.")
        if not chunks:
            return

        data = []
        docs_in_batch: Set[str] = set()
        for idx, (chunk, vector) in enumerate(zip(chunks, embeddings), start=1):
            doc_name = chunk["documento"]
            docs_in_batch.add(doc_name)
            chunk_id = chunk.get("chunk_id") or chunk.get("id") or f"{doc_name}_c{idx:03d}_{uuid.uuid4().hex[:6]}"
            data.append({
                "id": str(chunk_id),
                "vector": vector,
                "text": chunk["text"],
                "raw_text": chunk.get("raw_text", ""),
                "documento": doc_name,
                "categoria": chunk["categoria"],
                "subcategoria": chunk.get("subcategoria", ""),
                "carrera": chunk.get("carrera", "GENERAL_FI"),
                "periodo": chunk.get("periodo", "VIGENTE"),
                "articulo": chunk.get("articulo", ""),
                "pagina_inicio": int(chunk.get("pagina_inicio", 1)),
                "pagina_fin": int(chunk.get("pagina_fin", 1)),
            })

        schema = get_vector_schema(self.embedding_dim)

        if self.table is None or mode == "overwrite":
            self.table = self.db.create_table(
                self.table_name,
                data=data,
                schema=schema,
                mode="overwrite",
            )
        else:
            # Upsert idempotente: borrar registros previos de los documentos que se están actualizando
            for doc_name in docs_in_batch:
                escaped_doc = doc_name.replace("'", "''")
                self.table.delete(f"documento = '{escaped_doc}'")
            self.table.add(data)
        # Las cachés derivadas del acervo se recalculan con los datos nuevos
        self._df_terminos = None
        self._nombres_documentos = None

    def documentos_reforzados(self, query_text: str) -> Set[str]:
        """Documentos cuyo nombre corresponde a un tema normativo de la pregunta (D-02)."""
        temas = _temas(query_text or "")
        if not temas or self.table is None:
            return set()
        if getattr(self, "_nombres_documentos", None) is None:
            self._nombres_documentos = sorted(set(self.table.to_arrow().column("documento").to_pylist()))
        return {d for d in self._nombres_documentos
                if any(re.search(patron, _normalizar(d)) for _, _, patron in temas)}

    def _frecuencia_terminos(self) -> Dict[str, int]:
        """En cuántos fragmentos aparece cada palabra (se calcula una vez por proceso)."""
        if getattr(self, "_df_terminos", None) is None:
            frecuencia: Dict[str, int] = {}
            if self.table is not None:
                for texto in self.table.to_arrow().column("text").to_pylist():
                    for p in _palabras(texto):
                        frecuencia[p] = frecuencia.get(p, 0) + 1
            self._df_terminos = frecuencia
        return self._df_terminos

    def terminos_distintivos(self, query_text: str) -> Set[str]:
        """Palabras de la pregunta que aparecen en pocos fragmentos del acervo (p. ej. un nombre propio)."""
        frecuencia = self._frecuencia_terminos()
        return {p for p in _palabras(query_text) if 0 < frecuencia.get(p, 0) <= TERMINO_MAX_FRAGMENTOS}

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        similarity_threshold: float = 0.52,
        filter_dict: Optional[Dict[str, str]] = None,
        query_text: Optional[str] = None,
        quitar_duplicados: bool = True,
        reforzar_normativa: bool = False,
        max_por_documento: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda por similitud vectorial con pre-filtrado seguro por metadatos (prefilter=True)
        y calibración de umbral anti-alucinaciones (RF13: Xbase = 0.52).

        Si se pasa query_text, también se aceptan fragmentos bajo el umbral (pero sobre
        SIMILITUD_MINIMA_TERMINO) que contienen tal cual una palabra poco común de la pregunta.

        Con quitar_duplicados (por defecto), un candidato casi idéntico a otro mejor clasificado
        se descarta y su lugar lo toma el siguiente candidato.

        Con reforzar_normativa y query_text, los fragmentos de la norma del tema de la pregunta
        suman REFUERZO_TITULO a su puntaje (D-02). max_por_documento limita cuántos fragmentos
        de un mismo documento entran al resultado.
        """
        if self.table is None:
            return []

        terminos = self.terminos_distintivos(query_text) if query_text else set()
        reforzados = self.documentos_reforzados(query_text) if (reforzar_normativa and query_text) else set()

        where_clause = build_safe_where_clause(filter_dict) if filter_dict else ""

        def consulta():
            q = self.table.search(query_vector).metric("cosine")
            if where_clause:   # filtros sanitizados ANTES de la búsqueda ANN (prefilter=True)
                q = q.where(where_clause, prefilter=True)
            return q

        limite = max(top_k, CANDIDATOS_TERMINO) if terminos else top_k
        if quitar_duplicados or max_por_documento:
            limite = max(limite, top_k * FACTOR_CANDIDATOS, MIN_CANDIDATOS)
        if max_por_documento:   # con el tope se descartan más candidatos: hay que pedir más
            limite = max(limite, MIN_CANDIDATOS_TOPE)
        results = consulta().limit(limite).to_pandas()

        if reforzados:
            # La norma puede quedar lejos en el orden coseno: se piden aparte sus mejores fragmentos.
            # Los nombres salen de la propia tabla y se escapan; no vienen del usuario.
            lista = ", ".join("'" + d.replace("'", "''") + "'" for d in sorted(reforzados))
            extra = (self.table.search(query_vector).metric("cosine")
                     .where(" AND ".join(filter(None, [where_clause, f"documento IN ({lista})"])), prefilter=True)
                     .limit(CANDIDATOS_REFUERZO).to_pandas())
            results = pd.concat([results, extra]).drop_duplicates(subset="id")

        results = results.copy()
        results["_similitud"] = 1.0 - results["_distance"].astype(float)
        results["_puntaje"] = results["_similitud"] + results["documento"].isin(reforzados) * REFUERZO_TITULO
        results = results.sort_values("_puntaje", ascending=False, kind="stable")

        filtered_results = []
        huellas: List[Set[str]] = []
        por_documento: Dict[str, int] = {}
        for _, row in results.iterrows():
            similarity = float(row["_similitud"])
            puntaje = float(row["_puntaje"])

            coincidencia = (
                puntaje < similarity_threshold
                and similarity >= SIMILITUD_MINIMA_TERMINO
                and bool(terminos & _palabras(row["text"]))
            )
            if puntaje >= similarity_threshold or coincidencia:
                if len(filtered_results) >= top_k:
                    break
                if (max_por_documento and row["documento"] not in reforzados
                        and por_documento.get(row["documento"], 0) >= max_por_documento):
                    continue
                if quitar_duplicados:
                    huella = _huella(row["text"])
                    if es_casi_duplicado(huella, huellas):
                        continue
                    huellas.append(huella)
                por_documento[row["documento"]] = por_documento.get(row["documento"], 0) + 1
                filtered_results.append({
                    "id": row["id"],
                    "documento": row["documento"],
                    "categoria": row["categoria"],
                    "subcategoria": row.get("subcategoria", ""),
                    "carrera": row.get("carrera", ""),
                    "periodo": row.get("periodo", ""),
                    "articulo": row["articulo"],
                    "pagina": f"{row['pagina_inicio']}-{row['pagina_fin']}",
                    "text": row["text"],
                    "raw_text": row.get("raw_text", ""),
                    "similarity": round(similarity, 4),
                    "coincidencia_exacta": coincidencia,
                    "reforzado": row["documento"] in reforzados,
                })

        return filtered_results

    def count(self) -> int:
        if self.table is None:
            return 0
        return self.table.count_rows()
