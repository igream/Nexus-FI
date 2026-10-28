import os
import re
from typing import Dict, Any


def clean_filename(orig_name: str) -> str:
    """Genera un nombre de archivo canónico y seguro libre de caracteres especiales."""
    base = os.path.splitext(os.path.basename(orig_name))[0]
    base = base.replace("\ufffd", "")
    clean = re.sub(r"[^\w\-\.]", "_", base)
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "documento"


class DocumentClassifier:
    """
    Clasificador híbrido unificado (basado en rutas, nombres y contenido semántico)
    para etiquetar con metadatos estructurados y rutas de destino cada documento.
    """

    def classify(self, file_path: str, sample_text: str = "") -> Dict[str, Any]:
        filename = os.path.basename(file_path)
        fn_lower = filename.lower()
        rel_path = file_path.lower().replace("\\", "/")

        categoria = "coordinacion_ico"
        subcategoria = "guia_operativa"
        carrera = "ICO"
        periodo = "2026B" if "26b" in rel_path or "2026-b" in rel_path else "VIGENTE"
        cat_dir = "06_Coordinacion_ICO"
        tags = []

        # 1. Clasificación por Ruta y Patrones de Nombre
        if "becas" in rel_path or "beca" in fn_lower:
            cat_dir = "03_Becas_y_Apoyos"
            categoria = "becas"
            subcategoria = (
                "convocatoria"
                if ("bre" in fn_lower or "convoca" in fn_lower or "convoca" in sample_text.lower())
                else "manual_reglamento"
            )
            carrera = "GENERAL_FI"
            tags.extend(["becas", "apoyo_economico", "convocatoria"])

        elif "planes de estudio" in rel_path or "pe_ico" in fn_lower or "temario" in fn_lower:
            cat_dir = "02_Planes_de_Estudio_ICO"
            categoria = "planes_estudio"
            subcategoria = "temario_asignatura"
            carrera = "ICO"
            tags.extend(["plan_estudios", "asignatura", "ico", "temario"])

        elif "tramite" in rel_path or "tramites" in fn_lower:
            cat_dir = "04_Tramites_y_Servicios"
            categoria = "tramites"
            subcategoria = "guia_tramites"
            carrera = "GENERAL_FI"
            tags.extend(["tramites", "servicios_escolares", "requisitos"])

        elif "reglamento" in rel_path or "normativa" in rel_path:
            categoria = "normativa"
            carrera = "UAEMEX"
            if "acuerdo" in fn_lower or "acuerdos" in rel_path:
                cat_dir = "01_Normativa_Universitaria/Acuerdos"
                subcategoria = "acuerdo_rectoral"
            elif "protocolo" in fn_lower or "protocolos" in rel_path:
                cat_dir = "01_Normativa_Universitaria/Protocolos"
                subcategoria = "protocolo"
            elif "codigo" in rel_path or "lineamiento" in rel_path or "decreto" in rel_path:
                cat_dir = "01_Normativa_Universitaria/Codigos_y_Lineamientos"
                subcategoria = "codigo_lineamiento"
            elif "reglamentos internos" in rel_path:
                cat_dir = "01_Normativa_Universitaria/Reglamentos_Internos"
                subcategoria = "reglamento_interno"
            else:
                cat_dir = "01_Normativa_Universitaria/Reglamentos"
                subcategoria = "reglamento_general"
            tags.extend(["normativa", "legal", "derechos", "obligaciones"])

        elif (
            "controle,convenios,biblioteca" in rel_path
            or "biblioteca" in rel_path
            or "idiomas" in rel_path
            or "control escolar" in rel_path
            or "convenios" in rel_path
        ):
            cat_dir = "05_Instalaciones_y_Servicios"
            categoria = "instalaciones_servicios"
            subcategoria = "modulo_informativo"
            carrera = "GENERAL_FI"
            tags.extend(["instalaciones", "servicios", "laboratorio_idiomas", "control_escolar"])

        elif "coordinacion" in fn_lower or "plantilla_coordinacion" in fn_lower:
            cat_dir = "06_Coordinacion_ICO"
            categoria = "coordinacion_ico"
            subcategoria = "guia_operativa"
            carrera = "ICO"
            tags.extend(["aulas", "laboratorios", "profesores", "cubiculos", "cambio_grupo", "altas"])

        # 2. Refinamiento por Contenido Semántico
        sample_lower = sample_text[:1000].lower()
        if "ingeniería en computación" in sample_lower or "ingenieria en computacion" in sample_lower:
            if categoria not in ("normativa", "becas", "tramites"):
                carrera = "ICO"

        if "otoño 2026" in sample_lower or "2026-b" in sample_lower:
            periodo = "2026B"
        elif "primavera 2026" in sample_lower or "2026-a" in sample_lower or "26a" in fn_lower:
            periodo = "2026A"

        clean_name = clean_filename(filename)
        clean_id = f"{carrera.lower()}_{clean_name}".lower()[:60]

        return {
            "id": clean_id,
            "clean_id": clean_id,
            "clean_name": clean_name,
            "cat_dir": cat_dir,
            "titulo": os.path.splitext(filename)[0],
            "documento_original": filename,
            "categoria": categoria,
            "subcategoria": subcategoria,
            "carrera": carrera,
            "periodo": periodo,
            "tags": sorted(list(set(tags))),
        }
