"""
WBS 1.4.2 - Control de Sesión con Límite de Uso (Rate Limiter)
Facultad de Ingeniería UAEMéx — Equipo 404 — Nexus FI

Protege los créditos de inferencia limitando el número de consultas
por dispositivo/sesión: 20/hora y 60/día.
"""
import logging
import time
from collections import deque
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .ip_filter import get_client_ip

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración de límites
# ---------------------------------------------------------------------------
HOURLY_LIMIT: int = 20
DAILY_LIMIT: int = 60
HOUR_SECONDS: int = 3600
DAY_SECONDS: int = 86400

# ---------------------------------------------------------------------------
# Storage en memoria
# Estructura: { device_id: {"hourly": deque[timestamps], "daily": deque[timestamps]} }
# ---------------------------------------------------------------------------
_rate_limit_store: dict[str, dict[str, deque]] = {}


def _get_or_create_store(device_id: str) -> dict[str, deque]:
    """Obtiene o inicializa el registro de timestamps para un device_id."""
    if device_id not in _rate_limit_store:
        _rate_limit_store[device_id] = {
            "hourly": deque(),
            "daily": deque(),
        }
    return _rate_limit_store[device_id]


def _cleanup_old_timestamps(store: dict[str, deque], now: float) -> None:
    """Elimina timestamps expirados para mantener el store limpio."""
    hour_cutoff = now - HOUR_SECONDS
    day_cutoff = now - DAY_SECONDS

    hourly_queue = store["hourly"]
    while hourly_queue and hourly_queue[0] < hour_cutoff:
        hourly_queue.popleft()

    daily_queue = store["daily"]
    while daily_queue and daily_queue[0] < day_cutoff:
        daily_queue.popleft()


def check_rate_limit(device_id: str) -> dict:
    """
    Verifica el estado de cuota para un device_id sin registrar una nueva consulta.

    Returns:
        dict con campos: allowed, hourly_used, hourly_remaining, daily_used,
        daily_remaining, retry_after
    """
    now = time.time()
    store = _get_or_create_store(device_id)
    _cleanup_old_timestamps(store, now)

    hourly_used = len(store["hourly"])
    daily_used = len(store["daily"])

    hourly_remaining = max(0, HOURLY_LIMIT - hourly_used)
    daily_remaining = max(0, DAILY_LIMIT - daily_used)

    allowed = hourly_used < HOURLY_LIMIT and daily_used < DAILY_LIMIT

    # Calcular segundos hasta que expira la consulta más antigua de la ventana horaria
    retry_after = 0
    if not allowed and store["hourly"]:
        oldest_in_hour = store["hourly"][0]
        retry_after = max(0, int(HOUR_SECONDS - (now - oldest_in_hour)) + 1)

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


def record_request(device_id: str) -> None:
    """Registra una nueva consulta para el device_id dado."""
    now = time.time()
    store = _get_or_create_store(device_id)
    store["hourly"].append(now)
    store["daily"].append(now)


def clear_store_for_testing() -> None:
    """Limpia el store completo. Solo usar en pruebas unitarias."""
    _rate_limit_store.clear()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    WBS 1.4.2 — Middleware de Control de Sesión con Límite de Uso.

    Limita el número de consultas por dispositivo/sesión:
    - 20 consultas por hora
    - 60 consultas por día

    El device_id se determina con la siguiente prioridad:
    1. Header X-Device-Fingerprint
    2. Header X-Session-ID
    3. IP del cliente
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Solo aplicar a rutas /api/*
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Determinar device_id
        device_id = (
            request.headers.get("X-Device-Fingerprint")
            or request.headers.get("X-Session-ID")
            or get_client_ip(request)
        )

        # Verificar cuota actual
        quota = check_rate_limit(device_id)

        if not quota["allowed"]:
            logger.warning(
                "Rate limit excedido [WBS 1.4.2] — device_id: %s | "
                "hora: %d/%d | día: %d/%d",
                device_id,
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
                        "Has alcanzado el límite de consultas permitidas por "
                        "dispositivo/sesión para proteger los créditos de inferencia de Nexus FI."
                    ),
                    "device_id": device_id,
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
            response.headers["X-RateLimit-Limit-Hour"] = str(HOURLY_LIMIT)
            response.headers["X-RateLimit-Remaining-Hour"] = str(quota["hourly_remaining"])
            response.headers["X-RateLimit-Limit-Day"] = str(DAILY_LIMIT)
            response.headers["X-RateLimit-Remaining-Day"] = str(quota["daily_remaining"])
            return response

        # Registrar la consulta
        record_request(device_id)

        # Obtener cuota actualizada para headers
        updated_quota = check_rate_limit(device_id)

        response = await call_next(request)

        # Agregar headers de cuota a la respuesta exitosa
        response.headers["X-RateLimit-Limit-Hour"] = str(HOURLY_LIMIT)
        response.headers["X-RateLimit-Remaining-Hour"] = str(updated_quota["hourly_remaining"])
        response.headers["X-RateLimit-Limit-Day"] = str(DAILY_LIMIT)
        response.headers["X-RateLimit-Remaining-Day"] = str(updated_quota["daily_remaining"])

        return response
