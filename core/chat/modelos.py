"""
Modelos generativos de Nexus FI y sus cuotas (plan de implementación, fase F3).

Tabla única MODELOS: todo lo que depende del modelo sale de aquí (id de API, clave, bolsa
del panel admin, tarifas, tope de salida, cuotas y parámetros admitidos). El usuario elige
el modelo en la interfaz (decisión D1); no hay ruteo automático.

Parámetros verificados el 2026-11-10 con llamadas reales a Chat Completions:
  - gpt-6-luna y gpt-5.6-luna son modelos de razonamiento: no aceptan `max_tokens`
    (hay que usar `max_completion_tokens`, que incluye los tokens de razonamiento) y solo
    admiten `temperature` con `reasoning_effort="none"`.
  - Precios por millón de tokens (developers.openai.com, 2026-11-10):
      gpt-4o-mini   entrada 0.15  salida 0.60
      gpt-6-luna    entrada 0.10  salida 0.50  (entrada en caché 0.01)
      gpt-5.6-luna  entrada 0.20  salida 1.20  (entrada en caché 0.02)
    Los tokens de razonamiento se cobran como salida y ya vienen en completion_tokens.

Cuotas (decisión D3), en consultas y por modelo, contadas desde la tabla `mensajes`
para que sobrevivan a los reinicios. `cuota_dia=None` significa sin tope diario
(el del modelo avanzado sigue por definir).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

MODELO_POR_DEFECTO = "gpt-4o-mini"
MODELO_REESCRITURA = "gpt-4o-mini"   # F2: la reescritura siempre usa el modelo rápido
HORA, DIA = timedelta(hours=1), timedelta(days=1)

MODELOS: dict[str, dict[str, Any]] = {
    "gpt-4o-mini": {
        "etiqueta": "Rápido (4o-mini)",
        "api_id": "gpt-4o-mini",
        "env_clave": ("OPENAI_API_KEY_CHAT_4O_MINI", "OPENAI_API_KEY_CHAT", "OPENAI_API_KEY"),
        "bolsa": "gpt4oMini",
        "precio_entrada": 0.15 / 1_000_000,
        "precio_salida": 0.60 / 1_000_000,
        "max_salida": 1200,          # alcanza para listas largas (p. ej. todas las clases de un día)
        "cuota_hora": 20,
        "cuota_dia": 60,
        "razonamiento": False,
        "temperature": 0.2,
        "en_selector": True,
    },
    "gpt-6-luna": {
        "etiqueta": "Avanzado (gpt-6)",
        "api_id": "gpt-6-luna",
        "env_clave": ("OPENAI_API_KEY_GPT6_LUNA",),
        "bolsa": "luna6",
        "precio_entrada": 0.10 / 1_000_000,
        "precio_salida": 0.50 / 1_000_000,
        "max_salida": 2000,          # incluye razonamiento; afinar con scripts/comparar_modelos.py
        "cuota_hora": 5,
        "cuota_dia": None,           # por definir con el equipo
        "razonamiento": True,
        "reasoning_effort": "low",
        "en_selector": True,
    },
    # Candidato en comparación (D2). Se retira de la tabla cuando se elija al ganador.
    "gpt-5.6-luna": {
        "etiqueta": "Avanzado (gpt-5.6)",
        "api_id": "gpt-5.6-luna",
        "env_clave": ("OPENAI_API_KEY_GPT5_6_LUNA",),
        "bolsa": "luna56",
        "precio_entrada": 0.20 / 1_000_000,
        "precio_salida": 1.20 / 1_000_000,
        "max_salida": 2000,
        "cuota_hora": 5,
        "cuota_dia": None,
        "razonamiento": True,
        "reasoning_effort": "low",
        "en_selector": False,
    },
}


def parametros_llamada(modelo: str, max_salida: Optional[int] = None,
                       temperature: Optional[float] = None) -> dict[str, Any]:
    """Argumentos de chat.completions.create que admite el modelo (sin `messages`)."""
    m = MODELOS[modelo]
    tope = max_salida or m["max_salida"]
    if m["razonamiento"]:
        kw: dict[str, Any] = {"model": m["api_id"], "max_completion_tokens": tope,
                              "reasoning_effort": m.get("reasoning_effort", "low")}
        if kw["reasoning_effort"] == "none" and temperature is not None:
            kw["temperature"] = temperature
        return kw
    return {"model": m["api_id"], "max_tokens": tope,
            "temperature": m.get("temperature", 0.2) if temperature is None else temperature}


def costo(modelo: str, tokens_entrada: int, tokens_salida: int) -> float:
    m = MODELOS[modelo]
    return tokens_entrada * m["precio_entrada"] + tokens_salida * m["precio_salida"]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def estado_cuota(modelo: str, contar, ahora: Optional[datetime] = None) -> dict[str, Any]:
    """Cuota de un usuario para un modelo.

    `contar(desde_iso)` debe regresar (consultas desde esa fecha, fecha ISO de la más antigua);
    así esta función no depende de la base y se prueba sola.
    """
    m = MODELOS[modelo]
    ahora = ahora or datetime.now(timezone.utc)
    usadas_hora, primera_hora = contar(_iso(ahora - HORA))
    usadas_dia, primera_dia = contar(_iso(ahora - DIA)) if m["cuota_dia"] else (usadas_hora, None)

    agotada_hora = usadas_hora >= m["cuota_hora"]
    agotada_dia = bool(m["cuota_dia"]) and usadas_dia >= m["cuota_dia"]
    retry_after = 0
    if agotada_dia and primera_dia:
        retry_after = int((datetime.fromisoformat(primera_dia) + DIA - ahora).total_seconds()) + 1
    if agotada_hora and primera_hora:
        retry_after = max(retry_after, int((datetime.fromisoformat(primera_hora) + HORA - ahora).total_seconds()) + 1)
    retry_after = max(retry_after, 0)

    return {
        "model": modelo,
        "label": m["etiqueta"],
        "allowed": not (agotada_hora or agotada_dia),
        "hourly_limit": m["cuota_hora"],
        "hourly_used": usadas_hora,
        "hourly_remaining": max(0, m["cuota_hora"] - usadas_hora),
        "daily_limit": m["cuota_dia"],
        "daily_used": usadas_dia if m["cuota_dia"] else None,
        "daily_remaining": max(0, m["cuota_dia"] - usadas_dia) if m["cuota_dia"] else None,
        "retry_after": retry_after,
        "reset_at": _iso(ahora + timedelta(seconds=retry_after)) if retry_after else None,
    }
