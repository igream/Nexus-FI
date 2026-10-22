# Nexus FI — Asistente Virtual Inteligente (RAG)
### Facultad de Ingeniería · Universidad Autónoma del Estado de México (UAEMéx)
**Licenciatura en Ingeniería en Computación | Equipo 404**  
**Product Manager:** Fernando Azuara Ibarra (`@igream`)

---

## 📌 Descripción General

**Nexus FI** es un sistema de asistencia virtual inteligente basado en **Generación Aumentada por Recuperación (RAG)**, diseñado para orientar de manera ágil, precisa y empática a la comunidad universitaria de la Facultad de Ingeniería (UAEMéx). 

El sistema responde consultas sobre trámites escolares, opciones de titulación, servicio social, becas, programas académicos y normativa universitaria, fundamentando cada respuesta exclusivamente en el acervo institucional oficial verificado y citando de forma explícita las fuentes documentales.

```
       _   _ _____ _   _ _   _ ____    _____ ___ 
      | \ | | ____| \ | | | | / ___|  |  ___|_ _|
      |  \| |  _| |  \| | | | \___ \  | |_   | | 
      | |\  | |___| |\  | |_| |___) | |  _|  | | 
      |_| \_|_____|_| \_|\___/|____/  |_|   |___|
      
   Asistente Virtual Inteligente con Búsqueda Semántica RAG
      Facultad de Ingeniería - UAEMéx | Equipo 404
```

---

## 🏛️ Arquitectura del Sistema

El proyecto integra una arquitectura desacoplada, reproducible y lista para despliegue en entornos locales o de nube (AWS):

```mermaid
flowchart TD
    subgraph Cliente["Frontend PWA"]
        UI[Chat Web & Dashboard PWA\nHTML5 / CSS3 / JS Vanilla]
    end

    subgraph BackendAPI["Backend REST & Inferencia"]
        SRV[FastAPI Server\nbackend/app.py]
        TELEMETRY[Módulo DT-10\nTelemetría & Seguridad]
        ROUTER[Router de Chat & Salud\n/api/chat | /api/health | /api/stats]
    end

    subgraph RAGCore["Motor RAG & Embeddings"]
        EMBED[TextEmbedder\ntext-embedding-3-small 1536d]
        LLM[OpenAI GPT-4o-mini / Fallback]
    end

    subgraph Storage["Almacenamiento & Vectores"]
        VDB[(LanceDB Vector Store\n3,977 fragmentos)]
        CORPUS[(Corpus Procesado\n211 documentos en Markdown/JSON)]
        S3[(AWS S3 Bucket\nRespaldos & PDFs Crudos)]
    end

    UI -->|HTTP / JSON| ROUTER
    ROUTER --> TELEMETRY
    ROUTER --> EMBED
    EMBED -->|Vector de Consulta| VDB
    VDB -->|Top-K Chunks + RF13 Sim >= 0.52| ROUTER
    ROUTER -->|Contexto Verificado + RF09| LLM
    LLM -->|Respuesta con Citas Oficiales| UI
    STORAGE_SYNC[Scripts de Ingestión] -.-> CORPUS
    STORAGE_SYNC -.-> VDB
    VDB -.->|Sincronización Cloud| S3
```

---

## 📁 Estructura del Repositorio

```
Nexus-FI/
├── backend/                               # Servidor API REST y herramientas de conectividad
│   ├── app.py                             # Aplicación FastAPI (endpoints RAG y archivos estáticos)
│   └── config_api/                        # Scripts de diagnóstico, auditoría y modelos
│       ├── auditor_seguridad_api.py       # Auditor de secretos y control de versiones
│       ├── probar_conexion_api.py         # Diagnóstico de API Keys (OpenAI / Gemini)
│       ├── modelos_soportados.json        # Catálogo de modelos de lenguaje compatibles
│       └── INSTRUCCIONES_Y_PROCEDIMIENTOS1.md
│
├── frontend/                              # Interfaz Web Progresiva (PWA) para estudiantes
│   ├── index.html                         # Vista interactiva del chatbot institucional
│   ├── dashboard.html                     # Tablero de métricas y telemetría de uso
│   ├── styles.css                         # Hoja de estilos con identidad institucional UAEMéx
│   ├── app.js                             # Lógica de consumo de API REST con fallback local
│   ├── manifest.webmanifest               # Manifiesto PWA para instalación móvil
│   ├── service-worker.js                  # Manejo de caché y funcionamiento sin conexión
│   └── assets/                            # Logotipos e isotipos oficiales
│
├── nexus_ingestion/                       # Biblioteca modular de ingesta, OCR y base vectorial
│   ├── chunker.py                         # Segmentador estructural con control de solapamiento
│   ├── cleaner.py                         # Limpieza de textos y normalización UTF-8
│   ├── embedder.py                        # Generador de embeddings con reintentos y jitter
│   ├── extractor.py                       # Extractor híbrido de PDFs (digital y OCR local)
│   ├── pipeline.py                        # Orquestador del flujo ETL de procesamiento
│   └── vector_store.py                    # Gestor LanceDB con filtrado de metadatos y RF13
│
├── Procesados/                            # Corpus canónico oficial segmentado y estructurado
│   ├── 01_Normativa_Universitaria/        # Reglamentos, estatutos y acuerdos generales UAEMéx
│   ├── 02_Planes_de_Estudio_ICO/          # Malla curricular, materias y créditos de Computación
│   ├── 03_Becas_y_Apoyos/                 # Convocatorias de becas institucionales y federales
│   ├── 04_Tramites_y_Servicios/           # Servicio social, prácticas, titulación, reinscripciones
│   ├── 05_Instalaciones_y_Servicios/      # Laboratorios, biblioteca, cafetería, tutorías
│   ├── 06_Coordinacion_ICO/               # Información de contacto y avisos de la Coordinación
│   ├── corpus_chunks_para_embedding.jsonl # Dataset maestro (3,977 fragmentos con metadatos)
│   └── manifest.json                      # Catálogo y manifiesto de auditoría del corpus
│
├── docs/                                  # Documentación técnica y académica de entrega
│   ├── Documento Final Nexus FI.pdf       # Memoria y especificación de requisitos del proyecto
│   ├── ENTREGA_BASE_DATOS_VECTORIAL_NEXUS_FI.md # Manual técnico del vector store
│   └── plantilla_coordinacion_ico.md      # Plantilla normalizada para carga de trámites
│
├── scripts/                               # Scripts de automatización y procesamiento masivo
│   ├── vectorize_corpus.py                # Vectorización del dataset hacia LanceDB
│   ├── process_to_procesados.py           # Pipeline de OCR y extracción por lotes
│   └── finalize_procesados.py             # Normalización y exportación canónica JSONL
│
├── .env.example                           # Plantilla de variables de entorno para colaboradores
├── .gitignore                             # Reglas estrictas de exclusión de secretos y binarios
├── .dockerignore                          # Optimización para contenedores Docker
├── requirements.txt                       # Dependencias Python fijadas
├── main.py                                # Punto de entrada unificado (Servidor / CLI / Auditoría)
└── README.md                              # Documentación general del repositorio
```

---

## 📊 Especificaciones del Acervo y la Base Vectorial

El sistema opera sobre una base de datos vectorial de alta velocidad y mínima huella en disco:

| Parámetro | Valor Oficial | Especificación Requisito |
| :--- | :--- | :--- |
| **Documentos Canónicos** | 211 documentos limpios | Cobertura integral FI UAEMéx |
| **Categorías Temáticas** | 6 directorios normalizados | Organización institucional |
| **Total de Fragmentos** | 3,977 chunks | Cumplimiento estricto **RF08** |
| **Rango de Tokens** | 132 a 674 tokens (promedio 338) | Min: 100, Target: 650, Max: 800 |
| **Solapamiento (Overlap)** | ~15% (100 tokens) | Preservación de contexto inter-párrafo |
| **Motor Vectorial** | **LanceDB** (`data/lancedb/`) | Serverless, formato columnar Apache Arrow |
| **Modelo de Embeddings** | `text-embedding-3-small` | 1,536 dimensiones densas |
| **Métrica de Distancia** | Distancia Coseno | Similitud = $1 - \text{distancia}$ |
| **Umbral Anti-Alucinación** | $X_{base} \ge 0.52$ | Requisito **RF13** |
| **Citas Institucionales** | Documento, Categoría, Artículo y Pág | Requisito **RF09** |

---

## 🔒 Política de Ciberseguridad y Credenciales

El repositorio implementa una estricta política de protección de credenciales y auditoría previa a cualquier despliegue:

1. **Aislamiento Total de Secretos:** El archivo `.env` se encuentra protegido por `.gitignore` y **nunca** se sube a GitHub.
2. **Plantilla Pública:** Se incluye `.env.example` con la lista de variables requeridas para que cualquier integrante pueda levantar el entorno.
3. **Auditor Automático:** El comando `python main.py --audit` escanea todo el código fuente en busca de cadenas sensibles antes de cada commit.
4. **Exclusión de Binarios:** Los PDFs crudos de gran tamaño (`Pre Procesados/`, ~243 MB) y la base binaria (`data/`, ~58 MB) no saturan el árbol de Git; su sincronización en producción se efectúa hacia Amazon S3.

---

## 🚀 Guía de Instalación y Uso

### 1. Clonar el Repositorio y Crear Entorno Virtual
```bash
git clone https://github.com/igream/Nexus-FI.git
cd Nexus-FI

python -m venv venv
# En Windows:
.\venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate
```

### 2. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno
Copia la plantilla y coloca tu clave de API:
```bash
copy .env.example .env
```
Edita `.env`:
```env
OPENAI_API_KEY=sk-proj-tu-clave-aqui
```

### 4. Ejecución del Sistema

#### A) Iniciar Servidor Web y API REST (Predeterminado)
```bash
python main.py --serve
```
- **Interfaz Web de Chat:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Panel de Métricas:** [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
- **Documentación Interactiva Swagger:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

#### B) Búsqueda Semántica desde Terminal (CLI)
```bash
python main.py --search "¿Cuáles son los requisitos para liberar el servicio social?"
```

#### C) Diagnóstico de Seguridad y Telemetría (DT-10)
```bash
python main.py --telemetry
```

#### D) Auditoría de Secretos y Repositorio
```bash
python main.py --audit
```

---

## 🔌 Referencia de la API REST

### `GET /api/health`
Verifica el estado del servicio, tabla vectorial e integraciones.
```json
{
  "status": "healthy",
  "service": "Nexus FI RAG Backend",
  "version": "0.1.0-alpha",
  "vector_database": {
    "engine": "LanceDB",
    "status": "online",
    "total_vectors": 3977,
    "table": "nexus_documents"
  },
  "telemetry": {
    "openai_configured": true,
    "gemini_configured": false,
    "aws_configured": false
  }
}
```

### `GET /api/stats`
Métricas institucionales del acervo procesado.
```json
{
  "total_documents": 211,
  "categories_count": 6,
  "total_indexed_chunks": 3977,
  "embedding_model": "text-embedding-3-small (1536 dimensiones)",
  "similarity_threshold_rf13": 0.52
}
```

### `POST /api/chat`
Endpoint principal para resolución de dudas con búsqueda semántica y citas RF09.
**Cuerpo de la petición (JSON):**
```json
{
  "query": "¿Cuántas opciones de titulación existen para Ingeniería en Computación?",
  "top_k": 4,
  "use_llm": true
}
```
**Respuesta:**
```json
{
  "query": "¿Cuántas opciones de titulación existen...",
  "answer": "De acuerdo con el Reglamento de Estudios Profesionales de la UAEMéx, existen 8 modalidades oficiales de titulación...",
  "found": true,
  "citations": [
    {
      "documento": "reglamento_estudios_profesionales.md",
      "categoria": "01_Normativa_Universitaria",
      "articulo": "Artículo 85",
      "similarity": 0.74,
      "snippet": "..."
    }
  ],
  "telemetry": {
    "total_latency_ms": 680.4,
    "embed_latency_ms": 110.2,
    "search_latency_ms": 18.5,
    "llm_latency_ms": 551.7,
    "chunks_retrieved": 4,
    "model": "gpt-4o-mini"
  }
}
```

---

## 🔀 Mapa de Integración de Ramas

Este repositorio consolida en la rama `Integracion` (y posteriormente en `main`) el trabajo colaborativo distribuido:

| Rama Origen | Componente Aportado | Ubicación en el Proyecto Unificado |
| :--- | :--- | :--- |
| `feature/daniel-nexusfi-ui` | Interfaz PWA, estilos institucionales y dashboard | `frontend/` (conectado a la API REST) |
| `API` | Herramientas de diagnóstico, guías y auditor de seguridad | `backend/config_api/` |
| `BaseVectorial` | Ingestión OCR, dataset de 3,977 chunks y LanceDB | `nexus_ingestion/`, `Procesados/`, `data/` |
| `main` | Módulo de telemetría inicial DT-10 y especificaciones | Unificado y expandido en `main.py` |

---

## 👥 Equipo de Trabajo — Equipo 404

- **Fernando Azuara Ibarra** — *Product Manager & Integración de Sistemas*
- **Daniel Ávila** — *Desarrollo Frontend & Experiencia de Usuario (PWA)*
- **Ángel / Integrantes del Equipo 404** — *Configuración de API, Ciberseguridad y Telemetría*
- **Facultad de Ingeniería · UAEMéx** — *Periodo 2026*
