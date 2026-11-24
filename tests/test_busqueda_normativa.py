"""Defecto D-02: preguntas de trámite que deben recuperar su norma (glosario, refuerzo y diversidad)."""
import math

import pytest

from nexus_ingestion import vector_store as vs_mod
from nexus_ingestion.vector_store import LanceDBVectorStore, expandir_consulta

CONSULTA = [1.0, 0.0, 0.0]


def vector(similitud: float, eje: int = 1):
    v = [similitud, 0.0, 0.0]
    v[eje] = math.sqrt(1 - similitud ** 2)
    return v


def chunk(i, texto, documento, categoria):
    return {"chunk_id": f"c{i}", "text": texto, "documento": documento, "categoria": categoria}


REGLAMENTO = "REGLAMENTO DE EVALUACIÓN PROFESIONAL.pdf"
SERVICIO = "REGLAMENTO DEL SERVICIO SOCIAL.pdf"


@pytest.fixture
def store(tmp_path):
    s = LanceDBVectorStore(uri=str(tmp_path / "db"), table_name="t", embedding_dim=3)
    filas = [  # los programas de materia ganan por coseno, como en CP-01 y CP-02
        (chunk(i, f"Programa de materia {i} de Ingeniería en Computación", f"PE_ICO_{i}.pdf", "planes_estudio"),
         vector(0.55 - i * 0.01)) for i in range(6)
    ]
    filas += [
        (chunk(20, "Las modalidades de evaluación profesional son trece", REGLAMENTO, "normativa"), vector(0.50)),
        (chunk(21, "El alumno debe cubrir el cincuenta por ciento de créditos", SERVICIO, "normativa"), vector(0.49, 2)),
        (chunk(22, "Guía de trámites: tres opciones", "Guia_Tramites.pdf", "tramites"), vector(0.545, 2)),
        (chunk(23, "Guía de trámites: titulación", "Guia_Tramites.pdf", "tramites"), vector(0.54, 2)),
        (chunk(24, "Guía de trámites: constancias", "Guia_Tramites.pdf", "tramites"), vector(0.535, 2)),
    ]
    s.save_chunks([c for c, _ in filas], [v for _, v in filas], mode="overwrite")
    return s


def docs(r):
    return [x["documento"] for x in r]


@pytest.mark.parametrize("pregunta", [
    "¿Cuántas y cuáles son las opciones de titulación disponibles para la carrera de Ingeniería en Computación?",
    "¿Cómo me puedo titular?",
])
def test_glosario_agrega_la_norma_de_titulacion(pregunta):
    assert "Evaluación Profesional" in expandir_consulta(pregunta)
    assert expandir_consulta(pregunta).startswith(pregunta)


def test_glosario_no_toca_otros_temas():
    # Servicio social solo se refuerza: el glosario dejaba fuera el art. 16 (480 horas)
    for q in ["Dame una receta de pozole rojo", "¿Qué materias hay en séptimo semestre de ICO?",
              "¿Cuántas horas de servicio social se deben cubrir?"]:
        assert expandir_consulta(q) == q


def test_sin_refuerzo_la_norma_queda_fuera(store):
    r = store.search(CONSULTA, top_k=4, query_text="¿Qué opciones de titulación tengo en ICO?")
    assert REGLAMENTO not in docs(r)


def test_refuerzo_recupera_la_norma_con_su_similitud_real(store):
    r = store.search(CONSULTA, top_k=4, query_text="¿Qué opciones de titulación tengo en ICO?",
                     reforzar_normativa=True)
    assert docs(r)[0] == REGLAMENTO
    assert r[0]["similarity"] == 0.5 and r[0]["reforzado"] is True
    assert SERVICIO not in docs(r)          # solo se refuerza la norma del tema de la pregunta


def test_refuerzo_servicio_social(store):
    r = store.search(CONSULTA, top_k=4, query_text="¿Qué créditos pide el servicio social?",
                     reforzar_normativa=True)
    assert SERVICIO in docs(r) and REGLAMENTO not in docs(r)


def test_refuerzo_no_cambia_preguntas_fuera_de_tema(store):
    base = store.search(CONSULTA, top_k=4, query_text="receta de pozole")
    assert store.search(CONSULTA, top_k=4, query_text="receta de pozole", reforzar_normativa=True) == base


def test_maximo_por_documento(store, monkeypatch):
    # Sin refuerzo, la Guía de Trámites aporta hasta 3 fragmentos; con el tope, 2
    q = dict(top_k=10, query_text="trámites")
    assert docs(store.search(CONSULTA, **q)).count("Guia_Tramites.pdf") == 3
    assert docs(store.search(CONSULTA, max_por_documento=2, **q)).count("Guia_Tramites.pdf") == 2


def test_refuerzo_respeta_el_filtro_de_categoria(store):
    r = store.search(CONSULTA, top_k=4, query_text="opciones de titulación", reforzar_normativa=True,
                     filter_dict={"categoria": "planes_estudio"})
    assert all(x["categoria"] == "planes_estudio" for x in r)


def test_nombres_de_documentos_se_recalculan_al_guardar(store):
    assert store.documentos_reforzados("movilidad") == set()
    store.save_chunks([chunk(30, "Promedio mínimo de 8.0", "Reglamento de Movilidad.pdf", "normativa")],
                      [vector(0.3)], mode="upsert")
    assert store.documentos_reforzados("movilidad") == {"Reglamento de Movilidad.pdf"}


def test_la_norma_reforzada_no_tiene_tope(tmp_path):
    # Todas las respuestas de servicio social viven en el mismo reglamento: el tope no debe recortarlo
    s = LanceDBVectorStore(uri=str(tmp_path / "db2"), table_name="t", embedding_dim=3)
    filas = [(chunk(i, f"Artículo {i} del servicio social", SERVICIO, "normativa"), vector(0.50 - i * 0.01))
             for i in range(3)]
    filas += [(chunk(10 + i, f"Programa {i}", "PE_ICO.pdf", "planes_estudio"), vector(0.58 - i * 0.01, 2))
              for i in range(3)]
    s.save_chunks([c for c, _ in filas], [v for _, v in filas], mode="overwrite")
    r = s.search(CONSULTA, top_k=5, query_text="horas de servicio social", reforzar_normativa=True,
                 max_por_documento=2)
    assert docs(r).count(SERVICIO) == 3 and docs(r).count("PE_ICO.pdf") == 2


def test_constantes_documentadas():
    assert vs_mod.REFUERZO_TITULO == 0.06 and vs_mod.MAX_POR_DOCUMENTO == 2


# Temas agregados el 24/11/2026 por la prueba de 41 preguntas de estudiantes
NOMBRES = ["1 BRE 26Bv1.pdf", "17 BSIv3.pdf", "8 AEV-26B.pdf", "10 EC-26B.pdf", "11 EDv1.pdf",
           "reglamento Becas.pdf", "2026 Convenios.pdf", "09-reglamento_del_sistema_bibliotecario.pdf",
           "Facultad de Ingeniería - Control Escolar FI.html",
           "REGLAMENTO DE MOVILIDAD ESTUDIANTIL DE ESTUDIOS PROFESIONALES.pdf",
           "REGLAMENTO DE PRÁCTICAS Y ESTANCIAS PROFESIONALES.pdf", SERVICIO]


@pytest.fixture
def acervo(tmp_path):
    s = LanceDBVectorStore(uri=str(tmp_path / "db3"), table_name="t", embedding_dim=3)
    s.save_chunks([chunk(i, "texto", d, "x") for i, d in enumerate(NOMBRES)], [vector(0.3)] * len(NOMBRES),
                  mode="overwrite")
    return s


@pytest.mark.parametrize("pregunta,esperados", [
    ("¿A qué área debo acudir con una duda escolar?", {"Facultad de Ingeniería - Control Escolar FI.html"}),
    ("¿Cómo saco una constancia de estudios?", {"Facultad de Ingeniería - Control Escolar FI.html"}),
    ("¿Qué necesito para irme de intercambio?", {"REGLAMENTO DE MOVILIDAD ESTUDIANTIL DE ESTUDIOS PROFESIONALES.pdf"}),
    ("¿Qué actividades culturales y deportivas hay?", {"10 EC-26B.pdf", "11 EDv1.pdf"}),
    ("¿Puedo hacer las prácticas profesionales y el servicio social al mismo tiempo?",
     {"REGLAMENTO DE PRÁCTICAS Y ESTANCIAS PROFESIONALES.pdf", SERVICIO}),
])
def test_temas_de_estudiantes(acervo, pregunta, esperados):
    assert acervo.documentos_reforzados(pregunta) == esperados


def test_becas_refuerza_solo_las_convocatorias(acervo):
    r = acervo.documentos_reforzados("¿Qué becas hay?")
    assert r == {"1 BRE 26Bv1.pdf", "17 BSIv3.pdf", "8 AEV-26B.pdf", "10 EC-26B.pdf", "11 EDv1.pdf"}
    assert "8 AEV-26B.pdf" in acervo.documentos_reforzados("¿Hay alguna beca si soy mamá y estudio?")


def test_temas_nuevos_no_tocan_otras_preguntas(acervo):
    for q in ["¿Qué materias hay en séptimo semestre de ICO?", "receta de pozole", "¿Cuál es el horario de Cálculo?"]:
        assert acervo.documentos_reforzados(q) == set()
