"""
tests/test_rate_limiter.py — Pruebas unitarias WBS 1.4.2
Límite de consultas por usuario registrado (SC-001) — Nexus FI — Facultad de Ingeniería UAEMéx

El inicio de sesión todavía no existe; las pruebas lo simulan con un middleware
que copia la cabecera X-Test-User a request.state.user_id, que es donde el
login real deberá dejar al usuario.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from core.security.rate_limiter import (
    DAILY_LIMIT,
    HOURLY_LIMIT,
    RateLimiterMiddleware,
    check_rate_limit,
    clear_store_for_testing,
    record_request,
    usage_snapshot,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_rate_limit_store():
    """Limpia el almacén antes y después de cada prueba."""
    clear_store_for_testing()
    yield
    clear_store_for_testing()


class _FakeLoginMiddleware(BaseHTTPMiddleware):
    """Simula el inicio de sesión: identifica al usuario con la cabecera X-Test-User."""

    async def dispatch(self, request, call_next):
        user = request.headers.get("X-Test-User")
        if user:
            request.state.user_id = user
        return await call_next(request)


def _build_app() -> FastAPI:
    """App mínima con el limitador y el login simulado (Starlette ejecuta en orden LIFO)."""
    app = FastAPI()
    app.add_middleware(RateLimiterMiddleware)
    app.add_middleware(_FakeLoginMiddleware)

    @app.get("/api/test")
    async def api_test():
        return {"ok": True}

    @app.get("/api/session/info")
    async def session_info():
        return {"ok": True}

    @app.get("/public/health")
    async def public_health():
        return {"ok": True}

    return app


def _saturar(user_id: str, n: int = HOURLY_LIMIT) -> None:
    for _ in range(n):
        record_request(user_id)


# ---------------------------------------------------------------------------
# Pruebas de check_rate_limit (función pura)
# ---------------------------------------------------------------------------


def test_check_rate_limit_initial_state():
    """Un usuario nuevo tiene toda la cuota disponible."""
    quota = check_rate_limit("usuario-nuevo")
    assert quota["allowed"] is True
    assert quota["hourly_remaining"] == HOURLY_LIMIT == 20
    assert quota["daily_remaining"] == DAILY_LIMIT == 60
    assert quota["hourly_used"] == 0
    assert quota["daily_used"] == 0


def test_within_hourly_limit():
    """Con 19 consultas, la número 20 sigue permitida."""
    _saturar("u-hora", 19)
    quota = check_rate_limit("u-hora")
    assert quota["allowed"] is True
    assert quota["hourly_remaining"] == 1


def test_exceeds_hourly_limit():
    """Con 20 consultas en la hora, la siguiente se rechaza."""
    _saturar("u-hora-max")
    quota = check_rate_limit("u-hora-max")
    assert quota["allowed"] is False
    assert quota["hourly_remaining"] == 0


def test_exceeds_daily_limit():
    """Con 60 consultas en el día, la siguiente se rechaza."""
    _saturar("u-dia", DAILY_LIMIT)
    quota = check_rate_limit("u-dia")
    assert quota["allowed"] is False
    assert quota["daily_remaining"] == 0


def test_retry_after_is_positive_when_limited():
    """Al agotar la cuota horaria, retry_after está entre 1 y 3600 segundos."""
    _saturar("u-retry")
    quota = check_rate_limit("u-retry")
    assert 0 < quota["retry_after"] <= 3600


def test_user_isolation():
    """Cada usuario tiene su propia cuota."""
    _saturar("u-a")
    assert check_rate_limit("u-a")["allowed"] is False
    assert check_rate_limit("u-b")["allowed"] is True


def test_usage_snapshot_por_usuario():
    """El monitoreo devuelve el consumo de cada usuario registrado."""
    _saturar("u-monitor", 3)
    snap = usage_snapshot()
    assert snap["u-monitor"]["hourly_used"] == 3


# ---------------------------------------------------------------------------
# Pruebas del middleware HTTP
# ---------------------------------------------------------------------------


def test_usuario_dentro_del_limite():
    client = TestClient(_build_app())
    r = client.get("/api/test", headers={"X-Test-User": "u-ok"})
    assert r.status_code == 200
    assert r.headers["x-ratelimit-remaining-hour"] == str(HOURLY_LIMIT - 1)
    assert "x-ratelimit-limit-day" in r.headers


def test_usuario_excedido_recibe_429():
    client = TestClient(_build_app())
    _saturar("u-429")
    r = client.get("/api/test", headers={"X-Test-User": "u-429"})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    body = r.json()
    assert {"ok", "error", "detail", "quota", "wbs"}.issubset(body)
    assert {"hourly_limit", "hourly_remaining", "daily_limit", "daily_remaining", "retry_after"}.issubset(body["quota"])
    assert body["error"] == "HTTP_429_TOO_MANY_REQUESTS"
    assert body["wbs"] == "1.4.2"


def test_middleware_cuenta_cada_consulta():
    client = TestClient(_build_app())
    for _ in range(HOURLY_LIMIT):
        assert client.get("/api/test", headers={"X-Test-User": "u-cuenta"}).status_code == 200
    assert client.get("/api/test", headers={"X-Test-User": "u-cuenta"}).status_code == 429


def test_sin_sesion_no_consume_cuota():
    """Sin usuario en sesión (antes del login) el limitador no interviene."""
    client = TestClient(_build_app())
    for _ in range(HOURLY_LIMIT + 5):
        assert client.get("/api/test").status_code == 200
    assert usage_snapshot() == {}


def test_ya_no_usa_ip_ni_huella():
    """Las cabeceras de IP y de huella de dispositivo ya no identifican a nadie (SC-001)."""
    client = TestClient(_build_app())
    _saturar("fp-antiguo")
    _saturar("148.215.18.5")
    r = client.get(
        "/api/test",
        headers={"X-Device-Fingerprint": "fp-antiguo", "X-Forwarded-For": "148.215.18.5"},
    )
    assert r.status_code == 200


def test_rutas_informativas_y_publicas_exentas():
    client = TestClient(_build_app())
    _saturar("u-exento")
    headers = {"X-Test-User": "u-exento"}
    assert client.get("/api/session/info", headers=headers).status_code == 200
    assert client.get("/public/health", headers=headers).status_code == 200
