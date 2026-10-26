from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models.models import UsuarioModel
from app.infrastructure.security.jwt_handler import decode_access_token
from app.shared.exceptions.exceptions import UnauthorizedException, ForbiddenException
from typing import List

# Configurar el esquema de extracción de tokens de OAuth2 (cabecera Authorization: Bearer <token>)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UsuarioModel:
    """Extrae, valida el JWT (desde cabecera Bearer o cookie HttpOnly segura) y obtiene el usuario autenticado."""
    actual_token = token
    if not actual_token and request:
        actual_token = request.cookies.get("fm_access_token")

    if not actual_token:
        raise UnauthorizedException("Token JWT ausente. Por favor inicie sesión")
        
    payload = decode_access_token(actual_token)
    sub: str = str(payload.get("sub") or "")
    if not sub:
        raise UnauthorizedException("Token JWT inválido o corrupto")
        
    # Support both email and user_id in token payload
    if sub.isdigit():
        user = db.query(UsuarioModel).filter(
            (UsuarioModel.email == sub) | (UsuarioModel.id_usuarios == int(sub))
        ).first()
    else:
        user = db.query(UsuarioModel).filter(UsuarioModel.email == sub).first()
    
    if not user:
        raise UnauthorizedException("El usuario asociado al token no existe en el sistema")
        
    return user

class RoleChecker:
    """Validador de roles para endpoints protegidos."""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles
        
    def __call__(self, current_user: UsuarioModel = Depends(get_current_user)) -> UsuarioModel:
        if current_user.rol not in self.allowed_roles:
            raise ForbiddenException(
                f"Acceso denegado. Se requiere uno de los siguientes roles: {self.allowed_roles}"
            )
        return current_user
