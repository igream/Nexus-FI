#!/usr/bin/env python3
"""
Generador y Recalculador de Embeddings Vectoriales con Gemini API
Proyecto: PotroBot UAEMéx (Ingeniería en Computación)
Modelo utilizado: gemini-embedding-2 (3,072 dimensiones)
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.config import GEMINI_API_KEY, VECTOR_STORE_PATH, RAW_DATA_DIR
from core.vector_db import VectorDatabase
from core.gemini_client import GeminiClient

def main():
    print("=" * 65)
    print("     GENERADOR DE EMBEDDINGS VECTORIALES CON GEMINI API")
    print("         PotroBot UAEMéx - Ingeniería en Computación")
    print("=" * 65)

    client = GeminiClient(api_key=GEMINI_API_KEY)
    if not client.has_valid_key():
        print("\n[X] Error: No se ha detectado una API Key válida en .env.")
        print("    Ingresa tu clave en 'Ajustes' desde la interfaz web o en el archivo .env.")
        sys.exit(1)

    vdb = VectorDatabase(VECTOR_STORE_PATH)
    print(f"\n[+] Base de datos vectorial cargada desde: {VECTOR_STORE_PATH.name}")
    print(f"[+] Total de fragmentos registrados: {len(vdb.chunks)}")

    embedded_before = sum(1 for c in vdb.chunks if c.get("embedding") is not None)
    print(f"[+] Fragmentos con vectores densos actuales: {embedded_before}/{len(vdb.chunks)}")

    print("\n[+] Calculando vectores semánticos con 'gemini-embedding-2'...")
    res = vdb.reindex_all_with_gemini(client)

    if res.get("ok"):
        embedded_after = sum(1 for c in vdb.chunks if c.get("embedding") is not None)
        print(f"\n[✓] Proceso completado con éxito.")
        print(f"    - Nuevos fragmentos vectorizados: {res.get('indexed')}")
        print(f"    - Total de fragmentos listos: {embedded_after}/{len(vdb.chunks)}")
        print(f"    - Archivo actualizado: {VECTOR_STORE_PATH}")
    else:
        print(f"\n[X] Error durante el proceso: {res.get('error')}")

if __name__ == "__main__":
    main()
