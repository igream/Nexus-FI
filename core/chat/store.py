"""
Historial de conversaciones de Nexus FI (plan de implementación, fase F1).

Dos tablas en la misma base de usuarios (data/usuarios.db):
  conversaciones  una por hilo de chat, siempre ligada a un usuario
  mensajes        preguntas y respuestas de cada conversación, con su telemetría

Protección de datos: el título y el texto de los mensajes se guardan cifrados con
la misma clave Fernet del inicio de sesión (CUENTA_FERNET_KEY). Quedan en claro solo
los datos técnicos que usan los tableros: modelo, categoría de la fuente principal,
tokens, costo y latencia. Las citas son referencias a documentos públicos del acervo.

Borrar una conversación es un borrado lógico (eliminada = 1): deja de mostrarse, pero
sus mensajes se conservan para que las cuotas y los tableros sigan cuadrando.
"""
import json
import uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import Optional

from core.auth.store import _conectar, cifrar, descifrar

TITULO_MAX = 80
ROLES_MENSAJE = ("user", "assistant")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _titulo_de(pregunta: str) -> str:
    """Título por defecto: la primera pregunta, en una línea y recortada."""
    texto = " ".join(pregunta.split())
    return texto if len(texto) <= 60 else texto[:57].rstrip() + "..."


def init_db() -> None:
    with closing(_conectar()) as conn, conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS conversaciones(
                   id TEXT PRIMARY KEY,
                   usuario_id TEXT NOT NULL,
                   titulo_cifrado TEXT NOT NULL,
                   creada_en TEXT NOT NULL,
                   actualizada_en TEXT NOT NULL,
                   eliminada INTEGER NOT NULL DEFAULT 0)"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS mensajes(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   conversacion_id TEXT NOT NULL REFERENCES conversaciones(id),
                   usuario_id TEXT NOT NULL,
                   rol TEXT NOT NULL CHECK(rol IN ('user','assistant')),
                   contenido_cifrado TEXT NOT NULL,
                   consulta_reescrita_cifrada TEXT,
                   modelo TEXT,
                   categoria_principal TEXT,
                   encontrado INTEGER,
                   citas_json TEXT,
                   tokens_entrada INTEGER,
                   tokens_salida INTEGER,
                   costo_usd REAL,
                   latencia_ms REAL,
                   creado_en TEXT NOT NULL)"""
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_conv_usuario ON conversaciones(usuario_id, eliminada, actualizada_en)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_msg_conversacion ON mensajes(conversacion_id, id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_msg_usuario_fecha ON mensajes(usuario_id, creado_en)")
        # F2: tokens de la reescritura de la pregunta (siempre gpt-4o-mini), aparte de los del
        # modelo que respondió, para que los costos por modelo cuadren. Bases creadas en F1
        # no tienen estas columnas: se agregan sin tocar los datos.
        columnas = {f["name"] for f in conn.execute("PRAGMA table_info(mensajes)")}
        for col in ("reescritura_tokens_entrada", "reescritura_tokens_salida"):
            if col not in columnas:
                conn.execute(f"ALTER TABLE mensajes ADD COLUMN {col} INTEGER")


def crear_conversacion(usuario_id, primera_pregunta: str) -> str:
    conv_id = str(uuid.uuid4())
    ahora = _ahora()
    with closing(_conectar()) as conn, conn:
        conn.execute(
            "INSERT INTO conversaciones(id, usuario_id, titulo_cifrado, creada_en, actualizada_en) VALUES (?, ?, ?, ?, ?)",
            (conv_id, str(usuario_id), cifrar(_titulo_de(primera_pregunta)), ahora, ahora),
        )
    return conv_id


def es_de_usuario(usuario_id, conv_id: str) -> bool:
    """True si la conversación existe, no está borrada y pertenece al usuario."""
    with closing(_conectar()) as conn:
        fila = conn.execute(
            "SELECT 1 FROM conversaciones WHERE id = ? AND usuario_id = ? AND eliminada = 0",
            (conv_id, str(usuario_id)),
        ).fetchone()
    return fila is not None


def agregar_mensaje(
    conv_id: str,
    usuario_id,
    rol: str,
    contenido: str,
    *,
    consulta_reescrita: Optional[str] = None,
    modelo: Optional[str] = None,
    categoria_principal: Optional[str] = None,
    encontrado: Optional[bool] = None,
    citas: Optional[list] = None,
    tokens_entrada: Optional[int] = None,
    tokens_salida: Optional[int] = None,
    costo_usd: Optional[float] = None,
    latencia_ms: Optional[float] = None,
    reescritura_tokens_entrada: Optional[int] = None,
    reescritura_tokens_salida: Optional[int] = None,
) -> int:
    if rol not in ROLES_MENSAJE:
        raise ValueError("Rol de mensaje no válido")
    ahora = _ahora()
    with closing(_conectar()) as conn, conn:
        cur = conn.execute(
            """INSERT INTO mensajes(conversacion_id, usuario_id, rol, contenido_cifrado, consulta_reescrita_cifrada,
                   modelo, categoria_principal, encontrado, citas_json, tokens_entrada, tokens_salida,
                   costo_usd, latencia_ms, reescritura_tokens_entrada, reescritura_tokens_salida, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                conv_id, str(usuario_id), rol, cifrar(contenido),
                cifrar(consulta_reescrita) if consulta_reescrita else None,
                modelo, categoria_principal,
                None if encontrado is None else int(bool(encontrado)),
                json.dumps(citas, ensure_ascii=False) if citas else None,
                tokens_entrada, tokens_salida, costo_usd, latencia_ms,
                reescritura_tokens_entrada, reescritura_tokens_salida, ahora,
            ),
        )
        conn.execute("UPDATE conversaciones SET actualizada_en = ? WHERE id = ?", (ahora, conv_id))
        return cur.lastrowid


def listar_conversaciones(usuario_id, limite: int = 50) -> list[dict]:
    with closing(_conectar()) as conn:
        filas = conn.execute(
            """SELECT id, titulo_cifrado, creada_en, actualizada_en FROM conversaciones
               WHERE usuario_id = ? AND eliminada = 0
               ORDER BY actualizada_en DESC, rowid DESC LIMIT ?""",
            (str(usuario_id), limite),
        ).fetchall()
    return [
        {"id": f["id"], "titulo": descifrar(f["titulo_cifrado"]),
         "creada_en": f["creada_en"], "actualizada_en": f["actualizada_en"]}
        for f in filas
    ]


def obtener_conversacion(usuario_id, conv_id: str) -> Optional[dict]:
    """La conversación con sus mensajes en orden, o None si no es del usuario o está borrada."""
    with closing(_conectar()) as conn:
        conv = conn.execute(
            """SELECT id, titulo_cifrado, creada_en, actualizada_en FROM conversaciones
               WHERE id = ? AND usuario_id = ? AND eliminada = 0""",
            (conv_id, str(usuario_id)),
        ).fetchone()
        if conv is None:
            return None
        filas = conn.execute(
            """SELECT rol, contenido_cifrado, modelo, encontrado, citas_json, latencia_ms, creado_en
               FROM mensajes WHERE conversacion_id = ? ORDER BY id""",
            (conv_id,),
        ).fetchall()
    return {
        "id": conv["id"],
        "titulo": descifrar(conv["titulo_cifrado"]),
        "creada_en": conv["creada_en"],
        "actualizada_en": conv["actualizada_en"],
        "mensajes": [
            {
                "rol": f["rol"],
                "contenido": descifrar(f["contenido_cifrado"]),
                "modelo": f["modelo"],
                "encontrado": None if f["encontrado"] is None else bool(f["encontrado"]),
                "citas": json.loads(f["citas_json"]) if f["citas_json"] else [],
                "latencia_ms": f["latencia_ms"],
                "creado_en": f["creado_en"],
            }
            for f in filas
        ],
    }


def ultimos_mensajes(usuario_id, conv_id: str, limite: int) -> list[dict]:
    """Los últimos `limite` mensajes ({rol, contenido}) en orden cronológico (F2).

    Solo trae lo necesario para armar el contexto, sin cargar toda la conversación.
    Regresa [] si la conversación no es del usuario o está borrada.
    """
    with closing(_conectar()) as conn:
        filas = conn.execute(
            """SELECT m.rol, m.contenido_cifrado FROM mensajes m
               JOIN conversaciones c ON c.id = m.conversacion_id
               WHERE m.conversacion_id = ? AND c.usuario_id = ? AND c.eliminada = 0
               ORDER BY m.id DESC LIMIT ?""",
            (conv_id, str(usuario_id), limite),
        ).fetchall()
    return [{"rol": f["rol"], "contenido": descifrar(f["contenido_cifrado"])} for f in reversed(filas)]


def renombrar_conversacion(usuario_id, conv_id: str, titulo: str) -> bool:
    titulo = " ".join(titulo.split())[:TITULO_MAX]
    if not titulo:
        raise ValueError("El título no puede estar vacío")
    with closing(_conectar()) as conn, conn:
        cur = conn.execute(
            "UPDATE conversaciones SET titulo_cifrado = ? WHERE id = ? AND usuario_id = ? AND eliminada = 0",
            (cifrar(titulo), conv_id, str(usuario_id)),
        )
    return cur.rowcount == 1


def eliminar_conversacion(usuario_id, conv_id: str) -> bool:
    with closing(_conectar()) as conn, conn:
        cur = conn.execute(
            "UPDATE conversaciones SET eliminada = 1 WHERE id = ? AND usuario_id = ? AND eliminada = 0",
            (conv_id, str(usuario_id)),
        )
    return cur.rowcount == 1
