import base64
import time
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from app.infrastructure.config.settings import settings


class GmailApiService:
    """
    Servicio de despacho de correos electrónicos corporativos oficiales mediante
    la API REST v1 de Gmail y autenticación OAuth 2.0 (Google Cloud Console).
    
    Utiliza el flujo de Refresh Token para obtener tokens de acceso de corta duración
    con almacenamiento en caché en memoria y reintentos automáticos.
    """
    _cached_access_token: Optional[str] = None
    _token_expires_at: float = 0.0

    @classmethod
    def get_credentials(cls) -> Dict[str, str]:
        """Obtiene las credenciales configuradas aceptando prefijos GOOGLE_ o GMAIL_."""
        import os
        client_id = (
            getattr(settings, "GOOGLE_CLIENT_ID", None) or 
            getattr(settings, "GMAIL_CLIENT_ID", None) or 
            os.getenv("GOOGLE_CLIENT_ID", "") or 
            os.getenv("GMAIL_CLIENT_ID", "")
        ).strip()
        client_secret = (
            getattr(settings, "GOOGLE_CLIENT_SECRET", None) or 
            getattr(settings, "GMAIL_CLIENT_SECRET", None) or 
            os.getenv("GOOGLE_CLIENT_SECRET", "") or 
            os.getenv("GMAIL_CLIENT_SECRET", "")
        ).strip()
        refresh_token = (
            getattr(settings, "GOOGLE_REFRESH_TOKEN", None) or 
            getattr(settings, "GMAIL_REFRESH_TOKEN", None) or 
            os.getenv("GOOGLE_REFRESH_TOKEN", "") or 
            os.getenv("GMAIL_REFRESH_TOKEN", "")
        ).strip()
        email = (
            getattr(settings, "GOOGLE_EMAIL", None) or 
            getattr(settings, "GMAIL_SENDER_EMAIL", None) or 
            os.getenv("GOOGLE_EMAIL", "") or 
            os.getenv("GMAIL_SENDER_EMAIL", "") or 
            "jonathan.d.castro.ortiz@gmail.com"
        ).strip()
        name = getattr(settings, "GMAIL_SENDER_NAME", "Flymetrics").strip()

        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "email": email,
            "name": name,
            "formatted": f"{name} <{email}>"
        }

    @classmethod
    def is_configured(cls) -> bool:
        """Verifica si las credenciales de Gmail OAuth2 están configuradas en el entorno."""
        creds = cls.get_credentials()
        return bool(
            creds["client_id"] and 
            creds["client_secret"] and 
            creds["refresh_token"]
        )

    @classmethod
    def get_sender_info(cls) -> Dict[str, str]:
        """Retorna el remitente oficial configurado."""
        creds = cls.get_credentials()
        return {
            "email": creds["email"],
            "name": creds["name"],
            "formatted": creds["formatted"]
        }

    @classmethod
    def _get_access_token(cls) -> str:
        """
        Obtiene un token de acceso válido de Google OAuth2.
        Reutiliza el token almacenado en caché si aún no ha expirado.
        """
        now = time.time()
        if cls._cached_access_token and now < (cls._token_expires_at - 60):
            return cls._cached_access_token

        creds = cls.get_credentials()
        if not cls.is_configured():
            raise ValueError(
                "Credenciales de Gmail API OAuth2 incompletas. "
                "Configure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET y GOOGLE_REFRESH_TOKEN en el archivo .env"
            )

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token"
        }

        try:
            resp = requests.post(token_url, data=payload, timeout=12)
            data = resp.json()

            if resp.status_code != 200:
                err_desc = data.get("error_description", data.get("error", "Error desconocido de OAuth2"))
                raise RuntimeError(f"Error renovando token con Google OAuth2 ({resp.status_code}): {err_desc}")

            cls._cached_access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            cls._token_expires_at = now + expires_in

            return cls._cached_access_token
        except requests.exceptions.RequestException as req_err:
            raise RuntimeError(f"Fallo de conexión al servidor OAuth2 de Google: {req_err}")

    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envía un correo electrónico a través de la API de Gmail.
        Si las credenciales no están configuradas aún en el .env, realiza una simulación
        elegante en los registros sin interrumpir la operación del sistema.
        """
        sender = cls.get_sender_info()

        # Si aún no se han provisto credenciales OAuth2 reales en el archivo .env
        if not cls.is_configured():
            print("\n" + "=" * 65)
            print(" [GMAIL API (OAuth2) — SIMULACIÓN EN DESARROLLO]")
            print(f" DE:      {sender['formatted']}")
            print(f" PARA:    {to_email}")
            print(f" ASUNTO:  {subject}")
            print(" ESTADO:  Listo para producción. Configure GMAIL_REFRESH_TOKEN en .env")
            print("=" * 65 + "\n")
            return {
                "success": True,
                "mock": True,
                "message": "Correo simulado con éxito (credenciales OAuth2 pendientes)",
                "sender": sender["email"]
            }

        try:
            # 1. Obtener Access Token mediante Refresh Token
            access_token = cls._get_access_token()

            # 2. Construir mensaje MIME multipart
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender["formatted"]
            msg["To"] = to_email

            # Texto plano de respaldo
            if text_body:
                msg.attach(MIMEText(text_body, "plain", "utf-8"))
            else:
                # Versión básica de texto plano
                msg.attach(MIMEText("Por favor visualice este mensaje en un cliente con soporte HTML.", "plain", "utf-8"))

            # Contenido principal en HTML
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            # 3. Codificar en Base64URL según requerimiento de la API de Gmail
            raw_b64 = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

            # 4. Enviar mediante endpoint REST de Gmail API v1
            api_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            body = {"raw": raw_b64}

            response = requests.post(api_url, headers=headers, json=body, timeout=15)
            res_data = response.json()

            if response.status_code in [200, 201]:
                msg_id = res_data.get("id", "ok")
                print(f"[GMAIL API OAUTH2 SUCCESS] Correo despachado a {to_email} (Msg ID: {msg_id})")
                return {
                    "success": True,
                    "mock": False,
                    "message_id": msg_id,
                    "thread_id": res_data.get("threadId"),
                    "sender": sender["email"]
                }
            else:
                err_msg = res_data.get("error", {}).get("message", response.text)
                print(f"[GMAIL API ERROR {response.status_code}] No se pudo enviar el correo: {err_msg}")
                return {
                    "success": False,
                    "error": err_msg,
                    "status_code": response.status_code
                }

        except Exception as ex:
            print(f"[GMAIL API EXCEPTION] Fallo en el envío a {to_email}: {ex}")
            return {
                "success": False,
                "error": str(ex)
            }

    @classmethod
    def test_connection(cls) -> Dict[str, Any]:
        """
        Diagnostica el estado de la conexión con Google Cloud / Gmail API.
        Verifica si las credenciales son válidas y recupera el perfil de la cuenta.
        """
        sender = cls.get_sender_info()
        if not cls.is_configured():
            return {
                "configured": False,
                "connected": False,
                "sender_configurado": sender["email"],
                "detalles": "Faltan credenciales de OAuth2 en .env (GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN)"
            }

        try:
            token = cls._get_access_token()
            profile_url = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
            headers = {"Authorization": f"Bearer {token}"}
            res = requests.get(profile_url, headers=headers, timeout=10)
            
            if res.status_code == 200:
                p_data = res.json()
                return {
                    "configured": True,
                    "connected": True,
                    "email_cuenta": p_data.get("emailAddress"),
                    "mensajes_totales": p_data.get("messagesTotal"),
                    "sender_configurado": sender["email"]
                }
            else:
                return {
                    "configured": True,
                    "connected": False,
                    "error": res.text,
                    "status_code": res.status_code
                }
        except Exception as e:
            return {
                "configured": True,
                "connected": False,
                "error": str(e)
            }
