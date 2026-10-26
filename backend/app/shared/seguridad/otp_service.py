"""
Servicio centralizado de Códigos OTP de 8 Dígitos de Alta Seguridad para Flymetrics.
Gestiona generación criptográfica, almacenamiento en memoria con TTL (15 min),
límite de intentos y quema de códigos tras uso exitoso.
"""
import time
import secrets
from typing import Optional, Dict, Any

class Otp8Service:
    # Estructura: (email, proposito) -> { "codigo": str, "expira_en": float, "intentos": int, "creado_en": float }
    _store: Dict[str, Dict[str, Any]] = {}

    TTL_SEGUNDOS = 15 * 60  # 15 minutos
    MAX_INTENTOS = 5

    @classmethod
    def _get_key(cls, email: str, proposito: str) -> str:
        return f"{email.strip().lower()}:{proposito.strip().lower()}"

    @classmethod
    def generar_codigo(cls, email: str, proposito: str = "password") -> str:
        """
        Genera un código numérico criptográfico de exactamente 8 dígitos (10000000 - 99999999).
        Almacena el código con tiempo de expiración de 15 minutos y 0 intentos.
        """
        # Número criptográficamente seguro en rango [10000000, 99999999]
        codigo_num = secrets.randbelow(90000000) + 10000000
        codigo_str = str(codigo_num)

        key = cls._get_key(email, proposito)
        cls._store[key] = {
            "codigo": codigo_str,
            "expira_en": time.time() + cls.TTL_SEGUNDOS,
            "intentos": 0,
            "creado_en": time.time()
        }
        return codigo_str

    @classmethod
    def verificar_codigo(cls, email: str, codigo_ingresado: str, proposito: str = "password", quemar: bool = True) -> Dict[str, Any]:
        """
        Valida el código de 8 dígitos.
        Si es válido y quemar=True, lo invalida inmediatamente (single-use).
        Retorna dict con { "valido": bool, "mensaje": str }
        """
        key = cls._get_key(email, proposito)
        registro = cls._store.get(key)

        if not registro:
            return {
                "valido": False,
                "mensaje": "No hay un código de seguridad activo para este correo o ya fue utilizado."
            }

        ahora = time.time()
        if ahora > registro["expira_en"]:
            cls._store.pop(key, None)
            return {
                "valido": False,
                "mensaje": "El código de 8 dígitos ha expirado (validez: 15 minutos). Solicita uno nuevo."
            }

        if registro["intentos"] >= cls.MAX_INTENTOS:
            cls._store.pop(key, None)
            return {
                "valido": False,
                "mensaje": "Has superado el número máximo de intentos permitidos. Por seguridad, solicita un nuevo código."
            }

        # Normalizar código ingresado (eliminar espacios y guiones)
        codigo_limpio = str(codigo_ingresado or "").strip().replace(" ", "").replace("-", "")

        if not secrets.compare_digest(codigo_limpio, str(registro["codigo"])):
            registro["intentos"] += 1
            restantes = cls.MAX_INTENTOS - registro["intentos"]
            return {
                "valido": False,
                "mensaje": f"Código de 8 dígitos incorrecto. Te quedan {restantes} intento(s)."
            }

        # Código correcto
        if quemar:
            cls._store.pop(key, None)

        return {
            "valido": True,
            "mensaje": "Código de seguridad de 8 dígitos verificado correctamente."
        }

    @classmethod
    def tiene_codigo_activo(cls, email: str, proposito: str = "password") -> bool:
        """Verifica si existe un código vigente para el email y propósito dados."""
        key = cls._get_key(email, proposito)
        registro = cls._store.get(key)
        if not registro:
            return False
        if time.time() > registro["expira_en"]:
            cls._store.pop(key, None)
            return False
        return True
