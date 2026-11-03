"""
WBS 1.4.2 - Límite de consultas por usuario registrado
Facultad de Ingeniería UAEMéx — Equipo 404 — Nexus FI

Protege los créditos de inferencia limitando las consultas de cada usuario
registrado: 20 por hora y 60 por día (SC-001, 29/10/2026).

El usuario lo identifica el inicio de sesión (tarea del Avance 3), que debe
guardar su identificador en `request.state.user_id`. Mientras no exista el
login, las peticiones sin usuario no consumen cuota. El límite ya no se mide
por IP ni por huella de dispositivo; esa versión quedó en la etiqueta
`pre-SC-001` del repositorio.
"""
import logging
import time
from collections import deque
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración de límites
# ---------------------------------------------------------------------------
HOURLY_LIMIT: int = 20
DAILY_LIMIT: int = 60

# Rutas informativas que no consumen cuota
QUOTA_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/session/info",
    "/api/auth/",
    "/api/status",
    "/api/health",
    "/api/v1/metrics/",
    "/api/v1/admin/",
)
HOUR_SECONDS: int = 3600
DAY_SECONDS: int = 86400

# ---------------------------------------------------------------------------
# Almacén en memoria
# Estructura: { user_id: {"hourly": deque[timestamps], "daily": deque[timestamps]} }
# ---------------------------------------------------------------------------
_rate_limit_store: dict[str, dict[str, deque]] = {}


def get_user_id(request: Request) -> Optional[str]:
    """Identificador del usuario que dejó el inicio de sesión, o None si no hay sesión."""
    return getattr(request.state, "user_id", None)


def _get_or_create_store(user_id: str) -> dict[str, deque]:
    """Obtiene o inicializa el registro de timestamps de un usuario."""
    if user_id not in _rate_limit_store:
        _rate_limit_store[user_id] = {
            "hourly": deque(),
            "daily": deque(),
        }
    return _rate_limit_store[user_id]


def _cleanup_old_timestamps(store: dict[str, deque], now: float) -> None:
    """Elimina timestamps expirados para mantener el almacén limpio."""
    hour_cutoff = now - HOUR_SECONDS
    day_cutoff = now - DAY_SECONDS

    hourly_queue = store["hourly"]
    while hourly_queue and hourly_queue[0] < hour_cutoff:
        hourly_queue.popleft()

    daily_queue = store["daily"]
    while daily_queue and daily_queue[0] < day_cutoff:
        daily_queue.popleft()


def check_rate_limit(user_id: str) -> dict:
    """
    Verifica la cuota de un usuario sin registrar una nueva consulta.

    Returns:
        dict con campos: allowed, hourly_used, hourly_remaining, daily_used,
        daily_remaining, retry_after
    """
    now = time.time()
    store = _get_or_create_store(user_id)
    _cleanup_old_timestamps(store, now)

    hourly_used = len(store["hourly"])
    daily_used = len(store["daily"])

    hourly_remaining = max(0, HOURLY_LIMIT - hourly_used)
    daily_remaining = max(0, DAILY_LIMIT - daily_used)

    allowed = hourly_used < HOURLY_LIMIT and daily_used < DAILY_LIMIT

    # Segundos hasta que expire la consulta más antigua de la ventana que se agotó
    retry_after = 0
    if not allowed:
        if hourly_used >= HOURLY_LIMIT and store["hourly"]:
            retry_after = max(0, int(HOUR_SECONDS - (now - store["hourly"][0])) + 1)
        elif store["daily"]:
            retry_after = max(0, int(DAY_SECONDS - (now - store["daily"][0])) + 1)

    return {
        "allowed": allowed,
        "hourly_used": hourly_used,
        "hourly_remaining": hourly_remaining,
        "hourly_limit": HOURLY_LIMIT,
        "daily_used": daily_used,
        "daily_remaining": daily_remaining,
        "daily_limit": DAILY_LIMIT,
        "retry_after": retry_after,
    }


def record_request(user_id: str) -> None:
    """Registra una nueva consulta del usuario."""
    now = time.time()
    store = _get_or_create_store(user_id)
    store["hourly"].append(now)
    store["daily"].append(now)


def usage_snapshot() -> dict[str, dict]:
    """Consumo actual de cada usuario, para el monitoreo por usuario registrado."""
    return {user_id: check_rate_limit(user_id) for user_id in list(_rate_limit_store)}


def clear_store_for_testing() -> None:
    """Limpia el almacén completo. Solo usar en pruebas unitarias."""
    _rate_limit_store.clear()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    WBS 1.4.2 — Límite de consultas por usuario registrado.

    - 20 consultas por hora
    - 60 consultas por día

    Solo cuenta peticiones a /api/* (salvo las informativas) que traen un
    usuario en `request.state.user_id`.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not path.startswith("/api/") or path.startswith(QUOTA_EXEMPT_PREFIXES):
            return await call_next(request)

        user_id = get_user_id(request)
        if not user_id:
            return await call_next(request)

        quota = check_rate_limit(user_id)

        if not quota["allowed"]:
            logger.warning(
                "Límite de consultas excedido [WBS 1.4.2] — usuario: %s | hora: %d/%d | día: %d/%d",
                user_id,
                quota["hourly_used"],
                HOURLY_LIMIT,
                quota["daily_used"],
                DAILY_LIMIT,
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "error": "HTTP_429_TOO_MANY_REQUESTS",
                    "detail": (
                        "Has alcanzado el límite de consultas de tu cuenta "
                        "(20 por hora y 60 por día) para proteger los créditos de inferencia de Nexus FI."
                    ),
                    "quota": {
                        "hourly_limit": HOURLY_LIMIT,
                        "hourly_remaining": quota["hourly_remaining"],
                        "daily_limit": DAILY_LIMIT,
                        "daily_remaining": quota["daily_remaining"],
                        "retry_after": quota["retry_after"],
                    },
                    "wbs": "1.4.2",
                },
            )
            response.headers["Retry-After"] = str(quota["retry_after"])
            _quota_headers(response, quota)
            return response

        record_request(user_id)
        updated_quota = check_rate_limit(user_id)

        response = await call_next(request)
        _quota_headers(response, updated_quota)
        return response


def _quota_headers(response: Response, quota: dict) -> None:
    response.headers["X-RateLimit-Limit-Hour"] = str(HOURLY_LIMIT)
    response.headers["X-RateLimit-Remaining-Hour"] = str(quota["hourly_remaining"])
    response.headers["X-RateLimit-Limit-Day"] = str(DAILY_LIMIT)
    response.headers["X-RateLimit-Remaining-Day"] = str(quota["daily_remaining"])
