import argparse
import json
from .config import config, IngestionConfig
from .pipeline import IngestionPipeline


def main():
    parser = argparse.ArgumentParser(
        description="Nexus FI — Motor de Ingesta, Clasificación y Vectorización (WBS 1.3.2)"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="Pre Procesados",
        help="Ruta al archivo o directorio de documentos a procesar.",
    )
    parser.add_argument(
        "--lancedb-uri",
        type=str,
        default=config.lancedb_uri,
        help="URI de almacenamiento para LanceDB (ej. ./data/lancedb o s3://tu-bucket/lancedb).",
    )
    parser.add_argument(
        "--ocr-provider",
        type=str,
        choices=["local", "aws_textract"],
        default=config.ocr_provider,
        help="Motor de OCR para PDFs escaneados: 'local' (RapidOCR ONNX) o 'aws_textract'.",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Ejecuta la extracción, clasificación y chunking sin llamar a la API de OpenAI (modo dry-run).",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["upsert", "overwrite"],
        default="upsert",
        help="Modo de escritura en LanceDB: 'upsert' (actualización idempotente) o 'overwrite' (reemplazo total).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=config.chunk_size_tokens,
        help="Tamaño objetivo de cada fragmento en tokens (por defecto 650).",
    )

    args = parser.parse_args()

    cfg = IngestionConfig(
        ocr_provider=args.ocr_provider,
        lancedb_uri=args.lancedb_uri,
        chunk_size_tokens=args.chunk_size,
    )

    pipeline = IngestionPipeline(cfg=cfg)
    stats = pipeline.run_directory(
        args.input,
        skip_embeddings=args.skip_embeddings,
        mode=args.mode,
    )

    print("\n--- Resumen de Ingesta Nexus FI ---")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
