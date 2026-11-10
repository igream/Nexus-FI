"""
Tablero de usuario y panel admin con datos reales (plan de implementación, fase F4).

Todo se calcula desde la tabla `mensajes` de data/usuarios.db, así que sobrevive a los
reinicios y ya no hay líneas base de demostración. Cada respuesta del asistente es una
consulta; de ella salen el modelo pedido (`modelo_cuota`), si encontró fuentes, la categoría
de la fuente principal, la latencia, los tokens del modelo, los de la reescritura (siempre
gpt-4o-mini) y los del embedding de la búsqueda.

Las fechas se agrupan en hora del centro de México (UTC-6; sin horario de verano desde 2022).
Las preguntas sin resultado se muestran al administrador agrupadas y sin decir quién las hizo.
"""
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.auth.store import _conectar, descifrar
from core.chat import modelos

ZONA = timezone(timedelta(hours=-6), "America/Mexico_City")
PRECIO_EMBEDDING = 0.02 / 1_000_000          # text-embedding-3-small, USD por token
MAX_SIN_RESULTADO = 20


def _fecha_local(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(ZONA).date().isoformat()


def _desde_iso(ahora: datetime, dias: int) -> str:
    """Inicio (en UTC) del primer día de una ventana de `dias` días locales que termina hoy."""
    inicio_local = ahora.astimezone(ZONA).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=dias - 1)
    return inicio_local.astimezone(timezone.utc).isoformat(timespec="seconds")


def _dias(ahora: datetime, dias: int) -> list[str]:
    hoy = ahora.astimezone(ZONA).date()
    return [(hoy - timedelta(days=i)).isoformat() for i in range(dias - 1, -1, -1)]


def percentil(valores: list[float], p: float) -> Optional[float]:
    """Percentil por rango más cercano (p entre 0 y 100)."""
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None
    k = max(0, min(len(v) - 1, int(round(p / 100 * len(v) + 0.5)) - 1))
    return round(v[k], 1)


def _etiqueta(modelo: Optional[str]) -> str:
    return modelos.MODELOS.get(modelo or "", {}).get("etiqueta", modelo or "sin modelo")


# ---------------------------------------------------------------------------
# Tablero del usuario (solo sus propios datos)
# ---------------------------------------------------------------------------
def tablero_usuario(usuario_id, dias: int = 7, ahora: Optional[datetime] = None) -> dict:
    ahora = ahora or datetime.now(timezone.utc)
    with closing(_conectar()) as conn:
        filas = conn.execute(
            """SELECT modelo_cuota, encontrado, categoria_principal, latencia_ms, creado_en
               FROM mensajes WHERE usuario_id = ? AND rol = 'assistant' AND creado_en >= ?
               ORDER BY creado_en""",
            (str(usuario_id), _desde_iso(ahora, dias)),
        ).fetchall()

    fechas = _dias(ahora, dias)
    serie: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(fechas, 0))
    por_modelo, temas = Counter(), Counter()
    latencias, encontradas = [], 0
    for f in filas:
        m = f["modelo_cuota"] or modelos.MODELO_POR_DEFECTO
        dia = _fecha_local(f["creado_en"])
        if dia in serie[m]:
            serie[m][dia] += 1
        por_modelo[m] += 1
        if f["encontrado"]:
            encontradas += 1
            if f["categoria_principal"]:
                temas[f["categoria_principal"]] += 1
        if f["latencia_ms"] is not None:
            latencias.append(f["latencia_ms"])

    total = len(filas)
    return {
        "periodo_dias": dias,
        "consultas": total,
        "por_modelo": [{"modelo": m, "etiqueta": _etiqueta(m), "consultas": n} for m, n in por_modelo.most_common()],
        "con_fuentes": encontradas,
        "tasa_con_fuentes": round(encontradas / total * 100, 1) if total else None,
        "latencia_promedio_ms": round(sum(latencias) / len(latencias)) if latencias else None,
        "fechas": fechas,
        "serie": {m: list(v.values()) for m, v in serie.items()},
        "temas": [{"categoria": c, "consultas": n} for c, n in temas.most_common(8)],
    }


# ---------------------------------------------------------------------------
# Panel admin (todos los usuarios; solo administradores)
# ---------------------------------------------------------------------------
def _consumo(filas) -> dict:
    """Tokens y costo por bolsa (modelo de respuesta, reescritura y embeddings)."""
    bolsas: dict[str, dict] = {}

    def sumar(clave, etiqueta, tokens, costo):
        b = bolsas.setdefault(clave, {"clave": clave, "etiqueta": etiqueta, "tokens": 0, "costo_usd": 0.0, "consultas": 0})
        b["tokens"] += tokens
        b["costo_usd"] += costo

    for f in filas:
        m = f["modelo_cuota"] or modelos.MODELO_POR_DEFECTO
        te, ts = f["tokens_entrada"] or 0, f["tokens_salida"] or 0
        costo = f["costo_usd"]
        if costo is None and m in modelos.MODELOS and (te or ts):
            costo = modelos.costo(m, te, ts)
        sumar(m, _etiqueta(m), te + ts, costo or 0.0)
        bolsas[m]["consultas"] += 1
        re, rs = f["reescritura_tokens_entrada"] or 0, f["reescritura_tokens_salida"] or 0
        if re or rs:
            mr = modelos.MODELO_REESCRITURA
            sumar(f"{mr}:reescritura", f"{_etiqueta(mr)} · reescritura", re + rs, modelos.costo(mr, re, rs))
        emb = f["embedding_tokens"] or 0
        if emb:
            sumar("embeddings", "Embeddings (text-embedding-3-small)", emb, emb * PRECIO_EMBEDDING)

    lista = sorted(bolsas.values(), key=lambda b: -b["costo_usd"])
    for b in lista:
        b["costo_usd"] = round(b["costo_usd"], 6)
    return {"bolsas": lista, "costo_total_usd": round(sum(b["costo_usd"] for b in lista), 6),
            "tokens_total": sum(b["tokens"] for b in lista)}


def panel_admin(ahora: Optional[datetime] = None) -> dict:
    ahora = ahora or datetime.now(timezone.utc)
    with closing(_conectar()) as conn:
        filas = conn.execute(
            """SELECT id, conversacion_id, usuario_id, modelo_cuota, encontrado, latencia_ms, creado_en,
                      tokens_entrada, tokens_salida, costo_usd, reescritura_tokens_entrada,
                      reescritura_tokens_salida, embedding_tokens
               FROM mensajes WHERE rol = 'assistant' AND creado_en >= ? ORDER BY creado_en""",
            (_desde_iso(ahora, 30),),
        ).fetchall()
        carreras = {str(f["id"]): f["carrera"] for f in conn.execute("SELECT id, carrera FROM usuarios")}
        sin_resultado = conn.execute(
            """SELECT u.contenido_cifrado, a.creado_en FROM mensajes a
               JOIN mensajes u ON u.id = a.id - 1 AND u.conversacion_id = a.conversacion_id AND u.rol = 'user'
               WHERE a.rol = 'assistant' AND a.encontrado = 0 AND a.creado_en >= ?
               ORDER BY a.id DESC LIMIT 500""",
            (_desde_iso(ahora, 30),),
        ).fetchall()

    # Preguntas sin resultado agrupadas (sin importar mayúsculas ni espacios), la más reciente primero
    grupos: dict[str, dict] = {}
    for f in sin_resultado:
        texto = descifrar(f["contenido_cifrado"])
        clave = " ".join(texto.lower().split())
        g = grupos.setdefault(clave, {"pregunta": texto, "fecha": _fecha_local(f["creado_en"]), "veces": 0})
        g["veces"] += 1

    hoy, semana = _desde_iso(ahora, 1), _desde_iso(ahora, 7)
    periodos = {
        "hoy": [f for f in filas if f["creado_en"] >= hoy],
        "semana": [f for f in filas if f["creado_en"] >= semana],
        "mes": list(filas),
    }

    fechas = _dias(ahora, 30)
    costo_diario = dict.fromkeys(fechas, 0.0)
    consultas_diarias = dict.fromkeys(fechas, 0)
    for f in filas:
        dia = _fecha_local(f["creado_en"])
        if dia in costo_diario:
            costo_diario[dia] += _consumo([f])["costo_total_usd"]
            consultas_diarias[dia] += 1

    por_carrera = Counter(carreras.get(str(f["usuario_id"]), "Sin carrera") for f in filas)
    latencias = [f["latencia_ms"] for f in filas if f["latencia_ms"] is not None]
    total_sin = sum(1 for f in filas if f["encontrado"] == 0)

    return {
        "consumo": {p: _consumo(fs) for p, fs in periodos.items()},
        "consultas": {p: len(fs) for p, fs in periodos.items()},
        "usuarios_activos": {p: len({f["usuario_id"] for f in fs}) for p, fs in periodos.items()},
        "por_carrera": [{"carrera": c, "consultas": n} for c, n in por_carrera.most_common()],
        "latencia_ms": {"p50": percentil(latencias, 50), "p95": percentil(latencias, 95), "muestras": len(latencias)},
        "sin_resultado": {
            "total_mes": total_sin,
            "tasa_mes": round(total_sin / len(filas) * 100, 1) if filas else None,
            "recientes": list(grupos.values())[:MAX_SIN_RESULTADO],
        },
        "serie_30_dias": {
            "fechas": fechas,
            "costo_usd": [round(v, 6) for v in costo_diario.values()],
            "consultas": list(consultas_diarias.values()),
        },
    }
