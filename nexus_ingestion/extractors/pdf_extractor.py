import os
from typing import List, Dict, Any
import pymupdf
from .text_normalizer import normalize_text
from .ocr_engine import BaseOCREngine


class PDFExtractor:
    def __init__(
        self,
        ocr_engine: BaseOCREngine,
        max_file_size_mb: int = 50,
        max_pdf_pages: int = 500,
    ):
        self.ocr_engine = ocr_engine
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_pdf_pages = max_pdf_pages

    def extract(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extrae texto estructurado página por página con protecciones contra DoS/OOM.
        Aplica OCR de forma transparente si la página carece de texto digital suficiente.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo PDF no encontrado: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size_bytes:
            raise ValueError(
                f"El archivo '{os.path.basename(file_path)}' ({file_size / (1024 * 1024):.1f} MB) "
                f"excede el límite de seguridad de {self.max_file_size_bytes // (1024 * 1024)} MB."
            )

        pages_content: List[Dict[str, Any]] = []

        with pymupdf.open(file_path) as doc:
            total_pages = min(len(doc), self.max_pdf_pages)

            for page_idx in range(total_pages):
                page = doc[page_idx]
                raw_text = page.get_text("text") or ""
                raw_text_clean = raw_text.strip()

                is_ocr = False
                # Si la página tiene menos de 50 caracteres y contiene imágenes, aplicar OCR
                if len(raw_text_clean) < 50:
                    # Ajustar DPI dinámicamente para evitar bombas de memoria en planos/páginas gigantes
                    max_dim = max(page.rect.width, page.rect.height, 1.0)
                    dpi = 150 if (max_dim * 150 / 72.0) <= 2500 else int(2500 * 72.0 / max_dim)
                    dpi = max(72, dpi)

                    pix = page.get_pixmap(dpi=dpi)
                    img_bytes = pix.tobytes("png")
                    ocr_text = self.ocr_engine.extract_text_from_bytes(img_bytes)
                    if ocr_text.strip():
                        text_to_save = ocr_text
                        is_ocr = True
                    else:
                        text_to_save = raw_text_clean
                else:
                    text_to_save = raw_text_clean

                normalized = normalize_text(text_to_save)
                if normalized:
                    pages_content.append({
                        "page_number": page_idx + 1,
                        "text": normalized,
                        "is_ocr": is_ocr,
                    })

        return pages_content
