"""
Endpoints del historial de conversaciones (plan de implementación, fase F1).
Todos requieren sesión y solo operan sobre las conversaciones del propio usuario;
una conversación ajena o borrada responde 404, igual que una inexistente.

  GET    /api/conversaciones          lista (más recientes primero)
  GET    /api/conversaciones/{id}     conversación con sus mensajes
  PATCH  /api/conversaciones/{id}     cambiar el título
  DELETE /api/conversaciones/{id}     borrar (deja de mostrarse)
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import store

router = APIRouter(prefix="/api/conversaciones", tags=["Historial"])

NO_ENCONTRADA = "Conversación no encontrada."


def _usuario(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Inicia sesión para ver tu historial.")
    return str(user_id)


class RenombrarRequest(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=store.TITULO_MAX)


@router.get("")
def listar(request: Request):
    return {"conversaciones": store.listar_conversaciones(_usuario(request))}


@router.get("/{conv_id}")
def obtener(conv_id: str, request: Request):
    conv = store.obtener_conversacion(_usuario(request), conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail=NO_ENCONTRADA)
    return conv


@router.patch("/{conv_id}")
def renombrar(conv_id: str, req: RenombrarRequest, request: Request):
    usuario = _usuario(request)
    try:
        ok = store.renombrar_conversacion(usuario, conv_id, req.titulo)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail=NO_ENCONTRADA)
    return {"ok": True}


@router.delete("/{conv_id}")
def eliminar(conv_id: str, request: Request):
    if not store.eliminar_conversacion(_usuario(request), conv_id):
        raise HTTPException(status_code=404, detail=NO_ENCONTRADA)
    return {"ok": True}
