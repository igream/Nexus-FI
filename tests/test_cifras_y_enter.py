"""Cifras del acervo y envío con Enter en el chat (defectos DC-01 y DC-02)."""
from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as appmod

FRONTEND = Path(appmod.__file__).resolve().parent.parent / "frontend"
client = TestClient(appmod.app)


def test_stats_usa_la_cuenta_real_del_acervo(monkeypatch):
    # Se sustituye el conteo para no depender de data/lancedb (fuera de Git)
    monkeypatch.setattr(appmod, "_acervo", lambda: {"documentos": 198, "fragmentos": 3340})
    corpus = client.get("/api/stats").json()["corpus"]
    assert corpus["total_documents"] == 198


def test_interfaz_sin_cifras_fijas_del_acervo():
    for nombre in ("index.html", "app.js"):
        texto = (FRONTEND / nombre).read_text(encoding="utf-8")
        assert "211" not in texto, f"{nombre} trae un número de documentos escrito a mano"
        assert "3,977" not in texto, f"{nombre} trae un número de vectores escrito a mano"


def test_enter_envia_y_mayus_enter_no():
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    assert "addEventListener('keydown'" in js
    assert "e.key !== 'Enter' || e.shiftKey || e.isComposing" in js
    assert "form.requestSubmit()" in js
