"""
Copia los PDF originales del acervo a data/acervo_original/ para que el servidor los muestre
desde las citas del chat (ver core/documentos/catalogo.py).

Solo copia los PDF que el catálogo puede citar, con la misma estructura de carpetas que
"Pre Procesados/". data/ está fuera de Git y de la imagen de Docker, y docker compose la monta
como volumen, así que en la EC2 basta con subir esa carpeta:

    python scripts/preparar_acervo_original.py
    scp -r data/acervo_original <usuario>@<servidor>:~/Nexus-FI/data/

Sin argumentos no borra nada; con --limpiar quita de data/acervo_original los archivos que ya
no están en el catálogo.
"""
import argparse
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.documentos.catalogo import Catalogo  # noqa: E402

ORIGEN = RAIZ / "Pre Procesados"
DESTINO = RAIZ / "data" / "acervo_original"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limpiar", action="store_true", help="quitar del destino los archivos fuera del catálogo")
    args = ap.parse_args()

    cat = Catalogo()
    pdfs = [d for d in cat.por_id.values() if d["extension"] == ".pdf"]
    copiados = existentes = 0
    faltan, total = [], 0
    esperados = set()
    for d in pdfs:
        origen, destino = ORIGEN / d["fuente"], DESTINO / d["fuente"]
        esperados.add(destino.resolve())
        if not origen.is_file():
            faltan.append(d["fuente"])
            continue
        total += origen.stat().st_size
        if destino.is_file() and destino.stat().st_size == origen.stat().st_size:
            existentes += 1
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
        copiados += 1

    borrados = 0
    if args.limpiar and DESTINO.exists():
        for f in DESTINO.rglob("*"):
            if f.is_file() and f.resolve() not in esperados:
                f.unlink()
                borrados += 1

    print(f"PDF citables: {len(pdfs)} | copiados: {copiados} | ya estaban: {existentes} | "
          f"faltan en '{ORIGEN.name}': {len(faltan)} | borrados: {borrados}")
    print(f"Tamaño total: {total / 1_048_576:.1f} MB en {DESTINO}")
    for f in faltan:
        print("  falta:", f)


if __name__ == "__main__":
    main()
