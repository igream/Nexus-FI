"""
tests/test_ip_filter.py — Pruebas unitarias WBS 1.3.5
Filtrado Perimetral por IP — Nexus FI — Facultad de Ingeniería UAEMéx
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

if not os.getenv("AUTHORIZED_SUBNETS"):
    os.environ["AUTHORIZED_SUBNETS"] = (
        "172.17.18.0/24,148.215.12.0/24,148.215.18.0/24,148.215.30.0/24,148.215.31.0/24"
    )

from core.security.ip_filter import (
    get_client_ip,
    is_ip_in_perimeter,
    IPFilterMiddleware,
    AUTHORIZED_CIDRS,
)


# ---------------------------------------------------------------------------
# Pruebas de is_ip_in_perimeter
# ---------------------------------------------------------------------------


class TestIsIpInPerimeter:
    def test_ip_in_perimeter_valid_148_215_18(self):
        """148.215.18.5 debe estar dentro del perímetro institucional."""
        assert is_ip_in_perimeter("148.215.18.5") is True

    def test_ip_in_perimeter_valid_148_215_30(self):
        """148.215.30.100 debe estar dentro del perímetro institucional."""
        assert is_ip_in_perimeter("148.215.30.100") is True

    def test_ip_in_perimeter_valid_148_215_31(self):
        """148.215.31.1 debe estar dentro del perímetro institucional."""
        assert is_ip_in_perimeter("148.215.31.1") is True

    def test_ip_in_perimeter_valid_148_215_12(self):
        """148.215.12.50 debe estar dentro del perímetro institucional."""
        assert is_ip_in_perimeter("148.215.12.50") is True

    def test_ip_in_perimeter_valid_172_17_18(self):
        """172.17.18.200 debe estar dentro del perímetro institucional."""
        assert is_ip_in_perimeter("172.17.18.200") is True

    def test_ip_in_perimeter_valid_network_address(self):
        """Las direcciones de red base también deben estar en el perímetro."""
        assert is_ip_in_perimeter("148.215.18.1") is True

    def test_ip_in_perimeter_valid_broadcast(self):
        """La dirección broadcast de la subred también debe estar incluida."""
        assert is_ip_in_perimeter("148.215.18.254") is True


def test_ip_in_perimeter_valid():
    """
    IPs válidas deben ser reconocidas dentro del perímetro institucional.
    Agrupa: 148.215.18.5, 148.215.30.100, 148.215.31.1, 148.215.12.50, 172.17.18.200
    """
    valid_ips = [
        "148.215.18.5",
        "148.215.30.100",
        "148.215.31.1",
        "148.215.12.50",
        "172.17.18.200",
    ]
    for ip in valid_ips:
        assert is_ip_in_perimeter(ip) is True, f"IP {ip} debería estar en el perímetro"


def test_ip_outside_perimeter():
    """
    IPs externas no deben pasar el filtro perimetral.
    Prueba: 8.8.8.8, 192.168.1.1, 201.144.12.3
    """
    invalid_ips = [
        "8.8.8.8",
        "192.168.1.1",
        "201.144.12.3",
        "10.0.0.1",
        "1.1.1.1",
        "172.16.0.1",   # 172.16.0.0/12 — distinta a 172.17.18.0/24
    ]
    for ip in invalid_ips:
        assert is_ip_in_perimeter(ip) is False, f"IP {ip} NO debería estar en el perímetro"


def test_ip_invalid_string():
    """Una cadena que no es IP debe retornar False sin lanzar excepción."""
    assert is_ip_in_perimeter("not-an-ip") is False
    assert is_ip_in_perimeter("") is False
    assert is_ip_in_perimeter("999.999.999.999") is False


# ---------------------------------------------------------------------------
# Pruebas de get_client_ip
# ---------------------------------------------------------------------------


def _make_request(headers: dict, client_host: str = "127.0.0.1") -> Request:
    """Helper: construye un objeto Request con headers y host simulados."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_get_client_ip_from_forwarded_for():
    """
    Cuando X-Forwarded-For tiene múltiples IPs, debe retornar la primera (cliente original).
    """
    request = _make_request(
        headers={"X-Forwarded-For": "148.215.18.5, 10.0.0.1, 172.31.0.1"}
    )
    ip = get_client_ip(request)
    assert ip == "148.215.18.5", f"Esperado '148.215.18.5', obtenido '{ip}'"


def test_get_client_ip_single_forwarded_for():
    """X-Forwarded-For con una sola IP debe retornarla directamente."""
    request = _make_request(headers={"X-Forwarded-For": "148.215.30.100"})
    ip = get_client_ip(request)
    assert ip == "148.215.30.100"


def test_get_client_ip_from_real_ip():
    """Sin X-Forwarded-For pero con X-Real-IP, debe usar X-Real-IP."""
    request = _make_request(headers={"X-Real-IP": "148.215.31.50"})
    ip = get_client_ip(request)
    assert ip == "148.215.31.50"


def test_get_client_ip_fallback():
    """Sin headers de proxy, debe usar request.client.host como fallback."""
    request = _make_request(headers={}, client_host="172.17.18.10")
    ip = get_client_ip(request)
    assert ip == "172.17.18.10"


def test_get_client_ip_priority_forwarded_over_real_ip():
    """X-Forwarded-For tiene mayor prioridad que X-Real-IP."""
    request = _make_request(
        headers={
            "X-Forwarded-For": "148.215.12.1",
            "X-Real-IP": "148.215.12.99",
        }
    )
    ip = get_client_ip(request)
    assert ip == "148.215.12.1"


# ---------------------------------------------------------------------------
# Pruebas del Middleware
# ---------------------------------------------------------------------------


def _build_app_with_ip_filter() -> FastAPI:
    """Helper: crea una app FastAPI mínima con IPFilterMiddleware."""
    app = FastAPI()
    app.add_middleware(IPFilterMiddleware)

    @app.get("/api/test")
    async def api_test():
        return {"ok": True, "message": "Acceso permitido"}

    @app.get("/public/health")
    async def public_health():
        return {"ok": True, "message": "Servicio disponible"}

    return app


def test_middleware_allows_internal_ip():
    """Una IP dentro del perímetro debe pasar el middleware sin bloqueo."""
    app = _build_app_with_ip_filter()
    client = TestClient(app, raise_server_exceptions=True)

    # Simular request con IP institucional
    response = client.get(
        "/api/test",
        headers={"X-Forwarded-For": "148.215.18.5"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_middleware_blocks_external_ip():
    """
    Una IP fuera del perímetro debe ser bloqueada con HTTP 403
    y el payload de error correspondiente.
    """
    app = _build_app_with_ip_filter()
    client = TestClient(app, raise_server_exceptions=True)

    response = client.get(
        "/api/test",
        headers={"X-Forwarded-For": "8.8.8.8"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "HTTP_403_FORBIDDEN"
    assert body["client_ip"] == "8.8.8.8"
    assert body["wbs"] == "1.3.5"


def test_middleware_does_not_block_public_routes():
    """
    Las rutas fuera de /api/* no deben ser filtradas,
    incluso si la IP es externa.
    """
    app = _build_app_with_ip_filter()
    client = TestClient(app, raise_server_exceptions=True)

    response = client.get(
        "/public/health",
        headers={"X-Forwarded-For": "8.8.8.8"},
    )
    assert response.status_code == 200


def test_middleware_403_payload_structure():
    """El payload 403 debe tener todos los campos requeridos por la especificación."""
    app = _build_app_with_ip_filter()
    client = TestClient(app, raise_server_exceptions=True)

    response = client.get(
        "/api/test",
        headers={"X-Forwarded-For": "201.144.12.3"},
    )
    assert response.status_code == 403
    body = response.json()
    required_keys = {"ok", "error", "detail", "client_ip", "required_network", "wbs"}
    assert required_keys.issubset(body.keys()), (
        f"Faltan claves en el payload 403: {required_keys - body.keys()}"
    )


def test_authorized_cidrs_count():
    """Debe haber exactamente 5 subredes institucionales autorizadas."""
    assert len(AUTHORIZED_CIDRS) == 5


def test_authorized_cidrs_content():
    """Las subredes deben coincidir exactamente con las definidas en el proyecto."""
    expected = {
        "172.17.18.0/24",
        "148.215.12.0/24",
        "148.215.18.0/24",
        "148.215.30.0/24",
        "148.215.31.0/24",
    }
    assert set(AUTHORIZED_CIDRS) == expected
