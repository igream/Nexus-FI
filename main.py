"""
main.py — Aplicación FastAPI principal
Nexus FI — Facultad de Ingeniería UAEMéx — Equipo 404

Avance 2 (50%) — WBS 1.3.5 / 1.4.2
  - Middleware de Filtrado Perimetral por IP
  - Control de Sesión con Límite de Uso
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router as api_router
from core.security.ip_filter import IPFilterMiddleware
from core.security.rate_limiter import RateLimiterMiddleware

# ---------------------------------------------------------------------------
# Configuración de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nexus-fi")

# ---------------------------------------------------------------------------
# Rutas de archivos estáticos
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

# ---------------------------------------------------------------------------
# Inicialización de la aplicación FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Nexus FI — API",
    description=(
        "Sistema de consulta documental con IA para la Facultad de Ingeniería UAEMéx. "
        "Avance 2: Middleware de Filtrado Perimetral por IP (WBS 1.3.5) y "
        "Control de Sesión con Límite de Uso (WBS 1.4.2)."
    ),
    version="0.2.0",
    contact={
        "name": "Equipo 404 — FI UAEMéx",
        "url": "https://fi.uaemex.mx",
    },
)

# ---------------------------------------------------------------------------
# Agregar middlewares en orden:
# 1. IPFilterMiddleware  → valida que la IP esté en el perímetro institucional
# 2. RateLimiterMiddleware → verifica y registra el límite de consultas
#
# NOTA: En Starlette/FastAPI los middlewares se ejecutan en orden LIFO
# (el último agregado se ejecuta primero), por eso se agrega
# RateLimiterMiddleware primero y IPFilterMiddleware segundo.
# ---------------------------------------------------------------------------
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(IPFilterMiddleware)

# ---------------------------------------------------------------------------
# Montar archivos estáticos
# ---------------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# Incluir router de la API
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix="/api", tags=["Nexus FI API"])


# ---------------------------------------------------------------------------
# Ruta raíz — sirve el frontend
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    """Sirve la interfaz web principal de Nexus FI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse(
        content="<h1>Nexus FI</h1><p>Frontend no encontrado. Verifique static/index.html</p>",
        status_code=200,
    )


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("=" * 60)
    logger.info("  Nexus FI — Facultad de Ingeniería UAEMéx — Equipo 404")
    logger.info("  Avance 2 — WBS 1.3.5 / 1.4.2")
    logger.info("=" * 60)
    logger.info("Subredes autorizadas (perímetro institucional FI UAEMéx):")
    for cidr in [
        "172.17.18.0/24",
        "148.215.12.0/24",
        "148.215.18.0/24",
        "148.215.30.0/24",
        "148.215.31.0/24",
    ]:
        logger.info("  → %s", cidr)
    logger.info("Rate limits: %d req/hora, %d req/día por dispositivo", 20, 60)
    logger.info("Servidor iniciado. Documentación: http://127.0.0.1:8000/docs")
