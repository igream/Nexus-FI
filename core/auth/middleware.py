"""Lee la cabecera Authorization y deja al usuario en request.state (lo usan el límite de consultas y los roles)."""
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .store import ClavesNoConfiguradas, obtener_rol
from .tokens import leer_token, token_de_cabecera


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        token = token_de_cabecera(request.headers.get("authorization"))
        if token:
            claims = leer_token(token)
            if claims:
                try:
                    rol = obtener_rol(claims["sub"])
                except ClavesNoConfiguradas:
                    rol = None
                # Si el registro se reinició, el usuario ya no existe y el token deja de servir
                if rol:
                    request.state.user_id = claims["sub"]
                    request.state.rol = rol
                    request.state.auth_claims = claims
        return await call_next(request)
