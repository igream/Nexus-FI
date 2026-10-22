#!/usr/bin/env python3
"""
Herramienta de Diagnóstico y Verificación de la API de Google Gemini
Proyecto: PotroBot UAEMéx (Ingeniería en Computación)
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

# Configure utf-8 stdout for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

def load_key_from_env():
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.getenv("GEMINI_API_KEY", "")

def print_banner():
    print("=" * 65)
    print("      DIAGNOSTICO OFICIAL DE LA API DE GOOGLE GEMINI")
    print("         PotroBot UAEMex - Ingenieria en Computacion")
    print("=" * 65)

def main():
    print_banner()
    api_key = load_key_from_env()

    if not api_key:
        print("\n[!] No se encontro GEMINI_API_KEY en el archivo .env")
        api_key = input("Introduce tu API Key de Gemini para evaluarla: ").strip()

    if not api_key:
        print("\n[X] Error: No se proporciono ninguna clave API. Abortando.")
        sys.exit(1)

    masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
    print(f"\n[+] Clave detectada: {masked_key}")
    print("[+] Conectando con Google Generative Language API...")

    # 1. Test listing models
    url_models = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    t0 = time.time()
    try:
        req = urllib.request.Request(url_models, method="GET")
        with urllib.request.urlopen(req, timeout=12) as resp:
            elapsed_ms = round((time.time() - t0) * 1000)
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "").replace("models/", "") for m in data.get("models", [])]
            print(f"[OK] Conexion HTTP exitosa (Latencia: {elapsed_ms} ms)")
            print(f"[OK] Modelos disponibles para tu cuenta: {len(models)}")
    except urllib.error.HTTPError as e:
        print(f"\n[X] Error de autenticacion HTTP {e.code}:")
        try:
            err_json = json.loads(e.read().decode("utf-8"))
            print(f"    Detalle: {err_json.get('error', {}).get('message', str(e))}")
        except Exception:
            print(f"    Detalle: {e}")
        print("\n[!] Verifica que tu clave haya sido generada en: https://aistudio.google.com/app/apikey")
        sys.exit(1)
    except Exception as e:
        print(f"\n[X] Error de red: {e}")
        sys.exit(1)

    # 2. Test Chat Inference with Auto-Fallback
    print("\n--- Evaluando Modelos de Chat ---")
    chat_models = ["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-flash-latest"]
    chat_success = False

    for model in chat_models:
        url_chat = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": "En una frase breve: Que es la ingenieria en computacion?"}]}]
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req_chat = urllib.request.Request(url_chat, data=data_bytes, headers={"Content-Type": "application/json"}, method="POST")

        t1 = time.time()
        try:
            with urllib.request.urlopen(req_chat, timeout=20) as resp:
                chat_elapsed = round((time.time() - t1) * 1000)
                res_data = json.loads(resp.read().decode("utf-8"))
                reply = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                print(f"[OK] Modelo '{model}': ACTIVO ({chat_elapsed} ms)")
                print(f"     Respuesta de prueba: {reply.strip()[:90]}...")
                chat_success = True
                break
        except urllib.error.HTTPError as e:
            if e.code == 503:
                print(f"[-]  Modelo '{model}': 503 (Servidores saturados temporalmente). Conmutando por fallback...")
            elif e.code == 404:
                print(f"[-]  Modelo '{model}': 404 (No disponible). Conmutando por fallback...")
            else:
                print(f"[-]  Modelo '{model}': Error {e.code}")
        except Exception as e:
            print(f"[-]  Modelo '{model}': Error de conexion {e}")

    # 3. Test Embedding Model
    print("\n--- Evaluando Modelos de Embeddings (Vectores) ---")
    emb_models = ["gemini-embedding-2", "gemini-embedding-001"]
    emb_success = False

    for em in emb_models:
        url_emb = f"https://generativelanguage.googleapis.com/v1beta/models/{em}:embedContent?key={api_key}"
        payload_emb = {"content": {"parts": [{"text": "UAEMex Ingenieria en Computacion"}]}}
        data_emb = json.dumps(payload_emb).encode("utf-8")
        req_emb = urllib.request.Request(url_emb, data=data_emb, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with urllib.request.urlopen(req_emb, timeout=12) as resp:
                res_emb = json.loads(resp.read().decode("utf-8"))
                dims = len(res_emb.get("embedding", {}).get("values", []))
                print(f"[OK] Modelo de Embeddings '{em}': ACTIVO (Vector de {dims} dimensiones)")
                emb_success = True
                break
        except Exception as e:
            print(f"[-]  Modelo '{em}': No disponible ({e})")

    # Final Verdict
    print("\n" + "=" * 65)
    if chat_success and emb_success:
        print("  ESTADO FINAL: [OK] API CONFIGURADA Y OPERATIVA AL 100%")
        print("  Tu clave de Google Gemini esta lista para produccion y chat RAG.")
    elif chat_success:
        print("  ESTADO FINAL: [!] CHAT OPERATIVO / EMBEDDINGS EN MODO LEXICO")
    else:
        print("  ESTADO FINAL: [X] HUBO PROBLEMAS CON LOS MODELOS")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
