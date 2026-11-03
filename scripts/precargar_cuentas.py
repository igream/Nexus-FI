"""
Precarga el padrón de cuentas autorizadas para la prueba piloto (SC-001).

Uso:
    python scripts/precargar_cuentas.py --csv C:\\ruta\\fuera\\del\\repo\\padron.csv
    python scripts/precargar_cuentas.py --ficticias
    python scripts/precargar_cuentas.py --reiniciar-registro 1234567

El CSV lleva encabezado numero_cuenta,nombre,carrera,rol (nombre y rol son opcionales).
La carrera puede ser la clave (ICO) o el nombre completo
(Licenciatura en Ingeniería en Computación). El rol es admin (integrantes del
equipo) o alumno (por defecto).

--ficticias carga las cuentas de prueba 1000001 a 1000009 con rol alumno
(no son datos reales; se guardan igual, cifradas).

El reinicio de registro también lo pueden hacer los administradores desde el
menú del chat («Reiniciar registro de una cuenta»).

Datos privados: el CSV nunca se guarda dentro del proyecto ni se sube a GitHub.
En la base solo quedan cifrados; este script nunca imprime números ni nombres.
"""
import argparse
import csv
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
load_dotenv(RAIZ / ".env")

from core.auth import store  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", help="CSV con numero_cuenta,nombre,carrera")
    p.add_argument("--reiniciar-registro", metavar="NUMERO",
                   help="Borra la contraseña de esa cuenta para que su dueño vuelva a registrarse")
    p.add_argument("--ficticias", action="store_true",
                   help="Carga las cuentas de prueba 1000001 a 1000009 (rol alumno)")
    args = p.parse_args()

    store.init_db()

    if args.reiniciar_registro:
        ok = store.eliminar_registro(args.reiniciar_registro)
        print("Registro reiniciado." if ok else "Esa cuenta no tenía registro.")
        return 0

    if args.ficticias:
        print(f"Cuentas ficticias nuevas: {store.precargar_ficticias()} de {len(store.CUENTAS_FICTICIAS)}")
        if not args.csv:
            print(f"Total en el padrón: {store.conteo()['autorizadas']}")
            return 0

    if not args.csv:
        p.error("indica --csv, --ficticias o --reiniciar-registro")

    ruta = Path(args.csv).resolve()
    if RAIZ in ruta.parents and "Local" not in ruta.relative_to(RAIZ).parts:
        print("Aviso: el CSV está dentro del proyecto. Muévelo fuera (o a Local/) para que no se suba a GitHub.")

    nuevas = existentes = invalidas = 0
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            numero = (fila.get("numero_cuenta") or "").strip()
            if not (numero.isdigit() and len(numero) == 7):
                invalidas += 1
                continue
            try:
                rol = (fila.get("rol") or "").strip().lower() or None
                if store.autorizar_cuenta(numero, fila.get("carrera") or "", fila.get("nombre") or "", rol):
                    nuevas += 1
                else:
                    existentes += 1
            except ValueError:
                invalidas += 1

    print(f"Cuentas nuevas: {nuevas} · ya existían: {existentes} · filas inválidas: {invalidas}")
    print(f"Total en el padrón: {store.conteo()['autorizadas']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
