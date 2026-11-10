"""
Pruebas de los documentos consultables desde las citas del chat.
El catálogo se arma con el Procesados/ real del repositorio; los PDF originales se simulan
en una carpeta temporal para no depender de "Pre Procesados/" (fuera de Git).
"""
import importlib
from urllib.parse import parse_qs, urlparse

import pytest

import backend.app as app_module
from core.documentos.catalogo import Catalogo, catalogo

# El paquete exporta la función catalogo(), que tapa al submódulo del mismo nombre
catalogo_mod = importlib.import_module("core.documentos.catalogo")
from tests.test_conversaciones import CUENTA_A, FRAGMENTO, client, sesion  # noqa: F401 (fixture)

REGLAMENTO = "REGLAMENTO DEL SERVICIO SOCIAL.pdf"
PILOTO = "horarios_ico_semestre_6.md"


@pytest.fixture
def originales(tmp_path, monkeypatch):
    """Carpeta temporal de originales con el PDF del Reglamento del Servicio Social."""
    base = tmp_path / "acervo"
    doc = catalogo().obtener(catalogo().id_de(REGLAMENTO))
    pdf = base / doc["fuente"]
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4\n% prueba\n")
    monkeypatch.setattr(catalogo_mod, "dirs_originales", lambda: [base])
    return base


def enlace(c, h, doc_id):
    return c.post(f"/api/documentos/{doc_id}/enlace", headers=h)


# --- Catálogo -----------------------------------------------------------------------

def test_catalogo_cubre_el_acervo():
    cat = Catalogo()
    assert len(cat.por_id) >= 198
    assert cat.id_de(REGLAMENTO) and cat.id_de(PILOTO)
    assert cat.id_de("no_existe.pdf") is None


def test_piloto_se_muestra_como_texto():
    cat = catalogo()
    doc = cat.obtener(cat.id_de(PILOTO))
    assert cat.ruta_pdf(doc) is None
    assert "COMPILADORES" in cat.texto(doc) and not cat.texto(doc).startswith("---")


def test_html_nunca_se_sirve_como_archivo():
    cat = catalogo()
    htmls = [d for d in cat.por_id.values() if d["extension"] == ".html"]
    assert htmls and all(cat.ruta_pdf(d) is None for d in htmls)


# --- Endpoints -----------------------------------------------------------------------

def test_enlace_requiere_sesion(client):
    assert client.post(f"/api/documentos/{catalogo().id_de(REGLAMENTO)}/enlace").status_code == 401
    assert client.get(f"/api/documentos/{catalogo().id_de(PILOTO)}/texto").status_code == 401


def test_pdf_se_abre_con_enlace_firmado(client, originales):
    h = sesion(client, CUENTA_A)
    doc_id = catalogo().id_de(REGLAMENTO)
    e = enlace(client, h, doc_id).json()
    assert e["tipo"] == "pdf" and e["url"].startswith(f"/api/documentos/{doc_id}/archivo?")
    r = client.get(e["url"])          # sin cabecera de sesión: basta la firma
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")
    assert r.content.startswith(b"%PDF")


def test_firma_alterada_o_vencida_da_403(client, originales):
    h = sesion(client, CUENTA_A)
    doc_id = catalogo().id_de(REGLAMENTO)
    url = enlace(client, h, doc_id).json()["url"]
    q = parse_qs(urlparse(url).query)
    base = f"/api/documentos/{doc_id}/archivo"
    assert client.get(f"{base}?exp={q['exp'][0]}&firma={'0' * 64}").status_code == 403
    assert client.get(f"{base}?exp=1&firma={q['firma'][0]}").status_code == 403
    # La firma de un documento no sirve para otro
    otro = catalogo().id_de("Guia_Tramites.pdf")
    assert client.get(f"/api/documentos/{otro}/archivo?exp={q['exp'][0]}&firma={q['firma'][0]}").status_code == 403


def test_pdf_ausente_cae_al_visor_de_texto(client, tmp_path, monkeypatch):
    monkeypatch.setattr(catalogo_mod, "dirs_originales", lambda: [tmp_path / "vacia"])
    h = sesion(client, CUENTA_A)
    doc_id = catalogo().id_de(REGLAMENTO)
    e = enlace(client, h, doc_id).json()
    assert e["tipo"] == "texto" and e["url"] == f"/documento?id={doc_id}"
    t = client.get(f"/api/documentos/{doc_id}/texto", headers=h).json()
    assert "480" in t["markdown"]


def test_fuente_piloto_abre_el_visor(client):
    h = sesion(client, CUENTA_A)
    doc_id = catalogo().id_de(PILOTO)
    assert enlace(client, h, doc_id).json()["tipo"] == "texto"
    t = client.get(f"/api/documentos/{doc_id}/texto", headers=h)
    assert t.status_code == 200 and "COMPILADORES" in t.json()["markdown"]


@pytest.mark.parametrize("doc_id", ["no_existe", "..", "..%2F..%2F.env"])
def test_id_desconocido_da_404(client, doc_id):
    h = sesion(client, CUENTA_A)
    assert enlace(client, h, doc_id).status_code == 404
    assert client.get(f"/api/documentos/{doc_id}/texto", headers=h).status_code in (404, 405)


def test_las_citas_del_chat_traen_doc_id(client):
    client.vs.resultados = [dict(FRAGMENTO, documento=REGLAMENTO), FRAGMENTO]
    h = sesion(client, CUENTA_A)
    r = client.post("/api/chat", json={"query": "¿Cuántas horas de servicio social?"}, headers=h).json()
    assert r["citations"][0]["doc_id"] == catalogo().id_de(REGLAMENTO)
    assert r["citations"][1]["doc_id"] is None       # documento fuera del catálogo: sin enlace
    # Al reabrir la conversación las citas conservan el enlace
    conv = client.get(f"/api/conversaciones/{r['conversation_id']}", headers=h).json()
    assert conv["mensajes"][1]["citas"][0]["doc_id"] == catalogo().id_de(REGLAMENTO)


def test_abrir_documentos_no_consume_cuota(client, originales, monkeypatch):
    monkeypatch.setattr(app_module, "RATE_LIMIT_ENABLED", True)
    h = sesion(client, CUENTA_A)
    doc_id = catalogo().id_de(REGLAMENTO)
    for _ in range(30):
        assert enlace(client, h, doc_id).status_code == 200
