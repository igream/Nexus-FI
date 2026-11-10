"""
Pruebas del selector de modelo y las cuotas por modelo (plan de implementación, fase F3).
Reutilizan la base temporal y las cuentas inventadas de test_conversaciones; cada modelo
tiene su propio doble del LLM que registra los argumentos que recibe.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import backend.app as app_module
from core.chat import contexto, modelos
from core.chat import store as chat_store
from core.security import rate_limiter
from tests.test_conversaciones import CUENTA_A, CUENTA_B, client, sesion  # noqa: F401 (fixture)

AVANZADO = "gpt-6-luna"
RAPIDO = "gpt-4o-mini"


class _LLM:
    def __init__(self, nombre):
        self.nombre, self.llamadas = nombre, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.llamadas.append(kw)
        es_reescritura = kw["messages"][0]["content"] == contexto.PROMPT_REESCRITURA
        texto = "¿Pregunta reescrita?" if es_reescritura else f"Respuesta de {self.nombre}"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=texto), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )


@pytest.fixture
def llms(client, monkeypatch):
    dobles = {RAPIDO: _LLM(RAPIDO), AVANZADO: _LLM(AVANZADO)}
    monkeypatch.setattr(app_module, "chat_clients", dict(dobles))
    monkeypatch.setattr(app_module, "chat_key_names", {m: f"CLAVE_{i}" for i, m in enumerate(dobles)})
    monkeypatch.setattr(app_module, "RATE_LIMIT_ENABLED", True)
    return dobles


def chat(c, h, q="¿Qué requisitos tiene el servicio social?", model=None, conv=None):
    body = {"query": q}
    if model:
        body["model"] = model
    if conv:
        body["conversation_id"] = conv
    return c.post("/api/chat", json=body, headers=h)


# --- Modelo elegido y parámetros ---------------------------------------------------

def test_se_llama_al_modelo_elegido_con_sus_parametros(client, llms):
    h = sesion(client, CUENTA_A)
    r = chat(client, h, model=AVANZADO)
    assert r.status_code == 200 and r.json()["answer"] == f"Respuesta de {AVANZADO}"
    kw = llms[AVANZADO].llamadas[-1]
    assert kw["model"] == "gpt-6-luna"
    assert kw["max_completion_tokens"] == modelos.MODELOS[AVANZADO]["max_salida"]
    assert kw["reasoning_effort"] == "low"
    assert "max_tokens" not in kw and "temperature" not in kw   # el modelo los rechaza
    assert llms[RAPIDO].llamadas == []
    assert r.json()["telemetry"]["model"] == AVANZADO


def test_modelo_por_defecto_es_4o_mini(client, llms):
    h = sesion(client, CUENTA_A)
    chat(client, h)
    kw = llms[RAPIDO].llamadas[-1]
    assert kw["model"] == "gpt-4o-mini" and kw["max_tokens"] == 1200 and kw["temperature"] == 0.2


def test_modelo_invalido_da_422(client, llms):
    h = sesion(client, CUENTA_A)
    r = chat(client, h, model="gpt-inventado")
    assert r.status_code == 422
    assert llms[RAPIDO].llamadas == [] and llms[AVANZADO].llamadas == []


def test_modelo_sin_clave_da_503(client, llms):
    h = sesion(client, CUENTA_A)
    assert chat(client, h, model="gpt-5.6-luna").status_code == 503


def test_reescritura_usa_4o_mini_aunque_se_elija_el_avanzado(client, llms):
    h = sesion(client, CUENTA_A)
    conv = chat(client, h, model=AVANZADO).json()["conversation_id"]
    chat(client, h, q="¿y el plazo?", model=AVANZADO, conv=conv)
    assert any(k["messages"][0]["content"] == contexto.PROMPT_REESCRITURA for k in llms[RAPIDO].llamadas)
    assert all(k["messages"][0]["content"] != contexto.PROMPT_REESCRITURA for k in llms[AVANZADO].llamadas)


def test_costo_registrado_usa_la_tarifa_del_modelo(client, llms):
    h = sesion(client, CUENTA_A)
    chat(client, h, model=AVANZADO)
    chat(client, h, model=RAPIDO)
    with sqlite3.connect(client.db_path) as db:
        filas = dict(db.execute(
            "SELECT modelo_cuota, costo_usd FROM mensajes WHERE rol = 'assistant'"
        ).fetchall())
    assert filas[AVANZADO] == pytest.approx(100 * 0.10e-6 + 20 * 0.50e-6)
    assert filas[RAPIDO] == pytest.approx(100 * 0.15e-6 + 20 * 0.60e-6)


# --- Cuotas por modelo ---------------------------------------------------------------

def test_agotar_el_avanzado_no_afecta_a_4o_mini(client, llms):
    h = sesion(client, CUENTA_A)
    for _ in range(modelos.MODELOS[AVANZADO]["cuota_hora"]):
        assert chat(client, h, model=AVANZADO).status_code == 200
    r = chat(client, h, model=AVANZADO)
    assert r.status_code == 429
    body = r.json()
    assert body["model"] == AVANZADO and "Avanzado" in body["detail"]
    assert body["quota"]["retry_after"] > 0 and int(r.headers["retry-after"]) > 0
    assert body["quota"]["reset_at"]
    # La consulta rechazada no llegó al LLM ni al embedding
    assert len(llms[AVANZADO].llamadas) == modelos.MODELOS[AVANZADO]["cuota_hora"]
    assert chat(client, h, model=RAPIDO).status_code == 200


def test_agotar_4o_mini_no_afecta_al_avanzado(client, llms):
    h = sesion(client, CUENTA_A)
    for _ in range(modelos.MODELOS[RAPIDO]["cuota_hora"]):
        assert chat(client, h).status_code == 200
    assert chat(client, h).status_code == 429
    assert chat(client, h, model=AVANZADO).status_code == 200


def test_cuota_es_por_usuario(client, llms):
    ha, hb = sesion(client, CUENTA_A), sesion(client, CUENTA_B)
    for _ in range(modelos.MODELOS[AVANZADO]["cuota_hora"]):
        chat(client, ha, model=AVANZADO)
    assert chat(client, ha, model=AVANZADO).status_code == 429
    assert chat(client, hb, model=AVANZADO).status_code == 200


def test_cuotas_sobreviven_al_reinicio(client, llms):
    h = sesion(client, CUENTA_A)
    for _ in range(modelos.MODELOS[AVANZADO]["cuota_hora"]):
        chat(client, h, model=AVANZADO)
    # Simula un reinicio: se pierde todo lo que vive en memoria y se reabre la base
    rate_limiter.clear_store_for_testing()
    chat_store.init_db()
    assert chat(client, h, model=AVANZADO).status_code == 429


def test_borrar_la_conversacion_no_devuelve_cuota(client, llms):
    h = sesion(client, CUENTA_A)
    ids = [chat(client, h, model=AVANZADO).json()["conversation_id"]
           for _ in range(modelos.MODELOS[AVANZADO]["cuota_hora"])]
    for i in ids:
        client.delete(f"/api/conversaciones/{i}", headers=h)
    assert chat(client, h, model=AVANZADO).status_code == 429


def test_session_info_devuelve_la_cuota_de_cada_modelo(client, llms):
    h = sesion(client, CUENTA_A)
    chat(client, h, model=AVANZADO)
    s = client.get("/api/session/info", headers=h).json()
    assert set(s["quotas"]) == {RAPIDO, AVANZADO}          # gpt-5.6-luna no va al selector
    assert s["quotas"][AVANZADO]["hourly_remaining"] == modelos.MODELOS[AVANZADO]["cuota_hora"] - 1
    assert s["quotas"][RAPIDO]["hourly_remaining"] == 20
    assert s["quotas"][AVANZADO]["available"] is True
    assert s["quota"] == s["quotas"][RAPIDO] and s["default_model"] == RAPIDO


# --- Funciones puras -----------------------------------------------------------------

def test_estado_cuota_calcula_cuando_se_libera():
    ahora = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    primera = (ahora - timedelta(minutes=50)).isoformat(timespec="seconds")
    q = modelos.estado_cuota(AVANZADO, lambda desde: (5, primera), ahora=ahora)
    assert q["allowed"] is False and q["hourly_remaining"] == 0
    assert 600 <= q["retry_after"] <= 601                     # la más antigua sale en 10 min
    assert q["daily_limit"] is None and q["daily_remaining"] is None


def test_estado_cuota_tope_diario_de_4o_mini():
    ahora = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    def contar(desde):
        es_hora = desde > (ahora - timedelta(hours=2)).isoformat()
        return (3, None) if es_hora else (60, (ahora - timedelta(hours=20)).isoformat(timespec="seconds"))

    q = modelos.estado_cuota(RAPIDO, contar, ahora=ahora)
    assert q["allowed"] is False and q["hourly_remaining"] == 17 and q["daily_remaining"] == 0
    assert 4 * 3600 <= q["retry_after"] <= 4 * 3600 + 1


def test_parametros_por_tipo_de_modelo():
    assert modelos.parametros_llamada(RAPIDO, max_salida=100, temperature=0) == {
        "model": "gpt-4o-mini", "max_tokens": 100, "temperature": 0}
    kw = modelos.parametros_llamada(AVANZADO, temperature=0.2)
    assert "temperature" not in kw and kw["max_completion_tokens"] == 2000


def test_migracion_marca_mensajes_viejos_como_4o_mini(client):
    # Base de F1/F2 sin la columna modelo_cuota
    with sqlite3.connect(client.db_path) as db:
        db.execute("DROP INDEX IF EXISTS ix_msg_cuota")
        db.execute("ALTER TABLE mensajes DROP COLUMN modelo_cuota")
        db.execute(
            """INSERT INTO mensajes(conversacion_id, usuario_id, rol, contenido_cifrado, creado_en)
               VALUES ('c', 'u', 'assistant', 'x', '2026-11-10T00:00:00+00:00')"""
        )
    chat_store.init_db()
    with sqlite3.connect(client.db_path) as db:
        assert db.execute("SELECT modelo_cuota FROM mensajes").fetchone()[0] == "gpt-4o-mini"
