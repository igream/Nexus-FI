"""
Comparación de modelos generativos de Nexus FI (plan de implementación, fase F3, decisión D2).

Pasa cada pregunta de scripts/preguntas_comparacion.json por el mismo flujo de /api/chat
que usa producción (búsqueda, prompt y parámetros de core/chat/modelos.py), con una base de
usuarios temporal y una cuenta ficticia, y mide por modelo:
  - acierto: la respuesta contiene los hechos esperados (sin acentos ni mayúsculas); en las
    preguntas fuera de tema, que diga que no encontró información
  - cita correcta: alguna fuente es el documento esperado
  - latencia, tokens y costo por consulta (desde la tabla mensajes)

Uso:
    python scripts/comparar_modelos.py
    python scripts/comparar_modelos.py --modelos gpt-6-luna --esfuerzo medium
Los modelos deben estar en la tabla MODELOS (core/chat/modelos.py). La corrida del
2026-11-10 que eligió a gpt-6-luna sobre gpt-5.6-luna está en docs/02_Ejecucion/.
Requiere las claves de OpenAI en .env. Costo aproximado: menos de 0.10 USD por corrida.
El reporte se guarda en docs/02_Ejecucion/ (Markdown y JSON con las respuestas completas).
"""
import argparse
import json
import os
import secrets
import sqlite3
import statistics
import sys
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="nexus_comparacion_"))
os.environ["USUARIOS_DB_PATH"] = str(TMP / "usuarios.db")
os.environ["RATE_LIMIT_ENABLED"] = "false"   # la comparación no debe chocar con las cuotas
os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

import backend.app as app_module  # noqa: E402
from core.auth import store  # noqa: E402
from core.chat import modelos  # noqa: E402
from core.chat import store as chat_store  # noqa: E402

CUENTA = "2999999"   # ficticia
FRASES_SIN_INFO = ("no se encontro informacion", "no encontre", "no cuento con", "no tengo informacion",
                   "no se encontro", "no dispongo", "no hay informacion")


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).lower().split())


def calificar(p: dict, r: dict) -> tuple[bool, bool]:
    texto = normalizar(r.get("answer", ""))
    if p.get("fuera_de_tema"):
        sin_info = (not r.get("found")) or any(f in texto for f in FRASES_SIN_INFO)
        return sin_info, sin_info
    acierto = all(any(normalizar(alt) in texto for alt in grupo) for grupo in p["hechos"])
    docs = [normalizar(c["documento"]) for c in r.get("citations", [])]
    cita = any(normalizar(f) in d for f in p["fuentes"] for d in docs)
    return acierto, cita


def ultimo_turno(db: Path) -> dict:
    with sqlite3.connect(db) as conn:
        f = conn.execute(
            """SELECT tokens_entrada, tokens_salida, costo_usd, latencia_ms FROM mensajes
               WHERE rol = 'assistant' ORDER BY id DESC LIMIT 1"""
        ).fetchone()
    return {"tokens_entrada": f[0], "tokens_salida": f[1], "costo_usd": f[2], "latencia_ms": f[3]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelos", nargs="+", default=["gpt-4o-mini", "gpt-6-luna"])
    ap.add_argument("--esfuerzo", choices=["none", "low", "medium", "high"],
                    help="reasoning_effort para los modelos de razonamiento (por defecto, el de la tabla)")
    ap.add_argument("--preguntas", default=str(RAIZ / "scripts" / "preguntas_comparacion.json"))
    ap.add_argument("--salida", default=str(RAIZ / "docs" / "02_Ejecucion"))
    args = ap.parse_args()

    for m in args.modelos:
        if m not in modelos.MODELOS:
            sys.exit(f"Modelo desconocido: {m}")
        if m not in app_module.chat_clients:
            sys.exit(f"Falta la clave de {m} en .env")
        if args.esfuerzo and modelos.MODELOS[m]["razonamiento"]:
            modelos.MODELOS[m]["reasoning_effort"] = args.esfuerzo

    preguntas = json.loads(Path(args.preguntas).read_text(encoding="utf-8"))
    store.init_db()
    chat_store.init_db()
    store.autorizar_cuenta(CUENTA, "ICO", "Cuenta De Comparacion")
    clave = secrets.token_urlsafe(16)
    c = TestClient(app_module.app)
    c.post("/api/auth/registro", json={"carrera": "ICO", "numero_cuenta": CUENTA, "password": clave})
    token = c.post("/api/auth/login", json={"numero_cuenta": CUENTA, "password": clave}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    filas = []
    for p in preguntas:
        for m in args.modelos:
            resp = c.post("/api/chat", json={"query": p["pregunta"], "model": m}, headers=h)
            r = resp.json() if resp.status_code == 200 else {"answer": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            acierto, cita = calificar(p, r)
            t = ultimo_turno(TMP / "usuarios.db") if resp.status_code == 200 else {}
            filas.append({
                "id": p["id"], "pregunta": p["pregunta"], "modelo": m, "acierto": acierto, "cita": cita,
                "modelo_respondio": r.get("telemetry", {}).get("model"),
                "latencia_llm_ms": r.get("telemetry", {}).get("llm_latency_ms"), **t,
                "fuentes": [x["documento"] for x in r.get("citations", [])],
                "respuesta": r.get("answer", ""), "referencia": p["referencia"],
            })
            print(f"[{p['id']:>2}] {m:13s} acierto={'sí' if acierto else 'NO':2s} cita={'sí' if cita else 'NO':2s} "
                  f"total={t.get('latencia_ms') or 0:>7.0f} ms costo={t.get('costo_usd') or 0:.6f}")

    # Resumen por modelo
    resumen = {}
    for m in args.modelos:
        fm = [f for f in filas if f["modelo"] == m]
        lat = [f["latencia_llm_ms"] for f in fm if f.get("latencia_llm_ms")]
        cost = [f["costo_usd"] for f in fm if f.get("costo_usd")]
        resumen[m] = {
            "aciertos": sum(f["acierto"] for f in fm), "citas": sum(f["cita"] for f in fm), "total": len(fm),
            "latencia_llm_mediana_ms": round(statistics.median(lat)) if lat else None,
            "latencia_llm_max_ms": round(max(lat)) if lat else None,
            "tokens_salida_promedio": round(statistics.mean([f["tokens_salida"] for f in fm if f.get("tokens_salida")] or [0])),
            "costo_promedio_usd": statistics.mean(cost) if cost else None,
            "costo_total_usd": sum(cost),
            "esfuerzo": modelos.MODELOS[m].get("reasoning_effort") if modelos.MODELOS[m]["razonamiento"] else "—",
        }

    fecha = datetime.now().strftime("%Y-%m-%d_%H%M")
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"COMPARACION_MODELOS_{fecha}.json").write_text(
        json.dumps({"resumen": resumen, "resultados": filas}, ensure_ascii=False, indent=2), encoding="utf-8")

    lineas = [
        f"# Comparación de modelos — Nexus FI ({fecha.replace('_', ' ')})", "",
        f"Generado con `scripts/comparar_modelos.py` sobre {len(preguntas)} preguntas de "
        "`scripts/preguntas_comparacion.json`, por el mismo flujo de `/api/chat` que usa producción. "
        "Acierto = la respuesta contiene los hechos esperados; cita = alguna fuente es el documento esperado. "
        "Las respuestas completas están en el JSON del mismo nombre.", "",
        "| Modelo | Esfuerzo | Aciertos | Citas correctas | Latencia LLM (mediana / máx.) | Tokens de salida (prom.) | Costo por consulta | Costo total |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for m, s in resumen.items():
        prom = f"{s['costo_promedio_usd']:.6f} USD" if s["costo_promedio_usd"] else "—"
        lineas.append(
            f"| `{m}` | {s['esfuerzo']} | {s['aciertos']}/{s['total']} | {s['citas']}/{s['total']} | "
            f"{s['latencia_llm_mediana_ms']} / {s['latencia_llm_max_ms']} ms | {s['tokens_salida_promedio']} | "
            f"{prom} | {s['costo_total_usd']:.5f} USD |")
    lineas += ["", "## Detalle por pregunta", "",
               "| # | Pregunta | " + " | ".join(f"`{m}`" for m in args.modelos) + " |",
               "| :---: | :--- | " + " | ".join(":---:" for _ in args.modelos) + " |"]
    for p in preguntas:
        celdas = []
        for m in args.modelos:
            f = next(x for x in filas if x["id"] == p["id"] and x["modelo"] == m)
            celdas.append(("✅" if f["acierto"] else "❌") + (" 📄" if f["cita"] else " ∅"))
        lineas.append(f"| {p['id']} | {p['pregunta']} | " + " | ".join(celdas) + " |")
    lineas += ["", "✅/❌ acierto · 📄 cita correcta · ∅ sin la fuente esperada", "",
               "## Respuestas que fallaron", ""]
    for f in filas:
        if not f["acierto"]:
            lineas += [f"**[{f['id']}] `{f['modelo']}`** — {f['pregunta']}", "",
                       f"- Esperado: {f['referencia']}",
                       f"- Fuentes: {', '.join(f['fuentes']) or '—'}",
                       f"- Respuesta: {f['respuesta'][:600].replace(chr(10), ' ')}", ""]
    (salida / f"COMPARACION_MODELOS_{fecha}.md").write_text("\n".join(lineas), encoding="utf-8")
    print(f"\nReporte: {salida / f'COMPARACION_MODELOS_{fecha}.md'}")
    for m, s in resumen.items():
        print(f"  {m:13s} aciertos {s['aciertos']}/{s['total']}  citas {s['citas']}/{s['total']}  "
              f"latencia mediana {s['latencia_llm_mediana_ms']} ms  costo total {s['costo_total_usd']:.5f} USD")


if __name__ == "__main__":
    main()
