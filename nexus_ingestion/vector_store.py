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

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        similarity_threshold: float = 0.52,
        filter_dict: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda por similitud vectorial con pre-filtrado seguro por metadatos (prefilter=True)
        y calibración de umbral anti-alucinaciones (RF13: Xbase = 0.52).
        """
        if self.table is None:
            return []

        query = self.table.search(query_vector).metric("cosine")

        # Aplicar filtros sanitizados ANTES de la búsqueda ANN (prefilter=True)
        if filter_dict:
            where_clause = build_safe_where_clause(filter_dict)
            if where_clause:
                query = query.where(where_clause, prefilter=True)

        results = query.limit(top_k).to_pandas()

        filtered_results = []
        for _, row in results.iterrows():
            distance = float(row.get("_distance", 1.0))
            similarity = 1.0 - distance

            if similarity >= similarity_threshold:
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
                })

        return filtered_results

    def count(self) -> int:
        if self.table is None:
            return 0
        return self.table.count_rows()
