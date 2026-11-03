"""Los archivos del frontend deben revalidarse con el servidor para no mostrar versiones viejas."""
import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


@pytest.mark.parametrize("ruta", ["/", "/login", "/app.js", "/login.js", "/styles.css", "/service-worker.js"])
def test_frontend_se_revalida(ruta):
    r = client.get(ruta)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"


def test_archivo_sin_cambios_responde_304():
    etag = client.get("/app.js").headers["etag"]
    assert client.get("/app.js", headers={"If-None-Match": etag}).status_code == 304


def test_api_no_recibe_cabecera_de_frontend():
    assert client.get("/api/session/info").headers.get("cache-control") != "no-cache"
