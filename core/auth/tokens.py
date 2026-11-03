"""Tokens de sesión (JWT HS256, 8 horas). El token solo guarda el id interno, nunca el número de cuenta."""
import os
import time
import uuid
from typing import Optional

import jwt

from .store import ClavesNoConfiguradas

VIGENCIA_SEGUNDOS = 8 * 3600

# jti de tokens cerrados con /logout -> momento en que expiran (se limpian solos)
_revocados: dict[str, float] = {}


def _secreto() -> str:
    s = (os.getenv("AUTH_JWT_SECRET") or "").strip()
    if not s or s.startswith("cambia"):
        raise ClavesNoConfiguradas("Falta configurar AUTH_JWT_SECRET en el archivo .env")
    return s


def crear_token(user_id: int) -> str:
    ahora = int(time.time())
    payload = {"sub": str(user_id), "jti": uuid.uuid4().hex, "iat": ahora, "exp": ahora + VIGENCIA_SEGUNDOS}
    return jwt.encode(payload, _secreto(), algorithm="HS256")


def leer_token(token: str) -> Optional[dict]:
    """Regresa los claims si el token es válido, no expiró y no fue cerrado; si no, None."""
    try:
        claims = jwt.decode(token, _secreto(), algorithms=["HS256"], options={"require": ["sub", "jti", "exp"]})
    except (jwt.PyJWTError, ClavesNoConfiguradas):
        return None
    if claims["jti"] in _revocados:
        return None
    return claims


def revocar(claims: dict) -> None:
    ahora = time.time()
    for jti, exp in list(_revocados.items()):
        if exp < ahora:
            del _revocados[jti]
    _revocados[claims["jti"]] = float(claims["exp"])


def token_de_cabecera(valor: Optional[str]) -> Optional[str]:
    if valor and valor.lower().startswith("bearer "):
        return valor[7:].strip() or None
    return None
