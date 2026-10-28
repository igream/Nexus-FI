# Nexus FI — Servicio de Ingesta, Clasificación y Vectorización

Este módulo implementa el paquete de trabajo **WBS 1.3.2** (*Flujo de procesamiento Automatizado de Ingesta y Embeddings*) del proyecto **Nexus FI** (Facultad de Ingeniería — UAEMéx).

## Características Principales

1. **Extracción Dual (Nativa + OCR):**
   * Extrae texto digital nativo con `PyMuPDF`.
   * Si detecta páginas escaneadas o imágenes sin texto (como los planes de estudio y normativas antiguas), activa automáticamente OCR local (`RapidOCR` sobre ONNX) o en la nube (`AWS Textract`).
2. **Normalización y Reparación de Caracteres:**
   * Corrige artefactos de codificación habituales en documentos de la UAEMéx (acentos, diacríticos y ligaduras).
3. **Clasificador Multitipo con Metadatos:**
   * Clasifica automáticamente los documentos en: `normativa`, `planes_estudio`, `becas`, `tramites`, `instalaciones` y `coordinacion_ico`.
   * Asocia metadatos como carrera (`ICO` / `GENERAL_FI`), periodo de vigencia (`2026B`) y etiquetas.
4. **Chunking Estructural Context-Aware (RF08 & RF09):**
   * Segmenta en fragmentos de 500 a 800 tokens con 15% de solapamiento (`cl100k_base` con `tiktoken`).
   * Inyecta una cabecera de contexto en cada fragmento con el nombre del documento, sección, artículo y página, garantizando trazabilidad y citación obligatoria.
5. **Base Vectorial Serverless sobre S3 (LanceDB):**
   * Soporta almacenamiento columnar directo en buckets de Amazon S3 (`s3://...`) o carpetas locales (`./data/lancedb`).
   * Búsqueda por similitud coseno con calibración de umbral anti-alucinaciones $X_{base} = 0.52$ (**RF13**).

---

## Instalación

```bash
pip install -r requirements.txt
```

Copia el archivo de variables de entorno y ajusta tus credenciales:
```bash
cp .env.example .env
```

---

## Modos de Uso

### 1. Validación de Ingesta (Dry-Run / Sin costo de API)
Extrae, clasifica y segmenta todos los documentos sin invocar la API de OpenAI:
```bash
python -m nexus_ingestion.cli --input "Pre Procesados" --skip-embeddings
```

### 2. Ingesta y Vectorización Completa (Local)
Procesa los documentos y genera los vectores en la base local:
```bash
python -m nexus_ingestion.cli --input "Pre Procesados" --lancedb-uri "./data/lancedb"
```

### 3. Ingesta Directa a Amazon S3
Para subir los índices vectoriales a la nube:
```bash
python -m nexus_ingestion.cli --input "Pre Procesados" --lancedb-uri "s3://nexus-fi-vectors/lancedb"
```

---

## Estructura del Módulo

```
nexus_ingestion/
├── config.py                 # Configuración y variables de entorno
├── classifier.py             # Clasificador semántico y de metadatos
├── chunker.py                # Segmentador estructural (RF08)
├── embedder.py               # Cliente de embeddings (text-embedding-3-small)
├── vector_store.py           # Gestor LanceDB / S3 Vectors (RF13)
├── pipeline.py               # Orquestador del flujo de ingesta
├── cli.py                    # Punto de entrada CLI
├── extractors/
│   ├── text_normalizer.py    # Limpieza Unicode y reparación de acentos
│   ├── ocr_engine.py         # Motores OCR (RapidOCR y AWS Textract)
│   ├── pdf_extractor.py      # Extractor híbrido de PDFs
│   └── html_extractor.py     # Extractor limpio para páginas web
└── requirements.txt          # Dependencias del servicio
```
