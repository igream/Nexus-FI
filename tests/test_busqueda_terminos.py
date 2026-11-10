"""Búsqueda: aceptar nombres propios poco comunes que aparecen tal cual (complemento de RF13)."""
import math

import pytest

from nexus_ingestion.vector_store import LanceDBVectorStore

CONSULTA = [1.0, 0.0, 0.0]


def vector(similitud: float, eje: int = 1):
    """Vector unitario cuya similitud coseno con CONSULTA es la indicada."""
    v = [similitud, 0.0, 0.0]
    v[eje] = math.sqrt(1 - similitud ** 2)
    return v


def chunk(i, texto):
    return {"chunk_id": f"c{i}", "text": texto, "documento": f"doc{i}.md", "categoria": "prueba"}


@pytest.fixture
def store(tmp_path):
    s = LanceDBVectorStore(uri=str(tmp_path / "db"), table_name="t", embedding_dim=3)
    filas = [
        (chunk(1, "Reglamento general de alumnos de la Facultad"), vector(0.60)),
        (chunk(2, "Potropath es un proyecto del Reto Innovatics 2026"), vector(0.40)),
        (chunk(3, "Convocatoria de becas y sus requisitos"), vector(0.45, 2)),
        (chunk(4, "Otra mención de Potropath muy lejana"), vector(0.20, 2)),
    ]
    # «laboratorio» aparece en muchos fragmentos: no es un término poco común
    filas += [(chunk(10 + i, f"Laboratorio de cómputo número {i}"), vector(0.40, 2)) for i in range(6)]
    s.save_chunks([c for c, _ in filas], [v for _, v in filas], mode="overwrite")
    return s


def documentos(resultados):
    return {r["documento"] for r in resultados}


def test_sin_texto_de_consulta_solo_aplica_el_umbral(store):
    assert documentos(store.search(CONSULTA, top_k=4, similarity_threshold=0.52)) == {"doc1.md"}


def test_nombre_propio_poco_comun_se_acepta_bajo_el_umbral(store):
    r = store.search(CONSULTA, top_k=4, similarity_threshold=0.52, query_text="¿Qué es Potropath?")
    assert documentos(r) == {"doc1.md", "doc2.md"}
    assert next(x for x in r if x["documento"] == "doc2.md")["coincidencia_exacta"] is True


def test_coincidencia_bajo_el_piso_minimo_no_se_acepta(store):
    r = store.search(CONSULTA, top_k=10, similarity_threshold=0.52, query_text="potropath")
    assert "doc4.md" not in documentos(r)


def test_pregunta_fuera_de_tema_no_cambia(store):
    r = store.search(CONSULTA, top_k=4, similarity_threshold=0.52, query_text="Dame una receta de pozole")
    assert documentos(r) == {"doc1.md"}


def test_palabra_frecuente_no_cuenta_como_termino_distintivo(store):
    assert store.terminos_distintivos("¿Dónde está el laboratorio?") == set()
    r = store.search(CONSULTA, top_k=10, similarity_threshold=0.52, query_text="laboratorio")
    assert documentos(r) == {"doc1.md"}


# --- Fragmentos casi duplicados (mapa curricular repetido en los temarios) -------------

MAPA = " ".join(f"Materia{i}" for i in range(60)) + " PERIODO 6 PERIODO 7 PERIODO 8"


@pytest.fixture
def store_mapa(tmp_path):
    s = LanceDBVectorStore(uri=str(tmp_path / "db"), table_name="t", embedding_dim=3)
    filas = [
        # Cuatro temarios con la misma página del mapa; solo cambia el encabezado y una palabra
        (dict(chunk(i, f"[DOCUMENTO: temario{i}.pdf | PÁG: 5-5]\n{MAPA} extra{i}"),
              documento=f"temario{i}.pdf"), vector(0.63 - i * 0.001))
        for i in range(4)
    ]
    filas.append((dict(chunk(9, "[DOCUMENTO: horarios_ico_semestre_6.md]\n" + " ".join(
        f"Horario{i}" for i in range(40))), documento="horarios_ico_semestre_6.md"), vector(0.61)))
    filas.append((chunk(8, "Texto distinto sobre otra cosa " + " ".join(f"Otro{i}" for i in range(40))), vector(0.60)))
    s.save_chunks([c for c, _ in filas], [v for _, v in filas], mode="overwrite")
    return s


def test_copias_del_mapa_no_desplazan_al_documento_correcto(store_mapa):
    r = store_mapa.search(CONSULTA, top_k=4, similarity_threshold=0.52)
    docs = [x["documento"] for x in r]
    assert docs[0] == "temario0.pdf"                      # se queda la copia mejor clasificada
    assert sum(d.startswith("temario") for d in docs) == 1
    assert "horarios_ico_semestre_6.md" in docs


def test_sin_filtro_las_copias_ocupan_todas_las_fuentes(store_mapa):
    r = store_mapa.search(CONSULTA, top_k=4, similarity_threshold=0.52, quitar_duplicados=False)
    assert all(x["documento"].startswith("temario") for x in r)


def test_fragmentos_cortos_parecidos_no_se_descartan(store):
    # Los «Laboratorio de cómputo número i» se parecen mucho, pero son cortos: se conservan todos
    r = store.search(CONSULTA, top_k=10, similarity_threshold=0.0)
    assert sum(x["documento"].startswith("doc1") and len(x["documento"]) == 8 for x in r) == 6
