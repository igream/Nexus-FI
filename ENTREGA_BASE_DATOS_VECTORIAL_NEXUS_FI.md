# Nexus FI — Documento de Entrega Técnica: Ingesta, Procesamiento y Base de Datos Vectorial

> **Proyecto:** Nexus FI — Asistente Virtual Inteligente RAG (Facultad de Ingeniería — UAEMéx)  
> **Destinatario:** Santiago Cuevas Sánchez (Ingeniero de Datos & Base Vectorial) / Equipo de Desarrollo 404  
> **Emisor:** Fernando Azuara Ibarra (Project Manager & Coordinador General)  
> **Fecha de Entrega Inicial:** 21 de octubre de 2026  
> **Fecha de Auditoría y Refactorización de Producción:** 22 de octubre de 2026  
> **Fase del Proyecto:** Fase 2: Ejecución Técnica — Desarrollo RAG, Seguridad y Calidad  
> **Paquetes de Trabajo Concluidos:** WBS 1.2.1, WBS 1.2.2, WBS 1.3.1, WBS 1.3.2  
> **Requerimientos SRS Cumplidos:** RF08, RF09, RF13 (preparados RF04, RF05)

---



### Métricas Consolidadas del Corpus

| Métrica | Estado Inicial (21 Oct) | Estado Auditado y Optimizado (22 Oct) | Observaciones Técnicas |
| :--- | :--- | :--- | :--- |
| **Documentos procesados** | **211 archivos** | **211 archivos** | 100 % de los documentos válidos del acervo. |
| **Total de páginas procesadas** | **3,280 páginas** | **3,280 páginas** | Reglamentos, acuerdos, convocatorias y planes de estudio. |
| **Documentos con OCR Local** | **47 archivos** | **47 archivos** | ~650 páginas escaneadas procesadas con RapidOCR ($0.00 USD). |
| **Documentos digitales nativos** | **164 archivos** | **164 archivos** | Extracción nativa con PyMuPDF y normalización NFKC. |
| **Total de Chunks generados** | **3,014 fragmentos** | **3,977 fragmentos** | Segmentación estricta RF08 delimitada por ventana de tokens. |
| **Rango de Tokens por Chunk** | 48 a 1,068 tokens | **132 a 674 tokens** | **0 chunks > 800 tokens** y **0 chunks < 100 tokens**. |
| **Promedio de Tokens / Chunk** | 689 tokens | **609.9 tokens** | Presupuesto de cabecera RF09 descontado preventivamente. |
| **Chunks con Trazabilidad Art.** | Parcial (solo 1er match) | **2,691 fragmentos** | Propagación de estado de `Artículo`/`Capítulo` entre chunks contiguos. |
| **Tokens totales procesados** | **2,077,608 tokens** | **2,425,384 tokens** | Costo estimado OpenAI: **$0.0485 USD** (~$0.97 MXN). |
| **Vectores en BD Activa Local** | **3,014 vectores** *(inicial)* | **3,977 vectores** *(activo)* | Dimensión: **1,536**, Métrica: **Similitud Coseno** (100% sincronizado). |
| **Tamaño de la BD en disco** | **25.84 MB** | **58.54 MB** *(versionado activo)* | Ubicación: `data/lancedb/nexus_documents.lance`. |

---

## 2. Mapa y Organización de Directorios

El espacio de trabajo ha sido completamente auditado, refactorizado y protegido para entornos locales y contenedores en la nube:

```
Documentos FI UAEMex/
│
├── .env                                    # Variables de entorno locales (NO SUBIR A GIT NI A DOCKER)
├── .env.example                            # Plantilla de variables de entorno segura
├── .gitignore                              # Reglas de protección de secretos y datos para Git
├── .dockerignore                           # Reglas de exclusión para imágenes Docker de producción
├── Documento Final Nexus FI.pdf            # Documento Maestro oficial del proyecto
├── plantilla_coordinacion_ico.md           # Plantilla estructurada para capturar info operativa de ICO
├── vectorize_corpus.py                     # Script ejecutor de vectorización con connection pooling
├── process_to_procesados.py                # Script batch multiproceso delegado a nexus_ingestion
├── finalize_procesados.py                  # Script normalizador de nombres y chunks canónicos RF08
│
├── nexus_ingestion/                        # PAQUETE PYTHON REUTILIZABLE (WBS 1.3.2 — PRODUCCIÓN)
│   ├── __init__.py
│   ├── config.py                           # Parámetros (tokens, límites DoS, umbral 0.52, endpoints, caché S3)
│   ├── classifier.py                       # Clasificador híbrido unificado y generador de clean_id
│   ├── chunker.py                          # Segmentador estricto RF08/RF09 con overlap acotado y hashes
│   ├── embedder.py                         # Cliente batch OpenAI con keep-alive y backoff exponencial en 429/5xx
│   ├── vector_store.py                     # Wrapper LanceDB con pre-filtrado seguro, esquema PyArrow y upsert
│   ├── pipeline.py                         # Orquestador end-to-end con soporte de archivo o directorio
│   ├── cli.py                              # Interfaz de línea de comandos (soporta -i archivo o carpeta)
│   ├── requirements.txt                    # Dependencias pip del paquete
│   ├── .env.example                        # Ejemplo de configuración para el repositorio
│   ├── README.md                           # Manual técnico del servicio
│   └── extractors/
│       ├── text_normalizer.py              # Normalización NFKC, regex \b y sanitización contra prompt injection
│       ├── ocr_engine.py                   # Motores OCR (RapidOCR local y AWS Textract)
│       ├── pdf_extractor.py                # Extractor híbrido con límites DoS, contexto seguro y DPI dinámico
│       └── html_extractor.py               # Extractor limpio con formato de tablas y sin duplicación de nodos
│
├── Pre Procesados/                         # Acervo crudo original (depurado de archivos corruptos)
│   ├── Becas/
│   ├── ControlE,Convenios,Biblioteca/
│   ├── info fi planes de estudio/
│   ├── reglamentos y normativas uaemex/
│   └── Tramites y Servicios/
│
├── Procesados/                             # ACERVO CANÓNICO Y ESTRUCTURADO (Insumo RAG)
│   ├── manifest.json                       # Metadatos globales y trazabilidad de los 211 docs
│   ├── corpus_chunks_para_embedding.jsonl  # Dataset unificado con los 3,977 chunks estrictos listos
│   ├── 01_Normativa_Universitaria/         # Reglamentos, acuerdos, decretos, códigos (2,591 chunks)
│   ├── 02_Planes_de_Estudio_ICO/           # Temarios oficiales de Ingeniería en Computación (703 chunks)
│   ├── 03_Becas_y_Apoyos/                  # Convocatorias 2026B y manuales de becas (196 chunks)
│   ├── 04_Tramites_y_Servicios/            # Guías oficiales de trámites universitarios (89 chunks)
│   ├── 05_Instalaciones_y_Servicios/       # Control escolar, biblioteca, idiomas (395 chunks)
│   └── 06_Coordinacion_ICO/                # Información operativa y de coordinación (3 chunks)
│
└── data/
    └── lancedb/                            # BASE DE DATOS VECTORIAL ACTIVA
        └── nexus_documents.lance/          # Tabla columnar Apache Arrow lista para RAG
```

---

## 3. Estructura de los Datos en `/Procesados`

Para cada documento original en `/Pre Procesados`, se generaron dos archivos canónicos dentro de su categoría en `/Procesados`:

1. **`{nombre_limpio}.md` (Markdown Legible):**  
   Contiene cabecera YAML Frontmatter segura (con cadenas escapadas para evitar inyecciones) con metadatos completos (`id`, `categoria`, `subcategoria`, `carrera`, `periodo`, `es_ocr`, `total_tokens`, `total_chunks`) y el texto normalizado separado por comentarios de página `<!-- Página X -->`.
2. **`{nombre_limpio}.json` (JSON Estructurado):**  
   Estructura machine-readable con la metadata, el array de páginas y el array de fragmentos (chunks) listos para el motor de búsqueda.
3. **`corpus_chunks_para_embedding.jsonl`:**  
   Archivo maestro JSON Lines donde cada línea es un objeto listo para el modelo de embeddings, enriquecido con hash criptográfico SHA-256 para verificación de integridad e idempotencia:
   ```json
   {
     "chunk_id": "becas_1_bre_26bv1_c001",
     "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
     "text": "[DOCUMENTO: 1 BRE 26Bv1.pdf | CATEGORÍA: BECAS | PÁG: 1-1]\n\nBECA REINSCRIPCIÓN ESCOLAR OTOÑO 2026...",
     "raw_text": "BECA REINSCRIPCIÓN ESCOLAR...",
     "token_count": 642,
     "documento": "1 BRE 26Bv1.pdf",
     "categoria": "becas",
     "subcategoria": "convocatoria",
     "carrera": "GENERAL_FI",
     "periodo": "2026B",
     "articulo": "",
     "pagina_inicio": 1,
     "pagina_fin": 1
   }
   ```

---

## 4. Estado de la Base Vectorial (`data/lancedb`)

* **Tecnología:** LanceDB (formato Apache Arrow columnar optimizado para búsqueda ANN).
* **Tabla principal:** `nexus_documents`.
* **Dimensiones vectoriales:** 1,536 (`text-embedding-3-small`).
* **Métrica de distancia:** Coseno (`metric="cosine"`).
* **Esquema Tipado Apache Arrow:** Implementado mediante `pa.schema` explícito en [`get_vector_schema`](file:///C:/Users/feraz/Desktop/Documentos%20FI%20UAEMex/nexus_ingestion/vector_store.py#L46-L61), garantizando vectores `pa.list_(pa.float32(), 1536)` sin fallos de inferencia dinámica.
* **Pre-Filtrado Seguro (`prefilter=True`):** Los filtros por metadatos se aplican **antes** de calcular los vecinos más cercanos, evitando que consultas específicas (ej. solo `tramites`) devuelvan 0 resultados por saturación de la categoría `normativa`.
* **Umbral de Calibración Anti-Alucinaciones (RF13):**  
  $$X_{base} = 0.52$$
  *(Cualquier coincidencia con similitud menor a 0.52 debe activar el protocolo de abstención informada).*
* **Trazabilidad (RF09):**  
  Cada fragmento contiene el texto de cabecera con el documento fuente, categoría y número de página para forzar al LLM a emitir citas institucionales exactas.

### Prueba de Búsqueda Semántica Realizada
* **Query:** *"¿Cuáles son los requisitos para la beca de reinscripción escolar en otoño?"*
* **Coincidencia Top 1:** `1 BRE 26Bv1.pdf` $\rightarrow$ Similitud: **0.7394** *(Pág. 1, Criterios y requisitos).*
* **Coincidencia Top 2:** `3 BMA 26B.pdf` $\rightarrow$ Similitud: **0.6257**.
* **Coincidencia Top 3:** `5 BPU 26B.pdf` $\rightarrow$ Similitud: **0.6085**.

---

## 5. Guía para el Compañero: ¿Cómo Continuar?

### Tarea A: Consultar la Base de Datos Vectorial en Python (Cliente Seguro)
Para interactuar con la base vectorial localmente o en un microservicio RAG (FastAPI/Flask), utiliza el componente oficial protegido contra inyecciones:

```python
import os
from dotenv import load_dotenv
from nexus_ingestion.embedder import TextEmbedder
from nexus_ingestion.vector_store import LanceDBVectorStore

load_dotenv()

# 1. Inicializar cliente de embeddings y base de datos
embedder = TextEmbedder()
store = LanceDBVectorStore(uri="./data/lancedb")

# 2. Generar embedding de la pregunta
query = "¿Cuál es el procedimiento para el servicio social?"
query_vec = embedder.embed_query(query)

# 3. Búsqueda por similitud con pre-filtrado seguro y umbral RF13 (0.52)
results = store.search(
    query_vector=query_vec,
    top_k=3,
    similarity_threshold=0.52,
    filter_dict={"categoria": "tramites"}  # Validado contra lista blanca de columnas
)

for idx, res in enumerate(results, start=1):
    print(f"[{idx}] Similitud: {res['similarity']} | {res['documento']} (Pág: {res['pagina']})")
    print(res["text"][:200] + "...\n")
```

---

### Tarea B: Despliegue de la Base de Datos a Amazon S3 y Optimización Cloud

Cuando el equipo DevOps (`Ángel Israel`) tenga disponible el bucket de S3:

1. **Sincronizar la carpeta local con S3:**
   ```bash
   aws s3 sync data/lancedb s3://nexus-fi-vectors/lancedb
   ```

2. **Estrategia de Caching Local para Baja Latencia (<5 ms vs ~300 ms):**
   > [!IMPORTANT]
   > Conectar directamente LanceDB a `s3://` en cada query agrega de 150 a 500 ms de latencia HTTP y costos por peticiones GET.  
   > Dado que toda la base pesa solo ~30 MB, la mejor práctica en producción (EC2 `t4g.small` o `/tmp` en AWS Lambda) es descargar o sincronizar la carpeta al almacenamiento efímero local durante el arranque del contenedor.
   
   Configuración recomendada en `.env` de producción:
   ```env
   LANCEDB_URI=s3://nexus-fi-vectors/lancedb
   LANCEDB_LOCAL_CACHE=/tmp/nexus_lancedb
   ```

---

### Tarea C: Incorporación de Nuevos Datos o Actualizaciones (Idempotente)
Cuando se actualicen reglamentos o se ingrese nueva información (por ejemplo, en [`plantilla_coordinacion_ico.md`](file:///C:/Users/feraz/Desktop/Documentos%20FI%20UAEMex/plantilla_coordinacion_ico.md)):

1. Editar o agregar el documento en Markdown, PDF o HTML.
2. Ejecutar la ingesta selectiva mediante la CLI:
   ```bash
   python -m nexus_ingestion.cli --input "plantilla_coordinacion_ico.md" --mode upsert
   ```
3. Gracias al modo `upsert`, el sistema eliminará automáticamente los vectores viejos asociados al documento y cargará los nuevos sin generar duplicados.

---

### Tarea D: Actualizar la Base Vectorial con los 3,977 Chunks Estrictos
Para sincronizar la tabla local de LanceDB con el corpus regenerado (sin desbordamientos ni fragmentos huérfanos):
```bash
python vectorize_corpus.py --mode overwrite
```

---

## 6. Políticas de Seguridad y Despliegue en la Nube

1. **Protección Absoluta de Secretos:**
   * El archivo `.env` **NUNCA** debe commitearse a Git ni incluirse en imágenes Docker.
   * Se incluye un archivo `.dockerignore` estricto que excluye automáticamente `.env`, `.env.*`, `Pre Procesados/`, `scratch/` y llaves privadas.
   * En producción (AWS ECS / EC2 / Lambda), inyectar `OPENAI_API_KEY` mediante **AWS Secrets Manager** o **SSM Parameter Store**, y utilizar **IAM Roles** para permisos de S3 en lugar de credenciales estáticas.

2. **Protección contra Inyección de Predicados:**
   * La interfaz de búsqueda solo permite filtrar por columnas autorizadas (`id`, `documento`, `categoria`, `subcategoria`, `carrera`, `periodo`, `articulo`). Cualquier intento de inyectar código DataFusion/SQL es interceptado con `ValueError`.

3. **Prevención de DoS / OOM:**
   * Límites de archivo (`MAX_FILE_SIZE_MB=50`) y páginas (`MAX_PDF_PAGES=500`).
   * Resolución de OCR acotada dinámicamente para prevenir bombas de descompresión en instancias con memoria limitada (ej. `t4g.small` con 2 GB RAM).

4. **Resiliencia de Red:**
   * Pool de conexiones HTTP reutilizables (`requests.Session()`) para evitar el costo de re-negociar TLS en cada llamada a OpenAI.
   * Backoff exponencial con jitter para recuperarse automáticamente de límites de tasa (HTTP 429) y caídas temporales de la API (HTTP 500, 502, 503, 504).

---

## 7. Bitácora de Auditoría Técnica y Refactorización (WBS 1.3.2)

| Componente | Hallazgo / Vulnerabilidad Detectada | Solución Implementada en Refactorización |
| :--- | :--- | :--- |
| **`vector_store.py`** | Inyección de predicados en `.where()` vía f-strings; post-filtering por omisión de `prefilter=True`; `uuid4()` provocaba duplicación de vectores. | Validación estricta con `ALLOWED_FILTER_COLUMNS`, escape de comillas, forzado de `prefilter=True`, esquema `pa.schema` explícito y modo `upsert` idempotente. |
| **`chunker.py`** | 63 chunks superaban los 800 tokens (hasta 1,068) y 15 eran huérfanos (<100 tokens); el overlap conservaba párrafos enteros desbordando el target. | Overlap token-bounded exacto (`100 tokens`), presupuesto de cabecera descontado previamente, fusión de chunks huérfanos y propagación de estado de artículos. |
| **`text_normalizer.py`** | Bucle ineficiente de 98 `.replace()` sin `\b` que causaba corrupciones de subcadenas (`pasíillo`, `ingestáa`); falta de normalización NFKC. | Aplicación de `unicodedata.normalize("NFKC")`, expresión regular compilada única con límites de palabra `\b`, e integración de correcciones léxicas automáticas. |
| **`html_extractor.py`** | XPath extraía `<table>` y luego sus `<p>`/`<li>` internos duplicando contenido; eliminaba encabezados cortos válidos (`< 15` caracteres). | Formateo tabular estructurado con ` | `, exclusión de nodos anidados duplicados y preservación explícita de etiquetas de encabezado `h1`–`h4`. |
| **`pdf_extractor.py`** | Sin límites de tamaño ni páginas; sin context manager en excepciones; riesgo de OOM en imágenes masivas. | Integración de context manager `with pymupdf.open(...)`, límites de seguridad DoS configurables y ajuste dinámico de DPI. |
| **`embedder.py`** | Llamadas HTTP sin sesión persistente; sin reintentos en errores 5xx transitorios de OpenAI. | Implementación de `requests.Session()`, ordenamiento estricto por índice de vector y reintentos con backoff exponencial y jitter. |
| **`cli.py` / `pipeline.py`**| Fallaba silenciosamente al recibir un archivo individual (`os.walk` devolvía vacío). | Detección polimórfica de archivo único o directorio con validación de extensiones y modo `upsert` configurable. |
| **Seguridad de Archivos** | Parámetro `--api-key` expuesto en línea de comandos; ausencia de `.dockerignore`. | Eliminación de `--api-key` en CLI (uso exclusivo de variables de entorno) y creación de `.dockerignore` exhaustivo. |
