#!/usr/bin/env bash
# ==============================================================================
# Nexus FI — Script de Instalación Automatizada para Linux / macOS / AWS EC2
# Facultad de Ingeniería · UAEMéx (Equipo 404)
#
# Prepara un proyecto recién clonado: Python, entorno virtual y dependencias.
# El archivo .env y la base vectorial data/lancedb se copian a mano; al final
# se indica qué falta.
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
    echo "Instálalo con, por ejemplo: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

echo "[1/4] Python detectado: $($PYTHON_BIN --version) ($PYTHON_BIN)"

# 2. Crear entorno virtual
echo "[2/4] Verificando entorno virtual (.venv)..."
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual en .venv..."
    if ! $PYTHON_BIN -m venv .venv; then
        echo "[ERROR] Falló la creación del entorno virtual."
        echo "En Ubuntu/Debian instala el paquete venv con:"
        echo "  sudo apt update && sudo apt install python3-venv python3-pip"
        exit 1
    fi
fi

# shellcheck source=/dev/null
source .venv/bin/activate

# 3. Instalar dependencias
echo "[3/4] Instalando dependencias de requirements.txt (puede tardar varios minutos)..."
pip install --upgrade pip setuptools wheel --quiet
pip install -r requirements.txt --quiet --disable-pip-version-check
python -c "import lancedb, pyarrow, pandas, fastapi, uvicorn, openai"
echo "[OK] Dependencias instaladas y verificadas."

# 4. Archivos que se copian a mano
echo "[4/4] Verificando archivos que se copian a mano..."
ENV_OK=0; DB_OK=0
[ -f ".env" ] && ENV_OK=1
[ -d "data/lancedb/nexus_documents.lance" ] && DB_OK=1

if [ "$ENV_OK$DB_OK" = "11" ]; then
    echo "[OK] .env y data/lancedb presentes. Ejecutando diagnóstico del sistema..."
    python main.py --telemetry || true
fi

echo ""
echo "========================================================================"
echo "                     RESUMEN DE LA INSTALACIÓN"
echo "========================================================================"
echo "  [OK]    Python, entorno virtual .venv y dependencias"
[ "$ENV_OK" = "1" ] && echo "  [OK]    Archivo .env" || echo "  [FALTA] Archivo .env  (claves de OpenAI y subredes de la FI)"
[ "$DB_OK" = "1" ] && echo "  [OK]    Base vectorial data/lancedb" || echo "  [FALTA] Base vectorial data/lancedb  (3,977 vectores, ~59 MB)"
echo "========================================================================"

if [ "$ENV_OK$DB_OK" != "11" ]; then
    echo ""
    echo " PASOS PENDIENTES (nunca se suben a GitHub; cópialos de un equipo donde ya"
    echo " funcione Nexus FI, por ejemplo con scp):"
    [ "$ENV_OK" = "0" ] && echo "   - Copia el archivo .env a: $(pwd)/.env  (o parte de .env.example)"
    [ "$DB_OK" = "0" ] && echo "   - Copia la carpeta lancedb a: $(pwd)/data/lancedb  (regenerarla cuesta créditos)"
    echo ""
    echo " Después ejecuta de nuevo ./setup.sh para verificar."
    exit 0
fi

echo ""
echo " ¡Instalación completada! Para iniciar el servidor:"
echo "   source .venv/bin/activate"
echo "   python main.py --serve --dev     # desarrollo"
echo "   python main.py --serve --fi      # prueba final (filtro FI y límite de uso)"
echo "   docker compose -f docker-compose.yml -f docker-compose.fi.yml up -d   # producción con Docker"
