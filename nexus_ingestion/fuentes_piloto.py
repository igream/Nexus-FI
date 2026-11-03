"""
Fragmentación de las fuentes de la prueba piloto ICO (fuentes_piloto/*.md, SC-001).

El fragmentador general agrupa el texto en bloques de ~650 tokens. Para estas fuentes eso
mezcla filas de horario de varias materias (sin su título) o varios avisos en un mismo
bloque, y la búsqueda semántica no distingue unos de otros. Aquí cada fragmento es una
unidad con sentido propio:

- Horarios: un fragmento por materia, uno por día de la semana y uno con la lista de
  materias del semestre, redactados en texto que se entiende sin la tabla.
- Avisos, capítulos y demás: un fragmento por sección «## ».
"""
import hashlib
import re
from typing import Any, Dict, List

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
NOMBRE_CARRERA = "Licenciatura en Ingeniería en Computación (ICO)"


def _celdas(linea: str) -> List[str]:
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def _es_separador(linea: str) -> bool:
    return bool(re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?", linea.strip()))


def _lugar(aula: str) -> str:
    a = (aula or "").strip()
    if not a or a.lower().startswith("sin aula"):
        return "sin aula indicada"
    if "mediaci" in a.lower():
        return "por mediación tecnológica (en línea)"
    return f"en {a}"


def _horario(h: str) -> str:
    partes = [p.strip() for p in re.split(r"\s*-\s*", h or "") if p.strip()]
    return f"de {partes[0]} a {partes[1]}" if len(partes) == 2 else (h or "sin horario indicado")


def _clave_hora(h: str) -> str:
    m = re.match(r"\s*(\d{1,2}):(\d{2})", h or "")
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else "99:99"


def _leer_tabla_horarios(texto: str) -> List[Dict[str, str]]:
    """Filas de la tabla con columnas Materia | Grupo | Profesor | Día | Horario | Aula."""
    filas, columnas = [], None
    for linea in texto.splitlines():
        if not linea.strip().startswith("|") or _es_separador(linea):
            continue
        celdas = _celdas(linea)
        if columnas is None:
            columnas = [c.lower() for c in celdas]
            continue
        fila = dict(zip(columnas, celdas))
        if fila.get("materia"):
            filas.append({
                "materia": fila.get("materia", ""),
                "grupo": fila.get("grupo", ""),
                "profesor": fila.get("profesor", "") or fila.get("docente", ""),
                "dia": fila.get("día", "") or fila.get("dia", ""),
                "horario": fila.get("horario", ""),
                "aula": fila.get("aula", "") or fila.get("aula o modalidad", ""),
            })
    return filas


def _secciones_horario(doc_name: str, texto: str, periodo: str) -> List[Dict[str, str]]:
    m = re.search(r"semestre[_\s-]*(\d+)", doc_name, re.IGNORECASE)
    semestre = m.group(1) if m else "?"
    contexto = f"Horario del periodo {periodo} de la {NOMBRE_CARRERA}, semestre {semestre}."
    filas = _leer_tabla_horarios(texto)
    if not filas:
        return []

    materias: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    for f in filas:
        materias.setdefault(f["materia"], {}).setdefault(f["grupo"], []).append(f)

    secciones = []
    # 1. Lista de materias del semestre
    lista = [f"- {mat}: grupos {', '.join(grupos)}" for mat, grupos in materias.items()]
    secciones.append({
        "titulo": f"Semestre {semestre} · materias",
        "texto": f"{contexto}\nMaterias que se imparten en el semestre {semestre} y sus grupos:\n" + "\n".join(lista),
    })

    # 2. Una sección por materia
    for mat, grupos in materias.items():
        lineas = [contexto, f"Materia: {mat} (semestre {semestre} de ICO).", "Grupos, profesores, días, horarios y aulas:"]
        for grupo, sesiones in grupos.items():
            lineas.append(f"- Grupo {grupo}, profesor(a) {sesiones[0]['profesor']}:")
            for s in sorted(sesiones, key=lambda x: (DIAS.index(x["dia"]) if x["dia"] in DIAS else 9, _clave_hora(x["horario"]))):
                lineas.append(f"  - {s['dia']} {_horario(s['horario'])}, {_lugar(s['aula'])}")
        secciones.append({"titulo": f"Semestre {semestre} · {mat}", "texto": "\n".join(lineas)})

    # 3. Una sección por día de la semana
    for dia in DIAS:
        del_dia = sorted([f for f in filas if f["dia"] == dia], key=lambda x: (_clave_hora(x["horario"]), x["materia"]))
        if not del_dia:
            continue
        lineas = [contexto, f"Clases del semestre {semestre} de ICO los días {dia.lower()}:"]
        for f in del_dia:
            lineas.append(f"- {_horario(f['horario']).capitalize()}: {f['materia']}, grupo {f['grupo']}, "
                          f"profesor(a) {f['profesor']}, {_lugar(f['aula'])}")
        secciones.append({"titulo": f"Semestre {semestre} · {dia}", "texto": "\n".join(lineas)})
    return secciones


def _secciones_markdown(texto: str) -> List[Dict[str, str]]:
    """Divide por «## »; cada sección lleva el título del documento como contexto."""
    titulo_doc = ""
    m = re.search(r"^#\s+(.+)$", texto, re.MULTILINE)
    if m:
        titulo_doc = m.group(1).strip()
    partes = re.split(r"(?m)^##\s+", texto)
    secciones = []
    for parte in partes[1:]:
        titulo, _, cuerpo = parte.partition("\n")
        cuerpo = re.sub(r"\n-{3,}\s*$", "", cuerpo.strip()).strip()   # quita el separador «---» final
        if not cuerpo:
            continue
        secciones.append({
            "titulo": titulo.strip(),
            "texto": f"{titulo_doc}\n\n## {titulo.strip()}\n{cuerpo}" if titulo_doc else f"## {titulo.strip()}\n{cuerpo}",
        })
    if not secciones and texto.strip():
        secciones.append({"titulo": titulo_doc, "texto": texto.strip()})
    return secciones


def fragmentar_fuente_piloto(doc_name: str, texto: str, meta: Dict[str, Any], chunker) -> List[Dict[str, Any]]:
    """Regresa los fragmentos con el mismo formato que StructuralChunker.chunk_document."""
    categoria = meta.get("categoria", "general")
    periodo = meta.get("periodo", "2026B")
    if categoria == "horarios":
        secciones = _secciones_horario(doc_name, texto, periodo)
    else:
        secciones = _secciones_markdown(texto)

    chunks: List[Dict[str, Any]] = []
    for sec in secciones:
        # Si una sección rebasa el máximo, se usa el fragmentador general solo para ella
        partes = [sec["texto"]]
        if chunker.count_tokens(sec["texto"]) > chunker.max_tokens - 60:
            sub = chunker.chunk_document(doc_name, [{"page_number": 1, "text": sec["texto"]}], meta)
            partes = [c["raw_text"] for c in sub]
        for parte in partes:
            idx = len(chunks) + 1
            header = chunker._build_header(doc_name, categoria, 1, 1, sec["titulo"])
            full_text = header + parte
            chunks.append({
                "chunk_id": f"{meta['clean_id']}_c{idx:03d}",
                "content_hash": hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
                "text": full_text,
                "raw_text": parte,
                "token_count": chunker.count_tokens(full_text),
                "documento": doc_name,
                "categoria": categoria,
                "subcategoria": meta.get("subcategoria", ""),
                "carrera": meta.get("carrera", "ICO"),
                "periodo": periodo,
                "articulo": sec["titulo"],
                "pagina_inicio": 1,
                "pagina_fin": 1,
            })
    return chunks
