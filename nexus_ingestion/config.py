import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class IngestionConfig:
    # OpenAI Embedding Specs (WBS 1.3.2 / RF08)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "128"))

    # Chunking Specs (RF08: 500-800 tokens, ~15% overlap)
    chunk_size_tokens: int = int(os.getenv("CHUNK_SIZE_TOKENS", "650"))
    chunk_overlap_tokens: int = int(os.getenv("CHUNK_OVERLAP_TOKENS", "100"))
    min_chunk_tokens: int = int(os.getenv("MIN_CHUNK_TOKENS", "100"))
    max_chunk_tokens: int = int(os.getenv("MAX_CHUNK_TOKENS", "800"))

    # Límites de Seguridad contra DoS / OOM en contenedor Cloud
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    max_pdf_pages: int = int(os.getenv("MAX_PDF_PAGES", "500"))
    max_workers: int = int(os.getenv("MAX_WORKERS", str(min(4, os.cpu_count() or 2))))

    # RAG Calibration Threshold (RF13: Xbase = 0.52)
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.52"))

    # OCR Engine: "local" (RapidOCR ONNX) or "aws_textract"
    ocr_provider: str = os.getenv("OCR_PROVIDER", "local")

    # AWS S3 / LanceDB Target
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: str = os.getenv("S3_BUCKET_NAME", "nexus-fi-vectors")
    # LanceDB URI: Local path like "./data/lancedb" or S3 uri like "s3://nexus-fi-vectors/lancedb"
    lancedb_uri: str = os.getenv("LANCEDB_URI", "./data/lancedb")
    table_name: str = os.getenv("LANCEDB_TABLE_NAME", "nexus_documents")
    # Caché local efímero para lecturas de baja latencia cuando lancedb_uri es s3://
    local_cache_dir: str = os.getenv("LANCEDB_LOCAL_CACHE", "")


config = IngestionConfig()
