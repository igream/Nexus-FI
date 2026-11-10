import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import openai

# Cargar variables de entorno desde .env en la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from nexus_ingestion.embedder import TextEmbedder
from nexus_ingestion.vector_store import LanceDBVectorStore

# Límite de consultas por usuario registrado (WBS 1.4.2, SC-001)
from core.security.rate_limiter import RateLimiterMiddleware, get_user_id

# Inicio de sesión con número de cuenta (WBS 1.3.4, SC-001)
from core.auth import AuthMiddleware, init_db, obtener_usuario, requiere_admin, router as auth_router
from core.auth.store import ClavesNoConfiguradas

# Historial de conversaciones por usuario (plan de implementación, fase F1)
from core.chat import init_db as init_chat_db, router as chat_router
from core.chat import contexto, store as chat_store
from core.chat import modelos
from core.chat.modelos import MODELO_POR_DEFECTO, MODELO_REESCRITURA, MODELOS
from core.documentos import catalogo as catalogo_documentos, router as documentos_router

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

def _env_flag(name: str, default: bool) -> bool:
    """Lee una variable booleana de entorno (true/false, 1/0, si/no, on/off)."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "si", "sí", "yes", "on")


# Límite de consultas por usuario registrado: 20 por hora y 60 por día (WBS 1.4.2, SC-001).
# Activo por defecto; solo cuenta peticiones con usuario en sesión, así que surte efecto
# cuando exista el inicio de sesión (Avance 3). Se apaga con RATE_LIMIT_ENABLED=false.
# El control de acceso por IP se retiró con la SC-001 (ver etiqueta git pre-SC-001).
RATE_LIMIT_ENABLED = _env_flag("RATE_LIMIT_ENABLED", True)

if RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimiterMiddleware)
# Va después del limitador: Starlette ejecuta los middlewares al revés, así la sesión se lee primero
app.add_middleware(AuthMiddleware)


@app.middleware("http")
async def _revalidar_frontend(request: Request, call_next):
    """Las páginas, scripts y estilos se revalidan con el servidor en cada carga.

    Sin esta cabecera el navegador decide solo cuánto tiempo guardar cada archivo y puede
    seguir mostrando una versión vieja (por ejemplo en http://127.0.0.1:8000, que es otro
    sitio distinto de http://localhost:8000). Con no-cache, si el archivo no cambió el
    servidor responde 304 y no se vuelve a descargar.
    """
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        return response
    if "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-cache"
    # Si el navegador ya tiene esta misma versión, basta con un 304 sin contenido
    etag = response.headers.get("etag")
    if (request.method == "GET" and response.status_code == 200 and etag
            and etag in [e.strip() for e in request.headers.get("if-none-match", "").split(",")]):
        from fastapi.responses import Response as _Respuesta
        return _Respuesta(status_code=304, headers={"ETag": etag, "Cache-Control": response.headers["Cache-Control"]})
    return response

print(f"[Seguridad] Límite por usuario (WBS 1.4.2): {'ACTIVO' if RATE_LIMIT_ENABLED else 'apagado'}")

# Base de usuarios (data/usuarios.db). Si faltan las claves en .env, el login responde 503.
try:
    init_db()
    init_chat_db()
    print("[Seguridad] Inicio de sesión: base de usuarios e historial listos")
except ClavesNoConfiguradas as e:
    print(f"[Seguridad] Inicio de sesión sin configurar: {e}")

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documentos_router)
print(f"[Documentos] Catálogo del acervo: {len(catalogo_documentos().por_id)} documentos consultables desde las citas")


@app.exception_handler(ClavesNoConfiguradas)
async def _claves_no_configuradas(request: Request, exc: ClavesNoConfiguradas):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={"detail": "El inicio de sesión no está configurado en el servidor."})

# Rutas del sistema
LANCEDB_DIR = BASE_DIR / "data" / "lancedb"
FRONTEND_DIR = BASE_DIR / "frontend"

def mask_key(k: Optional[str]) -> str:
    if not k:
        return "No configurada"
    return k[:11] + "..." + k[-4:] if len(k) > 15 else "***"

# =============================================================================
# ALMACÉN DE TELEMETRÍA Y MÉTRICAS (WBS 1.3.4 - Daniel Aguilar Sánchez y Joan Alexis Ocaña Martínez)
# Los valores iniciales son una línea base de demostración; cada consulta real a /api/chat
# se acumula encima. El almacén vive en memoria y se reinicia al reiniciar el servidor.
# =============================================================================
user_metrics_store = {
    "total_queries": 1248,
    "total_latency_ms": 355680,
    "successful_queries": 1229,
    "hourly_queries": [45, 120, 230, 180, 160, 95],
    "hourly_latencies": [310, 280, 240, 350, 290, 285],
    "time_labels": ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00"],
    "topics": {
        "Evaluación Escolar": 35,
        "Servicio Social": 25,
        "Titulación": 20,
        "Becas": 12,
        "Otros": 8,
    },
}

admin_tokens_store = {
    "embeddings": {"tokens": 14250000, "cost": 2.85},
    "gpt4oMini": {"tokens": 8120000, "cost": 12.18},
    "luna6": {"tokens": 3400000, "cost": 9.18},
}

# Tarifas OpenAI (USD por token) para estimar el costo devengado de cada consulta
PRICE_EMBEDDING_PER_TOKEN = 0.02 / 1_000_000          # text-embedding-3-small
# Las tarifas, bolsas y cuotas de los modelos de chat viven en core/chat/modelos.py (F3)


def record_query_metrics(latency_ms: float, success: bool) -> None:
    """Acumula una consulta real en el almacén de métricas del dashboard de usuario."""
    user_metrics_store["total_queries"] += 1
    user_metrics_store["total_latency_ms"] += latency_ms
    if success:
        user_metrics_store["successful_queries"] += 1
    user_metrics_store["hourly_queries"][-1] += 1
    user_metrics_store["hourly_latencies"][-1] = int(latency_ms)


def record_token_usage(bucket: str, tokens: int, cost: float) -> None:
    """Suma tokens y costo devengado a la bolsa de facturación correspondiente."""
    admin_tokens_store[bucket]["tokens"] += tokens
    admin_tokens_store[bucket]["cost"] += cost


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

# Inicializar un cliente de chat por modelo de la tabla MODELOS, cada uno con su clave
# segregada (DT-10). Un modelo sin clave queda fuera y la API responde 503 si se elige.
chat_clients: Dict[str, openai.OpenAI] = {}
chat_key_names: Dict[str, str] = {}   # modelo -> variable de entorno de su clave
for _modelo, _cfg in MODELOS.items():
    _env = next((v for v in _cfg["env_clave"] if os.getenv(v)), None)
    if not _env:
        continue
    try:
        chat_clients[_modelo] = openai.OpenAI(api_key=os.getenv(_env))
        chat_key_names[_modelo] = _env
    except Exception as e:
        print(f"[Aviso] Error al inicializar el cliente de {_modelo}: {e}")


# Esquemas Pydantic
class ChatRequest(BaseModel):
    query: str = Field(..., description="Pregunta del usuario sobre trámites, normativa o vida universitaria en FI UAEMéx")
    top_k: int = Field(default=4, ge=1, le=10, description="Número de fragmentos vectoriales a recuperar")
    category_filter: Optional[str] = Field(default=None, description="Filtrar por categoría documental")
    use_llm: bool = Field(default=True, description="Si es True, sintetiza la respuesta con LLM; si es False, devuelve fragmentos directos")
    model: Optional[str] = Field(default=MODELO_POR_DEFECTO, description=f"Modelo generativo: {', '.join(MODELOS)}")
    conversation_id: Optional[str] = Field(default=None, max_length=64, description="Conversación a continuar; si no se envía se crea una nueva")


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
    doc_id: Optional[str] = None   # id del catálogo para abrir el documento (POST /api/documentos/{id}/enlace)


class ChatResponse(BaseModel):
    query: str
    answer: str
    found: bool
    citations: List[CitationItem]
    telemetry: Dict[str, Any]
    conversation_id: Optional[str] = None


# -----------------------------------------------------------------------------
# Endpoints de la API
# -----------------------------------------------------------------------------

@app.get("/health", summary="Health check público para balanceadores de carga AWS")
def public_health():
    """Endpoint público para health checks de AWS ALB/EC2 fuera de /api/."""
    return {"status": "healthy", "service": "Nexus FI", "environment": "cloud/aws"}


@app.get("/api/session/info", summary="Información de sesión y cuota del usuario (WBS 1.4.2)")
async def session_info(request: Request):
    """
    Indica si hay un usuario en sesión y, si lo hay, su cuota de consultas restante.
    Sin inicio de sesión, `user_id` y `quota` vienen en null.
    """
    user_id = get_user_id(request)
    quota = None
    quotas = None
    if user_id:
        quotas = {}
        for m, cfg in MODELOS.items():
            if not cfg["en_selector"]:
                continue
            try:
                q = cuota_modelo(user_id, m)
            except Exception as e:   # base sin configurar o sin historial: la info sigue saliendo
                print(f"[Cuota] No se pudo leer la cuota de {m}: {e}")
                quotas = None
                break
            q["available"] = m in chat_clients
            quotas[m] = q
        # Compatibilidad con el frontend anterior: `quota` es la del modelo por defecto
        quota = quotas.get(MODELO_POR_DEFECTO) if quotas else None

    usuario = None
    if user_id:
        try:
            usuario = obtener_usuario(user_id)
        except ClavesNoConfiguradas:
            usuario = None

    return {
        "ok": True,
        "rate_limit_enabled": RATE_LIMIT_ENABLED,
        "authenticated": bool(user_id),
        "user_id": user_id,
        "usuario": usuario,
        "quota": quota,
        "quotas": quotas,
        "default_model": MODELO_POR_DEFECTO,
    }


def cuota_modelo(user_id, modelo: str) -> Dict[str, Any]:
    """Cuota restante del usuario para un modelo, contada desde la tabla `mensajes` (F3)."""
    return modelos.estado_cuota(
        modelo, lambda desde: chat_store.contar_consultas(user_id, modelo, desde)
    )


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
                "purpose": "Modelo avanzado del selector (gpt-6-luna)",
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


@app.get("/api/v1/metrics/user-dashboard", summary="Métricas del dashboard de usuario (WBS 1.3.4)")
def get_user_dashboard_metrics():
    """Devuelve datos dinámicos para el dashboard de usuario."""
    total = max(user_metrics_store["total_queries"], 1)
    return {
        "totalQueries": user_metrics_store["total_queries"],
        "avgLatencyMs": int(user_metrics_store["total_latency_ms"] / total),
        "successRate": round(user_metrics_store["successful_queries"] / total * 100, 1),
        "timeSeriesLabels": user_metrics_store["time_labels"],
        "latencyData": user_metrics_store["hourly_latencies"],
        "queriesData": user_metrics_store["hourly_queries"],
        "topicLabels": list(user_metrics_store["topics"].keys()),
        "topicValues": list(user_metrics_store["topics"].values()),
        "dataSource": "baseline_demo + consultas reales en memoria",
    }


@app.get("/api/v1/admin/metrics", summary="Consumo de tokens y costos por clave segregada (WBS 1.3.4 / DT-10)")
def get_admin_metrics(request: Request):
    """Devuelve el consumo por clave segregada de OpenAI y los datos de infraestructura AWS. Solo administradores."""
    requiere_admin(request)
    return {
        "status": "healthy",
        "environment": "aws-docker",
        "openai": admin_tokens_store,
        # Valores de referencia capturados manualmente por el equipo Cloud DevOps
        # (Ángel Israel de la Cruz Martínez y Aarón Nevid Domínguez Fuentes); no se consultan en vivo a AWS.
        "aws": {
            "s3StorageGb": 18.4,
            "ec2Instances": "2x t3.medium",
            "ec2CpuUsage": 28,
            "bandwidthGb": 142.0,
            "availableCredit": 170.91,
        },
        "server": {
            "base_latency_seconds": 2.1,
            "active_connections": 45,
            "query_distribution": {"administrative": 60, "academic": 40},
            "proxy": "nginx",
        },
        "dataSource": "openai: baseline_demo + consumo real en memoria; aws/server: valores de referencia estáticos",
    }


def _guardar_turno(user_id, conv_id: Optional[str], pregunta: str, respuesta: str, **meta) -> Optional[str]:
    """Guarda la pregunta y la respuesta en el historial y regresa el id de la conversación.

    Si la conversación no existe todavía, la crea con la pregunta como título. Un fallo al
    guardar no debe dejar al usuario sin respuesta: se registra y se regresa None.
    """
    try:
        if not conv_id:
            conv_id = chat_store.crear_conversacion(user_id, pregunta)
        chat_store.agregar_mensaje(conv_id, user_id, "user", pregunta)
        chat_store.agregar_mensaje(conv_id, user_id, "assistant", respuesta, **meta)
        return conv_id
    except Exception as e:
        print(f"[Historial] No se pudo guardar la consulta: {e}")
        return None


def _reescribir_consulta(historial: List[Dict[str, str]], pregunta: str) -> Dict[str, Any]:
    """Convierte una pregunta de seguimiento en una autónoma con gpt-4o-mini (F2).

    Solo se usa cuando hay historial. Si no hay cliente, la llamada falla o la salida no sirve,
    regresa la pregunta original con `reescrita=None`: la consulta nunca se cae por esto.
    Los tokens se cargan a la bolsa de 4o-mini aunque responda otro modelo.
    """
    info: Dict[str, Any] = {"consulta": pregunta, "reescrita": None,
                            "tokens_in": None, "tokens_out": None, "latencia_ms": 0.0}
    cliente = chat_clients.get(MODELO_REESCRITURA)
    if not historial or not cliente:
        return info
    t0 = time.time()
    try:
        r = cliente.chat.completions.create(
            messages=contexto.mensajes_reescritura(historial, pregunta),
            **modelos.parametros_llamada(MODELO_REESCRITURA, max_salida=contexto.MAX_TOKENS_REESCRITURA,
                                         temperature=0),
        )
        usage = getattr(r, "usage", None)
        if usage:
            info["tokens_in"], info["tokens_out"] = usage.prompt_tokens, usage.completion_tokens
            record_token_usage(
                MODELOS[MODELO_REESCRITURA]["bolsa"],
                usage.prompt_tokens + usage.completion_tokens,
                modelos.costo(MODELO_REESCRITURA, usage.prompt_tokens, usage.completion_tokens),
            )
        reescrita = contexto.limpiar_reescritura(r.choices[0].message.content)
        if reescrita:
            info["consulta"], info["reescrita"] = reescrita, reescrita
    except Exception as e:
        print(f"[Contexto] No se pudo reescribir la consulta; se usa la original: {e}")
    info["latencia_ms"] = round((time.time() - t0) * 1000, 2)
    return info


def _telemetria_contexto(historial: List[Dict[str, str]], rw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "history_turns": len(historial) // 2,
        "rewritten_query": rw["reescrita"],
        "rewrite_latency_ms": rw["latencia_ms"],
        "rewrite_tokens": (rw["tokens_in"] or 0) + (rw["tokens_out"] or 0),
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest, request: Request):
    """
    Atiende consultas institucionales mediante búsqueda semántica vectorial (LanceDB)
    y generación aumentada por recuperación (RAG), garantizando segregación estricta de consumo.
    Requiere sesión iniciada (Authorization: Bearer <token>).
    """
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Inicia sesión para consultar.")

    start_time = time.time()
    user_query = req.query.strip()

    if not user_query:
        raise HTTPException(status_code=400, detail="La consulta no puede estar vacía.")

    # F3: el modelo lo elige el usuario y debe existir en la tabla MODELOS
    target_model = req.model or MODELO_POR_DEFECTO
    if target_model not in MODELOS:
        raise HTTPException(
            status_code=422,
            detail=f"Modelo no válido: '{target_model}'. Opciones: {', '.join(MODELOS)}.",
        )
    if req.use_llm and target_model not in chat_clients:
        raise HTTPException(
            status_code=503,
            detail=f"El modelo {MODELOS[target_model]['etiqueta']} no está disponible en este servidor.",
        )

    if req.conversation_id and not chat_store.es_de_usuario(user_id, req.conversation_id):
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")

    # F3: cuota independiente por modelo, contada desde la tabla `mensajes` (sobrevive a reinicios)
    if RATE_LIMIT_ENABLED:
        cuota = cuota_modelo(user_id, target_model)
        if not cuota["allowed"]:
            etiqueta = MODELOS[target_model]["etiqueta"]
            limites = f"{cuota['hourly_limit']} por hora"
            if cuota["daily_limit"]:
                limites += f" y {cuota['daily_limit']} por día"
            minutos = max(1, round(cuota["retry_after"] / 60))
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(cuota["retry_after"])},
                content={
                    "ok": False,
                    "error": "HTTP_429_TOO_MANY_REQUESTS",
                    "detail": (
                        f"Agotaste la cuota del modelo {etiqueta} ({limites}). "
                        f"Se libera una consulta en unos {minutos} min."
                    ),
                    "model": target_model,
                    "quota": cuota,
                    "wbs": "1.4.2",
                },
            )

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

    # 0. Contexto conversacional (F2): turnos previos y, si los hay, la pregunta reescrita
    #    como autónoma. La búsqueda usa la reescrita; el LLM final recibe la original.
    historial: List[Dict[str, str]] = []
    if req.conversation_id:
        try:
            historial = contexto.recortar_historial(
                chat_store.ultimos_mensajes(user_id, req.conversation_id, contexto.PARES_HISTORIAL * 2 + 1)
            )
        except Exception as e:
            print(f"[Contexto] No se pudo leer el historial; se responde sin él: {e}")
    rw = _reescribir_consulta(historial, user_query)
    search_query = rw["consulta"]
    meta_reescritura = {
        "modelo_cuota": target_model,
        "consulta_reescrita": rw["reescrita"],
        "reescritura_tokens_entrada": rw["tokens_in"],
        "reescritura_tokens_salida": rw["tokens_out"],
    }

    # 1. Generar vector de consulta (Facturado a OPENAI_API_KEY_EMBEDDINGS)
    try:
        t0_emb = time.time()
        query_vector = current_embedder.embed_query(search_query)
        emb_latency_ms = round((time.time() - t0_emb) * 1000, 2)
        # Estimación de tokens de embedding (~4 caracteres por token)
        emb_tokens = max(len(search_query) // 4, 1)
        record_token_usage("embeddings", emb_tokens, emb_tokens * PRICE_EMBEDDING_PER_TOKEN)
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
        query_text=search_query,   # acepta nombres propios poco comunes que aparecen tal cual
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
                doc_id=catalogo_documentos().id_de(r["documento"]),
                snippet=snippet_text,
            )
        )

    # Si no hubo fragmentos que superen el umbral RF13
    if not results:
        total_latency_ms = round((time.time() - start_time) * 1000, 2)
        record_query_metrics(total_latency_ms, success=False)
        fallback_msg = (
            "No se encontró información oficial suficiente en el corpus normativo y operativo "
            "de la Facultad de Ingeniería (UAEMéx) para responder a tu consulta con alta certeza. "
            "Te sugerimos acudir directamente a la Coordinación de ICO (Edificio C) o consultar "
            "el portal institucional oficial de la UAEMéx."
        )
        conv_id = _guardar_turno(
            user_id, req.conversation_id, user_query, fallback_msg,
            modelo="rule-based fallback", encontrado=False, latencia_ms=total_latency_ms,
            **meta_reescritura,
        )
        return ChatResponse(
            query=user_query,
            answer=fallback_msg,
            found=False,
            citations=[],
            conversation_id=conv_id,
            telemetry={
                "total_latency_ms": total_latency_ms,
                "embed_latency_ms": emb_latency_ms,
                "search_latency_ms": search_latency_ms,
                "chunks_retrieved": 0,
                "model": "rule-based fallback",
                "key_used_embeddings": mask_key(KEY_EMBEDDINGS),
                "key_used_chat": "none",
                **_telemetria_contexto(historial, rw),
            },
        )

    # 3. Cliente del modelo elegido (facturado a su clave segregada, DT-10)
    chosen_client = chat_clients.get(target_model)
    key_used_name = chat_key_names.get(target_model, "none")
    key_used_masked = mask_key(os.getenv(key_used_name, "")) if chosen_client else "none"

    t0_llm = time.time()
    generated_answer = ""
    tokens_in = tokens_out = None
    llm_cost = None
    model_name = "direct_synthesis"

    if req.use_llm and chosen_client:
        model_name = target_model
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
            "1. Responde de forma estructurada basándote EXCLUSIVAMENTE en el siguiente contexto oficial. "
            f"{MODELOS[target_model].get('estilo', '')}\n"
            "2. Cita de forma explícita el documento o reglamento fuente cuando menciones requisitos, trámites o plazos (cumpliendo con RF09).\n"
            "3. No inventes procedimientos ni especules si el contexto no lo especifica.\n"
            "4. Si la consulta involucra trámites presenciales, menciona las áreas correspondientes (p. ej. Coordinación de ICO, Subdirección Académica, Control Escolar).\n"
            "5. Solo afirma que una materia pertenece a un semestre o periodo si la fuente lo indica de forma explícita "
            "(p. ej. un horario del semestre o un encabezado claro con sus materias). Las listas o tablas desordenadas, "
            "como un mapa curricular cuyo texto quedó revuelto, NO prueban a qué semestre pertenece cada materia: "
            "no las uses para armar listas por semestre. Si no hay una fuente clara, dilo y sugiere consultar el plan de estudios "
            "o la Coordinación de ICO.\n"
            "6. Cuando presentes datos con varias columnas (horarios, grupos y profesores, requisitos comparados, montos), "
            "usa una tabla Markdown con fila de encabezado y fila separadora (| --- |).\n"
        )

        user_content = f"Contexto Oficial:\n{joined_context}\n\nPregunta del Estudiante: {user_query}"

        try:
            chat_completion = chosen_client.chat.completions.create(
                # Turnos previos (F2) entre el prompt de sistema y la pregunta actual
                messages=[
                    {"role": "system", "content": system_prompt},
                    *historial,
                    {"role": "user", "content": user_content},
                ],
                # Tope de salida, temperatura o esfuerzo de razonamiento según el modelo (F3)
                **modelos.parametros_llamada(target_model),
            )
            generated_answer = chat_completion.choices[0].message.content or ""
            if getattr(chat_completion.choices[0], "finish_reason", "") == "length":
                generated_answer = generated_answer.rstrip() + (
                    "\n\n*(La respuesta se recortó por su extensión. Haz una pregunta más específica "
                    "para ver el resto.)*"
                )
            usage = getattr(chat_completion, "usage", None)
            if usage:
                tokens_in, tokens_out = usage.prompt_tokens, usage.completion_tokens
                llm_cost = modelos.costo(target_model, tokens_in, tokens_out)
                record_token_usage(MODELOS[target_model]["bolsa"], tokens_in + tokens_out, llm_cost)
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
    record_query_metrics(total_latency_ms, success=True)

    conv_id = _guardar_turno(
        user_id, req.conversation_id, user_query, generated_answer,
        modelo=model_name,
        categoria_principal=results[0]["categoria"],
        encontrado=True,
        citas=[c.model_dump() for c in citations],
        tokens_entrada=tokens_in,
        tokens_salida=tokens_out,
        costo_usd=llm_cost,
        latencia_ms=total_latency_ms,
        **meta_reescritura,
    )

    return ChatResponse(
        query=user_query,
        answer=generated_answer,
        found=True,
        citations=citations,
        conversation_id=conv_id,
        telemetry={
            "total_latency_ms": total_latency_ms,
            "embed_latency_ms": emb_latency_ms,
            "search_latency_ms": search_latency_ms,
            "llm_latency_ms": llm_latency_ms,
            "chunks_retrieved": len(results),
            "top_similarity": results[0]["similarity"],
            "model": model_name,
            **_telemetria_contexto(historial, rw),
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
    @app.get("/index")
    @app.get("/index.html")
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

    @app.get("/admin-metrics")
    @app.get("/admin-metrics.html")
    def serve_admin_metrics():
        admin_file = FRONTEND_DIR / "admin-metrics.html"
        if admin_file.exists():
            return FileResponse(str(admin_file))
        return {"message": "Frontend admin-metrics.html no encontrado."}

    @app.get("/login")
    @app.get("/login.html")
    def serve_login():
        return FileResponse(str(FRONTEND_DIR / "login.html"))

    @app.get("/login.js")
    def serve_login_js():
        return FileResponse(str(FRONTEND_DIR / "login.js"))

    @app.get("/styles.css")
    def serve_styles():
        return FileResponse(str(FRONTEND_DIR / "styles.css"))

    @app.get("/app.js")
    def serve_app_js():
        return FileResponse(str(FRONTEND_DIR / "app.js"))

    @app.get("/markdown.js")
    def serve_markdown_js():
        return FileResponse(str(FRONTEND_DIR / "markdown.js"))

    # Visor de documentos del acervo sin PDF (fuentes piloto) o cuyo PDF no está en el servidor
    @app.get("/documento")
    def serve_documento():
        return FileResponse(str(FRONTEND_DIR / "documento.html"))

    @app.get("/documento.js")
    def serve_documento_js():
        return FileResponse(str(FRONTEND_DIR / "documento.js"))

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
