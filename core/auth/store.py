"""
Almacén de usuarios de Nexus FI (WBS 1.3.4, SC-001).

Base SQLite con dos tablas:
  cuentas_autorizadas  cuentas que precarga el PM (padrón del piloto ICO)
  usuarios             cuentas que ya crearon su contraseña

Protección de datos personales:
  - Número de cuenta: cifrado con Fernet y, para poder buscarlo, una huella HMAC-SHA256.
  - Nombre: cifrado con Fernet.
  - Contraseña: solo su hash bcrypt.
Nada se guarda en texto plano. Las claves se leen del entorno (.env) al usarse:
AUTH_JWT_SECRET, CUENTA_HMAC_KEY y CUENTA_FERNET_KEY. La ruta de la base es
USUARIOS_DB_PATH (por defecto data/usuarios.db, carpeta ignorada por Git).
"""
import hashlib
import hmac
import os
import sqlite3
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import bcrypt
from cryptography.fernet import Fernet

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Carreras habilitadas en el piloto (SC-001). Para abrir otra carrera basta con agregarla aquí.
CARRERAS = {
    "ICO": "Licenciatura en Ingeniería en Computación",
}

# Roles: los integrantes del equipo son administradores; el resto, alumnos.
ROLES = ("admin", "alumno")

# Cuentas ficticias de prueba (no son datos reales): 1000001 a 1000009, rol alumno
CUENTAS_FICTICIAS = [(f"100000{n}", f"Usuario de Prueba {n}") for n in range(1, 10)]


class CuentaNoAutorizada(Exception):
    """La cuenta no está en el padrón precargado."""


class CuentaYaRegistrada(Exception):
    """La cuenta ya creó su contraseña."""


class ClavesNoConfiguradas(RuntimeError):
    """Faltan las claves de cifrado en el .env."""


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _sin_acentos(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()


def normalizar_carrera(valor: str) -> Optional[str]:
    """Acepta la clave ("ICO") o el nombre completo de la carrera y regresa la clave, o None."""
    if not valor:
        return None
    v = _sin_acentos(valor)
    for clave, nombre in CARRERAS.items():
        if v in (clave.lower(), _sin_acentos(nombre)):
            return clave
    return None


def _clave(nombre: str) -> str:
    valor = (os.getenv(nombre) or "").strip()
    if not valor or valor.startswith("cambia") or valor.startswith("genera"):
        raise ClavesNoConfiguradas(f"Falta configurar {nombre} en el archivo .env")
    return valor


def _fernet() -> Fernet:
    return Fernet(_clave("CUENTA_FERNET_KEY").encode())


def _db_path() -> Path:
    ruta = os.getenv("USUARIOS_DB_PATH") or "data/usuarios.db"
    p = Path(ruta)
    return p if p.is_absolute() else BASE_DIR / p


def _conectar() -> sqlite3.Connection:
    ruta = _db_path()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta)
    conn.row_factory = sqlite3.Row
    return conn


def hash_cuenta(numero: str) -> str:
    """Huella HMAC-SHA256 del número de cuenta (permite buscarlo sin guardarlo en claro)."""
    return hmac.new(_clave("CUENTA_HMAC_KEY").encode(), numero.strip().encode(), hashlib.sha256).hexdigest()


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def descifrar(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


# Hash fijo para igualar el tiempo de respuesta cuando la cuenta no existe
_HASH_FICTICIO = bcrypt.hashpw(b"nexus-fi-sin-cuenta", bcrypt.gensalt())


# ---------------------------------------------------------------------------
# Operaciones
# ---------------------------------------------------------------------------
def init_db() -> None:
    with closing(_conectar()) as conn, conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cuentas_autorizadas(
                   cuenta_hash TEXT PRIMARY KEY,
                   cuenta_cifrada TEXT NOT NULL,
                   nombre_cifrado TEXT,
                   carrera TEXT NOT NULL,
                   rol TEXT NOT NULL DEFAULT 'alumno')"""
        )
        # Bases creadas antes de los roles: se agrega la columna sin perder datos
        columnas = {c["name"] for c in conn.execute("PRAGMA table_info(cuentas_autorizadas)")}
        if "rol" not in columnas:
            conn.execute("ALTER TABLE cuentas_autorizadas ADD COLUMN rol TEXT NOT NULL DEFAULT 'alumno'")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS usuarios(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   cuenta_hash TEXT UNIQUE NOT NULL,
                   cuenta_cifrada TEXT NOT NULL,
                   nombre_cifrado TEXT,
                   carrera TEXT NOT NULL,
                   password_hash TEXT NOT NULL,
                   creado_en TEXT NOT NULL)"""
        )


def autorizar_cuenta(numero: str, carrera: str, nombre: str = "", rol: Optional[str] = None) -> bool:
    """Agrega una cuenta al padrón. Si ya existía no la duplica (regresa False),
    pero sí actualiza su rol cuando se indica uno."""
    clave_carrera = normalizar_carrera(carrera)
    if not clave_carrera:
        raise ValueError("Carrera no habilitada en el piloto")
    if rol is not None and rol not in ROLES:
        raise ValueError("Rol no válido")
    h = hash_cuenta(numero)
    with closing(_conectar()) as conn, conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO cuentas_autorizadas(cuenta_hash, cuenta_cifrada, nombre_cifrado, carrera, rol) "
            "VALUES (?, ?, ?, ?, ?)",
            (h, cifrar(numero.strip()), cifrar(nombre.strip()) if nombre else None, clave_carrera, rol or "alumno"),
        )
        nueva = cur.rowcount == 1
        if not nueva and rol is not None:
            conn.execute("UPDATE cuentas_autorizadas SET rol = ? WHERE cuenta_hash = ?", (rol, h))
        return nueva


def precargar_ficticias() -> int:
    """Carga las cuentas ficticias de prueba (rol alumno). Regresa cuántas eran nuevas."""
    return sum(autorizar_cuenta(n, "ICO", nombre, "alumno") for n, nombre in CUENTAS_FICTICIAS)


def registrar_usuario(numero: str, carrera: str, password: str) -> int:
    """Crea la contraseña de una cuenta precargada. Regresa el id interno."""
    h = hash_cuenta(numero)
    with closing(_conectar()) as conn, conn:
        autorizada = conn.execute(
            "SELECT * FROM cuentas_autorizadas WHERE cuenta_hash = ?", (h,)
        ).fetchone()
        if not autorizada or autorizada["carrera"] != normalizar_carrera(carrera):
            raise CuentaNoAutorizada()
        if conn.execute("SELECT 1 FROM usuarios WHERE cuenta_hash = ?", (h,)).fetchone():
            raise CuentaYaRegistrada()
        cur = conn.execute(
            "INSERT INTO usuarios(cuenta_hash, cuenta_cifrada, nombre_cifrado, carrera, password_hash, creado_en) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                h,
                autorizada["cuenta_cifrada"],
                autorizada["nombre_cifrado"],
                autorizada["carrera"],
                bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        return int(cur.lastrowid)


def verificar_login(numero: str, password: str) -> Optional[int]:
    """Regresa el id del usuario si la contraseña es correcta, o None."""
    with closing(_conectar()) as conn:
        fila = conn.execute(
            "SELECT id, password_hash FROM usuarios WHERE cuenta_hash = ?", (hash_cuenta(numero),)
        ).fetchone()
    if not fila:
        bcrypt.checkpw(password.encode(), _HASH_FICTICIO)
        return None
    if bcrypt.checkpw(password.encode(), fila["password_hash"].encode()):
        return int(fila["id"])
    return None


def obtener_rol(user_id) -> Optional[str]:
    """Rol vigente del usuario, o None si ya no existe (por ejemplo, tras reiniciar su registro)."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    with closing(_conectar()) as conn:
        fila = conn.execute(
            "SELECT a.rol FROM usuarios u JOIN cuentas_autorizadas a ON a.cuenta_hash = u.cuenta_hash WHERE u.id = ?",
            (uid,),
        ).fetchone()
    return fila["rol"] if fila else None


def obtener_usuario(user_id) -> Optional[dict]:
    """Datos públicos del usuario en sesión: nombre, carrera y rol (nunca el número de cuenta)."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    with closing(_conectar()) as conn:
        fila = conn.execute(
            "SELECT u.nombre_cifrado, u.carrera, a.rol FROM usuarios u "
            "JOIN cuentas_autorizadas a ON a.cuenta_hash = u.cuenta_hash WHERE u.id = ?",
            (uid,),
        ).fetchone()
    if not fila:
        return None
    return {
        "nombre": descifrar(fila["nombre_cifrado"]) if fila["nombre_cifrado"] else "",
        "carrera": fila["carrera"],
        "carrera_nombre": CARRERAS.get(fila["carrera"], fila["carrera"]),
        "rol": fila["rol"],
        "es_admin": fila["rol"] == "admin",
    }


def listar_registrados() -> list[dict]:
    """Cuentas que ya crearon contraseña, descifradas solo para el menú de administración."""
    with closing(_conectar()) as conn:
        filas = conn.execute(
            "SELECT u.id, u.cuenta_cifrada, u.nombre_cifrado, u.carrera, u.creado_en, a.rol FROM usuarios u "
            "JOIN cuentas_autorizadas a ON a.cuenta_hash = u.cuenta_hash"
        ).fetchall()
    usuarios = [
        {
            "id": f["id"],
            "numero_cuenta": descifrar(f["cuenta_cifrada"]),
            "nombre": descifrar(f["nombre_cifrado"]) if f["nombre_cifrado"] else "",
            "carrera": f["carrera"],
            "rol": f["rol"],
            "registrado_en": f["creado_en"],
        }
        for f in filas
    ]
    return sorted(usuarios, key=lambda u: (u["rol"] != "admin", u["nombre"].lower()))


def estado_cuenta(numero: str) -> dict:
    """Si la cuenta está en el padrón y si ya se registró (para el menú de administración)."""
    h = hash_cuenta(numero)
    with closing(_conectar()) as conn:
        autorizada = conn.execute("SELECT 1 FROM cuentas_autorizadas WHERE cuenta_hash = ?", (h,)).fetchone()
        usuario = conn.execute("SELECT id FROM usuarios WHERE cuenta_hash = ?", (h,)).fetchone()
    return {"autorizada": bool(autorizada), "registrada": bool(usuario), "user_id": usuario["id"] if usuario else None}


def eliminar_registro(numero: str) -> bool:
    """Borra la contraseña de una cuenta para que su dueño se registre de nuevo (la cuenta sigue en el padrón).
    Las sesiones abiertas de esa cuenta dejan de valer, porque su id interno ya no existe."""
    with closing(_conectar()) as conn, conn:
        cur = conn.execute("DELETE FROM usuarios WHERE cuenta_hash = ?", (hash_cuenta(numero),))
        return cur.rowcount > 0


def conteo() -> dict:
    with closing(_conectar()) as conn:
        return {
            "autorizadas": conn.execute("SELECT COUNT(*) FROM cuentas_autorizadas").fetchone()[0],
            "registradas": conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0],
        }
