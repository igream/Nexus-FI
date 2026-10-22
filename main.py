#!/usr/bin/env python3
"""
Nexus FI — Asistente Virtual Inteligente RAG (Facultad de Ingeniería - UAEMéx)
Repositorio Oficial: https://github.com/igream/Nexus-FI
Equipo 404 (Ingeniería en Computación)
Product Manager: Fernando Azuara Ibarra

Punto de entrada unificado para el sistema:
- Servidor REST API & PWA Web (/api/chat, /api/health, /api/stats)
- Módulo DT-10: Seguridad, conectividad y telemetría
- CLI de Búsqueda Semántica Vectorial con umbral RF13 (0.52)
- Auditor de Seguridad de Secretos y Control de Versiones
"""

import os
import sys
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Configurar salida UTF-8 para consolas de Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def print_banner():
    banner = """
========================================================================
       _   _ _____ _   _ _   _ ____    _____ ___ 
      | \\ | | ____| \\ | | | | / ___|  |  ___|_ _|
      |  \\| |  _| |  \\| | | | \\___ \\  | |_   | | 
      | |\\  | |___| |\\  | |_| |___) | |  _|  | | 
      |_| \\_|_____|_| \\_|\\___/|____/  |_|   |___|
      
   Asistente Virtual Inteligente con Búsqueda Semántica RAG
      Facultad de Ingeniería - UAEMéx | Equipo 404
========================================================================
"""
    print(banner)


def run_telemetry_dt10():
    """Módulo DT-10: Verificación de Credenciales, Conectividad y Telemetría."""
    print("------------------------------------------------------------------------")
    print(" [MÓDULO DT-10] Verificación de Seguridad, Conectividad y Telemetría")
    print("------------------------------------------------------------------------")

    openai_key = os.getenv("OPENAI_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    aws_id = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    print(f" [1/4] OpenAI API Key:       {'Configurada ✓ (' + openai_key[:7] + '...)' if openai_key else 'NO configurada ✗'}")
    print(f" [2/4] Google Gemini API Key: {'Configurada ✓ (' + gemini_key[:7] + '...)' if gemini_key else 'NO configurada (opcional)'}")
    print(f" [3/4] AWS Access Key ID:     {'Configurada ✓ (' + aws_id[:6] + '...)' if aws_id else 'NO configurada (opcional S3)'}")
    print(f"       AWS Region:            {aws_region}")

    # Verificar Base de Datos Vectorial LanceDB
    print("\n [4/4] Verificando Base de Datos Vectorial LanceDB...")
    vdb_dir = BASE_DIR / "data" / "lancedb"
    if vdb_dir.exists():
        try:
            from nexus_ingestion.vector_store import LanceDBVectorStore
            store = LanceDBVectorStore(uri=str(vdb_dir), table_name="nexus_documents")
            total_chunks = store.count()
            print(f"       LanceDB Status:        ONLINE ✓")
            print(f"       Tabla:                 nexus_documents")
            print(f"       Vectores Indexados:    {total_chunks:,} fragmentos (1536 dimensiones)")
        except Exception as e:
            print(f"       LanceDB Status:        ERROR ({e})")
    else:
        print(f"       LanceDB Status:        Directorio {vdb_dir} no encontrado.")

    # Prueba de telemetría de inferencia
    if openai_key:
        print("\n [Test] Realizando prueba de telemetría y latencia con OpenAI...")
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            t0 = time.time()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Responde 'OK' en una sola palabra."}],
                max_tokens=5,
            )
            lat = round((time.time() - t0) * 1000, 2)
            content = resp.choices[0].message.content.strip()
            print(f"       Conexión exitosa ✓ (Latencia: {lat} ms | Respuesta: '{content}')")
        except Exception as e:
            print(f"       Aviso telemetría: {e}")
    else:
        print("\n [Aviso] Para activar telemetría en la nube, configura OPENAI_API_KEY en tu .env")

    print("------------------------------------------------------------------------\n")


def run_audit():
    """Ejecuta el auditor de seguridad de credenciales y repositorio."""
    print("------------------------------------------------------------------------")
    print(" [SEGURIDAD] Ejecutando Auditoría de Secretos y Repositorio Git...")
    print("------------------------------------------------------------------------")
    auditor_script = BASE_DIR / "backend" / "config_api" / "auditor_seguridad_api.py"
    if auditor_script.exists():
        import subprocess
        subprocess.run([sys.executable, str(auditor_script)])
    else:
        print(f"Error: No se encontró el script auditor en {auditor_script}")


def run_cli_search(query: str, top_k: int = 4):
    """Búsqueda semántica directa en la consola con umbral RF13 y citas RF09."""
    print(f"\n[BÚSQUEDA SEMÁNTICA RAG] Consulta: '{query}'")
    print(f"Umbral anti-alucinaciones RF13: Xbase >= 0.52 | Top-K: {top_k}\n")

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        print("[Error] Se requiere OPENAI_API_KEY en .env para vectorizar la consulta.")
        return

    from nexus_ingestion.embedder import TextEmbedder
    from nexus_ingestion.vector_store import LanceDBVectorStore

    t0 = time.time()
    embedder = TextEmbedder(api_key=openai_key)
    store = LanceDBVectorStore(uri=str(BASE_DIR / "data" / "lancedb"), table_name="nexus_documents")

    q_vector = embedder.embed_query(query)
    results = store.search(q_vector, top_k=top_k, similarity_threshold=0.52)
    elapsed = round((time.time() - t0) * 1000, 2)

    print(f"Resultados encontrados: {len(results)} (Latencia: {elapsed} ms)\n")
    if not results:
        print("[-] No se encontraron fragmentos que superen el umbral oficial (0.52).")
        return

    for idx, r in enumerate(results, 1):
        sim_pct = round(r["similarity"] * 100, 1)
        print(f"--- [Resultado #{idx}] Similitud: {sim_pct}% ({r['similarity']}) ---")
        print(f"Documento:   {r['documento']}")
        print(f"Categoría:   {r['categoria']}")
        if r.get("articulo"):
            print(f"Artículo:    {r['articulo']}")
        if r.get("pagina"):
            print(f"Páginas:     {r['pagina']}")
        print(f"Fragmento:\n{r['text'][:350]}...\n")


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Inicia el servidor web FastAPI con la interfaz PWA y endpoints RAG."""
    import uvicorn
    print(f"\n[+] Iniciando Servidor Web Nexus FI en http://{host}:{port}")
    print(f"    - Interfaz de Chat:     http://{host}:{port}/")
    print(f"    - Panel de Métricas:    http://{host}:{port}/dashboard")
    print(f"    - Documentación API:    http://{host}:{port}/docs")
    print(f"    - Endpoint de Salud:    http://{host}:{port}/api/health")
    print(f"    - Presiona Ctrl+C para detener el servidor.\n")
    uvicorn.run("backend.app:app", host=host, port=port, reload=False)


def main():
    parser = argparse.ArgumentParser(
        description="Nexus FI — Asistente RAG para la Facultad de Ingeniería (UAEMéx)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--serve", "-s", action="store_true", help="Inicia el servidor web y la API REST")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"), help="Host para el servidor (def: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Puerto para el servidor (def: 8000)")
    parser.add_argument("--search", "-q", type=str, help="Ejecuta una consulta semántica directa en terminal")
    parser.add_argument("--telemetry", "-t", action="store_true", help="Ejecuta el diagnóstico de telemetría y seguridad DT-10")
    parser.add_argument("--audit", "-a", action="store_true", help="Ejecuta auditoría de claves y git")

    args = parser.parse_args()

    print_banner()

    if args.telemetry:
        run_telemetry_dt10()
    elif args.audit:
        run_audit()
    elif args.search:
        run_cli_search(args.search)
    elif args.serve:
        run_server(host=args.host, port=args.port)
    else:
        # Modo interactivo predeterminado
        run_telemetry_dt10()
        print("Opciones disponibles:")
        print("  1. Iniciar servidor web y API REST (python main.py --serve)")
        print("  2. Realizar búsqueda semántica CLI  (python main.py --search \"pregunta\")")
        print("  3. Auditoría de ciberseguridad      (python main.py --audit)")
        print("\nPara iniciar automáticamente el servidor, ejecutando ahora...")
        run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()