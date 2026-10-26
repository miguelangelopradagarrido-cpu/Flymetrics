from pathlib import Path
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import ConfigDict

# Detectar ruta absoluta de .env (en backend/ o en root)
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"
if not _ENV_FILE.exists():
    _ENV_FILE = Path.cwd() / ".env"
if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE, override=True)

class Settings(BaseSettings):
    APP_NAME: str = "FlymetricsOS"
    APP_VERSION: str = "1.0.0"
    
    # Base de Datos
    DB_HOST: str = "mysql-114af443-flymetrics.i.aivencloud.com"
    DB_PORT: str = "20195"
    DB_NAME: str = "defaultdb"
    DB_USER: str = "avnadmin"
    DB_PASSWORD: str = "AVNS_N8EuTYZKojyfroJ82Hb"
    DB_SSL_CA: str = str(_BACKEND_DIR / "ca.pem")
    
    # Entorno y Seguridad
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "flymetrics_super_secret_key_2025_prod_local_key_hash"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,https://flymetrics.co,https://app.flymetrics.co"
    REDIS_URL: str = ""

    # JWT
    JWT_SECRET: str = "flymetrics_super_secret_key_2025_prod_local_key_hash"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    
    # Servidor
    PORT: int = 3000
    
    # APIS Externas Mocks / Reales
    GOOGLE_MAPS_API_KEY: str = "miguepro_maps_api_key_mock_local"
    WHATSAPP_VERIFY_TOKEN: str = "flymetrics_whatsapp_verification_token_local"
    WHATSAPP_ACCESS_TOKEN: str = "mock_whatsapp_access_token_from_meta_developer_portal"
    WHATSAPP_PHONE_NUMBER_ID: str = "1234567890"
    WEBHOOK_SECRET: str = "flymetrics_webhook_secret_2026"
    
    # AWS S3
    AWS_S3_BUCKET: str = "flymetrics-deliverables-bucket"
    AWS_REGION: str = "us-east-1"

    # SMTP Notificaciones por Correo Electrónico
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SENDER_EMAIL: str = ""
    PORTAL_CLIENTE_URL: str = "https://hip-despite-engines-moves.trycloudflare.com"
    FRONTEND_URL: str = "https://hip-despite-engines-moves.trycloudflare.com"

    # Gmail API & OAuth2 (Google Cloud) - Soporta tanto GOOGLE_ como GMAIL_
    GOOGLE_CLIENT_ID: str = ""
    GMAIL_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""
    GMAIL_REFRESH_TOKEN: str = ""
    GOOGLE_EMAIL: str = ""
    GMAIL_SENDER_EMAIL: str = ""
    GMAIL_SENDER_NAME: str = "Flymetrics"
    
    # Configuración de Pydantic
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
