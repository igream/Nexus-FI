import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import openai

# Cargar variables de entorno desde .env en la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from nexus_ingestion.embedder import TextEmbedder
from nexus_ingestion.vector_store import LanceDBVectorStore

# Inicialización de la aplicación FastAPI
app = FastAPI(
    title="Nexus FI - API Asistente Inteligente RAG",
    description="Backend oficial de Nexus FI para la Facultad de Ingeniería (UAEMéx). "
                "Búsqueda semántica sobre LanceDB y generación aumentada por recuperación (RAG).",
    version="0.1.0-alpha",
)

# Configuración de CORS para permitir consumo desde cualquier origen en desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar almacén vectorial y embedder
LANCEDB_DIR = BASE_DIR / "data" / "lancedb"
FRONTEND_DIR = BASE_DIR / "frontend"

vector_store: Optional[LanceDBVectorStore] = None
embedder: Optional[TextEmbedder] = None
openai_client: Optional[openai.OpenAI] = None

# Intentar inicializar componentes al arrancar
try:
    if LANCEDB_DIR.exists():
        vector_store = LanceDBVectorStore(uri=str(LANCEDB_DIR), table_name="nexus_documents")
except Exception as e:
    print(f"[Aviso] No se pudo conectar a LanceDB en {LANCEDB_DIR}: {e}")

api_key = os.getenv("OPENAI_API_KEY", "")
if api_key:
    try:
        embedder = TextEmbedder(api_key=api_key)
        openai_client = openai.OpenAI(api_key=api_key)
    except Exception as e:
        print(f"[Aviso] Error al inicializar cliente OpenAI: {e}")


# Esquemas Pydantic
class ChatRequest(BaseModel):
    query: str = Field(..., description="Pregunta del usuario sobre trámites, normativa o vida universitaria en FI UAEMéx")
    top_k: int = Field(default=4, ge=1, le=10, description="Número de fragmentos vectoriales a recuperar")
    category_filter: Optional[str] = Field(default=None, description="Filtrar por categoría documental")
    use_llm: bool = Field(default=True, description="Si es True, sintetiza la respuesta con LLM; si es False, devuelve los fragmentos directos")


class CitationItem(BaseModel):
    documento: str
    categoria: str
    subcategoria: Optional[str] = ""
    carrera: Optional[str] = ""
    articulo: Optional[str] = ""
    pagina: Optional[str] = ""
    similarity: float
    chunk_id: str
    snippet: str


class ChatResponse(BaseModel):
    query: str
    answer: str
    found: bool
    citations: List[CitationItem]
    telemetry: Dict[str, Any]


# -----------------------------------------------------------------------------
# Endpoints de la API
# -----------------------------------------------------------------------------

@app.get("/api/health")
def get_health():
    """Verifica el estado del servicio, base vectorial y conectividad externa."""
    total_chunks = 0
    vdb_status = "offline"
    if vector_store:
        try:
            total_chunks = vector_store.count()
            vdb_status = "online" if total_chunks > 0 else "empty"
        except Exception as e:
            vdb_status = f"error: {e}"

    return {
        "status": "healthy",
        "service": "Nexus FI RAG Backend",
        "version": "0.1.0-alpha",
        "environment": "development/local",
        "vector_database": {
            "engine": "LanceDB",
            "status": vdb_status,
            "total_vectors": total_chunks,
            "table": "nexus_documents",
            "path": str(LANCEDB_DIR),
        },
        "telemetry": {
            "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
            "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
            "aws_configured": bool(os.getenv("AWS_ACCESS_KEY_ID")),
            "aws_region": os.getenv("AWS_REGION", "us-east-1"),
        },
    }


@app.get("/api/stats")
def get_stats():
    """Devuelve métricas institucionales y estadísticas del corpus procesado."""
    total_chunks = vector_store.count() if vector_store else 0
    return {
        "facultad": "Facultad de Ingeniería - UAEMéx",
        "carrera": "Ingeniería en Computación (ICO)",
        "equipo": "Equipo 404 (Nexus FI)",
        "corpus": {
            "total_documents": 211,
            "categories_count": 6,
            "categories": [
                "01_Normativa_Universitaria",
                "02_Planes_de_Estudio_ICO",
                "03_Becas_y_Apoyos",
                "04_Tramites_y_Servicios",
                "05_Instalaciones_y_Servicios",
                "06_Coordinacion_ICO",
            ],
            "total_indexed_chunks": total_chunks,
            "embedding_model": "text-embedding-3-small (1536 dimensiones)",
            "similarity_threshold_rf13": 0.52,
        },
        "service_level": {
            "target_latency": "< 1000 ms",
            "target_availability": "99.5%",
            "citations_requirement_rf09": "Estricto (título, categoría, artículo y página)",
        },
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """
    Atiende consultas institucionales mediante búsqueda semántica vectorial (LanceDB)
    y generación aumentada por recuperación (RAG).
    """
    start_time = time.time()
    user_query = req.query.strip()

    if not user_query:
        raise HTTPException(status_code=400, detail="La consulta no puede estar vacía.")

    if not vector_store:
        raise HTTPException(status_code=503, detail="Base de datos vectorial no inicializada.")

    current_embedder = embedder
    if not current_embedder:
        api_k = os.getenv("OPENAI_API_KEY", "")
        if api_k:
            current_embedder = TextEmbedder(api_key=api_k)

    if not current_embedder:
        raise HTTPException(
            status_code=500,
            detail="No se encuentra configurada OPENAI_API_KEY para calcular el vector de búsqueda.",
        )

    # 1. Generar vector de consulta
    try:
        t0_emb = time.time()
        query_vector = current_embedder.embed_query(user_query)
        emb_latency_ms = round((time.time() - t0_emb) * 1000, 2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al vectorizar la consulta: {e}")

    # 2. Búsqueda por similitud semántica con umbral RF13 (0.52)
    filter_dict = {}
    if req.category_filter:
        filter_dict["categoria"] = req.category_filter

    t0_search = time.time()
    results = vector_store.search(
        query_vector=query_vector,
        top_k=req.top_k,
        similarity_threshold=0.52,
        filter_dict=filter_dict if filter_dict else None,
    )
    search_latency_ms = round((time.time() - t0_search) * 1000, 2)

    citations: List[CitationItem] = []
    for r in results:
        snippet_text = r["text"]
        if len(snippet_text) > 300:
            snippet_text = snippet_text[:297] + "..."

        citations.append(
            CitationItem(
                documento=r["documento"],
                categoria=r["categoria"],
                subcategoria=r.get("subcategoria", ""),
                carrera=r.get("carrera", ""),
                articulo=r.get("articulo", ""),
                pagina=r.get("pagina", ""),
                similarity=float(r["similarity"]),
                chunk_id=r["id"],
                snippet=snippet_text,
            )
        )

    # Si no hubo fragmentos que superen el umbral RF13
    if not results:
        total_latency_ms = round((time.time() - start_time) * 1000, 2)
        fallback_msg = (
            "No se encontró información oficial suficiente en el corpus normativo y operativo "
            "de la Facultad de Ingeniería (UAEMéx) para responder a tu consulta con alta certeza. "
            "Te sugerimos acudir directamente a la Coordinación de ICO (Edificio C) o consultar "
            "el portal institucional oficial de la UAEMéx."
        )
        return ChatResponse(
            query=user_query,
            answer=fallback_msg,
            found=False,
            citations=[],
            telemetry={
                "total_latency_ms": total_latency_ms,
                "embed_latency_ms": emb_latency_ms,
                "search_latency_ms": search_latency_ms,
                "chunks_retrieved": 0,
                "model": "rule-based fallback",
            },
        )

    # 3. Formular respuesta con LLM o síntesis contextual
    t0_llm = time.time()
    generated_answer = ""
    model_name = "direct_synthesis"

    if req.use_llm and openai_client:
        model_name = "gpt-4o-mini"
        context_blocks = []
        for idx, res in enumerate(results, start=1):
            doc_info = f"Documento: {res['documento']} | Categoría: {res['categoria']}"
            if res.get("articulo"):
                doc_info += f" | {res['articulo']}"
            if res.get("pagina"):
                doc_info += f" | Págs: {res['pagina']}"
            context_blocks.append(f"--- FUENTE [{idx}]: {doc_info} ---\n{res['text']}")

        joined_context = "\n\n".join(context_blocks)

        system_prompt = (
            "Eres Nexus FI, el asistente virtual inteligente de la Facultad de Ingeniería de la Universidad "
            "Autónoma del Estado de México (UAEMéx), especializado en Ingeniería en Computación.\n"
            "Tu misión es orientar con claridad, precisión y empatía a la comunidad estudiantil y académica.\n\n"
            "REGLAS OBLIGATORIAS:\n"
            "1. Responde de forma directa, concisa y estructurada basándote EXCLUSIVAMENTE en el siguiente contexto oficial.\n"
            "2. Cita de forma explícita el documento o reglamento fuente cuando menciones requisitos, trámites o plazos (cumpliendo con RF09).\n"
            "3. No inventes procedimientos ni especules si el contexto no lo especifica.\n"
            "4. Si la consulta involucra trámites presenciales, menciona las áreas correspondientes (p. ej. Coordinación de ICO, Subdirección Académica, Control Escolar).\n"
        )

        user_content = f"Contexto Oficial:\n{joined_context}\n\nPregunta del Estudiante: {user_query}"

        try:
            chat_completion = openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_tokens=600,
            )
            generated_answer = chat_completion.choices[0].message.content or ""
        except Exception as e:
            # Fallback en caso de fallo del LLM
            print(f"[Error LLM]: {e}. Empleando síntesis directa.")
            model_name = "direct_synthesis_fallback"
            primary_chunk = results[0]
            generated_answer = (
                f"Con base en el documento oficial '{primary_chunk['documento']}' "
                f"({primary_chunk['categoria']}):\n\n{primary_chunk['text']}"
            )
    else:
        # Síntesis directa sin llamada a LLM
        primary_chunk = results[0]
        generated_answer = (
            f"Información localizada en '{primary_chunk['documento']}' "
            f"({primary_chunk['categoria']}):\n\n{primary_chunk['text']}"
        )

    llm_latency_ms = round((time.time() - t0_llm) * 1000, 2)
    total_latency_ms = round((time.time() - start_time) * 1000, 2)

    return ChatResponse(
        query=user_query,
        answer=generated_answer,
        found=True,
        citations=citations,
        telemetry={
            "total_latency_ms": total_latency_ms,
            "embed_latency_ms": emb_latency_ms,
            "search_latency_ms": search_latency_ms,
            "llm_latency_ms": llm_latency_ms,
            "chunks_retrieved": len(results),
            "top_similarity": results[0]["similarity"],
            "model": model_name,
        },
    )


# -----------------------------------------------------------------------------
# Servir Archivos Estáticos del Frontend PWA
# -----------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "Frontend index.html no encontrado."}

    @app.get("/dashboard")
    @app.get("/dashboard.html")
    def serve_dashboard():
        dash_file = FRONTEND_DIR / "dashboard.html"
        if dash_file.exists():
            return FileResponse(str(dash_file))
        return {"message": "Frontend dashboard.html no encontrado."}

    # Atajos para archivos raíz del frontend (styles.css, app.js, manifest, favicon, etc.)
    @app.get("/styles.css")
    def serve_styles():
        return FileResponse(str(FRONTEND_DIR / "styles.css"))

    @app.get("/app.js")
    def serve_app_js():
        return FileResponse(str(FRONTEND_DIR / "app.js"))

    @app.get("/service-worker.js")
    def serve_sw():
        return FileResponse(str(FRONTEND_DIR / "service-worker.js"))

    @app.get("/manifest.webmanifest")
    def serve_manifest():
        return FileResponse(str(FRONTEND_DIR / "manifest.webmanifest"))

    @app.get("/assets/{asset_name:path}")
    def serve_assets(asset_name: str):
        asset_path = FRONTEND_DIR / "assets" / asset_name
        if asset_path.exists():
            return FileResponse(str(asset_path))
        raise HTTPException(status_code=404, detail="Recurso no encontrado.")
