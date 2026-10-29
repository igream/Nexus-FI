"""
WBS 1.3.5 - Middleware de Filtrado Perimetral por IP
Facultad de Ingeniería UAEMéx — Equipo 404 — Nexus FI
"""
import os
import ipaddress
import logging
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env si existe
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Subredes institucionales autorizadas — Facultad de Ingeniería UAEMéx
# Carga dinámica desde variable de entorno AUTHORIZED_SUBNETS (evita exposición en Git)
# ---------------------------------------------------------------------------
_raw_subnets = os.getenv("AUTHORIZED_SUBNETS", "")
AUTHORIZED_CIDRS: list[str] = [
    cidr.strip() for cidr in _raw_subnets.split(",") if cidr.strip()
]

# Pre-compilar objetos de red para mayor eficiencia
_AUTHORIZED_NETWORKS: list[ipaddress.IPv4Network] = [
    ipaddress.IPv4Network(cidr, strict=False) for cidr in AUTHORIZED_CIDRS
]


def get_client_ip(request: Request) -> str:
    """
    Extrae la dirección IP real del cliente considerando proxies y balanceadores.

    Orden de prioridad:
    1. Primera IP de X-Forwarded-For (la del cliente original)
    2. X-Real-IP
    3. request.client.host (conexión directa)
    """
    # 1. X-Forwarded-For (puede contener múltiples IPs separadas por coma)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Tomar la primera IP de la lista (la del cliente original)
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    # 2. X-Real-IP (configurado por Nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 3. Conexión directa
    if request.client and request.client.host:
        return request.client.host

    return "0.0.0.0"


def is_ip_in_perimeter(ip: str) -> bool:
    """
    Valida si una dirección IP pertenece a alguna de las subredes institucionales
    autorizadas de la Facultad de Ingeniería UAEMéx.

    Args:
        ip: Dirección IP en formato string (ej. "148.215.18.5")

    Returns:
        True si la IP está dentro del perímetro institucional, False en caso contrario.
    """
    try:
        client_addr = ipaddress.IPv4Address(ip)
    except (ipaddress.AddressValueError, ValueError):
        logger.warning("IP inválida recibida: %s", ip)
        return False

    for network in _AUTHORIZED_NETWORKS:
        if client_addr in network:
            return True

    return False


class IPFilterMiddleware(BaseHTTPMiddleware):
    """
    WBS 1.3.5 — Middleware de Filtrado Perimetral por IP.

    Intercepta todas las solicitudes a rutas /api/* y verifica que la IP
    del cliente pertenezca a las subredes institucionales autorizadas de la
    Facultad de Ingeniería UAEMéx. Las solicitudes fuera del perímetro son
    rechazadas con HTTP 403.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Solo aplicar filtrado a rutas /api/*
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = get_client_ip(request)

        if not is_ip_in_perimeter(client_ip):
            logger.warning(
                "Acceso denegado [WBS 1.3.5] — IP fuera de perímetro: %s | Ruta: %s",
                client_ip,
                request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": "HTTP_403_FORBIDDEN",
                    "detail": (
                        "Acceso restringido: Conexión fuera del perímetro institucional "
                        "de la Facultad de Ingeniería (UAEMéx)."
                    ),
                    "client_ip": client_ip,
                    "required_network": "148.215.X.X / 172.17.18.X (Subredes FI UAEMéx)",
                    "wbs": "1.3.5",
                },
            )

        logger.debug("IP autorizada [WBS 1.3.5]: %s", client_ip)
        return await call_next(request)
