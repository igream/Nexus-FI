#!/usr/bin/env bash
# ==============================================================================
# Nexus FI — Script de Instalación Automatizada para Linux / macOS / AWS EC2
# Facultad de Ingeniería · UAEMéx (Equipo 404)
# ==============================================================================

set -e

echo "========================================================================"
echo "    Nexus FI — Instalador Automatizado (Linux/macOS)"
echo "    Facultad de Ingeniería · UAEMéx (Equipo 404)"
echo "========================================================================"
echo ""

# 1. Detectar Python 3
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 no está instalado. Por favor instala Python >= 3.10."
    exit 1
fi

echo "[1/5] Python detectado: $($PYTHON_BIN --version)"

# 2. Crear entorno virtual
echo "[2/5] Verificando entorno virtual (.venv)..."
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual en .venv..."
    $PYTHON_BIN -m venv .venv
fi

source .venv/bin/activate
echo "Entorno virtual activado."

# 3. Instalar dependencias
echo "[3/5] Instalando dependencias de requirements.txt..."
pip install --upgrade pip --quiet
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
    echo "[!] No se encontró data/lancedb."
    read -p "¿Deseas generar la base de datos vectorial ahora? (s/n): " regen
    if [[ "$regen" =~ ^[Ss]$ ]]; then
        python scripts/vectorize_corpus.py
    else
        echo "Omitiendo generación. Puedes generarla después con 'python scripts/vectorize_corpus.py'."
    fi
fi

echo ""
echo "========================================================================"
echo "  ¡Instalación completada con éxito!"
echo "  Para iniciar el servidor ejecuta: python main.py --serve"
echo "========================================================================"
