import os, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
import jwt
import bcrypt
from app.infrastructure.config.settings import settings
from app.shared.exceptions.exceptions import UnauthorizedException

def hash_password(password: str) -> str:
    """Hashea una contrasena usando bcrypt nativo de forma directa (evita bug de passlib 72-byte init)."""
    if not password:
        password = ""
    # Truncar de forma segura a 72 bytes maximos que soporta la especificacion de bcrypt
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si una contrasena en texto plano coincide con el hash almacenado en BD."""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode('utf-8')[:72]
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        # Fallback a comparacion limpia por si es texto plano en migracion inicial
        return plain_password == hashed_password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un token JWT de acceso."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """Decodifica y valida un token JWT."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("El token de sesion ha expirado")
    except jwt.InvalidTokenError:
        raise UnauthorizedException("Token de autenticacion invalido")