import os
import re
from typing import List, Dict, Any, Optional
from .config import config, IngestionConfig
from .extractors.ocr_engine import get_ocr_engine
from .extractors.pdf_extractor import PDFExtractor
from .extractors.html_extractor import HTMLExtractor
from .extractors.text_normalizer import normalize_text
from .classifier import DocumentClassifier
from .chunker import StructuralChunker
from .embedder import TextEmbedder
from .vector_store import LanceDBVectorStore

_SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm", ".md", ".txt"}
_YAML_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


class IngestionPipeline:
    """
    Pipeline unificado de ingesta, clasificación, chunking estricto y vectorización
    para el proyecto Nexus FI. Soporta archivos individuales o directorios completos.
    """

    def __init__(self, cfg: Optional[IngestionConfig] = None):
        self.cfg = cfg or config

        ocr = get_ocr_engine(provider=self.cfg.ocr_provider, region=self.cfg.aws_region)
        self.pdf_extractor = PDFExtractor(
            ocr_engine=ocr,
            max_file_size_mb=self.cfg.max_file_size_mb,
            max_pdf_pages=self.cfg.max_pdf_pages,
        )
        self.html_extractor = HTMLExtractor(max_file_size_mb=self.cfg.max_file_size_mb)
        self.classifier = DocumentClassifier()
        self.chunker = StructuralChunker(
            target_tokens=self.cfg.chunk_size_tokens,
            overlap_tokens=self.cfg.chunk_overlap_tokens,
            min_tokens=self.cfg.min_chunk_tokens,
            max_tokens=self.cfg.max_chunk_tokens,
        )
        self.embedder = TextEmbedder(
            api_key=self.cfg.openai_api_key,
            model=self.cfg.embedding_model,
            dimensions=self.cfg.embedding_dimensions,
        )
        self.vector_store = LanceDBVectorStore(
            uri=self.cfg.lancedb_uri,
            table_name=self.cfg.table_name,
            embedding_dim=self.cfg.embedding_dimensions,
            local_cache_dir=self.cfg.local_cache_dir,
        )

    def process_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Procesa un único archivo, normaliza su texto y devuelve los chunks generados."""
        ext = os.path.splitext(file_path)[1].lower()
        doc_name = os.path.basename(file_path)

        if ext == ".pdf":
            pages = self.pdf_extractor.extract(file_path)
        elif ext in (".html", ".htm"):
            pages = self.html_extractor.extract(file_path)
        elif ext in (".md", ".txt"):
            max_bytes = self.cfg.max_file_size_mb * 1024 * 1024
            if os.path.getsize(file_path) > max_bytes:
                raise ValueError(f"El archivo excede el límite de {self.cfg.max_file_size_mb} MB: {file_path}")
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Remover YAML Frontmatter si el archivo proviene de /Procesados
            content = _YAML_FRONTMATTER_RE.sub("", content)
            normalized = normalize_text(content)
            pages = [{"page_number": 1, "text": normalized, "is_ocr": False}] if normalized else []
        else:
            return []

        if not pages:
            return []

        sample_text = "\n".join(p["text"] for p in pages[:2])
        metadata = self.classifier.classify(file_path, sample_text=sample_text)

        chunks = self.chunker.chunk_document(doc_name, pages, metadata)
        return chunks

    def run_directory(
        self,
        input_path: str,
        skip_embeddings: bool = False,
        mode: str = "upsert",
    ) -> Dict[str, Any]:
        """
        Ejecuta la ingesta sobre un archivo individual o un directorio completo.
        - skip_embeddings=True: Modo validación/dry-run sin costo de API.
        - mode='upsert': Actualiza de forma idempotente solo los documentos procesados.
        - mode='overwrite': Recrea la tabla vectorial completa.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"La ruta de entrada no existe: {input_path}")

        all_files: List[str] = []
        if os.path.isfile(input_path):
            ext = os.path.splitext(input_path)[1].lower()
            if ext in _SUPPORTED_EXTENSIONS:
                all_files.append(input_path)
            else:
                raise ValueError(f"Extensión de archivo no soportada: {ext}")
        else:
            for root, _, files in os.walk(input_path):
                for f in sorted(files):
                    ext = os.path.splitext(f)[1].lower()
                    if ext in _SUPPORTED_EXTENSIONS:
                        all_files.append(os.path.join(root, f))

        total_files = len(all_files)
        processed_files = 0
        total_chunks: List[Dict[str, Any]] = []
        stats: Dict[str, Any] = {
            "total_files": total_files,
            "processed_files": 0,
            "total_chunks": 0,
            "total_tokens": 0,
            "by_category": {},
        }

        print(f"[IngestionPipeline] Iniciando procesamiento de {total_files} archivo(s)...")

        for idx, file_path in enumerate(all_files):
            try:
                chunks = self.process_file(file_path)
                if chunks:
                    processed_files += 1
                    total_chunks.extend(chunks)
                    cat = chunks[0]["categoria"]
                    stats["by_category"][cat] = stats["by_category"].get(cat, 0) + len(chunks)

                if (idx + 1) % 10 == 0 or idx + 1 == total_files:
                    print(
                        f"  Progreso: {idx + 1}/{total_files} archivo(s) evaluados "
                        f"({len(total_chunks)} chunks acumulados)."
                    )
            except Exception as e:
                print(f"[Error en {file_path}]: {e}")

        stats["processed_files"] = processed_files
        stats["total_chunks"] = len(total_chunks)
        stats["total_tokens"] = sum(c.get("token_count", 0) for c in total_chunks)

        if not skip_embeddings and total_chunks:
            print(
                f"[IngestionPipeline] Generando embeddings para {len(total_chunks)} chunks "
                f"con {self.cfg.embedding_model} (modo={mode})..."
            )
            chunk_texts = [c["text"] for c in total_chunks]
            embeddings = self.embedder.embed_texts(
                chunk_texts,
                batch_size=self.cfg.embedding_batch_size,
            )

            print(f"[IngestionPipeline] Almacenando en LanceDB ({self.cfg.lancedb_uri})...")
            self.vector_store.save_chunks(total_chunks, embeddings, mode=mode)
            print(
                f"[IngestionPipeline] Ingesta completada con éxito. "
                f"Total registros en tabla: {self.vector_store.count()}."
            )
        elif skip_embeddings:
            print("[IngestionPipeline] Ingesta terminada en modo validación (sin llamadas a embeddings).")

        return stats
