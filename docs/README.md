# 📚 Índice y Estructura Documental — Proyecto Nexus FI
**Facultad de Ingeniería · Universidad Autónoma del Estado de México**  
**Equipo 404 · Licenciatura en Ingeniería en Computación**  
**Unidad de Aprendizaje:** Administración de Proyectos Informáticos  
**Docente:** I. en C. Cíntia González Mireles | **Project Manager:** Fernando Azuara Ibarra  

---

## 🗂️ Estructura del Directorio de Documentación (`docs/`)

La documentación oficial del proyecto Nexus FI se encuentra organizada de acuerdo con las fases del ciclo de vida del proyecto (PMBOK), gobernanza y control de calidad institucional:

```
docs/
├── Documento_Maestro/              # Documento final integral del proyecto (Word y PDF)
├── Plantillas_Oficiales/           # Formatos oficiales para gobernanza, tareas y cambios
├── Asignacion_Tareas/              # Asignaciones formales por integrante y fase
│   ├── Avance_1_25_Porciento/     # Tareas del primer corte (25% - 21/10/2026)
│   └── Avance_2_50_Porciento/     # Tareas hacia el segundo corte (50% - 28/10/2026)
├── Informes_Ejecutivos/            # Informes técnicos consolidados de ejecución
├── Investigaciones_Previas_Equipo/ # Reportes de investigación individual de los integrantes
└── Especificaciones_Tecnicas/      # Manifiestos de entrega vectorial y formatos canónicos
```

---

## 📋 Detalle de Contenidos por Directorio

### 1. `Documento_Maestro/`
Documentación académica y metodológica integral del proyecto Nexus FI:
* `Documento Final Nexus FI.docx`: Documento maestro editable que contiene la descripción del problema, objetivos, justificación, requerimientos (RF/RNF), matriz de trazabilidad y gobernanza PMBOK.
* `Documento Final Nexus FI.pdf`: Versión exportada para consulta y revisión.

### 2. `Plantillas_Oficiales/`
Formatos institucionales base en tipografía Times New Roman y color estrictamente negro:
* `FORMATO DE ASIGNACIÓN DE TAREAS Y RETROALIMENTACION.docx`: Plantilla institucional para la delegación de tareas por parte del Project Manager y registro de retroalimentación.
* `FORMATO UNIVERSAL DE DOCUMENTACIÓN DE TAREAS.docx`: Instrumento oficial obligatorio para que cada integrante documente sus entregables de código, capturas de prueba y casos evaluados.
* `Solicitud de cambio.docx`: Formato formal de control de cambios ante desviaciones de alcance, cronograma o presupuesto.
* `plantilla_portada_limpia.docx`: Portada institucional oficial de la Facultad de Ingeniería.

### 3. `Asignacion_Tareas/`
Formatos de asignación formal por integrante con nombres completos, ramas Git y alcances:

#### `Avance_1_25_Porciento/` (Corte 21 de octubre de 2026 — 25% de Ejecución)
* `FORMATO_ASIGNACION_AVANCE1_DANIEL_AGUILAR_Y_JOAN_OCANA.docx` (Rama: `feature/daniel-nexusfi-ui`)
* `FORMATO_ASIGNACION_AVANCE1_JOAQUIN_ULISES_GARCIA.docx` (Rama: `API`)
* `FORMATO_ASIGNACION_AVANCE1_SANTIAGO_CUEVAS_SANCHEZ.docx` (Scripts de extracción y reporte técnico)
* `FORMATO_ASIGNACION_AVANCE1_ANGEL_ISRAEL_DE_LA_CRUZ.docx` (Rama: `main` / Commit `6aa9d67`)
* `FORMATO_ASIGNACION_AVANCE1_AARON_NEVID_DOMINGUEZ.docx` (Rama: `BaseVectorial`)
* `FORMATO_ASIGNACION_AVANCE1_ZULEICA_BETSABEL_DE_LA_CRUZ.docx` (Rama: `BaseVectorial`)

#### `Avance_2_50_Porciento/` (Entrega Interna: Miércoles 28 de octubre de 2026 — 50% de Ejecución)
* `FORMATO_ASIGNACION_AVANCE2_DANIEL_AGUILAR_Y_JOAN_OCANA.docx` (Rama: `feature/dark-mode-and-metrics`)
* `FORMATO_ASIGNACION_AVANCE2_JOAQUIN_ULISES_GARCIA.docx` (Rama: `feature/ip-filter-and-session`)
* `FORMATO_ASIGNACION_AVANCE2_SANTIAGO_CUEVAS_Y_ZULEICA_DE_LA_CRUZ.docx` (Rama: `feature/fi-network-subnets`)
* `FORMATO_ASIGNACION_AVANCE2_ANGEL_ISRAEL_Y_AARON_NEVID.docx` (Rama: `feature/aws-docker-deployment`)

### 4. `Informes_Ejecutivos/`
Informes de avance técnico formal entregados ante la docencia:
* `Avance Ejecución 1.docx`: Documento formal de entrega del Avance 1 con tabla de contenidos nativa de Word, índice de tablas y figuras, y balance presupuestal.
* `Informe_Avance_Ejecucion_Nexus_FI.docx`: Versión canónica alineada con la plantilla de portada oficial.

### 5. `Investigaciones_Previas_Equipo/`
Informes y entregas parciales elaboradas por los integrantes durante la etapa de recopilación:
* `documentacionNexus.docx`: Investigación y propuestas de arquitectura de los integrantes.
* `Informe_Tecnico_Nexus_FI.pdf`: Estudio técnico de Santiago Cuevas Sánchez sobre extracción de datos de redes sociales con Apify y OCR Tesseract.
* `Recolección de Datos.docx`: Evidencias de acopio documental y normativo.
* `Reporte Técnico proyecto Nexus.docx`: Reporte técnico previo de integración.

### 6. `Especificaciones_Tecnicas/`
Manifiestos y especificaciones de ingesta de datos:
* `ENTREGA_BASE_DATOS_VECTORIAL_NEXUS_FI.md`: Dictamen técnico de entrega de la base de datos vectorial LanceDB (3,977 fragmentos y umbral RF13).
* `plantilla_coordinacion_ico.md`: Esquema de metadatos para trámites de la Coordinación de Ingeniería en Computación.

---

## ⚖️ Políticas de Formato y Presentación
1. **Tipografía:** Times New Roman en la totalidad del texto.
2. **Color de Fuente:** Estrictamente **color negro (`#000000`)**.
3. **Jerarquía:** Título 1 (16 pt, negritas), Título 2 (14 pt, negritas), Título 3 (13 pt, normal) y Cuerpo (11 pt, interlineado 1.1, justificado).
4. **Tablas:** Bordes visibles en color gris con encabezados sombreados y texto en color negro.
5. **Control de Cambios:** Cualquier modificación a los compromisos de las tareas debe formalizarse mediante la plantilla `docs/Plantillas_Oficiales/Solicitud de cambio.docx`.
