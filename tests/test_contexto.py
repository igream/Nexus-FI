"""
Pruebas del contexto conversacional (plan de implementación, fase F2).
Reutilizan la base temporal y las cuentas inventadas de test_conversaciones; el LLM,
el embedder y el buscador son dobles sin red que registran lo que reciben.
"""
import sqlite3
from types import SimpleNamespace

import pytest

import backend.app as app_module
from core.chat import contexto
from tests.test_conversaciones import CUENTA_A, client, preguntar, sesion  # noqa: F401 (fixture)

REESCRITA = "¿Cuál es el plazo para liberar el servicio social?"


def _respuesta(texto):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=texto), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=50, completion_tokens=10),
    )


class _LLM:
    """Distingue la llamada de reescritura (prompt de sistema propio) de la respuesta final."""

    def __init__(self, reescritura=REESCRITA, falla_reescritura=False):
        self.reescritura, self.falla = reescritura, falla_reescritura
        self.reescrituras, self.respuestas = [], []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        if kw["messages"][0]["content"] == contexto.PROMPT_REESCRITURA:
            self.reescrituras.append(kw)
            if self.falla:
                raise RuntimeError("fallo simulado de la API")
            return _respuesta(self.reescritura)
        self.respuestas.append(kw)
        return _respuesta(f"Respuesta {len(self.respuestas)}")


class _Embedder:
    def __init__(self):
        self.textos = []

    def embed_query(self, texto):
        self.textos.append(texto)
        return [0.0] * 8


@pytest.fixture
def llm(client, monkeypatch):
    doble = _LLM()
    monkeypatch.setattr(app_module, "chat_clients", {"gpt-4o-mini": doble})
    emb = _Embedder()
    monkeypatch.setattr(app_module, "embedder", emb)
    doble.embedder = emb
    return doble


# --- Integración con /api/chat -------------------------------------------------

def test_sin_historial_no_hay_reescritura(client, llm):
    h = sesion(client, CUENTA_A)
    r = preguntar(client, h, "¿Qué requisitos tiene el servicio social?")
    assert r.status_code == 200
    assert llm.reescrituras == []
    assert llm.embedder.textos == ["¿Qué requisitos tiene el servicio social?"]
    assert [m["role"] for m in llm.respuestas[0]["messages"]] == ["system", "user"]
    tel = r.json()["telemetry"]
    assert tel["rewritten_query"] is None and tel["history_turns"] == 0


def test_con_historial_reescribe_y_busca_con_la_reescrita(client, llm):
    h = sesion(client, CUENTA_A)
    conv = preguntar(client, h, "¿Qué requisitos tiene el servicio social?").json()["conversation_id"]
    r = preguntar(client, h, "¿y cuál es el plazo?", conv)

    assert len(llm.reescrituras) == 1
    rw = llm.reescrituras[0]
    assert rw["temperature"] == 0 and rw["max_tokens"] == contexto.MAX_TOKENS_REESCRITURA
    assert "servicio social" in rw["messages"][1]["content"]
    # El embedding usa la reescrita; el LLM final, la pregunta original
    assert llm.embedder.textos[-1] == REESCRITA
    assert llm.respuestas[-1]["messages"][-1]["content"].endswith("Pregunta del Estudiante: ¿y cuál es el plazo?")
    tel = r.json()["telemetry"]
    assert tel["rewritten_query"] == REESCRITA and tel["history_turns"] == 1 and tel["rewrite_tokens"] == 60
    assert r.json()["query"] == "¿y cuál es el plazo?"


def test_mensajes_incluyen_turnos_previos_en_orden_y_respetan_n(client, llm):
    h = sesion(client, CUENTA_A)
    conv = preguntar(client, h, "Pregunta 1").json()["conversation_id"]
    for i in range(2, 6):
        preguntar(client, h, f"Pregunta {i}", conv)

    msgs = llm.respuestas[-1]["messages"]   # quinta consulta: hay 4 pares previos, se envían 3
    assert msgs[0]["role"] == "system"
    previos = msgs[1:-1]
    assert [(m["role"], m["content"]) for m in previos] == [
        ("user", "Pregunta 2"), ("assistant", "Respuesta 2"),
        ("user", "Pregunta 3"), ("assistant", "Respuesta 3"),
        ("user", "Pregunta 4"), ("assistant", "Respuesta 4"),
    ]
    assert "Pregunta 5" in msgs[-1]["content"]


def test_falla_de_reescritura_no_rompe_la_respuesta(client, llm):
    llm.falla = True
    h = sesion(client, CUENTA_A)
    conv = preguntar(client, h, "¿Qué requisitos tiene el servicio social?").json()["conversation_id"]
    r = preguntar(client, h, "¿y cuál es el plazo?", conv)
    assert r.status_code == 200 and r.json()["found"] is True
    assert llm.embedder.textos[-1] == "¿y cuál es el plazo?"
    assert r.json()["telemetry"]["rewritten_query"] is None


def test_reescritura_inservible_usa_la_original(client, llm):
    llm.reescritura = "   "
    h = sesion(client, CUENTA_A)
    conv = preguntar(client, h, "Primera").json()["conversation_id"]
    preguntar(client, h, "¿y luego?", conv)
    assert llm.embedder.textos[-1] == "¿y luego?"


def test_reescritura_se_guarda_cifrada_con_sus_tokens(client, llm):
    h = sesion(client, CUENTA_A)
    conv = preguntar(client, h, "¿Qué requisitos tiene el servicio social?").json()["conversation_id"]
    preguntar(client, h, "¿y cuál es el plazo?", conv)
    with sqlite3.connect(client.db_path) as db:
        fila = db.execute(
            """SELECT consulta_reescrita_cifrada, reescritura_tokens_entrada, reescritura_tokens_salida
               FROM mensajes WHERE rol = 'assistant' ORDER BY id DESC LIMIT 1"""
        ).fetchone()
    assert fila[0] and "plazo" not in fila[0]   # cifrada
    assert fila[1:] == (50, 10)
    from core.auth.store import descifrar
    assert descifrar(fila[0]) == REESCRITA


def test_consulta_sin_resultados_tambien_usa_contexto(client, llm):
    h = sesion(client, CUENTA_A)
    conv = preguntar(client, h, "¿Qué requisitos tiene el servicio social?").json()["conversation_id"]
    client.vs.resultados = []
    r = preguntar(client, h, "¿y cuál es el plazo?", conv)
    assert r.json()["found"] is False
    assert r.json()["telemetry"]["rewritten_query"] == REESCRITA


# --- Funciones puras -------------------------------------------------------------

def _pares(n, largo=10):
    out = []
    for i in range(1, n + 1):
        out += [{"rol": "user", "contenido": f"P{i}" + "x" * largo},
                {"rol": "assistant", "contenido": f"R{i}" + "y" * largo}]
    return out


def test_recorte_por_tokens_descarta_los_mas_viejos():
    hist = contexto.recortar_historial(_pares(3, largo=1400), pares=3, tope_tokens=900)
    # cada par ronda 800 tokens: solo cabe el más reciente
    assert [m["content"][:2] for m in hist] == ["P3", "R3"]


def test_recorte_de_un_par_que_no_cabe_conserva_la_pregunta():
    msgs = [{"rol": "user", "contenido": "¿Qué materias hay en quinto semestre?"},
            {"rol": "assistant", "contenido": "z" * 20000}]
    hist = contexto.recortar_historial(msgs, pares=3, tope_tokens=1500)
    assert hist[0]["content"] == "¿Qué materias hay en quinto semestre?"
    assert hist[1]["content"].endswith("...")
    assert sum(contexto.estimar_tokens(m["content"]) for m in hist) <= 1500 + 2


def test_recorte_ignora_mensajes_sueltos():
    msgs = [{"rol": "user", "contenido": "huérfana"}] + _pares(2)
    hist = contexto.recortar_historial(msgs)
    assert [m["role"] for m in hist] == ["user", "assistant", "user", "assistant"]
    assert "huérfana" not in [m["content"] for m in hist]


@pytest.mark.parametrize("entrada,esperado", [
    ("¿Cuál es el plazo?", "¿Cuál es el plazo?"),
    ('"¿Cuál es el plazo?"', "¿Cuál es el plazo?"),
    ("Pregunta reescrita: ¿Cuál es el plazo?", "¿Cuál es el plazo?"),
    ("", None),
    (None, None),
    ("x" * 1000, None),
])
def test_limpiar_reescritura(entrada, esperado):
    assert contexto.limpiar_reescritura(entrada) == esperado
