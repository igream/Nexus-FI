# 📚 Índice y Estructura Documental — Proyecto Nexus FI
**Facultad de Ingeniería · Universidad Autónoma del Estado de México**  
**Equipo 404 · Licenciatura en Ingeniería en Computación**  
**Unidad de Aprendizaje:** Administración de Proyectos Informáticos  
**Docente:** I. en C. Cíntia González Mireles | **Project Manager:** Fernando Azuara Ibarra  

---

## 🗂️ Estructura del Directorio de Documentación (`docs/`)

La documentación se organiza por fase del ciclo de vida del proyecto (PMBOK) y, dentro de la ejecución, por avance:

```
docs/
├── 00_Formatos/                    # Plantillas oficiales de gobernanza, tareas y cambios
│   └── Matrices_Cumplimiento/      # Matrices de evaluación del desempeño y anexo de rúbricas
├── 01_Planeacion/                  # Documento maestro e investigaciones previas
│   └── Investigaciones_Previas/
└── 02_Ejecucion/                   # Grupo de procesos de ejecución
    ├── Avance_1_25/                # Corte del 25 % (21/10/2026)
    │   ├── Asignaciones/           # Lo que asigna el PM
    │   ├── Entregas/               # Lo que entrega cada integrante
    │   └── INFORME_EJECUCION_AVANCE1.docx
    ├── Avance_2_50/                # Corte del 50 % (28/10/2026)
    │   ├── Asignaciones/
    │   ├── Entregas/
    │   └── ESTADO_ENTREGAS_AVANCE2_SC001.md
    ├── Avance_3_100/               # Cierre del 100 % de la ejecución (03/11/2026)
    │   └── Asignaciones/
    ├── Control_Cambios/            # Solicitudes de cambio aprobadas (SC-001, ...)
    └── Especificaciones_Tecnicas/  # Base vectorial, plantilla ICO y pipeline Apify + OCR
```

### Convención de nombres
- Archivos en **MAYÚSCULAS_CON_GUIONES_BAJOS**, sin espacios ni acentos: `<TIPO>_<TEMA>_AVANCE<n>_<INTEGRANTES>.<ext>`.
- Integrantes con **nombre y primer apellido** (`JOAQUIN_GARCIA`, `ANGEL_DE_LA_CRUZ_Y_AARON_DOMINGUEZ`); los nombres completos van dentro de cada documento.
- Tipos: `FORMATO_ASIGNACION` (asigna el PM), `FORMATO_UNIVERSAL` (entrega del integrante), `ESPECIFICACION`, `OFICIO`, `RESUMEN`, `INFORME_EJECUCION`, `SOLICITUD_CAMBIO_SC<nnn>_<TEMA>`.
- `n = 1` para el 25 %, `2` para el 50 %, `3` para el 75 % y `4` para el 100 %.
- Excepción: los archivos que genera un script (`nexus_fi.db`, `informe_proceso.md`) conservan el nombre que usa el código.
- Los originales tal como se recibieron se guardan en `Local/Avances <fecha>/`, fuera del control de versiones.

### Clave de integrantes
| Clave en archivos | Nombre completo |
| :--- | :--- |
| `FERNANDO_AZUARA` | Fernando Azuara Ibarra |
| `JOAQUIN_GARCIA` | Joaquín Ulises García Álvarez |
| `DANIEL_AGUILAR` | Daniel Aguilar Sánchez |
| `JOAN_OCANA` | Joan Alexis Ocaña Martínez |
| `ANGEL_DE_LA_CRUZ` | Ángel Israel de la Cruz Martínez |
| `AARON_DOMINGUEZ` | Aarón Nevid Domínguez Fuentes |
| `SANTIAGO_CUEVAS` | Santiago Cuevas Sánchez |
| `AZULEICA_DE_LA_CRUZ` | Azuleica Betsabel de la Cruz González |

---

## 📋 Detalle de Contenidos

### `00_Formatos/`
Formatos institucionales en Times New Roman y texto negro:
* `FORMATO_ASIGNACION_TAREAS_Y_RETROALIMENTACION.docx`: delegación de tareas por el PM y registro de retroalimentación.
* `FORMATO_UNIVERSAL_DOCUMENTACION_TAREAS.docx`: instrumento obligatorio para documentar cada tarea terminada (código, pruebas y evidencias).
* `FORMATO_SOLICITUD_DE_CAMBIO.docx`: control de cambios ante desviaciones de alcance, cronograma o presupuesto.
* `PLANTILLA_PORTADA_OFICIAL.docx`: portada institucional de la Facultad de Ingeniería.
* `Matrices_Cumplimiento/`: matriz de cumplimiento individual, evaluación del Project Manager, matriz de desempeño por actividades (cada una en una cuartilla, con Excel incrustado y escala de color), anexo de rúbricas y Excel maestro.

### `01_Planeacion/`
* `DOCUMENTO_MAESTRO_NEXUS_FI.docx` / `.pdf`: documento maestro de planificación y gestión (problema, objetivos, RF/RNF, trazabilidad y gobernanza PMBOK). Versión 6.0 de uso interno: las secciones afectadas por la SC-001 llevan una «Nota de control de cambios»; el texto de la v5.0 se conserva como línea base.
* `Investigaciones_Previas/`
  * `BITACORA_RECOLECCION_DATOS_FERNANDO_AZUARA.docx`: bitácora de acopio documental y normativo.
  * `INVESTIGACION_APIFY_OCR_SANTIAGO_CUEVAS.pdf`: estudio de extracción de redes sociales con Apify y OCR Tesseract.
  * `INVESTIGACION_PLANTILLAS_WEB_DANIEL_AGUILAR.docx`: plantillas web del chatbot y del panel de métricas.
  * `REPORTE_TECNICO_DT10_ANGEL_DE_LA_CRUZ.docx`: módulo DT-10 de seguridad y telemetría.

### `02_Ejecucion/Avance_1_25/` (corte del 21 de octubre de 2026)
* `INFORME_EJECUCION_AVANCE1.docx`: informe formal del Avance 1 con la portada oficial.
* `Asignaciones/`: `FORMATO_ASIGNACION_AVANCE1_` + `AARON_DOMINGUEZ`, `ANGEL_DE_LA_CRUZ`, `AZULEICA_DE_LA_CRUZ`, `DANIEL_AGUILAR_Y_JOAN_OCANA`, `JOAQUIN_GARCIA`, `SANTIAGO_CUEVAS`.
* `Entregas/`
  * `FORMATO_UNIVERSAL_AVANCE1_JOAQUIN_GARCIA.docx`: seguridad de credenciales API, auditoría y catálogo de modelos.
  * `FORMATO_UNIVERSAL_AVANCE1_ANGEL_DE_LA_CRUZ.docx`: módulo DT-10 y telemetría de la API de OpenAI.
  * `FORMATO_UNIVERSAL_AVANCE1_SANTIAGO_CUEVAS.docx`: pipeline Apify, base SQLite y OCR (tarea retroactiva).
  * `FORMATO_UNIVERSAL_AVANCE1_AZULEICA_DE_LA_CRUZ.docx`: recopilación de información institucional de cuatro áreas.

### `02_Ejecucion/Avance_2_50/` (entrega interna del 28 de octubre de 2026)
* `Asignaciones/`: `FORMATO_ASIGNACION_AVANCE2_` + `ANGEL_DE_LA_CRUZ_Y_AARON_DOMINGUEZ`, `DANIEL_AGUILAR_Y_JOAN_OCANA`, `JOAQUIN_GARCIA`, `SANTIAGO_CUEVAS_Y_AZULEICA_DE_LA_CRUZ`.
* `Entregas/`
  * `FORMATO_UNIVERSAL_AVANCE2_JOAQUIN_GARCIA.docx` y `RESUMEN_AVANCE2_JOAQUIN_GARCIA.md`: filtrado perimetral por IP y límite de uso. *Descartado por la SC-001* (el límite de uso se reutiliza por usuario).
  * `FORMATO_UNIVERSAL_AVANCE2_DANIEL_AGUILAR_Y_JOAN_OCANA.docx`: modo oscuro, tablero de usuario y panel de métricas.
  * `FORMATO_UNIVERSAL_AVANCE2_ANGEL_DE_LA_CRUZ.docx`: Nginx como proxy inverso y Docker Compose.
  * `ESPECIFICACION_ARQUITECTURA_AWS_AVANCE2_ANGEL_DE_LA_CRUZ_Y_AARON_DOMINGUEZ.docx`: arquitectura cloud, contenedores y despliegue en AWS (WBS 1.5.3).
  * `OFICIO_SOLICITUD_META_API_AVANCE2_SANTIAGO_CUEVAS_Y_AZULEICA_DE_LA_CRUZ.docx`: oficio a la Coordinación de Difusión para solicitar el token institucional de la Meta API.
* `ESTADO_ENTREGAS_AVANCE2_SC001.md`: qué entregas del 50 % siguen vigentes y cuáles se descartan por la SC-001 (filtro IP e investigación de subredes). Nada se borra.
* *Pendientes:* Formato Universal del 50 % de Santiago Cuevas Sánchez, Azuleica Betsabel de la Cruz González y Aarón Nevid Domínguez Fuentes; Solicitud de Cambio por el pipeline Apify + OCR (SC-002).

### `02_Ejecucion/Avance_3_100/` (entrega del 3 de noviembre de 2026, Carpeta Digital)
* `Asignaciones/`: `FORMATO_ASIGNACION_AVANCE3_` + `JOAQUIN_GARCIA` (backend del login), `DANIEL_AGUILAR_Y_JOAN_OCANA` (pantallas de login y sesión en el chat), `SANTIAGO_CUEVAS_Y_AZULEICA_DE_LA_CRUZ` (fuentes de la prueba piloto y oficios), `ANGEL_DE_LA_CRUZ` (despliegue en EC2 y reporte de consumo), `AARON_DOMINGUEZ` (pruebas y control de cambios). Cada formato incluye una guía paso a paso con prompts para el IDE de Google Antigravity.

### `02_Ejecucion/Control_Cambios/`
* `SOLICITUD_CAMBIO_SC001_PRUEBA_PILOTO_ICO.docx`: SC-001, aprobada el 29/10/2026. Acota el proyecto a una prueba piloto en ICO, descarta el control por IP y define el nuevo alcance, los nuevos objetivos y las partes de la planeación afectadas.

### `02_Ejecucion/Especificaciones_Tecnicas/`
* `ENTREGA_BASE_DATOS_VECTORIAL_NEXUS_FI.md`: dictamen de entrega de la base vectorial LanceDB (3,977 fragmentos y umbral RF13).
* `PLANTILLA_COORDINACION_ICO.md`: plantilla de trámites de la Coordinación de ICO; la lee `scripts/process_to_procesados.py`.
* `Redes_Sociales_Apify_OCR/nexus_fi.db`: base SQLite con publicaciones e imágenes de las redes oficiales de la Facultad y su texto OCR.
* `Redes_Sociales_Apify_OCR/informe_proceso.md`: métricas de cada ejecución de `scripts/procesar_posts.py`.

---

## ⚖️ Políticas de Formato y Presentación
1. **Tipografía:** Times New Roman en la totalidad del texto.
2. **Color de Fuente:** Estrictamente **color negro (`#000000`)**.
3. **Jerarquía:** Título 1 (16 pt, negritas), Título 2 (14 pt, negritas), Título 3 (13 pt, normal) y Cuerpo (11 pt, interlineado 1.1, justificado).
4. **Tablas:** Bordes visibles en color gris con encabezados sombreados y texto en color negro.
5. **Control de Cambios:** Cualquier modificación a los compromisos de las tareas debe formalizarse mediante `docs/00_Formatos/FORMATO_SOLICITUD_DE_CAMBIO.docx`.
