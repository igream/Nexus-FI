"""
api/routes.py — Endpoints de la API Nexus FI
Facultad de Ingeniería UAEMéx — Equipo 404
"""
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.security.ip_filter import get_client_ip, is_ip_in_perimeter
from core.security.rate_limiter import check_rate_limit

router = APIRouter()


def _get_device_id(request: Request) -> str:
    """Obtiene el device_id del request siguiendo el orden de prioridad."""
    return (
        request.headers.get("X-Device-Fingerprint")
        or request.headers.get("X-Session-ID")
        or get_client_ip(request)
    )


@router.get("/session/info", summary="Información de sesión y perímetro")
async def session_info(request: Request) -> JSONResponse:
    """
    Retorna la IP del cliente, si está en el perímetro institucional,
    el device_id detectado y la cuota de consultas restante.
    """
    client_ip = get_client_ip(request)
    in_perimeter = is_ip_in_perimeter(client_ip)
    device_id = _get_device_id(request)
    quota = check_rate_limit(device_id)

    return JSONResponse(
        content={
            "ok": True,
            "client_ip": client_ip,
            "in_perimeter": in_perimeter,
            "device_id": device_id,
            "perimeter_networks": [
                "172.17.18.0/24",
                "148.215.12.0/24",
                "148.215.18.0/24",
                "148.215.30.0/24",
                "148.215.31.0/24",
            ],
            "quota": {
                "hourly_limit": quota["hourly_limit"],
                "hourly_remaining": quota["hourly_remaining"],
                "daily_limit": quota["daily_limit"],
                "daily_remaining": quota["daily_remaining"],
            },
        }
    )


@router.get("/status", summary="Estado del sistema (alias de session/info)")
async def status(request: Request) -> JSONResponse:
    """Alias de /api/session/info para compatibilidad."""
    return await session_info(request)


@router.post("/chat", summary="Consulta al motor de inferencia Nexus FI")
async def chat(request: Request) -> JSONResponse:
    """
    Endpoint simulado de chat con el motor de inferencia.
    En producción este endpoint llama al modelo Gemini vía API.
    """
    body: dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        pass

    query = body.get("query", body.get("message", ""))

    return JSONResponse(
        content={
            "ok": True,
            "response": (
                f"[Nexus FI — Simulado] Respuesta para: '{query}'. "
                "En producción, esta respuesta es generada por el modelo Gemini "
                "a través de la API de inferencia."
            ),
            "query": query,
            "model": "gemini-1.5-pro (simulado)",
            "wbs": ["1.3.5", "1.4.2"],
        }
    )


@router.post("/search", summary="Búsqueda semántica en el repositorio documental")
async def search(request: Request) -> JSONResponse:
    """Endpoint simulado de búsqueda semántica."""
    body: dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        pass

    query = body.get("query", "")

    return JSONResponse(
        content={
            "ok": True,
            "query": query,
            "results": [
                {
                    "title": "Reglamento de Titulación — FI UAEMéx",
                    "score": 0.92,
                    "excerpt": "Resultado simulado del corpus documental...",
                },
                {
                    "title": "Plan de Estudios 2024 — Ingeniería en Computación",
                    "score": 0.87,
                    "excerpt": "Resultado simulado del corpus documental...",
                },
            ],
            "total": 2,
        }
    )


@router.post("/reindex", summary="Reindexar el corpus documental")
async def reindex(request: Request) -> JSONResponse:
    """Endpoint simulado de reindexación del corpus."""
    job_id = str(uuid.uuid4())
    return JSONResponse(
        content={
            "ok": True,
            "job_id": job_id,
            "status": "queued",
            "message": "Reindexación programada. El proceso tomará aproximadamente 5 minutos.",
        }
    )


@router.post("/upload", summary="Subir documento al corpus")
async def upload(request: Request) -> JSONResponse:
    """Endpoint simulado de carga de documentos."""
    doc_id = str(uuid.uuid4())
    return JSONResponse(
        content={
            "ok": True,
            "doc_id": doc_id,
            "status": "received",
            "message": "Documento recibido. Será procesado e indexado en los próximos minutos.",
        }
    )
