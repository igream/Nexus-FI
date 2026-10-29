import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
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

# Middlewares y utilidades de seguridad perimetral y control de cuotas (WBS 1.3.5 / WBS 1.4.2)
from core.security.ip_filter import IPFilterMiddleware, is_ip_in_perimeter, get_client_ip, AUTHORIZED_CIDRS
from core.security.rate_limiter import RateLimiterMiddleware, check_rate_limit

# Inicialización de la aplicación FastAPI
app = FastAPI(
    title="Nexus FI - API Asistente Inteligente RAG",
    description="Backend oficial de Nexus FI para la Facultad de Ingeniería (UAEMéx). "
                "Búsqueda semántica sobre LanceDB y generación aumentada por recuperación (RAG) "
                "con facturación y claves API segregadas para telemetría precisa de consumo.",
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

# Middlewares de control perimetral y límite de uso (Starlette ejecuta en orden LIFO)
# 1. RateLimiterMiddleware (WBS 1.4.2: 20 req/h, 60 req/d por huella de dispositivo)
# 2. IPFilterMiddleware (WBS 1.3.5: filtrado perimetral por CIDRs institucionales de la FI)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(IPFilterMiddleware)

# Rutas del sistema
LANCEDB_DIR = BASE_DIR / "data" / "lancedb"
FRONTEND_DIR = BASE_DIR / "frontend"

def mask_key(k: Optional[str]) -> str:
    if not k:
        return "No configurada"
    return k[:11] + "..." + k[-4:] if len(k) > 15 else "***"

# =============================================================================
# SEGREGACIÓN DE CLAVES API POR SERVICIO (MEDICIÓN DE CONSUMO INDEPENDIENTE)
# =============================================================================
KEY_EMBEDDINGS = os.getenv("OPENAI_API_KEY_EMBEDDINGS") or os.getenv("OPENAI_API_KEY", "")
KEY_CHAT_4O_MINI = (
    os.getenv("OPENAI_API_KEY_CHAT_4O_MINI")
    or os.getenv("OPENAI_API_KEY_CHAT")
    or os.getenv("OPENAI_API_KEY", "")
)
KEY_GPT6_LUNA = os.getenv("OPENAI_API_KEY_GPT6_LUNA", "")
KEY_GPT5_6_LUNA = os.getenv("OPENAI_API_KEY_GPT5_6_LUNA", "")

vector_store: Optional[LanceDBVectorStore] = None
embedder: Optional[TextEmbedder] = None

# Inicializar almacén vectorial LanceDB
try:
    if LANCEDB_DIR.exists():
        vector_store = LanceDBVectorStore(uri=str(LANCEDB_DIR), table_name="nexus_documents")
except Exception as e:
    print(f"[Aviso] No se pudo conectar a LanceDB en {LANCEDB_DIR}: {e}")

# Inicializar embedder con su clave exclusiva
if KEY_EMBEDDINGS:
    try:
        embedder = TextEmbedder(api_key=KEY_EMBEDDINGS)
    except Exception as e:
        print(f"[Aviso] Error al inicializar embedder exclusivo: {e}")

# Inicializar clientes de chat independientes por modelo
chat_clients: Dict[str, openai.OpenAI] = {}
if KEY_CHAT_4O_MINI:
    try:
        chat_clients["gpt-4o-mini"] = openai.OpenAI(api_key=KEY_CHAT_4O_MINI)
    except Exception as e:
        print(f"[Aviso] Error al inicializar cliente GPT-4o-mini: {e}")

if KEY_GPT6_LUNA:
    try:
        chat_clients["gpt-6-luna"] = openai.OpenAI(api_key=KEY_GPT6_LUNA)
    except Exception as e:
        print(f"[Aviso] Error al inicializar cliente GPT-6 Luna: {e}")

if KEY_GPT5_6_LUNA:
    try:
        chat_clients["gpt-5.6-luna"] = openai.OpenAI(api_key=KEY_GPT5_6_LUNA)
    except Exception as e:
        print(f"[Aviso] Error al inicializar cliente GPT-5.6 Luna: {e}")


# Esquemas Pydantic
class ChatRequest(BaseModel):
    query: str = Field(..., description="Pregunta del usuario sobre trámites, normativa o vida universitaria en FI UAEMéx")
    top_k: int = Field(default=4, ge=1, le=10, description="Número de fragmentos vectoriales a recuperar")
    category_filter: Optional[str] = Field(default=None, description="Filtrar por categoría documental")
    use_llm: bool = Field(default=True, description="Si es True, sintetiza la respuesta con LLM; si es False, devuelve fragmentos directos")
    model: Optional[str] = Field(default="gpt-4o-mini", description="Modelo generativo: 'gpt-4o-mini', 'gpt-6-luna', 'gpt-5.6-luna'")


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

def _get_device_id(request: Request) -> str:
    """Obtiene el identificador de dispositivo o sesión para control de cuotas."""
    return (
        request.headers.get("X-Device-Fingerprint")
        or request.headers.get("X-Session-ID")
        or get_client_ip(request)
    )


@app.get("/health", summary="Health check público para balanceadores de carga AWS")
def public_health():
    """Endpoint público para health checks de AWS ALB/EC2 fuera de /api/."""
    return {"status": "healthy", "service": "Nexus FI", "environment": "cloud/aws"}


@app.get("/api/session/info", summary="Información de sesión y perímetro (WBS 1.3.5 / WBS 1.4.2)")
async def session_info(request: Request):
    """
    Retorna la IP del cliente, si está en el perímetro institucional de la FI,
    el device_id detectado y la cuota de consultas restante.
    """
    client_ip = get_client_ip(request)
    in_perimeter = is_ip_in_perimeter(client_ip)
    device_id = _get_device_id(request)
    quota = check_rate_limit(device_id)

    return {
        "ok": True,
        "client_ip": client_ip,
        "in_perimeter": in_perimeter,
        "device_id": device_id,
        "network_label": "Red Institucional FI UAEMéx" if in_perimeter else "Red Externa",
        "quota": {
            "hourly_limit": quota["hourly_limit"],
            "hourly_remaining": quota["hourly_remaining"],
            "daily_limit": quota["daily_limit"],
            "daily_remaining": quota["daily_remaining"],
        },
    }


@app.get("/api/status", summary="Estado del sistema (alias de session/info)")
async def status_endpoint(request: Request):
    """Alias de /api/session/info para compatibilidad."""
    return await session_info(request)


@app.get("/api/health")
def get_health():
    """Verifica el estado del servicio, base vectorial y segregación de claves API."""
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
        "segregated_api_keys": {
            "embeddings_service": {
                "configured": bool(KEY_EMBEDDINGS),
                "env_var": "OPENAI_API_KEY_EMBEDDINGS",
                "masked": mask_key(KEY_EMBEDDINGS),
                "purpose": "Cálculo de vectores semánticos (text-embedding-3-small, 1536d)",
            },
            "chat_4o_mini": {
                "configured": bool(KEY_CHAT_4O_MINI),
                "env_var": "OPENAI_API_KEY_CHAT_4O_MINI",
                "masked": mask_key(KEY_CHAT_4O_MINI),
                "purpose": "Generación RAG en producción (GPT-4o-mini)",
            },
            "chat_gpt6_luna": {
                "configured": bool(KEY_GPT6_LUNA),
                "env_var": "OPENAI_API_KEY_GPT6_LUNA",
                "masked": mask_key(KEY_GPT6_LUNA),
                "purpose": "Experimentación y benchmarking (Nexus FI GPT 6 Luna)",
            },
            "chat_gpt5_6_luna": {
                "configured": bool(KEY_GPT5_6_LUNA),
                "env_var": "OPENAI_API_KEY_GPT5_6_LUNA",
                "masked": mask_key(KEY_GPT5_6_LUNA),
                "purpose": "Experimentación y benchmarking (Nexus FI GPT 5.6 Luna)",
            },
        },
        "telemetry": {
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
    y generación aumentada por recuperación (RAG), garantizando segregación estricta de consumo.
    """
    start_time = time.time()
    user_query = req.query.strip()

    if not user_query:
        raise HTTPException(status_code=400, detail="La consulta no puede estar vacía.")

    if not vector_store:
        raise HTTPException(status_code=503, detail="Base de datos vectorial no inicializada.")

    current_embedder = embedder
    if not current_embedder and KEY_EMBEDDINGS:
        current_embedder = TextEmbedder(api_key=KEY_EMBEDDINGS)

    if not current_embedder:
        raise HTTPException(
            status_code=500,
            detail="No se encuentra configurada OPENAI_API_KEY_EMBEDDINGS para calcular el vector de búsqueda.",
        )

    # 1. Generar vector de consulta (Facturado a OPENAI_API_KEY_EMBEDDINGS)
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
                "key_used_embeddings": mask_key(KEY_EMBEDDINGS),
                "key_used_chat": "none",
            },
        )

    # 3. Selección de cliente y modelo LLM para inferencia (Facturado a la clave de Chat elegida)
    target_model = req.model or "gpt-4o-mini"
    chosen_client = chat_clients.get(target_model) or chat_clients.get("gpt-4o-mini")
    key_used_name = "OPENAI_API_KEY_CHAT_4O_MINI"
    key_used_masked = mask_key(KEY_CHAT_4O_MINI)

    if target_model in ("gpt-6-luna", "luna-6") and "gpt-6-luna" in chat_clients:
        chosen_client = chat_clients["gpt-6-luna"]
        key_used_name = "OPENAI_API_KEY_GPT6_LUNA"
        key_used_masked = mask_key(KEY_GPT6_LUNA)
    elif target_model in ("gpt-5.6-luna", "luna-5.6") and "gpt-5.6-luna" in chat_clients:
        chosen_client = chat_clients["gpt-5.6-luna"]
        key_used_name = "OPENAI_API_KEY_GPT5_6_LUNA"
        key_used_masked = mask_key(KEY_GPT5_6_LUNA)

    t0_llm = time.time()
    generated_answer = ""
    model_name = "direct_synthesis"

    if req.use_llm and chosen_client:
        model_name = "gpt-4o-mini"  # Modelo real OpenAI para ejecución
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
            chat_completion = chosen_client.chat.completions.create(
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
            print(f"[Error LLM]: {e}. Empleando síntesis directa.")
            model_name = "direct_synthesis_fallback"
            primary_chunk = results[0]
            generated_answer = (
                f"Con base en el documento oficial '{primary_chunk['documento']}' "
                f"({primary_chunk['categoria']}):\n\n{primary_chunk['text']}"
            )
    else:
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
            "billing_segregation": {
                "embeddings_account": f"OPENAI_API_KEY_EMBEDDINGS ({mask_key(KEY_EMBEDDINGS)})",
                "chat_account": f"{key_used_name} ({key_used_masked})",
            },
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
