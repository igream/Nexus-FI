"""
Documentos del acervo consultables desde las citas del chat.

  POST /api/documentos/{id}/enlace    (con sesión) enlace firmado que vence en 10 minutos
  GET  /api/documentos/{id}/archivo   PDF original, solo con un enlace firmado vigente
  GET  /api/documentos/{id}/texto     (con sesión) texto del documento para el visor

El chat guarda la sesión en un token Bearer, que una pestaña nueva no puede enviar; por eso
el PDF se abre con un enlace firmado (HMAC con AUTH_JWT_SECRET) que solo obtiene quien tiene
sesión. Los documentos son normativa y avisos públicos de la UAEMéx: el enlace protege el
acceso a la aplicación, no un secreto.
"""
import hashlib
import hmac
import time
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from core.auth.tokens import _secreto

from .catalogo import catalogo

router = APIRouter(prefix="/api/documentos", tags=["Documentos"])

VIGENCIA_SEGUNDOS = 600
NO_ENCONTRADO = "Documento no encontrado."


def _firma(doc_id: str, exp: int) -> str:
    return hmac.new(_secreto().encode(), f"doc:{doc_id}:{exp}".encode(), hashlib.sha256).hexdigest()


def _documento(doc_id: str) -> dict:
    doc = catalogo().obtener(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=NO_ENCONTRADO)
    return doc


def _requiere_sesion(request: Request) -> None:
    if not getattr(request.state, "user_id", None):
        raise HTTPException(status_code=401, detail="Inicia sesión para consultar los documentos.")


@router.post("/{doc_id}/enlace")
def enlace(doc_id: str, request: Request):
    _requiere_sesion(request)
    doc = _documento(doc_id)
    base = {"id": doc_id, "titulo": doc["titulo"], "documento": doc["documento"]}
    if catalogo().ruta_pdf(doc):
        exp = int(time.time()) + VIGENCIA_SEGUNDOS
        url = f"/api/documentos/{quote(doc_id)}/archivo?exp={exp}&firma={_firma(doc_id, exp)}"
        return {**base, "tipo": "pdf", "url": url, "vence": exp}
    # Fuente piloto, página guardada o PDF que este servidor no tiene: visor de texto
    return {**base, "tipo": "texto", "url": f"/documento?id={quote(doc_id)}"}


@router.get("/{doc_id}/archivo")
def archivo(doc_id: str, exp: int = 0, firma: str = ""):
    doc = _documento(doc_id)
    if exp < time.time() or not hmac.compare_digest(firma, _firma(doc_id, exp)):
        raise HTTPException(status_code=403, detail="El enlace venció o no es válido. Vuelve a abrirlo desde el chat.")
    ruta = catalogo().ruta_pdf(doc)
    if not ruta:
        raise HTTPException(status_code=404, detail=NO_ENCONTRADO)
    return FileResponse(
        ruta,
        media_type="application/pdf",
        filename=doc["documento"],
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=600"},
    )


@router.get("/{doc_id}/texto")
def texto(doc_id: str, request: Request):
    _requiere_sesion(request)
    doc = _documento(doc_id)
    return {"id": doc_id, "titulo": doc["titulo"], "documento": doc["documento"],
            "categoria": doc["categoria"], "markdown": catalogo().texto(doc)}
