#!/usr/bin/env bash
# ==============================================================================
# Nexus FI — Script de Instalación Automatizada para Linux / macOS / AWS EC2
# Facultad de Ingeniería · UAEMéx (Equipo 404)
# ==============================================================================

set -e
cd "$(dirname "$0")"

echo "========================================================================"
echo "    Nexus FI — Instalador Automatizado (Linux/macOS)"
echo "    Facultad de Ingeniería · UAEMéx (Equipo 404)"
echo "========================================================================"
echo ""

# 1. Detectar Python 3 (>= 3.10)
PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        if "$candidate" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" &>/dev/null; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Python >= 3.10 no está instalado o no se encuentra en el PATH."
    echo "Por favor instala Python 3.10, 3.11 o 3.12 (ej. sudo apt install python3 python3-venv python3-pip)"
    exit 1
fi

echo "[1/5] Python detectado: $($PYTHON_BIN --version) ($PYTHON_BIN)"

# 2. Crear entorno virtual
echo "[2/5] Verificando entorno virtual (.venv)..."
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual en .venv..."
    if ! $PYTHON_BIN -m venv .venv; then
        echo "[ERROR] Falló la creación del entorno virtual."
        echo "Si estás en Ubuntu/Debian, instala el paquete venv ejecutando:"
        echo "  sudo apt update && sudo apt install python3-venv python3-pip"
        exit 1
    fi
fi

# shellcheck source=/dev/null
source .venv/bin/activate
echo "Entorno virtual activado."

# 3. Instalar dependencias
echo "[3/5] Instalando dependencias de requirements.txt..."
pip install --upgrade pip setuptools wheel --quiet
pip install -r requirements.txt

# 4. Configurar .env
echo "[4/5] Verificando variables de entorno (.env)..."
if [ ! -f ".env" ]; then
    echo "Creando .env a partir de .env.example..."
    cp .env.example .env
    echo "[AVISO] Configura tu OPENAI_API_KEY dentro de .env para habilitar el RAG."
else
    echo "Archivo .env detectado."
fi

# 5. Base vectorial LanceDB
echo "[5/5] Verificando base vectorial..."
if [ -d "data/lancedb/nexus_documents.lance" ]; then
    echo "[OK] Base de datos vectorial detectada y lista."
else
    echo "[!] No se encontró data/lancedb (los binarios no se almacenan en Git)."
    
    # Comprobar si hay clave configurada
    if python -c "import os; from dotenv import load_dotenv; load_dotenv(); k=os.getenv('OPENAI_API_KEY_EMBEDDINGS') or os.getenv('OPENAI_API_KEY',''); exit(0 if k and not k.startswith('sk-proj-tu-api-key') and len(k)>20 else 1)" &>/dev/null; then
        read -p "¿Deseas generar la base de datos vectorial ahora? (s/n): " regen
        if [[ "$regen" =~ ^[Ss]$ ]]; then
            python scripts/vectorize_corpus.py
        else
            echo "Omitiendo generación. Puedes generarla después con 'python scripts/vectorize_corpus.py'."
        fi
    else
        echo "[AVISO] Configura tus API Keys en el archivo .env antes de generar la base vectorial."
        echo "Puedes generarla posteriormente ejecutando: python scripts/vectorize_corpus.py"
    fi
fi

echo ""
echo "========================================================================"
echo "  ¡Instalación completada con éxito!"
echo "  Para iniciar el servidor ejecuta: python main.py --serve"
echo "========================================================================"
