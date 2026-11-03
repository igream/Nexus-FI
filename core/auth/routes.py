"""
Endpoints de inicio de sesión (Anexo B del Avance 3):
  POST /api/auth/registro   201 / 403 / 409 / 422
  POST /api/auth/login      200 con token / 401 / 429 tras varios intentos fallidos
  POST /api/auth/logout     200, invalida el token
  GET  /api/auth/admin/usuarios             solo admin: cuentas que ya crearon contraseña
  POST /api/auth/admin/reiniciar-registro   solo admin: 200 / 401 / 403 / 404 / 409 / 422
"""
import logging
import re
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import store
from .tokens import VIGENCIA_SEGUNDOS, crear_token, revocar

router = APIRouter(prefix="/api/auth", tags=["Inicio de sesión"])
logger = logging.getLogger("nexus.auth")

MENSAJE_LOGIN_FALLIDO = "Número de cuenta o contraseña incorrectos"

# Freno a intentos de adivinar contraseñas: 5 fallos por cuenta en 15 minutos
MAX_FALLOS = 5
VENTANA_FALLOS = 15 * 60
_fallos: dict[str, deque] = {}


class RegistroRequest(BaseModel):
    carrera: str
    numero_cuenta: str
    password: str


class LoginRequest(BaseModel):
    numero_cuenta: str
    password: str


def _validar_cuenta(numero: str) -> str:
    numero = (numero or "").strip()
    if not re.fullmatch(r"\d{7}", numero):
        raise HTTPException(status_code=422, detail="El número de cuenta debe tener exactamente 7 dígitos.")
    return numero


def _fallos_recientes(clave: str) -> deque:
    cola = _fallos.setdefault(clave, deque())
    limite = time.time() - VENTANA_FALLOS
    while cola and cola[0] < limite:
        cola.popleft()
    return cola


@router.post("/registro", status_code=201, summary="Crea la contraseña de una cuenta precargada")
def registro(req: RegistroRequest):
    numero = _validar_cuenta(req.numero_cuenta)
    if store.normalizar_carrera(req.carrera) is None:
        raise HTTPException(status_code=422, detail="Por ahora solo está habilitada Ingeniería en Computación (ICO).")
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 8 caracteres.")
    if len(req.password.encode()) > 72:
        raise HTTPException(status_code=422, detail="La contraseña es demasiado larga (máximo 72 caracteres).")
    try:
        store.registrar_usuario(numero, req.carrera, req.password)
    except store.CuentaNoAutorizada:
        raise HTTPException(status_code=403, detail="Este número de cuenta no está autorizado para la prueba piloto.")
    except store.CuentaYaRegistrada:
        raise HTTPException(status_code=409, detail="Esta cuenta ya está registrada. Inicia sesión.")
    return {"ok": True}


@router.post("/login", summary="Inicia sesión y regresa un token de 8 horas")
def login(req: LoginRequest):
    numero = (req.numero_cuenta or "").strip()
    if not re.fullmatch(r"\d{7}", numero) or not req.password or len(req.password.encode()) > 72:
        raise HTTPException(status_code=401, detail=MENSAJE_LOGIN_FALLIDO)

    clave = store.hash_cuenta(numero)
    fallos = _fallos_recientes(clave)
    if len(fallos) >= MAX_FALLOS:
        espera = int(VENTANA_FALLOS - (time.time() - fallos[0])) + 1
        return JSONResponse(
            status_code=429,
            content={"detail": "Demasiados intentos fallidos. Espera unos minutos e inténtalo de nuevo."},
            headers={"Retry-After": str(espera)},
        )

    user_id = store.verificar_login(numero, req.password)
    if user_id is None:
        fallos.append(time.time())
        raise HTTPException(status_code=401, detail=MENSAJE_LOGIN_FALLIDO)

    _fallos.pop(clave, None)
    usuario = store.obtener_usuario(user_id) or {}
    return {
        "ok": True,
        "token": crear_token(user_id),
        "carrera": usuario.get("carrera", ""),
        "nombre": usuario.get("nombre", ""),
        "rol": usuario.get("rol", "alumno"),
        "expira_en": VIGENCIA_SEGUNDOS,
    }


@router.post("/logout", summary="Cierra la sesión e invalida el token")
def logout(request: Request):
    claims = getattr(request.state, "auth_claims", None)
    if claims:
        revocar(claims)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Administración (solo integrantes del equipo, rol admin)
# ---------------------------------------------------------------------------
def requiere_admin(request: Request) -> str:
    """Dependencia: 401 sin sesión, 403 si el usuario no es administrador. Regresa el id del admin."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Inicia sesión.")
    if getattr(request.state, "rol", None) != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden hacer esto.")
    return user_id


@router.get("/admin/usuarios", summary="Lista de cuentas que ya crearon contraseña (solo admin)")
def usuarios_registrados(request: Request):
    admin_id = requiere_admin(request)
    usuarios = store.listar_registrados()
    for u in usuarios:
        u["es_tu_cuenta"] = str(u.pop("id")) == str(admin_id)
    return {"ok": True, "usuarios": usuarios}


class ReinicioRequest(BaseModel):
    numero_cuenta: str


@router.post("/admin/reiniciar-registro", summary="Borra la contraseña de una cuenta para que su dueño se registre de nuevo")
def reiniciar_registro(req: ReinicioRequest, request: Request):
    admin_id = requiere_admin(request)
    numero = _validar_cuenta(req.numero_cuenta)
    estado = store.estado_cuenta(numero)
    if not estado["autorizada"]:
        raise HTTPException(status_code=404, detail="Ese número de cuenta no está en el padrón de la prueba piloto.")
    if not estado["registrada"]:
        return {"ok": True, "reiniciado": False, "detail": "Esa cuenta todavía no se había registrado; no hay nada que reiniciar."}
    if str(estado["user_id"]) == str(admin_id):
        raise HTTPException(status_code=409, detail="No puedes reiniciar tu propia cuenta desde aquí.")
    store.eliminar_registro(numero)
    _fallos.pop(store.hash_cuenta(numero), None)
    # Bitácora sin datos personales: solo ids internos
    logger.info("Registro reiniciado por el admin %s (usuario interno %s)", admin_id, estado["user_id"])
    return {"ok": True, "reiniciado": True, "detail": "Registro reiniciado. El dueño de la cuenta ya puede registrarse de nuevo."}
