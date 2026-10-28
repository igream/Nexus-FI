import re
import unicodedata

# Diccionario de palabras corruptas por falta de tabla ToUnicode/CMap en PDFs de la UAEMéx
SPANISH_REPAIR_MAP = {
    "REINSCRIPCIN": "REINSCRIPCIÓN",
    "Reinscripcin": "Reinscripción",
    "reinscripcin": "reinscripción",
    "INSCRIPCIN": "INSCRIPCIÓN",
    "Inscripcin": "Inscripción",
    "inscripcin": "inscripción",
    "EDUCACIN": "EDUCACIÓN",
    "Educacin": "Educación",
    "educacin": "educación",
    "OTOO": "OTOÑO",
    "Otoo": "Otoño",
    "otoo": "otoño",
    "AUTNOMA": "AUTÓNOMA",
    "Autnoma": "Autónoma",
    "autnoma": "autónoma",
    "MXICO": "MÉXICO",
    "Mxico": "México",
    "mxico": "méxico",
    "ACADMICOS": "ACADÉMICOS",
    "Acadmicos": "Académicos",
    "acadmicos": "académicos",
    "ACADMICO": "ACADÉMICO",
    "Acadmico": "Académico",
    "acadmico": "académico",
    "INVESTIGACIN": "INVESTIGACIÓN",
    "Investigacin": "Investigación",
    "investigacin": "investigación",
    "FUNCIN": "FUNCIÓN",
    "Funcin": "Función",
    "funcin": "función",
    "CMPUTO": "CÓMPUTO",
    "Cmputo": "Cómputo",
    "cmputo": "cómputo",
    "SMBOLOS": "SÍMBOLOS",
    "Smbolos": "Símbolos",
    "smbolos": "símbolos",
    "PLANEACIN": "PLANEACIÓN",
    "Planeacin": "Planeación",
    "planeacin": "planeación",
    "PROTECCIN": "PROTECCIÓN",
    "Proteccin": "Protección",
    "proteccin": "protección",
    "PRCTICAS": "PRÁCTICAS",
    "Prcticas": "Prácticas",
    "prcticas": "prácticas",
    "INFORMACIN": "INFORMACIÓN",
    "Informacin": "Información",
    "informacin": "información",
    "INGENIERA": "INGENIERÍA",
    "Ingeniera": "Ingeniería",
    "ingeniera": "ingeniería",
    "TRMITES": "TRÁMITES",
    "Trmites": "Trámites",
    "trmites": "trámites",
    "ARTCULO": "ARTÍCULO",
    "Artculo": "Artículo",
    "artculo": "artículo",
    "CAPTULO": "CAPÍTULO",
    "Captulo": "Capítulo",
    "captulo": "capítulo",
    "TTULO": "TÍTULO",
    "Ttulo": "Título",
    "ttulo": "título",
    "DISPOSICIN": "DISPOSICIÓN",
    "Disposicin": "Disposición",
    "disposicin": "disposición",
    "EVALUACIN": "EVALUACIÓN",
    "Evaluacin": "Evaluación",
    "evaluacin": "evaluación",
    "TITULACIN": "TITULACIÓN",
    "Titulacin": "Titulación",
    "titulacin": "titulación",
    "DIRECCIN": "DIRECCIÓN",
    "Direccin": "Dirección",
    "direccin": "dirección",
    "ORGANIZACIN": "ORGANIZACIÓN",
    "Organizacin": "Organización",
    "organizacin": "organización",
    "MISIN": "MISIÓN",
    "Misin": "Misión",
    "misin": "misión",
    "VISIN": "VISIÓN",
    "Visin": "Visión",
    "visin": "visión",
    "PROMOCIN": "PROMOCIÓN",
    "Promocin": "Promoción",
    "promocin": "promoción",
    "RECTORA": "RECTORÍA",
    "Rectora": "Rectoría",
    "rectora": "rectoría",
    "VINCULACIN": "VINCULACIÓN",
    "Vinculacin": "Vinculación",
    "vinculacin": "vinculación",
    "VERSIN": "VERSIÓN",
    "Versin": "Versión",
    "versin": "versión",
    "GRAFICACIN": "GRAFICACIÓN",
    "Graficacin": "Graficación",
    "graficacin": "graficación",
    "Gralfcacin": "Graficación",
    "PROGRAMACIN": "PROGRAMACIÓN",
    "Programacin": "Programación",
    "programacin": "programación",
    "REESTRUCTURACIN": "REESTRUCTURACIÓN",
    "Reestructuracin": "Reestructuración",
    "reestructuracin": "reestructuración",
    "ADMINISTRACIN": "ADMINISTRACIÓN",
    "Administracin": "Administración",
    "administracin": "administración",
    "Adnistracin": "Administración",
    "Admiristracin": "Administración",
    "COMUNICACIN": "COMUNICACIÓN",
    "Comunicacin": "Comunicación",
    "comunicacin": "comunicación",
    "coninicacin": "comunicación",
    "SERIACIN": "SERIACIÓN",
    "Seriacin": "Seriación",
    "seriacin": "seriación",
    "lineasdeseriacin": "líneas de seriación",
    "18ineasdeseriacin": "líneas de seriación",
    "18Ineasdeseriacin": "líneas de seriación",
    "18ineasdaserzcin": "líneas de seriación",
    "propsito": "propósito",
    "adquisin": "adquisición",
}

# Pre-compilación de expresión regular con límites de palabra (\b) para evitar
# falsos positivos dentro de otras palabras y optimizar el rendimiento a una sola pasada
_REPAIR_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(SPANISH_REPAIR_MAP.keys(), key=len, reverse=True)) + r")\b"
)

# Patrones para corregir artefactos de reemplazo de subcadenas previas ('así' / 'está' incrustados)
_SUBSTRING_AS_MID = re.compile(r"([a-zA-ZáéíóúÁÉÍÓÚñÑ])así([a-zA-ZáéíóúÁÉÍÓÚñÑ])")
_SUBSTRING_EST_MID = re.compile(r"([a-zA-ZáéíóúÁÉÍÓÚñÑ])está([a-zA-ZáéíóúÁÉÍÓÚñÑ])")
_SUBSTRING_AS_END = re.compile(r"([a-zA-ZáéíóúÁÉÍÓÚñÑ])así\b")

# Sanitización contra falsificación de cabeceras RAG ([DOCUMENTO: ...]) e inyección de caracteres de control
_FAKE_HEADER_PATTERN = re.compile(r"\[\s*(DOCUMENTO|CATEGOR[ÍI]A|P[ÁA]G)\s*:", re.IGNORECASE)
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def fix_corrupted_substrings(text: str) -> str:
    """Repara palabras con subcadenas 'así' o 'está' incrustadas accidentalmente."""
    text = _SUBSTRING_AS_MID.sub(r"\1as\2", text)
    text = _SUBSTRING_EST_MID.sub(r"\1est\2", text)
    text = _SUBSTRING_AS_END.sub(r"\1as", text)
    return text


def normalize_text(text: str) -> str:
    """
    Limpia caracteres corruptos, normaliza Unicode (NFKC), repara diacríticos
    con límites de palabra y sanitiza contra falsificación de cabeceras RAG.
    """
    if not text:
        return ""

    # 1. Eliminar caracteres de control invisibles y reemplazos Unicode (\ufffd)
    text = text.replace("\ufffd", "")
    text = _CONTROL_CHARS_PATTERN.sub("", text)

    # 2. Normalización canónica de compatibilidad Unicode (resuelve ligaduras ﬁ, ﬂ, espacios \xa0, etc.)
    text = unicodedata.normalize("NFKC", text)

    # 3. Reparar subcadenas corruptas ('pasíillo' -> 'pasillo', 'ingestáa' -> 'ingesta')
    text = fix_corrupted_substrings(text)

    # 4. Reemplazo en una sola pasada con límites de palabra (\b)
    text = _REPAIR_PATTERN.sub(lambda m: SPANISH_REPAIR_MAP[m.group(0)], text)

    # 5. Neutralizar posibles cabeceras falsificadas dentro del documento (mitigación Prompt Injection)
    text = _FAKE_HEADER_PATTERN.sub(r"(\1:", text)

    # 6. Normalizar saltos de línea Windows/Mac y guiones de separación silábica
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
