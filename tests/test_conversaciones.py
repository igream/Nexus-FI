"""
Pruebas del historial de conversaciones (plan de implementación, fase F1).
Usan una base temporal, claves de prueba y cuentas inventadas. El buscador
vectorial, el embedder y el LLM se sustituyen por dobles sin red.
"""
import sqlite3
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

import backend.app as app_module
from backend.app import app
from core.auth import routes, store
from core.chat import store as chat_store
from core.security import rate_limiter

CUENTA_A, CUENTA_B = "2000001", "2000002"   # inventadas
PASS = "contrasena-segura"
RESPUESTA_LLM = "Respuesta simulada sobre servicio social."
FRAGMENTO = {
    "id": "frag-1", "documento": "Guia_Servicio_Social.pdf", "categoria": "Servicio Social",
    "subcategoria": "", "carrera": "ICO", "articulo": "Art. 5", "pagina": "3",
    "similarity": 0.81, "text": "El servicio social se libera con 480 horas.",
}


class _Embedder:
    def embed_query(self, texto):
        return [0.0] * 8


class _VectorStore:
    def __init__(self):
        self.resultados = [FRAGMENTO]

    def search(self, **kwargs):
        return list(self.resultados)


class _ClienteLLM:
    def __init__(self):
        self.llamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.llamadas.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=RESPUESTA_LLM), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "u.db"
    monkeypatch.setenv("USUARIOS_DB_PATH", str(db))
    monkeypatch.setenv("AUTH_JWT_SECRET", "secreto-de-prueba-" + "x" * 20)
    monkeypatch.setenv("CUENTA_HMAC_KEY", "hmac-de-prueba-" + "y" * 20)
    monkeypatch.setenv("CUENTA_FERNET_KEY", Fernet.generate_key().decode())
    routes._fallos.clear()
    rate_limiter.clear_store_for_testing()
    store.init_db()
    chat_store.init_db()
    for cuenta in (CUENTA_A, CUENTA_B):
        store.autorizar_cuenta(cuenta, "ICO", "Alumno De Prueba")

    vs, llm = _VectorStore(), _ClienteLLM()
    monkeypatch.setattr(app_module, "vector_store", vs)
    monkeypatch.setattr(app_module, "embedder", _Embedder())
    monkeypatch.setattr(app_module, "chat_clients", {"gpt-4o-mini": llm})

    c = TestClient(app)
    c.db_path, c.vs, c.llm = db, vs, llm
    return c


def sesion(c, cuenta):
    c.post("/api/auth/registro", json={"carrera": "ICO", "numero_cuenta": cuenta, "password": PASS})
    token = c.post("/api/auth/login", json={"numero_cuenta": cuenta, "password": PASS}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def preguntar(c, h, query, conv_id=None):
    body = {"query": query}
    if conv_id:
        body["conversation_id"] = conv_id
    return c.post("/api/chat", json=body, headers=h)


def test_consulta_crea_conversacion_y_la_reutiliza(client):
    h = sesion(client, CUENTA_A)
    r1 = preguntar(client, h, "¿Qué requisitos tiene el servicio social?")
    assert r1.status_code == 200
    conv_id = r1.json()["conversation_id"]
    assert conv_id

    r2 = preguntar(client, h, "¿Y cuántas horas son?", conv_id)
    assert r2.json()["conversation_id"] == conv_id

    lista = client.get("/api/conversaciones", headers=h).json()["conversaciones"]
    assert [c["id"] for c in lista] == [conv_id]
    assert lista[0]["titulo"] == "¿Qué requisitos tiene el servicio social?"

    conv = client.get(f"/api/conversaciones/{conv_id}", headers=h).json()
    assert [m["rol"] for m in conv["mensajes"]] == ["user", "assistant", "user", "assistant"]
    assert conv["mensajes"][1]["contenido"] == RESPUESTA_LLM
    assert conv["mensajes"][1]["modelo"] == "gpt-4o-mini"
    assert conv["mensajes"][1]["citas"][0]["documento"] == FRAGMENTO["documento"]


def test_consulta_sin_resultados_tambien_se_guarda(client):
    h = sesion(client, CUENTA_A)
    client.vs.resultados = []
    r = preguntar(client, h, "Pregunta sin fuentes en el acervo")
    assert r.status_code == 200 and r.json()["found"] is False
    conv = client.get(f"/api/conversaciones/{r.json()['conversation_id']}", headers=h).json()
    assert conv["mensajes"][1]["encontrado"] is False


def test_lista_ordenada_por_actividad_reciente(client):
    h = sesion(client, CUENTA_A)
    vieja = preguntar(client, h, "Primera conversación").json()["conversation_id"]
    nueva = preguntar(client, h, "Segunda conversación").json()["conversation_id"]
    ids = [c["id"] for c in client.get("/api/conversaciones", headers=h).json()["conversaciones"]]
    assert ids == [nueva, vieja]


def test_usuario_no_ve_ni_toca_conversaciones_ajenas(client):
    ha, hb = sesion(client, CUENTA_A), sesion(client, CUENTA_B)
    conv_id = preguntar(client, ha, "Conversación privada de A").json()["conversation_id"]

    assert client.get("/api/conversaciones", headers=hb).json()["conversaciones"] == []
    assert client.get(f"/api/conversaciones/{conv_id}", headers=hb).status_code == 404
    assert client.patch(f"/api/conversaciones/{conv_id}", json={"titulo": "x"}, headers=hb).status_code == 404
    assert client.delete(f"/api/conversaciones/{conv_id}", headers=hb).status_code == 404
    # Tampoco puede escribir en ella desde el chat
    assert preguntar(client, hb, "Intento de B", conv_id).status_code == 404
    assert len(client.get(f"/api/conversaciones/{conv_id}", headers=ha).json()["mensajes"]) == 2


def test_historial_requiere_sesion(client):
    assert client.get("/api/conversaciones").status_code == 401
    assert client.get("/api/conversaciones/abc").status_code == 401
    assert client.delete("/api/conversaciones/abc").status_code == 401


def test_conversacion_inexistente_en_chat_responde_404(client):
    h = sesion(client, CUENTA_A)
    assert preguntar(client, h, "Hola", "no-existe").status_code == 404
    assert client.get("/api/conversaciones", headers=h).json()["conversaciones"] == []


def test_renombrar_y_borrar(client):
    h = sesion(client, CUENTA_A)
    conv_id = preguntar(client, h, "Titulación").json()["conversation_id"]

    assert client.patch(f"/api/conversaciones/{conv_id}", json={"titulo": "  Mis   dudas  "}, headers=h).status_code == 200
    assert client.get(f"/api/conversaciones/{conv_id}", headers=h).json()["titulo"] == "Mis dudas"
    assert client.patch(f"/api/conversaciones/{conv_id}", json={"titulo": ""}, headers=h).status_code == 422
    assert client.patch(f"/api/conversaciones/{conv_id}", json={"titulo": "   "}, headers=h).status_code == 422

    assert client.delete(f"/api/conversaciones/{conv_id}", headers=h).status_code == 200
    assert client.get("/api/conversaciones", headers=h).json()["conversaciones"] == []
    assert client.get(f"/api/conversaciones/{conv_id}", headers=h).status_code == 404
    assert client.delete(f"/api/conversaciones/{conv_id}", headers=h).status_code == 404
    assert preguntar(client, h, "Seguir en la borrada", conv_id).status_code == 404


def test_titulo_largo_se_recorta(client):
    h = sesion(client, CUENTA_A)
    preguntar(client, h, "palabra " * 30)
    titulo = client.get("/api/conversaciones", headers=h).json()["conversaciones"][0]["titulo"]
    assert len(titulo) <= 60 and titulo.endswith("...")


def test_historial_no_consume_cuota(client):
    h = sesion(client, CUENTA_A)
    preguntar(client, h, "Una consulta")
    for _ in range(rate_limiter.HOURLY_LIMIT + 5):
        assert client.get("/api/conversaciones", headers=h).status_code == 200
    assert client.get("/api/session/info", headers=h).json()["quota"]["hourly_remaining"] == rate_limiter.HOURLY_LIMIT - 1


def test_historial_persiste_y_va_cifrado(client):
    h = sesion(client, CUENTA_A)
    pregunta = "Pregunta muy confidencial sobre mi beca"
    conv_id = preguntar(client, h, pregunta).json()["conversation_id"]

    # Lectura directa de la base (equivale a un reinicio del servidor): nada en texto plano
    with sqlite3.connect(client.db_path) as conn:
        volcado = "\n".join(conn.iterdump())
    assert pregunta not in volcado
    assert RESPUESTA_LLM not in volcado
    assert "confidencial" not in volcado

    conv = chat_store.obtener_conversacion(sesion_id_de(client, CUENTA_A), conv_id)
    assert conv["mensajes"][0]["contenido"] == pregunta


def test_telemetria_queda_registrada(client):
    h = sesion(client, CUENTA_A)
    preguntar(client, h, "Servicio social")
    with sqlite3.connect(client.db_path) as conn:
        fila = conn.execute(
            "SELECT modelo, categoria_principal, encontrado, tokens_entrada, tokens_salida, costo_usd "
            "FROM mensajes WHERE rol = 'assistant'"
        ).fetchone()
    assert fila[:5] == ("gpt-4o-mini", "Servicio Social", 1, 100, 20)
    assert fila[5] > 0


def test_fallo_al_guardar_no_rompe_la_respuesta(client, monkeypatch):
    h = sesion(client, CUENTA_A)

    def _falla(*a, **k):
        raise sqlite3.OperationalError("base bloqueada")

    monkeypatch.setattr(chat_store, "crear_conversacion", _falla)
    r = preguntar(client, h, "Consulta con base caída")
    assert r.status_code == 200
    assert r.json()["answer"] == RESPUESTA_LLM
    assert r.json()["conversation_id"] is None


def sesion_id_de(c, cuenta):
    return str(store.verificar_login(cuenta, PASS))
