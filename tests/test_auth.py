"""
Pruebas del inicio de sesión (WBS 1.3.4, SC-001).
Usan una base temporal, claves de prueba y números de cuenta inventados.
"""
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.app import app
from core.auth import routes, store
from core.security import rate_limiter

CUENTA = "1234567"          # inventada
OTRA = "7654321"            # inventada, no precargada
NOMBRE = "Alumno De Prueba"
PASS = "contrasena-segura"


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
    store.autorizar_cuenta(CUENTA, "Licenciatura en Ingeniería en Computación", NOMBRE)
    c = TestClient(app)
    c.db_path = db
    return c


def registrar(c, cuenta=CUENTA, password=PASS, carrera="ICO"):
    return c.post("/api/auth/registro", json={"carrera": carrera, "numero_cuenta": cuenta, "password": password})


def login(c, cuenta=CUENTA, password=PASS):
    return c.post("/api/auth/login", json={"numero_cuenta": cuenta, "password": password})


def test_registro_cuenta_autorizada(client):
    assert registrar(client).status_code == 201


def test_registro_cuenta_no_autorizada(client):
    assert registrar(client, cuenta=OTRA).status_code == 403


def test_registro_doble(client):
    registrar(client)
    assert registrar(client).status_code == 409


@pytest.mark.parametrize("cuenta,password,carrera", [
    (CUENTA, "corta", "ICO"),          # contraseña de 5 caracteres
    ("12345", PASS, "ICO"),            # cuenta de 5 dígitos
    ("12345ab", PASS, "ICO"),          # cuenta con letras
    (CUENTA, PASS, "IME"),             # carrera no habilitada
])
def test_registro_datos_invalidos(client, cuenta, password, carrera):
    assert registrar(client, cuenta, password, carrera).status_code == 422


def test_login_correcto_devuelve_token_y_nombre(client):
    registrar(client)
    r = login(client)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] and data["token"] and data["carrera"] == "ICO" and data["expira_en"] == 28800
    assert data["nombre"] == NOMBRE
    assert CUENTA not in data["token"]


def test_login_contrasena_incorrecta(client):
    registrar(client)
    r = login(client, password="otra-contrasena")
    assert r.status_code == 401
    assert r.json()["detail"] == "Número de cuenta o contraseña incorrectos"


def test_login_bloqueo_tras_intentos_fallidos(client):
    registrar(client)
    for _ in range(routes.MAX_FALLOS):
        assert login(client, password="mala-contrasena").status_code == 401
    assert login(client).status_code == 429


def test_chat_sin_token_responde_401(client):
    assert client.post("/api/chat", json={"query": "hola"}).status_code == 401


def test_session_info_con_token(client):
    registrar(client)
    token = login(client).json()["token"]
    info = client.get("/api/session/info", headers={"Authorization": f"Bearer {token}"}).json()
    assert info["authenticated"] is True
    assert info["usuario"]["nombre"] == NOMBRE
    assert info["usuario"]["carrera_nombre"] == "Licenciatura en Ingeniería en Computación"


def test_logout_invalida_token(client):
    registrar(client)
    token = login(client).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/session/info", headers=h).json()["authenticated"] is False
    assert client.post("/api/chat", json={"query": "hola"}, headers=h).status_code == 401


ADMIN = "2345678"           # inventada, rol admin


def sesion(c, cuenta, password=PASS):
    registrar(c, cuenta, password)
    return {"Authorization": f"Bearer {login(c, cuenta, password).json()['token']}"}


def test_alumno_no_ve_panel_admin(client):
    h = sesion(client, CUENTA)
    info = client.get("/api/session/info", headers=h).json()
    assert info["usuario"]["rol"] == "alumno" and info["usuario"]["es_admin"] is False
    assert client.get("/api/v1/admin/metrics", headers=h).status_code == 403
    assert client.get("/api/v1/admin/metrics").status_code == 401


def test_admin_ve_panel_admin(client):
    store.autorizar_cuenta(ADMIN, "ICO", "Integrante Admin", "admin")
    h = sesion(client, ADMIN)
    assert login(client, ADMIN).json()["rol"] == "admin"
    assert client.get("/api/v1/admin/metrics", headers=h).status_code == 200


def test_rol_se_actualiza_en_cuenta_existente(client):
    assert store.autorizar_cuenta(CUENTA, "ICO", rol="admin") is False
    h = sesion(client, CUENTA)
    assert client.get("/api/session/info", headers=h).json()["usuario"]["rol"] == "admin"


def test_admin_reinicia_registro_y_cierra_sesiones(client):
    store.autorizar_cuenta(ADMIN, "ICO", "Integrante Admin", "admin")
    h_admin = sesion(client, ADMIN)
    h_alumno = sesion(client, CUENTA)

    r = client.post("/api/auth/admin/reiniciar-registro", json={"numero_cuenta": CUENTA}, headers=h_admin)
    assert r.status_code == 200 and r.json()["reiniciado"] is True
    # La sesión anterior del alumno ya no sirve y puede registrarse de nuevo
    assert client.get("/api/session/info", headers=h_alumno).json()["authenticated"] is False
    assert registrar(client, password="nueva-contrasena-1").status_code == 201


def test_reinicio_casos_limite(client):
    store.autorizar_cuenta(ADMIN, "ICO", "Integrante Admin", "admin")
    h_admin = sesion(client, ADMIN)
    url = "/api/auth/admin/reiniciar-registro"
    assert client.post(url, json={"numero_cuenta": OTRA}, headers=h_admin).status_code == 404
    assert client.post(url, json={"numero_cuenta": CUENTA}, headers=h_admin).json()["reiniciado"] is False
    assert client.post(url, json={"numero_cuenta": ADMIN}, headers=h_admin).status_code == 409
    assert client.post(url, json={"numero_cuenta": "12"}, headers=h_admin).status_code == 422


def test_admin_lista_registrados(client):
    store.autorizar_cuenta(ADMIN, "ICO", "Integrante Admin", "admin")
    store.precargar_ficticias()
    h_admin = sesion(client, ADMIN)
    registrar(client, CUENTA)
    data = client.get("/api/auth/admin/usuarios", headers=h_admin).json()["usuarios"]
    # Solo las cuentas con contraseña (las ficticias sin registrar no aparecen)
    assert {u["numero_cuenta"] for u in data} == {ADMIN, CUENTA}
    propia = next(u for u in data if u["numero_cuenta"] == ADMIN)
    assert propia["es_tu_cuenta"] is True and propia["rol"] == "admin"
    assert all("password" not in str(u).lower() and "id" not in u for u in data)


def test_alumno_no_ve_lista_de_registrados(client):
    h = sesion(client, CUENTA)
    assert client.get("/api/auth/admin/usuarios", headers=h).status_code == 403
    assert client.get("/api/auth/admin/usuarios").status_code == 401


def test_alumno_no_puede_reiniciar(client):
    store.autorizar_cuenta(ADMIN, "ICO", "Integrante Admin", "admin")
    registrar(client, ADMIN)
    h = sesion(client, CUENTA)
    r = client.post("/api/auth/admin/reiniciar-registro", json={"numero_cuenta": ADMIN}, headers=h)
    assert r.status_code == 403
    assert client.post("/api/auth/admin/reiniciar-registro", json={"numero_cuenta": ADMIN}).status_code == 401


def test_cuentas_ficticias_son_alumnos(client):
    assert store.precargar_ficticias() == 9
    assert store.precargar_ficticias() == 0          # no se duplican
    h = sesion(client, "1000005")
    assert client.get("/api/session/info", headers=h).json()["usuario"]["rol"] == "alumno"
    assert b"1000005" not in client.db_path.read_bytes()


def test_migracion_de_base_sin_roles(tmp_path, monkeypatch):
    import sqlite3
    db = tmp_path / "vieja.db"
    monkeypatch.setenv("USUARIOS_DB_PATH", str(db))
    monkeypatch.setenv("CUENTA_HMAC_KEY", "hmac-de-prueba-" + "y" * 20)
    monkeypatch.setenv("CUENTA_FERNET_KEY", Fernet.generate_key().decode())
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE cuentas_autorizadas(cuenta_hash TEXT PRIMARY KEY, cuenta_cifrada TEXT NOT NULL, "
                     "nombre_cifrado TEXT, carrera TEXT NOT NULL)")
        conn.execute("INSERT INTO cuentas_autorizadas VALUES (?, 'x', NULL, 'ICO')", (store.hash_cuenta(CUENTA),))
    store.init_db()
    assert store.autorizar_cuenta(CUENTA, "ICO", rol="admin") is False
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT rol FROM cuentas_autorizadas").fetchone()[0] == "admin"


def test_base_sin_datos_en_texto_plano(client):
    registrar(client)
    contenido = client.db_path.read_bytes()
    assert CUENTA.encode() not in contenido
    assert NOMBRE.encode() not in contenido
    assert PASS.encode() not in contenido
