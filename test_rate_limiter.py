"""
tests/test_rate_limiter.py — Pruebas unitarias WBS 1.4.2
Control de Sesión con Límite de Uso — Nexus FI — Facultad de Ingeniería UAEMéx
"""
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security.rate_limiter import (
    RateLimiterMiddleware,
    check_rate_limit,
    clear_store_for_testing,
    record_request,
    HOURLY_LIMIT,
    DAILY_LIMIT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_rate_limit_store():
    """Limpia el store de rate limiting antes y después de cada prueba."""
    clear_store_for_testing()
    yield
    clear_store_for_testing()


def _build_app_with_rate_limiter() -> FastAPI:
    """Helper: crea una app FastAPI mínima con RateLimiterMiddleware."""
    app = FastAPI()
    app.add_middleware(RateLimiterMiddleware)

    @app.get("/api/test")
    async def api_test():
        return {"ok": True}

    @app.post("/api/chat")
    async def api_chat():
        return {"ok": True, "response": "simulado"}

    return app


# ---------------------------------------------------------------------------
# Pruebas de check_rate_limit (función pura)
# ---------------------------------------------------------------------------


def test_check_rate_limit_initial_state():
    """Un device_id nuevo debe tener toda la cuota disponible."""
    quota = check_rate_limit("device-nuevo")
    assert quota["allowed"] is True
    assert quota["hourly_remaining"] == HOURLY_LIMIT
    assert quota["daily_remaining"] == DAILY_LIMIT
    assert quota["hourly_used"] == 0
    assert quota["daily_used"] == 0


def test_within_hourly_limit():
    """
    19 peticiones registradas deben dejar el dispositivo dentro del límite horario.
    La consulta 20 debe seguir siendo permitida.
    """
    device_id = "test-device-hourly"
    # Registrar 19 consultas (dentro del límite de 20)
    for _ in range(19):
        record_request(device_id)

    quota = check_rate_limit(device_id)
    assert quota["allowed"] is True, "Después de 19 consultas, la siguiente debe estar permitida"
    assert quota["hourly_remaining"] == 1
    assert quota["hourly_used"] == 19


def test_exceeds_hourly_limit():
    """
    21 peticiones registradas deben hacer que la consulta 21 sea rechazada.
    """
    device_id = "test-device-exceed-hourly"
    # Registrar 20 consultas (alcanza el límite)
    for _ in range(20):
        record_request(device_id)

    quota = check_rate_limit(device_id)
    assert quota["allowed"] is False, "Después de 20 consultas, la siguiente debe ser rechazada"
    assert quota["hourly_remaining"] == 0
    assert quota["hourly_used"] == 20


def test_within_daily_limit():
    """
    59 peticiones registradas deben mantener el dispositivo dentro del límite diario.
    """
    device_id = "test-device-daily"
    # Registrar 59 consultas (dentro del límite de 60)
    for _ in range(59):
        record_request(device_id)

    quota = check_rate_limit(device_id)
    assert quota["daily_remaining"] == 1
    assert quota["daily_used"] == 59


def test_exceeds_daily_limit():
    """
    61 peticiones totales: al alcanzar 60, la siguiente debe ser rechazada
    independientemente del límite horario.
    """
    device_id = "test-device-exceed-daily"
    # Registrar 60 consultas (alcanza el límite diario)
    for _ in range(60):
        record_request(device_id)

    quota = check_rate_limit(device_id)
    assert quota["allowed"] is False, "Después de 60 consultas, la siguiente debe ser rechazada"
    assert quota["daily_remaining"] == 0
    assert quota["daily_used"] == 60


def test_retry_after_is_positive_when_limited():
    """Cuando se supera el límite horario, retry_after debe ser un entero positivo."""
    device_id = "test-device-retry"
    for _ in range(HOURLY_LIMIT):
        record_request(device_id)

    quota = check_rate_limit(device_id)
    assert quota["allowed"] is False
    assert quota["retry_after"] > 0
    assert quota["retry_after"] <= 3600


def test_device_id_isolation():
    """Diferentes device_ids deben tener cuotas independientes."""
    device_a = "device-a"
    device_b = "device-b"

    for _ in range(HOURLY_LIMIT):
        record_request(device_a)

    quota_a = check_rate_limit(device_a)
    quota_b = check_rate_limit(device_b)

    assert quota_a["allowed"] is False
    assert quota_b["allowed"] is True


# ---------------------------------------------------------------------------
# Pruebas del Middleware HTTP
# ---------------------------------------------------------------------------


def test_middleware_allows_request_within_limit():
    """La primera solicitud de un dispositivo nuevo debe ser permitida (HTTP 200)."""
    app = _build_app_with_rate_limiter()
    client = TestClient(app, raise_server_exceptions=True)

    response = client.get(
        "/api/test",
        headers={
            "X-Forwarded-For": "148.215.18.5",  # IP en perímetro (no hay IP filter aquí)
            "X-Device-Fingerprint": "fp-test-001",
        },
    )
    assert response.status_code == 200


def test_device_id_from_fingerprint():
    """
    El middleware debe usar X-Device-Fingerprint como device_id prioritario
    cuando está presente en el header.
    """
    app = _build_app_with_rate_limiter()
    client = TestClient(app, raise_server_exceptions=True)

    fingerprint = "fp-priority-test-abc123"

    # Saturar el límite para este fingerprint
    for _ in range(HOURLY_LIMIT):
        record_request(fingerprint)

    # La siguiente solicitud con ese fingerprint debe ser rechazada
    response = client.get(
        "/api/test",
        headers={"X-Device-Fingerprint": fingerprint},
    )
    assert response.status_code == 429
    body = response.json()
    assert body["device_id"] == fingerprint


def test_device_id_fallback_to_session_id():
    """
    Sin X-Device-Fingerprint, el middleware debe usar X-Session-ID como device_id.
    """
    app = _build_app_with_rate_limiter()
    client = TestClient(app, raise_server_exceptions=True)

    session_id = "session-fallback-test-xyz"

    for _ in range(HOURLY_LIMIT):
        record_request(session_id)

    response = client.get(
        "/api/test",
        headers={"X-Session-ID": session_id},
    )
    assert response.status_code == 429
    body = response.json()
    assert body["device_id"] == session_id


def test_retry_after_header():
    """
    Cuando se devuelve HTTP 429, la respuesta debe incluir el header Retry-After
    con un valor numérico positivo.
    """
    app = _build_app_with_rate_limiter()
    client = TestClient(app, raise_server_exceptions=True)

    device_id = "device-for-retry-after-test"
    for _ in range(HOURLY_LIMIT):
        record_request(device_id)

    response = client.get(
        "/api/test",
        headers={"X-Device-Fingerprint": device_id},
    )
    assert response.status_code == 429
    assert "retry-after" in response.headers
    retry_after = int(response.headers["retry-after"])
    assert retry_after > 0


def test_rate_limit_headers_on_success():
    """Las respuestas exitosas deben incluir los headers X-RateLimit-*."""
    app = _build_app_with_rate_limiter()
    client = TestClient(app, raise_server_exceptions=True)

    response = client.get(
        "/api/test",
        headers={"X-Device-Fingerprint": "fp-header-test"},
    )
    assert response.status_code == 200
    assert "x-ratelimit-limit-hour" in response.headers
    assert "x-ratelimit-remaining-hour" in response.headers
    assert "x-ratelimit-limit-day" in response.headers
    assert "x-ratelimit-remaining-day" in response.headers


def test_middleware_429_payload_structure():
    """El payload 429 debe tener todos los campos requeridos por la especificación."""
    app = _build_app_with_rate_limiter()
    client = TestClient(app, raise_server_exceptions=True)

    device_id = "device-payload-test"
    for _ in range(HOURLY_LIMIT):
        record_request(device_id)

    response = client.get(
        "/api/test",
        headers={"X-Device-Fingerprint": device_id},
    )
    assert response.status_code == 429
    body = response.json()

    required_keys = {"ok", "error", "detail", "device_id", "quota", "wbs"}
    assert required_keys.issubset(body.keys())

    required_quota_keys = {
        "hourly_limit",
        "hourly_remaining",
        "daily_limit",
        "daily_remaining",
        "retry_after",
    }
    assert required_quota_keys.issubset(body["quota"].keys())

    assert body["ok"] is False
    assert body["error"] == "HTTP_429_TOO_MANY_REQUESTS"
    assert body["wbs"] == "1.4.2"


def test_middleware_does_not_apply_to_non_api_routes():
    """
    Rutas fuera de /api/* no deben ser afectadas por el rate limiter,
    incluso si el límite ha sido superado para ese device_id.
    """
    app = _build_app_with_rate_limiter()

    @app.get("/public/health")
    async def public_health():
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=True)

    device_id = "device-public-route-test"
    for _ in range(HOURLY_LIMIT + 5):
        record_request(device_id)

    response = client.get(
        "/public/health",
        headers={"X-Device-Fingerprint": device_id},
    )
    assert response.status_code == 200
