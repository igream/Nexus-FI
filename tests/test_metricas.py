"""
Pruebas del tablero de usuario y el panel admin con datos reales (plan de implementación, F4).
Reutilizan la base temporal y las cuentas inventadas de test_conversaciones; los mensajes se
siembran con fechas, tokens y latencias conocidos para comprobar que los totales cuadran.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from core import metricas
from core.auth import store
from core.chat import modelos
from core.chat import store as chat_store
from tests.test_conversaciones import CUENTA_A, CUENTA_B, client, preguntar, sesion  # noqa: F401 (fixture)

ADMIN = "2000009"   # inventada
AHORA = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)   # 12:00 en el centro de México


def uid(c, h):
    return c.get("/api/session/info", headers=h).json()["user_id"]


def sembrar(db, usuario, cuando, modelo="gpt-4o-mini", encontrado=True, categoria="normativa",
            latencia=1000.0, te=100, ts=20, re=0, rs=0, emb=10, pregunta="Pregunta de prueba"):
    """Un turno completo (pregunta y respuesta) con la fecha indicada."""
    conv = chat_store.crear_conversacion(usuario, pregunta)
    chat_store.agregar_mensaje(conv, usuario, "user", pregunta)
    chat_store.agregar_mensaje(
        conv, usuario, "assistant", "Respuesta", modelo=modelo, modelo_cuota=modelo,
        encontrado=encontrado, categoria_principal=categoria if encontrado else None,
        tokens_entrada=te, tokens_salida=ts, costo_usd=modelos.costo(modelo, te, ts) if te else None,
        latencia_ms=latencia, reescritura_tokens_entrada=re or None, reescritura_tokens_salida=rs or None,
        embedding_tokens=emb,
    )
    iso = cuando.isoformat(timespec="seconds")
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE mensajes SET creado_en = ? WHERE conversacion_id = ?", (iso, conv))


# --- Acceso -------------------------------------------------------------------------

def test_tablero_exige_sesion(client):
    assert client.get("/api/v1/metrics/user-dashboard").status_code == 401


def test_usuario_sin_rol_admin_recibe_403(client):
    h = sesion(client, CUENTA_A)
    assert client.get("/api/v1/admin/metrics", headers=h).status_code == 403
    assert client.get("/api/v1/admin/metrics").status_code == 401


def test_periodo_invalido_da_422(client):
    h = sesion(client, CUENTA_A)
    assert client.get("/api/v1/metrics/user-dashboard?dias=5", headers=h).status_code == 422


# --- Tablero de usuario -------------------------------------------------------------

def test_dos_usuarios_ven_datos_distintos(client):
    ha, hb = sesion(client, CUENTA_A), sesion(client, CUENTA_B)
    for q in ("Primera", "Segunda", "Tercera"):
        preguntar(client, ha, q)
    preguntar(client, hb, "Única de B")
    a = client.get("/api/v1/metrics/user-dashboard", headers=ha).json()
    b = client.get("/api/v1/metrics/user-dashboard", headers=hb).json()
    assert a["consultas"] == 3 and b["consultas"] == 1
    assert len(a["recientes"]) == 3 and len(b["recientes"]) == 1
    assert {r["titulo"] for r in b["recientes"]} == {"Única de B"}


def test_tablero_cuenta_por_modelo_dia_y_tema(client):
    h = sesion(client, CUENTA_A)
    u = uid(client, h)
    sembrar(client.db_path, u, AHORA - timedelta(hours=1), categoria="becas", latencia=800)
    sembrar(client.db_path, u, AHORA - timedelta(days=2), modelo="gpt-6-luna", categoria="becas", latencia=1200)
    sembrar(client.db_path, u, AHORA - timedelta(days=3), encontrado=False, latencia=1000)
    sembrar(client.db_path, u, AHORA - timedelta(days=20), categoria="horarios")   # fuera de 7 días

    t = metricas.tablero_usuario(u, 7, ahora=AHORA)
    assert t["consultas"] == 3 and t["con_fuentes"] == 2 and t["tasa_con_fuentes"] == 66.7
    assert {p["modelo"]: p["consultas"] for p in t["por_modelo"]} == {"gpt-4o-mini": 2, "gpt-6-luna": 1}
    assert t["latencia_promedio_ms"] == 1000
    assert t["temas"] == [{"categoria": "becas", "consultas": 2}]
    assert len(t["fechas"]) == 7 and t["fechas"][-1] == "2026-11-20"
    assert t["serie"]["gpt-6-luna"][-3] == 1 and t["serie"]["gpt-4o-mini"][-1] == 1

    t30 = metricas.tablero_usuario(u, 30, ahora=AHORA)
    assert t30["consultas"] == 4 and len(t30["fechas"]) == 30


def test_tablero_incluye_cuotas_y_acervo(client):
    h = sesion(client, CUENTA_A)
    preguntar(client, h, "Una consulta")
    t = client.get("/api/v1/metrics/user-dashboard", headers=h).json()
    cuotas = {q["model"]: q for q in t["cuotas"]}
    assert set(cuotas) == {"gpt-4o-mini", "gpt-6-luna"}
    assert cuotas["gpt-4o-mini"]["hourly_remaining"] == 19
    assert set(t["acervo"]) == {"documentos", "fragmentos"}


# --- Panel admin ----------------------------------------------------------------------

@pytest.fixture
def admin(client):
    store.autorizar_cuenta(ADMIN, "ICO", "Integrante Admin", "admin")
    return sesion(client, ADMIN)


def test_panel_admin_totales_coinciden_con_lo_sembrado(client, admin):
    ha, hb = sesion(client, CUENTA_A), sesion(client, CUENTA_B)
    a, b = uid(client, ha), uid(client, hb)
    db = client.db_path
    sembrar(db, a, AHORA - timedelta(hours=2), re=50, rs=10, emb=12, latencia=500)            # hoy
    sembrar(db, a, AHORA - timedelta(days=3), modelo="gpt-6-luna", te=200, ts=80, latencia=1500)  # semana
    sembrar(db, b, AHORA - timedelta(days=15), encontrado=False, te=0, ts=0, latencia=300,
            pregunta="¿Hay comedor en la facultad?")                                          # mes
    sembrar(db, b, AHORA - timedelta(days=45))                                                  # fuera

    p = metricas.panel_admin(ahora=AHORA)
    assert p["consultas"] == {"hoy": 1, "semana": 2, "mes": 3}
    assert p["usuarios_activos"] == {"hoy": 1, "semana": 1, "mes": 2}

    bolsas = {x["clave"]: x for x in p["consumo"]["mes"]["bolsas"]}
    assert bolsas["gpt-4o-mini"]["tokens"] == 120 and bolsas["gpt-4o-mini"]["consultas"] == 2
    assert bolsas["gpt-6-luna"]["tokens"] == 280
    assert bolsas["gpt-6-luna"]["costo_usd"] == pytest.approx(modelos.costo("gpt-6-luna", 200, 80))
    assert bolsas["gpt-4o-mini:reescritura"]["tokens"] == 60
    assert bolsas["embeddings"]["tokens"] == 12 + 10 + 10
    esperado = (modelos.costo("gpt-4o-mini", 100, 20) + modelos.costo("gpt-6-luna", 200, 80)
                + modelos.costo("gpt-4o-mini", 50, 10) + 32 * metricas.PRECIO_EMBEDDING)
    assert p["consumo"]["mes"]["costo_total_usd"] == pytest.approx(esperado, abs=1e-6)
    assert p["consumo"]["hoy"]["costo_total_usd"] < p["consumo"]["semana"]["costo_total_usd"]

    assert p["por_carrera"] == [{"carrera": "ICO", "consultas": 3}]
    assert p["latencia_ms"]["p50"] == 500 and p["latencia_ms"]["p95"] == 1500
    assert p["sin_resultado"]["total_mes"] == 1
    assert p["sin_resultado"]["recientes"] == [{"pregunta": "¿Hay comedor en la facultad?", "fecha": "2026-11-05", "veces": 1}]
    assert len(p["serie_30_dias"]["fechas"]) == 30 and sum(p["serie_30_dias"]["consultas"]) == 3


def test_endpoint_admin_sin_valores_fijos(client, admin):
    r = client.get("/api/v1/admin/metrics", headers=admin).json()
    assert r["aws"] is None                         # etapa 2: CloudWatch y Cost Explorer
    assert "openai" not in r and "server" not in r  # adiós a baseline_demo
    assert set(r["consumo"]) == {"hoy", "semana", "mes"}
    assert r["sin_resultado"]["recientes"] == []


def test_sin_resultado_no_revela_quien_pregunto(client, admin):
    h = sesion(client, CUENTA_A)
    client.vs.resultados = []
    preguntar(client, h, "Pregunta sin fuentes")
    r = client.get("/api/v1/admin/metrics", headers=admin).json()
    preguntar(client, h, "  pregunta SIN fuentes ")      # la misma, con otro formato
    r = client.get("/api/v1/admin/metrics", headers=admin).json()
    assert len(r["sin_resultado"]["recientes"]) == 1
    item = r["sin_resultado"]["recientes"][0]
    assert item["veces"] == 2 and set(item) == {"pregunta", "fecha", "veces"}   # nunca quién preguntó


def test_la_consulta_guarda_los_tokens_del_embedding(client):
    h = sesion(client, CUENTA_A)
    preguntar(client, h, "x" * 40)
    with sqlite3.connect(client.db_path) as db:
        assert db.execute("SELECT embedding_tokens FROM mensajes WHERE rol='assistant'").fetchone()[0] == 10


@pytest.mark.parametrize("valores,p,esperado", [([], 50, None), ([5], 95, 5), ([1, 2, 3, 4], 50, 2),
                                                ([1, 2, 3, 4, 100], 95, 100)])
def test_percentil(valores, p, esperado):
    assert metricas.percentil(valores, p) == esperado
