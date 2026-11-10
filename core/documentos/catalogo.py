"""
Catálogo de documentos del acervo para hacer consultables las citas del chat.

Cada cita del chat trae el nombre del archivo original (campo `documento` de LanceDB, p. ej.
"REGLAMENTO DEL SERVICIO SOCIAL.pdf"). El frontmatter de cada Markdown de Procesados/ dice de
dónde salió (`archivo_fuente`), así que el catálogo se arma al arrancar sin tocar la base
vectorial ni volver a calcular embeddings.

Cómo se muestra cada documento:
  - PDF: el original, abierto en la página citada. Los originales viven fuera de Git y de la
    imagen de Docker: en el servidor, en data/acervo_original/ (volumen montado; ver
    scripts/preparar_acervo_original.py); en desarrollo, en "Pre Procesados/".
  - Fuentes piloto (.md) y páginas guardadas (.html): su texto procesado. Los .html originales
    nunca se sirven tal cual porque ejecutarían scripts ajenos en el dominio de Nexus FI.
  - Si un PDF no está en el servidor, se cae al texto procesado en lugar de fallar.

Ninguna ruta viene del usuario: solo se aceptan ids del catálogo.
"""
import os
import re
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parent.parent.parent
PROCESADOS = RAIZ / "Procesados"
FUENTES_PILOTO = RAIZ / "fuentes_piloto"
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
_CAMPO = re.compile(r'^(\w+):\s*"?(.*?)"?\s*$', re.M)


def dirs_originales() -> list[Path]:
    """Carpetas donde buscar los PDF originales, en orden de preferencia."""
    propia = os.getenv("ACERVO_ORIGINALES_DIR")
    candidatas = [Path(propia)] if propia else []
    candidatas += [RAIZ / "data" / "acervo_original", RAIZ / "Pre Procesados"]
    return [c if c.is_absolute() else RAIZ / c for c in candidatas]


def _leer_frontmatter(md: Path) -> dict:
    texto = md.read_text(encoding="utf-8", errors="replace")
    m = _FRONTMATTER.match(texto)
    if not m:
        return {}
    return {k: v for k, v in _CAMPO.findall(m.group(1))}


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")[:120]


class Catalogo:
    def __init__(self, procesados: Path = PROCESADOS):
        self.por_id: dict[str, dict] = {}
        self.por_nombre: dict[str, str] = {}
        if not procesados.exists():
            return
        for md in sorted(procesados.rglob("*.md")):
            fm = _leer_frontmatter(md)
            fuente = fm.get("archivo_fuente")
            if not fuente:
                continue
            nombre = Path(fuente).name
            if nombre in self.por_nombre:      # el mismo original procesado dos veces
                continue
            doc_id = _slug(fm.get("id") or md.stem)
            while doc_id in self.por_id:
                doc_id += "_"
            self.por_id[doc_id] = {
                "id": doc_id,
                "documento": nombre,
                "titulo": fm.get("titulo") or Path(nombre).stem,
                "categoria": fm.get("categoria", ""),
                "fuente": fuente,                     # relativa a la carpeta de originales
                "extension": Path(nombre).suffix.lower(),
                "procesado": md,
            }
            self.por_nombre[nombre] = doc_id

    def id_de(self, documento: Optional[str]) -> Optional[str]:
        return self.por_nombre.get(documento or "")

    def obtener(self, doc_id: str) -> Optional[dict]:
        return self.por_id.get(doc_id)

    def ruta_pdf(self, doc: dict) -> Optional[Path]:
        """Ruta del PDF original si este servidor lo tiene; None si se debe mostrar el texto."""
        if doc["extension"] != ".pdf":
            return None
        for base in dirs_originales():
            ruta = (base / doc["fuente"]).resolve()
            # Defensa extra: la ruta debe quedar dentro de la carpeta de originales
            if base.resolve() in ruta.parents and ruta.is_file():
                return ruta
        return None

    def texto(self, doc: dict) -> str:
        """Texto para el visor: la fuente piloto original (.md) o el Markdown procesado."""
        if doc["fuente"].startswith("fuentes_piloto/"):
            original = FUENTES_PILOTO / Path(doc["fuente"]).name
            if original.is_file():
                return original.read_text(encoding="utf-8", errors="replace")
        texto = doc["procesado"].read_text(encoding="utf-8", errors="replace")
        return _FRONTMATTER.sub("", texto, count=1)


_catalogo: Optional[Catalogo] = None


def catalogo() -> Catalogo:
    global _catalogo
    if _catalogo is None:
        _catalogo = Catalogo()
    return _catalogo
