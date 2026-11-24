"""
Prueba de carga de Nexus FI con sesiones simultáneas reales (RNF01).

Cada sesión virtual usa su propia cuenta: se registra (si hace falta), inicia sesión, comprueba
que el servidor la reconoce como esa cuenta y envía sus consultas al mismo tiempo que las demás.
Así se mide el servidor y no el navegador: en el ensayo del 23/11/2026, 30 pestañas de un mismo
navegador compartían una sola sesión y todo se registró en una cuenta.

Uso (contra producción, con cuentas de carga que NO son las de la UAT):
    python scripts/prueba_carga.py --url https://d2j5rd06t9r4yq.cloudfront.net --desde 2990001 --rondas 10 20 30

Las cuentas deben estar autorizadas antes en la base del servidor (rol alumno). Las contraseñas
se generan al azar en memoria y no se guardan. Costo aproximado en modo Rápido: 0.0005 USD por consulta.
El reporte (Markdown y JSON) se guarda en --salida.
"""
import argparse
import asyncio
import json
import secrets
import statistics
import time
from datetime import datetime
from pathlib import Path

import httpx

PREGUNTAS = [
    "¿Cuántas horas de servicio social tengo que hacer?",
    "¿Qué opciones de titulación hay?",
    "¿Cuál es el correo de control escolar de la facultad?",
    "¿Qué promedio piden para la beca de reinscripción?",
    "¿Qué materias llevo en tercer semestre de ICO?",
    "¿Cuántos libros puedo pedir prestados en la biblioteca?",
    "¿Qué necesito para irme de intercambio a otra universidad?",
    "¿Hay grupos estudiantiles para los de computación?",
    "¿Qué temas se ven en Inteligencia Artificial?",
    "¿Qué hago en caso de sismo dentro del campus?",
]


def percentil(valores, p):
    if not valores:
        return None
    v = sorted(valores)
    k = (len(v) - 1) * p / 100
    i = int(k)
    return v[i] if i + 1 >= len(v) else v[i] + (v[i + 1] - v[i]) * (k - i)


class Sesion:
    def __init__(self, cliente, url, cuenta):
        self.c, self.url, self.cuenta = cliente, url, cuenta
        self.password = secrets.token_urlsafe(16)
        self.token = None
        self.nombre = None

    async def iniciar(self, registrar):
        if registrar:
            r = await self.c.post(f"{self.url}/api/auth/registro",
                                  json={"carrera": "ICO", "numero_cuenta": self.cuenta, "password": self.password})
            if r.status_code not in (201, 409):
                raise RuntimeError(f"registro {self.cuenta}: HTTP {r.status_code} {r.text[:120]}")
            if r.status_code == 409:
                raise RuntimeError(f"registro {self.cuenta}: ya estaba registrada (reinicia su registro antes)")
        r = await self.c.post(f"{self.url}/api/auth/login",
                              json={"numero_cuenta": self.cuenta, "password": self.password})
        if r.status_code != 200:
            raise RuntimeError(f"login {self.cuenta}: HTTP {r.status_code}")
        self.token = r.json()["token"]
        info = (await self.c.get(f"{self.url}/api/session/info", headers=self.h)).json()
        self.nombre = (info.get("usuario") or {}).get("nombre")
        return info.get("authenticated") is True

    @property
    def h(self):
        return {"Authorization": f"Bearer {self.token}"}

    async def consultar(self, pregunta, modelo):
        t0 = time.perf_counter()
        try:
            r = await self.c.post(f"{self.url}/api/chat", headers=self.h,
                                  json={"query": pregunta, "top_k": 4, "use_llm": True, "model": modelo})
            ms = (time.perf_counter() - t0) * 1000
            cuerpo = r.json() if "json" in r.headers.get("content-type", "") else {}
            return {"cuenta": self.cuenta, "pregunta": pregunta, "status": r.status_code, "ms": round(ms),
                    "found": cuerpo.get("found"), "respuesta": (cuerpo.get("answer") or "")[:160],
                    "reposo": "reposo" in r.text[:2000].lower() if r.status_code >= 500 else False}
        except Exception as e:
            return {"cuenta": self.cuenta, "pregunta": pregunta, "status": None,
                    "ms": round((time.perf_counter() - t0) * 1000), "error": f"{type(e).__name__}: {e}"}


async def ronda(sesiones, n, por_sesion, modelo, desfase):
    tareas = []
    for i, s in enumerate(sesiones[:n]):
        for j in range(por_sesion):
            tareas.append(s.consultar(PREGUNTAS[(i + j + desfase) % len(PREGUNTAS)], modelo))
    t0 = time.perf_counter()
    res = await asyncio.gather(*tareas)
    return res, round((time.perf_counter() - t0) * 1000)


def resumen(res, total_ms):
    ok = [r for r in res if r["status"] == 200]
    lat = [r["ms"] for r in ok]
    codigos = {}
    for r in res:
        codigos[str(r["status"])] = codigos.get(str(r["status"]), 0) + 1
    return {"consultas": len(res), "ok": len(ok), "codigos": codigos,
            "con_fuente": sum(1 for r in ok if r.get("found")),
            "p50_ms": round(percentil(lat, 50)) if lat else None,
            "p95_ms": round(percentil(lat, 95)) if lat else None,
            "max_ms": max(lat) if lat else None, "ronda_ms": total_ms,
            "errores": [r for r in res if r["status"] != 200][:10]}


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True)
    ap.add_argument("--desde", type=int, default=2990001, help="primera cuenta de carga")
    ap.add_argument("--rondas", type=int, nargs="+", default=[10, 20, 30], help="sesiones simultáneas por ronda")
    ap.add_argument("--por-sesion", type=int, nargs="+", default=None,
                    help="consultas simultáneas por sesión en cada ronda (por defecto 1, y 2 en la última)")
    ap.add_argument("--modelo", default="gpt-4o-mini")
    ap.add_argument("--sin-registro", action="store_true", help="las cuentas ya tienen contraseña conocida (no aplica)")
    ap.add_argument("--salida", default=".")
    a = ap.parse_args()
    por_sesion = a.por_sesion or [1] * (len(a.rondas) - 1) + [2]
    n_max = max(a.rondas)
    cuentas = [str(a.desde + i) for i in range(n_max)]

    limites = httpx.Limits(max_connections=200, max_keepalive_connections=100)
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), limits=limites) as c:
        sesiones = [Sesion(c, a.url.rstrip("/"), n) for n in cuentas]
        t0 = time.perf_counter()
        ok_sesion = await asyncio.gather(*[s.iniciar(not a.sin_registro) for s in sesiones])
        print(f"Sesiones iniciadas: {sum(ok_sesion)}/{len(sesiones)} en {time.perf_counter() - t0:.1f} s; "
              f"nombres distintos: {len({s.nombre for s in sesiones})}")
        resultados = []
        for k, (n, ps) in enumerate(zip(a.rondas, por_sesion)):
            res, ms = await ronda(sesiones, n, ps, a.modelo, k)
            rs = resumen(res, ms)
            resultados.append({"sesiones": n, "por_sesion": ps, **rs, "detalle": res})
            print(f"Ronda {k + 1}: {n} sesiones x {ps} = {rs['consultas']} consultas simultáneas | "
                  f"OK {rs['ok']} | códigos {rs['codigos']} | p50 {rs['p50_ms']} ms | p95 {rs['p95_ms']} ms | "
                  f"máx {rs['max_ms']} ms | ronda {ms} ms")
            await asyncio.sleep(5)

    esperado = {}
    for r in resultados:
        for d in r["detalle"]:
            if d["status"] == 200:
                esperado[d["cuenta"]] = esperado.get(d["cuenta"], 0) + 1
    sello = datetime.now().strftime("%Y-%m-%d_%H%M")
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    datos = {"url": a.url, "modelo": a.modelo, "fecha": sello, "sesiones_iniciadas": sum(ok_sesion),
             "nombres_distintos": len({s.nombre for s in sesiones}), "rondas": resultados,
             "consultas_ok_por_cuenta": esperado}
    (out / f"PRUEBA_CARGA_{sello}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf8")
    lineas = [f"# Prueba de carga {sello}", "", f"- URL: {a.url}", f"- Modelo: {a.modelo}",
              f"- Sesiones iniciadas: {sum(ok_sesion)} de {len(sesiones)}, cada una con su propia cuenta", "",
              "| Sesiones | Consultas simultáneas | OK | Códigos | p50 (ms) | p95 (ms) | Máx (ms) |",
              "| ---: | ---: | ---: | :--- | ---: | ---: | ---: |"]
    for r in resultados:
        lineas.append(f"| {r['sesiones']} | {r['consultas']} | {r['ok']} | {r['codigos']} | {r['p50_ms']} | "
                      f"{r['p95_ms']} | {r['max_ms']} |")
    (out / f"PRUEBA_CARGA_{sello}.md").write_text("\n".join(lineas) + "\n", encoding="utf8")
    print(f"Reporte: {out / f'PRUEBA_CARGA_{sello}.md'}")
    print("Consultas OK por cuenta:", json.dumps(esperado))


if __name__ == "__main__":
    asyncio.run(main())
