import os
from typing import List, Dict, Any
import lxml.html
from .text_normalizer import normalize_text


class HTMLExtractor:
    def __init__(self, max_file_size_mb: int = 20):
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    @staticmethod
    def _format_table(table_elem) -> str:
        """Convierte una tabla HTML en texto estructurado delimitado por barras verticales."""
        rows_out = []
        for tr in table_elem.xpath(".//tr"):
            cells = [
                " ".join(cell.text_content().split())
                for cell in tr.xpath("./th | ./td")
            ]
            cells = [c for c in cells if c]
            if cells:
                rows_out.append(" | ".join(cells))
        return "\n".join(rows_out)

    def extract(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extrae el contenido principal de un archivo HTML eliminando boilerplate
        y preservando encabezados cortos y tablas sin duplicar nodos anidados.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo HTML no encontrado: {file_path}")

        if os.path.getsize(file_path) > self.max_file_size_bytes:
            raise ValueError(f"Archivo HTML excede el tamaño máximo permitido: {file_path}")

        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        if not raw_bytes.strip():
            return []

        html_text = raw_bytes.decode("utf-8", errors="replace")
        root = lxml.html.fromstring(html_text)

        # Remover elementos de navegación, scripts, estilos y pies de página
        for bad_tag in root.xpath("//script | //style | //nav | //footer | //header | //noscript | //aside"):
            bad_tag.drop_tree()

        blocks: List[str] = []
        # Seleccionar elementos de bloque evitando duplicar nodos hijos dentro de tablas o listas
        xpath_expr = (
            "//h1[not(ancestor::table)] | "
            "//h2[not(ancestor::table)] | "
            "//h3[not(ancestor::table)] | "
            "//h4[not(ancestor::table)] | "
            "//p[not(ancestor::table) and not(ancestor::li)] | "
            "//li[not(ancestor::table)] | "
            "//table[not(ancestor::table)]"
        )

        for elem in root.xpath(xpath_expr):
            tag = elem.tag.lower() if isinstance(elem.tag, str) else ""
            if tag == "table":
                table_str = self._format_table(elem)
                if table_str:
                    blocks.append(table_str)
            elif tag in ("h1", "h2", "h3", "h4"):
                t = " ".join(elem.text_content().split())
                if t:
                    blocks.append(f"## {t}")
            else:
                t = " ".join(elem.text_content().split())
                if t and len(t) > 15:
                    blocks.append(t)

        joined_content = "\n\n".join(blocks)
        normalized = normalize_text(joined_content)
        if not normalized:
            return []

        return [{
            "page_number": 1,
            "text": normalized,
            "is_ocr": False,
        }]
