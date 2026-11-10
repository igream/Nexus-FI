"""
Contexto conversacional de Nexus FI (plan de implementación, fase F2).

Dos piezas, ambas sin red para poder probarlas solas:
  recortar_historial()        últimos N pares pregunta-respuesta dentro de un tope de tokens
  mensajes_reescritura()      prompt para que gpt-4o-mini convierta una pregunta de
                              seguimiento («¿y cuál es el plazo?») en una autónoma
  limpiar_reescritura()       valida lo que devuelve el modelo; si no sirve, None

Los tokens se estiman (unos 3.5 caracteres por token en español) en lugar de usar
tiktoken, que descarga su codificación la primera vez y podría fallar en plena consulta.
Para un tope de contexto basta una estimación.
"""
from typing import Optional

PARES_HISTORIAL = 3            # turnos previos que se envían al LLM
TOPE_TOKENS_HISTORIAL = 1500   # tope aproximado del historial completo
MAX_TOKENS_REESCRITURA = 100
MAX_CARACTERES_REESCRITURA = 400
CARACTERES_POR_TOKEN = 3.5
# En la reescritura las respuestas previas solo dan el tema; no hace falta enviarlas completas
RECORTE_RESPUESTA_REESCRITURA = 600

PROMPT_REESCRITURA = (
    "Reescribes preguntas para un buscador de documentos de la Facultad de Ingeniería de la UAEMéx.\n"
    "Recibes una conversación previa y la pregunta nueva del estudiante. Si la pregunta nueva depende "
    "de la conversación (pronombres, «y…», «¿cuál es el plazo?», «¿y para ICO?»), reescríbela como una "
    "pregunta autónoma en español que incluya el tema explícito. Si ya es autónoma, devuélvela igual.\n"
    "Responde SOLO con la pregunta reescrita, en una línea, sin comillas ni explicaciones."
)


def estimar_tokens(texto: str) -> int:
    return max(1, int(len(texto) / CARACTERES_POR_TOKEN) + 1) if texto else 0


def _recortar(texto: str, tokens: int) -> str:
    limite = int(tokens * CARACTERES_POR_TOKEN)
    return texto if len(texto) <= limite else texto[: max(limite - 3, 0)].rstrip() + "..."


def recortar_historial(
    mensajes: list[dict],
    pares: int = PARES_HISTORIAL,
    tope_tokens: int = TOPE_TOKENS_HISTORIAL,
) -> list[dict]:
    """Convierte mensajes guardados ({rol, contenido}, en orden) en mensajes para el LLM.

    Se quedan los últimos `pares` pares completos (pregunta seguida de respuesta). Si no caben
    en `tope_tokens`, se descartan los más viejos; si ni el par más reciente cabe, se recorta
    su respuesta para que al menos la última pregunta llegue completa.
    """
    seleccion: list[list[dict]] = []
    i = len(mensajes) - 1
    while i >= 1 and len(seleccion) < pares:
        prev, actual = mensajes[i - 1], mensajes[i]
        if prev.get("rol") == "user" and actual.get("rol") == "assistant":
            seleccion.append([
                {"role": "user", "content": prev.get("contenido") or ""},
                {"role": "assistant", "content": actual.get("contenido") or ""},
            ])
            i -= 2
        else:
            i -= 1   # mensaje suelto (p. ej. un turno que no terminó de guardarse)

    resultado: list[list[dict]] = []
    usados = 0
    for par in seleccion:   # del más reciente al más viejo
        costo = sum(estimar_tokens(m["content"]) for m in par)
        if usados + costo <= tope_tokens:
            resultado.append(par)
            usados += costo
            continue
        if not resultado:   # el par más reciente no cabe: recortar su respuesta
            libre = tope_tokens - estimar_tokens(par[0]["content"])
            if libre > 20:
                par[1]["content"] = _recortar(par[1]["content"], libre)
                resultado.append(par)
        break

    return [m for par in reversed(resultado) for m in par]


def mensajes_reescritura(historial: list[dict], pregunta: str) -> list[dict]:
    """Prompt de reescritura: la conversación previa como texto y la pregunta nueva."""
    lineas = []
    for m in historial:
        quien = "Estudiante" if m["role"] == "user" else "Asistente"
        texto = m["content"]
        if m["role"] == "assistant" and len(texto) > RECORTE_RESPUESTA_REESCRITURA:
            texto = texto[:RECORTE_RESPUESTA_REESCRITURA].rstrip() + "..."
        lineas.append(f"{quien}: {texto}")
    conversacion = "\n".join(lineas)
    return [
        {"role": "system", "content": PROMPT_REESCRITURA},
        {"role": "user", "content": f"Conversación previa:\n{conversacion}\n\nPregunta nueva: {pregunta}"},
    ]


def limpiar_reescritura(texto: Optional[str]) -> Optional[str]:
    """La pregunta reescrita lista para buscar, o None si la salida del modelo no sirve."""
    if not texto:
        return None
    linea = " ".join(texto.strip().split())
    for prefijo in ("Pregunta reescrita:", "Pregunta:"):
        if linea.lower().startswith(prefijo.lower()):
            linea = linea[len(prefijo):].strip()
    linea = linea.strip("\"'«»“” ")
    if not linea or len(linea) > MAX_CARACTERES_REESCRITURA:
        return None
    return linea
