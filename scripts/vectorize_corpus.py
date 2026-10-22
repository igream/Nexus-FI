import os
import sys
import json
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

from nexus_ingestion.embedder import TextEmbedder
from nexus_ingestion.vector_store import LanceDBVectorStore

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
CORPUS_JSONL = str(BASE_DIR / "Procesados" / "corpus_chunks_para_embedding.jsonl")
DEFAULT_LANCEDB_DIR = str(BASE_DIR / "data" / "lancedb")
TABLE_NAME = os.getenv("LANCEDB_TABLE_NAME", "nexus_documents")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))


def main():
    parser = argparse.ArgumentParser(description="Nexus FI — Vectorización del Acervo Documental (WBS 1.3.1)")
    parser.add_argument("--lancedb-uri", type=str, default=DEFAULT_LANCEDB_DIR, help="Ruta de destino de LanceDB")
    parser.add_argument("--batch-size", type=int, default=128, help="Tamaño de lote para la API de OpenAI")
    parser.add_argument("--limit", type=int, default=0, help="Limitar número de chunks para prueba (0 = procesar todos)")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["upsert", "overwrite"],
        default="overwrite",
        help="Modo de guardado en LanceDB: 'overwrite' o 'upsert'",
    )

    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("\n" + "=" * 70)
        print("ERROR: NO SE ENCONTRÓ LA VARIABLE DE ENTORNO OPENAI_API_KEY")
        print("=" * 70)
        print("Por seguridad, la API Key no debe pasarse por argumentos CLI.")
        print("Configúrala mediante:")
        print("  1. Archivo .env local (OPENAI_API_KEY=sk-proj-...)")
        print("  2. Variable de entorno del sistema / AWS Secrets Manager.")
        print("=" * 70 + "\n")
        sys.exit(1)

    if not os.path.exists(CORPUS_JSONL):
        print(f"Error: No se encontró el archivo {CORPUS_JSONL}.")
        sys.exit(1)

    print("=" * 80)
    print(f"NEXUS FI — VECTORIZACIÓN CON {EMBEDDING_MODEL} ({EMBEDDING_DIM} dimensiones)")
    print(f"Destino LanceDB: {args.lancedb_uri}")
    print("=" * 80)

    chunks = []
    with open(CORPUS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    total_chunks = len(chunks)
    if args.limit > 0:
        chunks = chunks[: args.limit]
        print(f"Modo prueba activado: Procesando {len(chunks)} de {total_chunks} chunks.")
    else:
        print(f"Total de chunks a vectorizar: {total_chunks}")

    total_tokens = sum(c.get("token_count", 0) for c in chunks)
    costo_usd = (total_tokens / 1_000_000) * 0.02
    costo_mxn = costo_usd * 20.0
    print(f"Tokens aproximados : {total_tokens:,}")
    print(f"Costo estimado API : ${costo_usd:.4f} USD (~${costo_mxn:.2f} MXN)")
    print("=" * 80)

    embedder = TextEmbedder(api_key=api_key, model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIM)
    store = LanceDBVectorStore(uri=args.lancedb_uri, table_name=TABLE_NAME, embedding_dim=EMBEDDING_DIM)

    t_start = time.time()
    texts = [item["text"] for item in chunks]
    print(f"\nGenerando embeddings en lotes de {args.batch_size} con connection pooling...")
    vectors = embedder.embed_texts(texts, batch_size=args.batch_size)

    print(f"Guardando {len(vectors)} registros en la tabla '{TABLE_NAME}' (modo={args.mode})...")
    store.save_chunks(chunks, vectors, mode=args.mode)
    total_time = time.time() - t_start

    print("=" * 80)
    print("VECTORIZACIÓN COMPLETADA CON ÉXITO")
    print(f"Tiempo total         : {total_time:.2f} segundos ({total_time / 60:.2f} minutos)")
    print(f"Total vectores en BD : {store.count()}")
    print(f"Base de datos lista en: {args.lancedb_uri}")
    print("=" * 80)

    print("\n--- EJECUTANDO PRUEBA DE BÚSQUEDA SEMÁNTICA (RF13) ---")
    query_text = "¿Cuáles son los requisitos para la beca de reinscripción escolar en otoño?"
    print(f"Consulta de prueba: '{query_text}'")

    query_vec = embedder.embed_query(query_text)
    results = store.search(query_vec, top_k=3, similarity_threshold=0.52)

    print("\nResultados obtenidos:")
    for idx, res in enumerate(results, start=1):
        print(f"\n[Resultado {idx}] Similitud Coseno: {res['similarity']:.4f}")
        print(f"Documento: {res['documento']} | Pág: {res['pagina']} | Art: {res['articulo']}")
        print(f"Texto:\n{res['text'][:250]}...")


if __name__ == "__main__":
    main()
