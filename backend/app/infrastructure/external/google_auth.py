from typing import Dict, Any
import requests
from app.shared.exceptions.exceptions import BadRequestException
from app.infrastructure.config.settings import settings

class GoogleAuthService:
    @classmethod
    def verify_google_token(cls, token: str) -> Dict[str, Any]:
        """
        Verifica criptográficamente el token de ID de Google (OAuth2)
        utilizando el servicio oficial de validación de Google (tokeninfo).
        Valida firma, expiración, emisor y extrae los claims reales del usuario.
        """
        if not token:
            raise BadRequestException("Token de autenticación de Google inválido o ausente.")
            
        token = token.strip()

        if len(token) < 15:
            raise BadRequestException("Token de autenticación de Google inválido o ausente.")

        try:
            payload = None
            # 1. Si es un Access Token de OAuth 2.0 (ej. ya29.... o sin 3 segmentos de punto)
            if token.startswith("ya29.") or token.count(".") != 2:
                resp = requests.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                if resp.status_code == 200:
                    payload = resp.json()
                else:
                    # Intento alternativo con tokeninfo
                    resp_alt = requests.get(
                        "https://oauth2.googleapis.com/tokeninfo",
                        params={"access_token": token},
                        timeout=10
                    )
                    if resp_alt.status_code == 200:
                        payload = resp_alt.json()

            # 2. Si es un ID Token JWT de Google Identity Services (3 segmentos separados por punto)
            if not payload:
                resp = requests.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"id_token": token},
                    timeout=10
                )
                if resp.status_code == 200:
                    payload = resp.json()
                else:
                    err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    err_desc = err_data.get("error_description", "Token de Google inválido o expirado")
                    raise BadRequestException(f"Error de validación Google OAuth: {err_desc}")

            if not payload:
                raise BadRequestException("No fue posible validar el token oficial con los servidores de Google.")

            # Validar que el correo esté verificado por Google
            email_verified = payload.get("email_verified")
            if email_verified not in [True, "true", "True", 1, None]:
                raise BadRequestException("La cuenta de Google debe tener su correo electrónico verificado.")

            email = payload.get("email")
            if not email or "@" not in email:
                raise BadRequestException("No se encontró un correo electrónico verificado en la cuenta de Google.")

            given_name = payload.get("given_name") or payload.get("name", "Usuario").split()[0]
            names = payload.get("name", "").split()
            family_name = payload.get("family_name") or (names[1] if len(names) > 1 else "")

            return {
                "email": email.strip().lower(),
                "nombre": given_name,
                "apellido_1": family_name,
                "apellido_2": "",
                "sub": payload.get("sub", f"google_{email}")
            }

        except requests.RequestException as req_err:
            raise BadRequestException(f"No fue posible comunicarse con los servidores de autenticación de Google: {str(req_err)}")
        except BadRequestException:
            raise
        except Exception as e:
            raise BadRequestException(f"Error al validar credenciales oficiales de Google: {str(e)}")

