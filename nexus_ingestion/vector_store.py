import os
import re
import uuid
from typing import List, Dict, Any, Optional, Set
import lancedb
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
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda por similitud vectorial con pre-filtrado seguro por metadatos (prefilter=True)
        y calibración de umbral anti-alucinaciones (RF13: Xbase = 0.52).

        Si se pasa query_text, también se aceptan fragmentos bajo el umbral (pero sobre
        SIMILITUD_MINIMA_TERMINO) que contienen tal cual una palabra poco común de la pregunta.
        """
        if self.table is None:
            return []

        terminos = self.terminos_distintivos(query_text) if query_text else set()

        query = self.table.search(query_vector).metric("cosine")

        # Aplicar filtros sanitizados ANTES de la búsqueda ANN (prefilter=True)
        if filter_dict:
            where_clause = build_safe_where_clause(filter_dict)
            if where_clause:
                query = query.where(where_clause, prefilter=True)

        limite = max(top_k, CANDIDATOS_TERMINO) if terminos else top_k
        results = query.limit(limite).to_pandas()

        filtered_results = []
        for _, row in results.iterrows():
            distance = float(row.get("_distance", 1.0))
            similarity = 1.0 - distance

            coincidencia = (
                similarity < similarity_threshold
                and similarity >= SIMILITUD_MINIMA_TERMINO
                and bool(terminos & _palabras(row["text"]))
            )
            if similarity >= similarity_threshold or coincidencia:
                if len(filtered_results) >= top_k:
                    break
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
                })

        return filtered_results

    def count(self) -> int:
        if self.table is None:
            return 0
        return self.table.count_rows()
