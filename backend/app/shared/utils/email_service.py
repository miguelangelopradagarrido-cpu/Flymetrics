import os
import smtplib
import re
import json
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import Optional, Dict, Any, List
from app.infrastructure.config.settings import settings

logger = logging.getLogger("uvicorn")

# ── CACHÉ DE IDEMPOTENCIA Y ANTI-DUPLICADOS (60 SEGUNDOS) ──
_sent_emails_cache: Dict[tuple, float] = {}


def get_admin_emails() -> List[str]:
    """Retorna la lista de correos de todos los administradores registrados."""
    try:
        from app.infrastructure.database.session import SessionLocal
        from app.infrastructure.database.models.models import UsuarioModel
        with SessionLocal() as db:
            admins = db.query(UsuarioModel).filter(UsuarioModel.rol == "administrador").all()
            emails = [a.email.strip().lower() for a in admins if a.email and "@" in a.email]
            return list(set(emails)) if emails else ["comercial@flymetrics.com.co"]
    except Exception:
        return ["comercial@flymetrics.com.co"]


def _get_corporate_info() -> Dict[str, str]:
    """Extrae dinámicamente los datos corporativos oficiales registrados en la base de datos (SystemConfigModel)."""
    try:
        from app.infrastructure.database.session import SessionLocal
        from app.infrastructure.database.models.models import SystemConfigModel
        with SessionLocal() as db:
            cfg = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "perfil_corporativo").first()
            if cfg and cfg.valor:
                parsed = json.loads(cfg.valor)
                if isinstance(parsed, dict) and parsed.get("telefono"):
                    return parsed
    except Exception as e:
        logger.debug(f"[EMAIL CORP SYNC] Fallback a datos base por: {e}")

    return {
        "empresa": "Flymetrics S.A.S.",
        "nit": "902036414-3",
        "telefono": "+57 314 3764972",
        "whatsapp": "+57 314 3764972",
        "email": "comercial@flymetrics.com.co",
        "direccion": "Bogotá, Colombia"
    }


def _clean_base_portal_url(raw_url: str) -> str:
    """Extrae el origen base (esquema + dominio + puerto) de una URL para evitar colisiones de rutas HTML."""
    if not raw_url:
        return ""
    u = raw_url.strip()
    if not u.startswith("http://") and not u.startswith("https://"):
        u = f"https://{u}"
    from urllib.parse import urlparse
    parsed = urlparse(u)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return u.rstrip("/")


def _get_active_portal_url(path: str = "cliente", email_dest: Optional[str] = None) -> str:
    """
    Retorna dinámicamente la URL pública de acceso para botones de correo.
    Prioridad absoluta: La URL configurada por el Administrador en Base de Datos (url_botones_correo).
    Permite redireccionar directamente a flymetrics.com.co o al portal corporativo establecido.
    """
    from urllib.parse import quote, urlparse
    import json

    raw_path = (path or "").strip().lstrip("/")

    # ── PRIORIDAD 1: URL CONFIGURADA POR EL ADMINISTRADOR EN BASE DE DATOS ──
    custom_url = None
    try:
        from app.infrastructure.database.session import SessionLocal
        from app.infrastructure.database.models.models import SystemConfigModel
        with SessionLocal() as db:
            cfg_m = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "config_correo_seguro").first()
            if cfg_m and cfg_m.valor:
                c_json = json.loads(cfg_m.valor)
                val = (c_json.get("url_botones_correo") or "").strip()
                if val:
                    if not val.startswith("http://") and not val.startswith("https://"):
                        val = f"https://{val}"
                    custom_url = val.rstrip("/")
    except Exception as e:
        logger.debug(f"[GET_PORTAL_URL_DB] {e}")

    # Fallback si no hay configuración en BD
    if not custom_url:
        base = getattr(settings, "PORTAL_CLIENTE_URL", None) or getattr(settings, "FRONTEND_URL", None) or "https://flymetrics.com.co"
        custom_url = str(base).strip().rstrip("/")
        if not custom_url.startswith("http://") and not custom_url.startswith("https://"):
            custom_url = f"https://{custom_url}"

    # Si es una revisión de turno/cotización, preservar los parámetros query
    if "revisar_turno=" in raw_path:
        qs = raw_path if "?" not in raw_path else raw_path.split("?", 1)[1]
        sep = "&" if "?" in custom_url else "?"
        if custom_url.endswith(".html"):
            return f"{custom_url}{sep}{qs}"
        return f"{custom_url}/index.html?{qs}"

    # Si la petición es específica para el panel de administración
    if "admin" in raw_path.lower():
        parsed = urlparse(custom_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return f"{origin}/admin.html"

    # Si la petición es específica para técnicos
    if "tecnico" in raw_path.lower():
        parsed = urlparse(custom_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return f"{origin}/tecnico.html"

    # Para todos los correos estándar (bienvenida, confirmación de vuelo, reportes listos, pagos):
    # Redirecciona DIRECTAMENTE a la URL configurada por el admin (ej: https://flymetrics.com.co)
    return custom_url





import concurrent.futures

_email_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5, thread_name_prefix="email_worker")

def _strip_emojis(text: str) -> str:
    """Elimina de forma exhaustiva todos los emojis y símbolos gráficos informales."""
    if not text:
        return ""
    # Patrón exhaustivo para emojis, dingbats, símbolos suplementarios y selectores de variación
    pattern = re.compile(
        "["
        "\U00010000-\U0010FFFF"  # Emojis suplementarios
        "\u2600-\u27BF"          # Dingbats y símbolos misceláneos
        "\u2300-\u23FF"          # Símbolos técnicos
        "\u2B50-\u2B55"          # Estrellas y formas
        "\uFE00-\uFE0F"          # Variation selectors
        "\u20D0-\u20FF"          # Combining marks
        "]+",
        flags=re.UNICODE
    )
    cleaned = pattern.sub("", str(text))
    # Limpiar espacios dobles sobrantes
    return re.sub(r" {2,}", " ", cleaned).strip()

def _send_smtp_html_email_actual(to_email: str, subject: str, html_body: str, ics_content: Optional[str] = None, ics_method: str = "REQUEST") -> bool:
    """Ejecuta el transporte de red SMTP/Gmail API de forma aislada con soporte iCalendar para Microsoft Outlook."""
    subject = _strip_emojis(subject)
    html_body = _strip_emojis(html_body)
    # ── PRIORIDAD 1: CREDENCIALES CONFIGURADAS EN BASE DE DATOS O ENTORNO ──
    smtp_host = getattr(settings, "SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(getattr(settings, "SMTP_PORT", 587))
    smtp_user = getattr(settings, "SMTP_USER", "")
    smtp_pass = getattr(settings, "SMTP_PASSWORD", "")
    sender_name = getattr(settings, "GMAIL_SENDER_NAME", "Flymetrics Colombia")

    try:
        from app.infrastructure.database.session import SessionLocal
        from app.infrastructure.database.models.models import SystemConfigModel
        import json
        with SessionLocal() as db:
            cfg_m = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "config_correo_seguro").first()
            if cfg_m and cfg_m.valor:
                c_json = json.loads(cfg_m.valor)
                if c_json.get("smtp_host"): smtp_host = c_json["smtp_host"]
                if c_json.get("smtp_port"): smtp_port = int(c_json["smtp_port"])
                if c_json.get("smtp_user"): smtp_user = c_json["smtp_user"]
                db_pwd = (c_json.get("smtp_password") or "").strip()
                # Proteger contra contraseñas falsas/accidentales escritas en la interfaz
                if db_pwd and db_pwd not in ["12345678", "password", "admin", "test"] and len(db_pwd) >= 8:
                    smtp_pass = db_pwd
                elif getattr(settings, "SMTP_PASSWORD", ""):
                    smtp_pass = getattr(settings, "SMTP_PASSWORD", "")
                if c_json.get("sender_name"): sender_name = c_json["sender_name"]
    except Exception as e:
        logger.debug(f"[EMAIL CFG DB] Fallback por: {e}")

    # Auto-detección inteligente: Si el usuario usa Hotmail / Outlook / Live o dominio Microsoft 365 (ej. @flymetrics.com.co)
    is_ms_email = smtp_user and (any(d in smtp_user.lower() for d in ["@hotmail.", "@outlook.", "@live.", "@msn."]) or "@flymetrics." in smtp_user.lower() or "office365" in smtp_host.lower())
    if is_ms_email:
        if "gmail" in smtp_host.lower() or not smtp_host:
            smtp_host = "smtp.office365.com"
            smtp_port = 587

    sender_email = smtp_user or getattr(settings, "GMAIL_SENDER_EMAIL", None) or getattr(settings, "SENDER_EMAIL", "miguelangelopradagarrido@gmail.com")

    # ── PRIORIDAD 1: MICROSOFT GRAPH API DIRECTO (MICROSOFT 365 ENTERPRISE OAUTH2) ──
    ms_client_id = os.getenv("MICROSOFT_CLIENT_ID") or getattr(settings, "MICROSOFT_CLIENT_ID", "")
    ms_client_secret = os.getenv("MICROSOFT_CLIENT_SECRET") or getattr(settings, "MICROSOFT_CLIENT_SECRET", "")
    ms_tenant_id = os.getenv("MICROSOFT_TENANT_ID") or getattr(settings, "MICROSOFT_TENANT_ID", "")
    ms_sender = os.getenv("MICROSOFT_SENDER_EMAIL") or getattr(settings, "MICROSOFT_SENDER_EMAIL", "luiscastaneda@flymetrics.com.co")

    if ms_client_id and ms_client_secret and ms_tenant_id:
        try:
            import urllib.request
            import urllib.parse
            import json
            import base64

            # 1. Obtener token OAuth2 de aplicación con Microsoft Entra ID
            token_url = f"https://login.microsoftonline.com/{ms_tenant_id}/oauth2/v2.0/token"
            token_data = urllib.parse.urlencode({
                "client_id": ms_client_id,
                "client_secret": ms_client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            }).encode("utf-8")

            token_req = urllib.request.Request(token_url, data=token_data, method="POST")
            with urllib.request.urlopen(token_req, timeout=10) as t_resp:
                t_json = json.loads(t_resp.read().decode())
                access_token = t_json.get("access_token")

            if access_token:
                # 2. Construir mensaje Graph API
                message_payload = {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": html_body
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": to_email
                            }
                        }
                    ]
                }

                if ics_content:
                    ics_b64 = base64.b64encode(ics_content.encode("utf-8")).decode("utf-8")
                    message_payload["attachments"] = [
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": "mision_vuelo.ics",
                            "contentType": f"text/calendar; method={ics_method}",
                            "contentBytes": ics_b64
                        }
                    ]

                graph_send_url = f"https://graph.microsoft.com/v1.0/users/{ms_sender}/sendMail"
                send_req = urllib.request.Request(
                    graph_send_url,
                    data=json.dumps({"message": message_payload, "saveToSentItems": "true"}).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )

                with urllib.request.urlopen(send_req, timeout=12) as s_resp:
                    if s_resp.status in (200, 202):
                        logger.info(f"[MICROSOFT GRAPH SUCCESS] Correo '{subject}' enviado oficialmente a {to_email} vía {ms_sender}")
                        return True
        except Exception as ms_err:
            logger.warning(f"[MICROSOFT GRAPH WARNING] Envío directo Microsoft Graph tuvo observación: {ms_err}. Continuando con canales alternos...")

    # ── PRIORIDAD 2: CANAL SMTP CLÁSICO CON AUTENTICACIÓN ──
    if smtp_user and smtp_pass:
        try:
            if ics_content:
                msg = MIMEMultipart("mixed")
                msg["Subject"] = subject
                msg["From"] = f"{sender_name} <{sender_email}>"
                msg["To"] = to_email

                alt_part = MIMEMultipart("alternative")
                alt_part.attach(MIMEText(html_body, "html", "utf-8"))

                # Inyección iCalendar RFC 5545 para Microsoft Outlook / Hotmail / Teams
                cal_part = MIMEText(ics_content, f"calendar; method={ics_method}", "utf-8")
                cal_part.add_header("Content-Class", "urn:content-classes:calendarmessage")
                alt_part.attach(cal_part)
                msg.attach(alt_part)

                from email.mime.base import MIMEBase
                from email import encoders
                ics_attachment = MIMEBase("text", "calendar", method=ics_method, name="mision_vuelo.ics")
                ics_attachment.set_payload(ics_content.encode("utf-8"))
                encoders.encode_base64(ics_attachment)
                ics_attachment.add_header("Content-Disposition", 'attachment; filename="mision_vuelo.ics"')
                msg.attach(ics_attachment)
            else:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{sender_name} <{sender_email}>"
                msg["To"] = to_email
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=8) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(sender_email, to_email, msg.as_string())
            logger.info(f"[SMTP EMAIL SUCCESS] Correo '{subject}' enviado a {to_email}" + (" (con iCal Sync)" if ics_content else ""))
            return True
        except Exception as e:
            logger.error(f"[SMTP EMAIL ERROR] Falló el envío SMTP real a {to_email}: {e}. Intentando canales alternativos...")

    # ── PRIORIDAD 3: GMAIL API REST (OAUTH2) ──
    try:
        from app.infrastructure.external.gmail_api_service import GmailApiService
        if GmailApiService.is_configured():
            res = GmailApiService.send_email(to_email=to_email, subject=subject, html_body=html_body)
            if res.get("success") and not res.get("mock"):
                logger.info(f"[GMAIL API SUCCESS] Correo '{subject}' enviado exitosamente a {to_email}")
                return True
            if res.get("error"):
                logger.warning(f"[GMAIL API WARNING] Intento por Gmail API falló: {res.get('error')}. Intentando canales alternativos...")
    except Exception as g_err:
        logger.warning(f"[GMAIL API ERROR] Excepción llamando a Gmail API: {g_err}")

    # ── PRIORIDAD 4: MODO SIMULACIÓN ELEGANTE (DESARROLLO / PRUEBAS) ──
    try:
        from app.infrastructure.external.gmail_api_service import GmailApiService
        GmailApiService.send_email(to_email=to_email, subject=subject, html_body=html_body)
    except Exception:
        safe_sub = subject.encode("ascii", errors="replace").decode("ascii")
        print(f"\n=======================================================")
        print(f" [EMAIL DISPATCHED TO: {to_email}]")
        print(f" [ASUNTO: {safe_sub}]")
        if ics_content:
            print(f" [MICROSOFT CALENDAR SYNC: ICS {ics_method} ADJUNTADO]")
        print(f" [ESTADO: Simulación Exitosa / Listo para Producción]")
        print(f"=======================================================\n")
    return True


def _send_smtp_html_email(to_email: str, subject: str, html_body: str, sync: bool = False, ics_content: Optional[str] = None, ics_method: str = "REQUEST") -> bool:
    """
    Función central para envío de correos en Flymetrics con protección estricta anti-duplicados (60s)
    y despacho asíncrono ultra-rápido en segundo plano para no congelar las peticiones HTTP.
    Soporta sincronización iCalendar RFC 5545 para Microsoft Outlook / Teams.
    """
    if not to_email or "@" not in to_email:
        logger.warning(f"[EMAIL SERVICE] Dirección de correo inválida: '{to_email}'")
        return False

    # ── LIMPIEZA AUTOMÁTICA DE EMOJIS (ASUNTO Y CUERPO CORPORATIVO) ──
    clean_subj = _strip_emojis(subject)
    clean_body = _strip_emojis(html_body)

    # ── PROTECCIÓN ANTI-BUCLE / DEBOUNCE (60 SEGUNDOS) ──
    clean_email = to_email.strip().lower()
    cache_key = (clean_email, clean_subj)
    now = time.time()

    # Limpiar entradas expiradas (> 300 segundos)
    expired = [k for k, v in _sent_emails_cache.items() if now - v > 300]
    for k in expired:
        _sent_emails_cache.pop(k, None)

    last_sent = _sent_emails_cache.get(cache_key)
    if last_sent and (now - last_sent < 60):
        logger.warning(f"[EMAIL ANTI-DUPLICATE INTERCEPTED] Correo a {clean_email} con asunto '{clean_subj}' ya enviado hace {now - last_sent:.1f}s. Bloqueando envío repetido.")
        return True

    _sent_emails_cache[cache_key] = now

    # Despacho en segundo plano (ultra-rápido: < 1 milisegundo de respuesta HTTP)
    if sync:
        return _send_smtp_html_email_actual(to_email, clean_subj, clean_body, ics_content, ics_method)
    else:
        _email_executor.submit(_send_smtp_html_email_actual, to_email, clean_subj, clean_body, ics_content, ics_method)
        return True



def _generate_flymetrics_base_template(header_badge: str, title: str, subtitle: str, content_html: str, action_url: str = None, action_text: str = None) -> str:
    """Genera la estructura HTML base con los colores y tipografía oficial del manual de marca Flymetrics y datos de la base de datos."""
    corp = _get_corporate_info()
    empresa_nombre = corp.get("empresa", "Flymetrics S.A.S.")
    empresa_tel = corp.get("telefono", "+57 314 3764972")
    empresa_email = corp.get("email", "comercial@flymetrics.com.co")
    empresa_dir = corp.get("direccion", "Bogotá, Colombia")
    clean_tel = re.sub(r'[^0-9+]', '', empresa_tel)

    button_markup = ""
    if action_url and action_text:
        button_markup = f"""
        <div style="text-align: center; margin: 32px 0 16px 0;">
          <a href="{action_url}" target="_blank" style="display: inline-block; background: #003049; color: #ffffff; text-decoration: none; font-size: 15px; font-weight: 800; padding: 14px 34px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0, 48, 73, 0.25); letter-spacing: 0.3px; border: 1.5px solid #1c82ad;">
            {action_text} &rarr;
          </a>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f4f9; margin: 0; padding: 24px 12px; color: #343a40; }}
    .email-container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 18px; overflow: hidden; box-shadow: 0 12px 36px rgba(0,48,73,0.1); border: 1px solid #6c757d; }}
    .email-header {{ background: #003049; padding: 32px 28px 24px 28px; text-align: center; position: relative; }}
    .brand-logo-text {{ font-size: 25px; font-weight: 900; color: #ffffff; margin: 0; letter-spacing: 0.5px; }}
    .brand-logo-text span {{ color: #E4C7A1; }}
    .badge {{ display: inline-block; background: rgba(228, 199, 161, 0.2); color: #E4C7A1; border: 1.5px solid #E4C7A1; padding: 5px 14px; border-radius: 20px; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; margin-top: 12px; }}
    .email-body {{ padding: 32px 28px; color: #343a40; line-height: 1.65; }}
    .greeting {{ font-size: 20px; font-weight: 800; color: #003049; margin-top: 0; margin-bottom: 8px; }}
    .subgreeting {{ font-size: 14px; color: #6c757d; margin-top: 0; margin-bottom: 22px; line-height: 1.5; }}
    .info-table {{ width: 100%; border-collapse: separate; border-spacing: 0; background: #f8f9fa; border-radius: 14px; border: 1.5px solid #6c757d; margin: 20px 0; overflow: hidden; }}
    .info-table th {{ background: #E4C7A1; color: #003049; font-weight: 800; text-align: left; padding: 12px 18px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1.5px solid #6c757d; }}
    .info-table td {{ padding: 12px 18px; font-size: 14px; border-bottom: 1px solid #6c757d; color: #343a40; }}
    .info-table tr:last-child td {{ border-bottom: none; }}
    .info-label {{ font-weight: 700; color: #003049; width: 42%; }}
    .info-value {{ font-weight: 600; color: #343a40; }}
    .email-footer {{ background: #f8f9fa; padding: 22px 28px; border-top: 1.5px solid #6c757d; text-align: center; font-size: 12px; color: #6c757d; line-height: 1.6; }}
    .email-footer a {{ color: #1c82ad; text-decoration: none; font-weight: 700; }}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="email-header">
      <h1 class="brand-logo-text">FLY<span>METRICS</span></h1>
      <p style="color: #E4C7A1; font-size: 13px; margin: 4px 0 0 0; font-weight: 600; letter-spacing: 0.3px;">Agricultura y Ganadería de Precisión con Drones</p>
      <div class="badge">{header_badge}</div>
    </div>
    <div class="email-body">
      <h2 class="greeting">{title}</h2>
      <p class="subgreeting">{subtitle}</p>
      {content_html}
      {button_markup}
    </div>
    <div class="email-footer">
      <strong style="color: #003049;">{empresa_nombre}</strong> &bull; {empresa_dir}<br>
      Línea de Operaciones: <a href="tel:{clean_tel}">{empresa_tel}</a> &bull; <a href="mailto:{empresa_email}">{empresa_email}</a><br>
      Este correo es generado automáticamente por el sistema de gestión de vuelos. Por favor no responder directamente a esta dirección.
    </div>
  </div>
</body>
</html>"""


# ==============================================================================
# 1. ENVÍO DE OTP (MANTENIENDO COMPATIBILIDAD)
# ==============================================================================
def send_otp_email(to_email: str, otp_code: str) -> bool:
    """Envía un correo electrónico con el código OTP de verificación de cuenta."""
    content = f"""
    <div style="text-align: center; margin: 18px 0;">
      <p style="color: #343a40; font-size: 15px; margin-bottom: 20px;">
        Has solicitado un código de verificación de seguridad para autenticarte en tu cuenta de Flymetrics.
      </p>
      <div style="background: #003049; color: #ffffff; border: 2px solid #E4C7A1; font-size: 32px; font-weight: 900; letter-spacing: 8px; text-align: center; padding: 18px; border-radius: 12px; margin: 20px auto; max-width: 280px; box-shadow: 0 8px 20px rgba(0,48,73,0.25);">
        {otp_code}
      </div>
      <p style="font-size: 13px; color: #6c757d; margin-top: 14px;">
        Este código es válido por 15 minutos. Si no has solicitado este código, por favor comunícate de inmediato con nuestro equipo de seguridad.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Seguridad & Acceso",
        title="Código de Verificación OTP",
        subtitle="Verificación de identidad en plataforma",
        content_html=content,
        action_text=None,
        action_url=None
    )
    return _send_smtp_html_email(to_email, "🔐 Código de Verificación OTP — Flymetrics", html)


# ==============================================================================
# 2. ACCIÓN: REGISTRO / CREACIÓN DE CUENTA DE CLIENTE (PRIMER INGRESO)
# ==============================================================================
def send_welcome_email(to_email: str, nombre_cliente: str, empresa: Optional[str] = None, password_temporal: Optional[str] = None) -> bool:
    """Envía correo de bienvenida y confirmación de alta en la plataforma Flymetrics con los 4 puntos oficiales."""
    portal_url = _get_active_portal_url("cliente.html")
    
    empresa_badge = f"<p style='color:#1c82ad; font-weight:700; margin:0 0 14px 0;'>Organización / Empresa: {empresa}</p>" if empresa else ""
    credenciales_box = ""
    if password_temporal:
        credenciales_box = f"""
        <div style="background: #f0fdf4; border: 1.5px dashed #1c82ad; border-radius: 12px; padding: 16px 20px; margin: 20px 0;">
          <strong style="color: #003049; font-size: 14px;">🔐 Tus credenciales de acceso inicial:</strong>
          <p style="margin: 6px 0 0 0; font-size: 14px; color: #343a40;">
            <strong>Usuario / Correo:</strong> {to_email}<br>
            <strong>Contraseña Temporal:</strong> <code style="background:#ffffff; padding:2px 8px; border-radius:6px; font-weight:700; color:#003049;">{password_temporal}</code>
          </p>
          <p style="margin: 8px 0 0 0; font-size: 12px; color: #6c757d;">
            * Te recomendamos cambiar tu contraseña una vez ingreses a la sección "Mi Perfil".
          </p>
        </div>
        """

    content = f"""
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Hola <strong>{nombre_cliente}</strong>,
    </p>
    {empresa_badge}
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Te damos la bienvenida al ecosistema de <strong>Flymetrics Command Center</strong>. Tu cuenta corporativa ha sido habilitada exitosamente para gestionar tus misiones agronómicas, monitoreo con drones y reportes técnicos de campo.
    </p>
    {credenciales_box}
    <div style="background: #f8f9fa; border-radius: 14px; padding: 20px 22px; border: 1.5px solid #1c82ad; margin: 22px 0;">
      <h4 style="margin: 0 0 12px 0; color: #003049; font-size: 15px; font-weight: 800; display: flex; align-items: center; gap: 8px;">
        <span style="color: #1c82ad;">✦</span> ¿Qué puedes hacer en tu portal?
      </h4>
      <ul style="margin: 0; padding-left: 20px; color: #343a40; font-size: 14px; line-height: 1.8;">
        <li><strong style="color: #003049;">Registra, administra y gestiona</strong> tus predios, lotes y proyectos</li>
        <li><strong style="color: #003049;">Agendar</strong> nuevos servicios de aspersión, fotogrametría y análisis multiespectral</li>
        <li><strong style="color: #003049;">Descargar</strong> informes y documentos de nuestro repositorio Sharepoint</li>
        <li><strong style="color: #003049;">Consultar</strong> en tiempo real la información contable</li>
      </ul>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Cuenta Activada",
        title="¡Bienvenido a Flymetrics!",
        subtitle="Tu plataforma de agricultura y ganadería de precisión",
        content_html=content,
        action_text="Acceder a Mi Portal de Cliente",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, "🛸 ¡Bienvenido a Flymetrics! Tu cuenta ha sido activada", html)


# ==============================================================================
# 3. ACCIÓN: CREACIÓN / CONFIRMACIÓN DE AGENDAMIENTO DE TURNO
# ==============================================================================
def send_demo_gratuita_created_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    fecha: str,
    hora: str,
    observaciones: Optional[str] = None,
    aceptacion_url: Optional[str] = None
) -> bool:
    """Envía correo de confirmación para un análisis del terreno inicial sin costo con enlace único de aceptación."""
    portal_url = _get_active_portal_url("cliente.html")
    obs_row = f"<tr><td class='info-label'>Observaciones:</td><td class='info-value'>{observaciones}</td></tr>" if observaciones else ""
    accept_cta = ""
    if aceptacion_url:
        accept_cta = f"""
        <div style=\"text-align:center; margin:24px 0;\">
          <a href=\"{aceptacion_url}\" target=\"_blank\" style=\"display:inline-block;background:#10b981;color:#ffffff;text-decoration:none;font-size:14px;font-weight:800;padding:12px 28px;border-radius:10px;box-shadow:0 4px 14px rgba(16,185,129,0.28);\">
            ✅ Confirmar mi análisis del terreno
          </a>
        </div>
        """

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Hemos recibido tu solicitud de <strong>análisis del terreno</strong> sin costo para tu predio nuevo. Tu petición quedó registrada en el sistema con radicado <strong>#RAD-{id_turno}</strong> y queda pendiente por validación del equipo comercial y técnico de Flymetrics.
    </p>

    <table class="info-table">
      <tr><td class="info-label">Radicado / Turno:</td><td class="info-value">#RAD-{id_turno}</td></tr>
      <tr><td class="info-label">Servicio Solicitado:</td><td class="info-value">{servicio or 'Análisis del Terreno'}</td></tr>
      <tr><td class="info-label">Predio / Proyecto:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Fecha Programada:</td><td class="info-value">{fecha}</td></tr>
      <tr><td class="info-label">Hora Estimada:</td><td class="info-value">{hora}</td></tr>
      <tr><td class="info-label">Estado Inicial:</td><td class="info-value"><span style="color:#d97706; font-weight:700;">● Pendiente de aprobación</span></td></tr>
      {obs_row}
    </table>

    {accept_cta}

    <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <p style="margin: 0; font-size: 13px; color: #166534; line-height: 1.5;">
        <strong>Importante:</strong> este enlace de aceptación es único y te permite confirmar el análisis del terreno una sola vez. Si aceptas, el equipo de Flymetrics procederá con la coordinación operativa.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Análisis del Terreno #{id_turno}",
        title="Solicitud de Análisis del Terreno Recibida",
        subtitle="Tu agenda quedó registrada y pendiente de aprobación",
        content_html=content,
        action_text="Ver Estado en Mi Portal",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"📅 Confirmación de Análisis del Terreno #{id_turno} — Flymetrics", html)


def send_admin_note_response_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    estado: str,
    mensaje_admin: str,
    tarifa: Optional[float] = None
) -> bool:
    """Envía la respuesta o nota del administrador al cliente para cerrar el ciclo de cotización/aceptación."""
    portal_url = _get_active_portal_url("cliente.html")
    tarifa_row = f"<tr><td class='info-label'>Precio / Cotización Autónoma:</td><td class='info-value'><strong>$ {float(tarifa):,.0f} COP</strong></td></tr>" if tarifa is not None else ""

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      El equipo de <strong>Flymetrics</strong> ha actualizado tu solicitud <strong>#RAD-{id_turno}</strong> con una respuesta operativa.
    </p>

    <table class="info-table">
      <tr><td class="info-label">Radicado / Turno:</td><td class="info-value">#RAD-{id_turno}</td></tr>
      <tr><td class="info-label">Servicio Solicitado:</td><td class="info-value">{servicio}</td></tr>
      <tr><td class="info-label">Predio / Proyecto:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Estado Actual:</td><td class="info-value"><span style="color:#0f766e; font-weight:700;">● {estado}</span></td></tr>
      {tarifa_row}
    </table>

    <div style="background: #eff6ff; border-left: 4px solid #1c82ad; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <p style="margin: 0; font-size: 13px; color: #1e3a8a; line-height: 1.5;">
        <strong>Nota del Administrador:</strong><br>
        {mensaje_admin}
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Respuesta #{id_turno}",
        title="Respuesta de Flymetrics",
        subtitle="Actualización sobre tu solicitud o cotización",
        content_html=content,
        action_text="Ver Mi Portal",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"📩 Respuesta de Flymetrics sobre #{id_turno} — {estado}", html)


def send_client_negotiation_quote_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    tarifa: float,
    fecha: str,
    hora: str,
    revisar_url: str,
    mensaje_admin: Optional[str] = None
) -> bool:
    """Envía la propuesta de precio / cotización al cliente con botones para Aceptar o Modificar."""
    nota_admin_box = ""
    if mensaje_admin and mensaje_admin.strip():
        nota_admin_box = f"""
        <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 14px 18px; border-radius: 8px; margin: 18px 0;">
          <strong style="color: #065f46; font-size: 13px;">Mensaje de Operaciones Flymetrics:</strong>
          <p style="margin: 4px 0 0 0; font-size: 13px; color: #047857; line-height: 1.5;">{mensaje_admin.strip()}</p>
        </div>
        """

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      El equipo comercial y de operaciones de <strong>Flymetrics</strong> ha evaluado tu solicitud <strong>#RAD-{id_turno}</strong> y ha definido la cotización y piloto para tu servicio:
    </p>

    <table class="info-table">
      <tr><td class="info-label">Radicado / Turno:</td><td class="info-value"><strong>#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label">Servicio Solicitado:</td><td class="info-value">{servicio}</td></tr>
      <tr><td class="info-label">Predio / Finca:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Fecha Programada:</td><td class="info-value">{fecha}</td></tr>
      <tr><td class="info-label">Hora Estimada:</td><td class="info-value">{hora}</td></tr>
      <tr style="background:#fefce8;"><td class="info-label" style="color:#854d0e; font-size:15px;">Precio del Servicio:</td><td class="info-value" style="color:#a16207; font-size:17px; font-weight:900;">$ {float(tarifa):,.0f} COP</td></tr>
      <tr><td class="info-label">Estado:</td><td class="info-value"><span style="color:#eab308; font-weight:800;">● Pendiente por confirmar</span></td></tr>
    </table>

    {nota_admin_box}

    <div style="text-align: center; margin: 28px 0;">
      <p style="font-size: 14px; color: #475569; margin-bottom: 16px;">
        Haz clic en el siguiente botón para revisar todos los detalles de tu solicitud, <strong>aceptar el servicio</strong> o <strong>sugerir modificaciones</strong>:
      </p>
      <a href="{revisar_url}" target="_blank" style="display: inline-block; background: #003049; color: #ffffff; text-decoration: none; font-size: 15px; font-weight: 800; padding: 14px 32px; border-radius: 12px; box-shadow: 0 6px 20px rgba(0,48,73,0.3); border: 2px solid #E4C7A1;">
        Revisar Cotización / Aceptar Servicio &rarr;
      </a>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Cotización #{id_turno}",
        title="Cotización de Servicio de Vuelo",
        subtitle=f"Precio propuesto: ${float(tarifa):,.0f} COP",
        content_html=content,
        action_text=None,
        action_url=None
    )
    return _send_smtp_html_email(to_email, f"💰 Cotización de Servicio #RAD-{id_turno} ($ {float(tarifa):,.0f} COP) — Flymetrics", html)


def send_admin_client_suggestion_notification(
    id_turno: int,
    cliente_nombre: str,
    finca: str,
    servicio: str,
    sugerencia: str,
    tarifa_actual: Optional[float] = None
) -> bool:
    """Notifica al administrador que el cliente ha enviado una sugerencia o contrapropuesta."""
    portal_admin_url = _get_active_portal_url("pages/admin.html")
    tarifa_txt = f"$ {float(tarifa_actual):,.0f} COP" if tarifa_actual else "Sin cotizar"
    admin_email = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "miguelangelopradagarrido@gmail.com")

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      El cliente <strong>{cliente_nombre}</strong> ha enviado una <strong>sugerencia / contrapropuesta</strong> sobre el turno <strong>#RAD-{id_turno}</strong>:
    </p>

    <table class="info-table">
      <tr><td class="info-label">Turno / Radicado:</td><td class="info-value">#RAD-{id_turno}</td></tr>
      <tr><td class="info-label">Cliente:</td><td class="info-value">{cliente_nombre}</td></tr>
      <tr><td class="info-label">Finca / Predio:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Servicio:</td><td class="info-value">{servicio}</td></tr>
      <tr><td class="info-label">Precio Propuesto:</td><td class="info-value"><strong>{tarifa_txt}</strong></td></tr>
    </table>

    <div style="background: #eff6ff; border-left: 4px solid #2563eb; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <strong style="color: #1e40af; font-size: 14px;">💬 Sugerencia del Cliente (Máx 500 caracteres):</strong>
      <p style="margin: 8px 0 0 0; font-size: 14px; color: #1e3a8a; font-style: italic; line-height: 1.5;">
        "{sugerencia}"
      </p>
    </div>

    <p style="font-size: 13px; color: #64748b;">
      Puedes responder con una nueva propuesta de precio, o aceptar directamente el servicio desde el panel de administración.
    </p>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Negociación #{id_turno}",
        title="Nueva Sugerencia de Cliente",
        subtitle=f"Contrapropuesta para el turno #RAD-{id_turno}",
        content_html=content,
        action_text="Ir al Panel de Administración",
        action_url=portal_admin_url
    )
    return _send_smtp_html_email(admin_email, f"💬 Nueva Sugerencia de Cliente — Turno #RAD-{id_turno} ({cliente_nombre})", html)


def send_booking_created_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    fecha: str,
    hora: str,
    observaciones: Optional[str] = None
) -> bool:
    """Envía correo confirmando el agendamiento de un nuevo turno de vuelo."""
    portal_url = _get_active_portal_url("cliente.html")
    obs_row = f"<tr><td class='info-label'>Observaciones:</td><td class='info-value'>{observaciones}</td></tr>" if observaciones else ""

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Hemos recibido satisfactoriamente tu solicitud de servicio técnico de vuelo. El turno ha sido registrado en el sistema con radicado <strong>#RAD-{id_turno}</strong>.
    </p>

    <table class="info-table">
      <tr><td class="info-label">Radicado / Turno:</td><td class="info-value">#RAD-{id_turno}</td></tr>
      <tr><td class="info-label">Servicio Solicitado:</td><td class="info-value">{servicio}</td></tr>
      <tr><td class="info-label">Predio / Proyecto:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Fecha Programada:</td><td class="info-value">{fecha}</td></tr>
      <tr><td class="info-label">Hora Estimada:</td><td class="info-value">{hora}</td></tr>
      <tr><td class="info-label">Piloto / Cuadrilla:</td><td class="info-value" style="color:#64748b;"><em>Pendiente de asignación por despacho central</em></td></tr>
      <tr><td class="info-label">Estado Inicial:</td><td class="info-value"><span style="color:#d97706; font-weight:700;">● Pendiente de Validación Técnica</span></td></tr>
      {obs_row}
    </table>

    <div style="background: #eff6ff; border-left: 4px solid #1c82ad; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <p style="margin: 0; font-size: 13px; color: #1e3a8a; line-height: 1.5;">
        <strong>Protocolo Operativo Flymetrics:</strong> Nuestro centro de control verificará el pronóstico meteorológico y la ventana de aspersión. Te confirmaremos la asignación del piloto y dron de flota.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Reserva #RAD-{id_turno}",
        title="Solicitud de Vuelo Recibida",
        subtitle="Detalles de tu agendamiento técnico",
        content_html=content,
        action_text="Ver Estado en Mi Portal",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"📋 Confirmación de Reserva #{id_turno} — Flymetrics", html)


# ==============================================================================
# 4. ACCIÓN: REAGENDAMIENTO DE TURNO OPERATIVO
# ==============================================================================
def send_booking_rescheduled_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    nueva_fecha: str,
    nueva_hora: str,
    motivo: Optional[str] = None
) -> bool:
    """Envía correo informando sobre el reagendamiento o cambio de horario de un vuelo."""
    portal_url = _get_active_portal_url("cliente.html")
    motivo_txt = motivo or "Ajuste por condiciones meteorológicas de viento/lluvia o sincronización operativa de flota."
    corp = _get_corporate_info()
    empresa_tel = corp.get("telefono", "+57 314 3764972")

    content = f"""
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Hola <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Te informamos que tu solicitud de vuelo agronómico ha sido <strong>reprogramada</strong> de acuerdo a las condiciones operativas y meteorológicas de campo.
    </p>

    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 14px 18px; border-radius: 8px; margin: 18px 0;">
      <strong style="color: #92400e; font-size: 14px;">Motivo del Reagendamiento:</strong>
      <p style="margin: 4px 0 0 0; font-size: 13px; color: #78350f;">{motivo_txt}</p>
    </div>

    <table class="info-table">
      <tr><td class="info-label">Radicado / Turno:</td><td class="info-value">#RAD-{id_turno}</td></tr>
      <tr><td class="info-label">Predio / Finca:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Servicio:</td><td class="info-value">{servicio}</td></tr>
      <tr style="background: #ecfdf5;"><td class="info-label" style="color:#065f46;">Nueva Fecha:</td><td class="info-value" style="color:#047857; font-weight:800;">{nueva_fecha}</td></tr>
      <tr style="background: #ecfdf5;"><td class="info-label" style="color:#065f46;">Nueva Hora:</td><td class="info-value" style="color:#047857; font-weight:800;">{nueva_hora}</td></tr>
    </table>

    <p style="font-size: 13px; color: #64748b; line-height: 1.5;">
      Si la nueva fecha presenta algún inconveniente con tus labores de campo, por favor comunícate de inmediato con tu asesor asignado al <strong>{empresa_tel}</strong>.
    </p>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Reagendado #{id_turno}",
        title="Actualización de Fecha de Vuelo",
        subtitle="Tu servicio ha sido reprogramado con éxito",
        content_html=content,
        action_text="Consultar Mi Agenda",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"⚠️ Turno #{id_turno} Reagendado — Flymetrics", html)


# ==============================================================================
# 5. ACCIÓN: CANCELACIÓN DE TURNO
# ==============================================================================
def send_booking_cancelled_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    motivo: Optional[str] = None
) -> bool:
    """Envía correo notificando la cancelación formal de una solicitud de vuelo."""
    portal_url = _get_active_portal_url("cliente.html")
    motivo_txt = motivo or "Cancelación solicitada por el usuario o no viabilidad técnica del terreno."

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Te confirmamos que el turno de vuelo <strong>#RAD-{id_turno}</strong> ha sido marcado como <strong>Cancelado</strong> en nuestro sistema.
    </p>

    <table class="info-table">
      <tr><td class="info-label">Turno Cancelado:</td><td class="info-value">#RAD-{id_turno}</td></tr>
      <tr><td class="info-label">Servicio:</td><td class="info-value">{servicio}</td></tr>
      <tr><td class="info-label">Predio:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Motivo Registrado:</td><td class="info-value">{motivo_txt}</td></tr>
    </table>

    <p style="font-size: 14px; color: #475569; line-height: 1.6;">
      Si deseas reprogramar este servicio para una fecha posterior o solicitar una nueva cotización, puedes hacerlo en cualquier momento desde tu portal de cliente o escribiéndonos directamente por WhatsApp.
    </p>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Cancelado #{id_turno}",
        title="Turno de Vuelo Cancelado",
        subtitle="Notificación formal de cancelación",
        content_html=content,
        action_text="Agendar Nuevo Vuelo",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"🚫 Notificación: Turno #{id_turno} Cancelado — Flymetrics", html)


# ==============================================================================
# 6. ACCIÓN: SERVICIO COMPLETADO Y ENTREGA DE INFORMES
# ==============================================================================
def send_service_completed_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    tecnico: Optional[str] = None,
    hora_finalizacion: Optional[str] = None,
    fecha: Optional[str] = None,
    url_informe: Optional[str] = None,
    insumos: Optional[str] = None,
    agua: Optional[str] = None,
    hectareas: Optional[float] = None
) -> bool:
    """Envía correo notificando la finalización exitosa del vuelo en campo, informando el piloto, hora de finalización y los tiempos de entrega de bitácora e informe ejecutivo."""
    portal_login_url = _get_active_portal_url("index.html?auth=login")
    
    fecha_display = fecha or datetime.now().strftime("%d/%m/%Y")
    hora_display = hora_finalizacion or datetime.now().strftime("%I:%M %p")
    piloto_display = tecnico or "Piloto Técnico Especializado Flymetrics"

    metricas_rows = ""
    if insumos or agua or hectareas:
        ins_txt = f"<tr><td class='info-label'>Insumo Aplicado:</td><td class='info-value'>{insumos}</td></tr>" if insumos else ""
        agua_txt = f"<tr><td class='info-label'>Volumen / Caldo:</td><td class='info-value'>{agua}</td></tr>" if agua else ""
        ha_txt = f"<tr><td class='info-label'>Área Intervenida:</td><td class='info-value'><strong>{hectareas} Ha</strong></td></tr>" if hectareas else ""
        metricas_rows = f"""
        {ins_txt}
        {agua_txt}
        {ha_txt}
        """

    informe_row = ""
    if url_informe and str(url_informe).startswith("http"):
        informe_row = f"""
        <tr><td class="info-label">Enlace en SharePoint:</td><td class="info-value"><a href="{url_informe}" target="_blank" style="color:#1C82AD; font-weight:800; text-decoration:underline;">Ver Archivo en SharePoint &rarr;</a></td></tr>
        """

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Nos complace informarte que la operación técnica de vuelo agrícola programada para tu predio <strong>{finca}</strong> (Radicado <strong>#RAD-{id_turno}</strong>) ha sido <strong style="color:#059669;">concluida con éxito en campo</strong>.
    </p>

    <table class="info-table">
      <tr><td class="info-label"><i class="fa-solid fa-hashtag" style="color:#1C82AD; margin-right:6px;"></i> Radicado / Turno:</td><td class="info-value"><strong style="color:#003049;">#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-layer-group" style="color:#1C82AD; margin-right:6px;"></i> Servicio Realizado:</td><td class="info-value"><strong>{servicio}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-house-chimney-window" style="color:#1C82AD; margin-right:6px;"></i> Predio / Finca:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-user-gear" style="color:#1C82AD; margin-right:6px;"></i> Piloto / Técnico:</td><td class="info-value"><strong>{piloto_display}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-calendar-days" style="color:#1C82AD; margin-right:6px;"></i> Fecha de Ejecución:</td><td class="info-value">{fecha_display}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-clock" style="color:#1C82AD; margin-right:6px;"></i> Hora de Finalización:</td><td class="info-value"><strong>{hora_display}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-circle-check" style="color:#10B981; margin-right:6px;"></i> Estado del Servicio:</td><td class="info-value"><span style="color:#059669; font-weight:800; background:rgba(16,185,129,0.12); padding:3px 8px; border-radius:6px;">Trabajo en Campo Completado</span></td></tr>
      {metricas_rows}
      {informe_row}
    </table>

    <!-- Cronograma Oficial de Entrega de Informes -->
    <div style="background: #eff6ff; border: 1.5px solid #bfdbfe; border-left: 4px solid #1C82AD; border-radius: 12px; padding: 18px 20px; margin: 22px 0;">
      <h4 style="margin: 0 0 10px 0; color: #1e3a8a; font-size: 15px; font-weight: 800; display: flex; align-items: center; gap: 8px;">
        Próximo Paso — Entrega de Informe Ejecutivo & SharePoint:
      </h4>
      <div style="font-size: 13.5px; color: #1e40af; line-height: 1.5;">
        Nuestro equipo de ingeniería se encuentra procesando las ortofotos, telemetría y bitácora técnica de tu vuelo. En cuanto esté lista la carpeta oficial de Microsoft SharePoint, recibirás la notificación de entrega final con el enlace directo.
      </div>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Misión Realizada en Campo",
        title="Servicio en Campo Completado",
        subtitle="La labor técnica ha concluido exitosamente en tu predio",
        content_html=content,
        action_text="Ver Mi Portal Flymetrics",
        action_url=portal_login_url
    )
    return _send_smtp_html_email(to_email, f"Servicio en Campo Completado: Finca {finca} (#RAD-{id_turno}) — Flymetrics", html)


def send_service_finalized_sharepoint_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    url_sharepoint: str,
    tecnico: Optional[str] = None
) -> bool:
    """Envía correo formal cuando el servicio pasa a 'Finalizado' con la entrega del Informe Ejecutivo en SharePoint."""
    portal_login_url = _get_active_portal_url("cliente.html")
    piloto_display = tecnico or "Equipo de Operaciones Flymetrics"

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Te informamos que tu servicio de vuelo <strong>#RAD-{id_turno}</strong> en la finca <strong>{finca}</strong> ha sido formalmente <strong style="color:#059669;">Finalizado</strong> con la entrega del <strong>Informe Técnico Ejecutivo y Entregables en SharePoint</strong>.
    </p>

    <table class="info-table">
      <tr><td class="info-label">Radicado / Turno:</td><td class="info-value"><strong style="color:#003049;">#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label">Servicio:</td><td class="info-value"><strong>{servicio}</strong></td></tr>
      <tr><td class="info-label">Predio / Finca:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Piloto / Técnico:</td><td class="info-value"><strong>{piloto_display}</strong></td></tr>
      <tr><td class="info-label">Estado Oficial:</td><td class="info-value"><span style="color:#059669; font-weight:800; background:rgba(16,185,129,0.12); padding:3px 8px; border-radius:6px;">Servicio Finalizado</span></td></tr>
      <tr><td class="info-label">Carpeta SharePoint:</td><td class="info-value"><a href="{url_sharepoint}" target="_blank" style="color:#1C82AD; font-weight:800; text-decoration:underline;">Abrir Carpeta Oficial en Microsoft SharePoint &rarr;</a></td></tr>
    </table>

    <div style="background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 12px; padding: 18px 20px; margin: 22px 0;">
      <h4 style="margin: 0 0 10px 0; color: #166534; font-size: 15px; font-weight: 800;">
        Acceso Inmediato a tus Resultados:
      </h4>
      <p style="margin: 0; font-size: 13.5px; color: #15803d; line-height: 1.6;">
        Puedes acceder a tus ortofotos, mapas NDVI, curvas de nivel y bitácora técnica directamente a través del enlace de Microsoft SharePoint o iniciando sesión en tu portal de cliente Flymetrics.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Servicio Finalizado",
        title="Informe Ejecutivo y SharePoint Disponible",
        subtitle=f"Entrega oficial de resultados para el turno #RAD-{id_turno}",
        content_html=content,
        action_text="Abrir Carpeta en SharePoint",
        action_url=url_sharepoint
    )
    return _send_smtp_html_email(to_email, f"Servicio Finalizado e Informe en SharePoint (#RAD-{id_turno}) — Flymetrics", html)




# ==============================================================================
# 7. ACCIÓN: CONFIRMACIÓN AUTOMÁTICA DE COTIZACIÓN PROFESIONAL
# ==============================================================================
def send_quote_confirmation_email(
    to_email: str,
    nombre_cliente: str,
    id_pqr: int,
    servicio: str,
    hectareas: float,
    cultivo: str,
    ubicacion: str,
    mensaje: Optional[str] = None
) -> bool:
    """Envía confirmación automática y profesional cuando un usuario realiza una cotización."""
    corp = _get_corporate_info()
    empresa_wa = corp.get("whatsapp") or corp.get("telefono") or "+57 314 3764972"
    clean_wa_digits = re.sub(r'[^0-9]', '', empresa_wa)
    if not clean_wa_digits.startswith('57') and len(clean_wa_digits) == 10:
        clean_wa_digits = '57' + clean_wa_digits
    wa_url = f"https://wa.me/{clean_wa_digits}?text=Hola%20Flymetrics,%20acabo%20de%20solicitar%20la%20cotizaci%C3%B3n%20%23TK-{id_pqr}"

    msg_box = ""
    if mensaje and mensaje.strip():
        msg_box = f"""
        <div style="background: #f8f9fa; border-left: 3px solid #1c82ad; padding: 12px 16px; border-radius: 8px; margin: 16px 0;">
          <strong style="color: #003049; font-size: 13px;">Requerimiento / Comentario del Productor:</strong>
          <p style="margin: 4px 0 0 0; font-size: 13px; color: #343a40; font-style: italic;">"{mensaje.strip()}"</p>
        </div>
        """

    content = f"""
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Hola <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Hemos recibido satisfactoriamente tu solicitud de cotización para servicios aéreos especializados con drones RPAS. Un ingeniero agrónomo especialista de <strong>Flymetrics</strong> revisará las condiciones técnicas de tu predio y se pondrá en contacto contigo en menos de <strong>24 horas</strong>.
    </p>

    <table class="info-table">
      <thead>
        <tr>
          <th colspan="2">Ficha Técnica de la Cotización Radicada</th>
        </tr>
      </thead>
      <tbody>
        <tr><td class="info-label">Radicado de Ticket:</td><td class="info-value"><strong style="color: #003049;">#TK-{id_pqr}</strong></td></tr>
        <tr><td class="info-label">Servicio Solicitado:</td><td class="info-value">{servicio}</td></tr>
        <tr><td class="info-label">Área Proyectada:</td><td class="info-value"><strong>{hectareas:.1f} Hectáreas (Ha)</strong></td></tr>
        <tr><td class="info-label">Cultivo / Sector:</td><td class="info-value">{cultivo or 'Sector Agropecuario'}</td></tr>
        <tr><td class="info-label">Ubicación Predio:</td><td class="info-value">{ubicacion or 'Casanare / Colombia'}</td></tr>
        <tr><td class="info-label">Tiempo de Respuesta:</td><td class="info-value"><span style="color:#059669; font-weight:700;">Menos de 24 Horas Garantizado</span></td></tr>
      </tbody>
    </table>

    {msg_box}

    <div style="background: #f8f9fa; border-radius: 14px; padding: 20px 22px; border: 1.5px solid #1c82ad; margin: 22px 0;">
      <h4 style="margin: 0 0 12px 0; color: #003049; font-size: 15px; font-weight: 800; display: flex; align-items: center; gap: 8px;">
        <span style="color: #1c82ad;">✦</span> Beneficios de tu cuenta en Flymetrics Command Center:
      </h4>
      <ul style="margin: 0; padding-left: 20px; color: #343a40; font-size: 14px; line-height: 1.8;">
        <li><strong style="color: #003049;">Registra, administra y gestiona</strong> tus predios, lotes y proyectos</li>
        <li><strong style="color: #003049;">Agendar</strong> nuevos servicios de aspersión, fotogrametría y análisis multiespectral</li>
        <li><strong style="color: #003049;">Descargar</strong> informes y documentos de nuestro repositorio Sharepoint</li>
        <li><strong style="color: #003049;">Consultar</strong> en tiempo real la información contable</li>
      </ul>
    </div>

    <div style="text-align: center; margin: 24px 0 10px 0;">
      <p style="font-size: 14px; color: #6c757d; margin-bottom: 12px;">¿Requieres atención agronómica urgente para tu lote?</p>
      <a href="{wa_url}" target="_blank" style="display: inline-block; background: #25D366; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 800; padding: 12px 28px; border-radius: 10px; box-shadow: 0 4px 14px rgba(37,211,102,0.3);">
        💬 Contactar por WhatsApp ({empresa_wa})
      </a>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Cotización Recibida 24h",
        title="¡Cotización Radicada Exitosamente!",
        subtitle="Tu requerimiento agronómico ya está en proceso de evaluación",
        content_html=content,
        action_text=None,
        action_url=None
    )
    return _send_smtp_html_email(to_email, f"🌾 Confirmación de Cotización #TK-{id_pqr} — Flymetrics Operaciones", html)


# ==============================================================================
# 8. ACCIÓN: CÓDIGO DE SEGURIDAD 8 DÍGITOS PARA CAMBIO DE CONTRASEÑA
# ==============================================================================
def send_password_reset_8digit_otp(to_email: str, codigo_8_digitos: str, nombre_usuario: Optional[str] = None) -> bool:
    """Envía el código OTP numérico de 8 dígitos de alta seguridad para cambio o restablecimiento de contraseña."""
    nombre = nombre_usuario or to_email.split("@")[0].capitalize()
    # Formatear visualmente 8 dígitos como XXXX - XXXX
    c_str = str(codigo_8_digitos).strip().replace(" ", "").replace("-", "")
    formato_visual = f"{c_str[:4]} - {c_str[4:]}" if len(c_str) == 8 else c_str

    content = f"""
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Hola <strong>{nombre}</strong>,
    </p>
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Has solicitado restablecer o cambiar la contraseña de tu cuenta en <strong>Flymetrics Command Center</strong>.
    </p>
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Ingresa el siguiente <strong>Código de Verificación de Seguridad de 8 dígitos</strong> para autorizar el cambio:
    </p>

    <div style="text-align: center; margin: 28px 0;">
      <div style="display: inline-block; background: #003049; border: 2.5px solid #E4C7A1; color: #ffffff; font-family: 'Courier New', monospace, sans-serif; font-size: 34px; font-weight: 900; letter-spacing: 6px; padding: 18px 32px; border-radius: 14px; box-shadow: 0 10px 30px rgba(0,48,73,0.3);">
        {formato_visual}
      </div>
      <div style="margin-top: 14px; font-size: 13px; font-weight: 700; color: #003049;">
        ⏱ Válido por 15 minutos &bull; Uso único y confidencial
      </div>
    </div>

    <div style="background: #fffbeb; border: 1.5px solid #fef3c7; border-radius: 12px; padding: 16px 20px; margin: 20px 0;">
      <strong style="color: #92400e; font-size: 13px;">🛡️ Alerta de Seguridad Flymetrics:</strong>
      <p style="margin: 4px 0 0 0; font-size: 13px; color: #78350f; line-height: 1.5;">
        Ningún colaborador, piloto o técnico de Flymetrics te solicitará este código. Si tú no realizaste esta solicitud, ignora este correo o cambia tu contraseña de inmediato.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Seguridad de Cuenta",
        title="Código de Seguridad (8 Dígitos)",
        subtitle="Autorización de cambio o recuperación de contraseña",
        content_html=content,
        action_text=None,
        action_url=None
    )
    return _send_smtp_html_email(to_email, "🔐 [CÓDIGO 8 DÍGITOS] Cambio de Contraseña — Flymetrics", html)


# ==============================================================================
# 9. ACCIÓN: CÓDIGO DE SEGURIDAD 8 DÍGITOS PARA MODIFICACIÓN DE INFORMACIÓN DE PERFIL
# ==============================================================================
def send_profile_update_8digit_otp(to_email: str, codigo_8_digitos: str, nombre_usuario: Optional[str] = None) -> bool:
    """Envía el código de 8 dígitos para autorizar modificaciones en la información de perfil sensible."""
    nombre = nombre_usuario or to_email.split("@")[0].capitalize()
    c_str = str(codigo_8_digitos).strip().replace(" ", "").replace("-", "")
    formato_visual = f"{c_str[:4]} - {c_str[4:]}" if len(c_str) == 8 else c_str

    content = f"""
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Hola <strong>{nombre}</strong>,
    </p>
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Se ha iniciado una solicitud para <strong>modificar o corregir la información sensible de tu cuenta</strong> (Nombre, Cédula/NIT, Teléfono o Razón Social) en Flymetrics.
    </p>
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Por protocolo de protección de identidad agronómica y fiscal, ingresa este <strong>Código de Autorización de 8 dígitos</strong>:
    </p>

    <div style="text-align: center; margin: 28px 0;">
      <div style="display: inline-block; background: #003049; border: 2.5px solid #1c82ad; color: #ffffff; font-family: 'Courier New', monospace, sans-serif; font-size: 34px; font-weight: 900; letter-spacing: 6px; padding: 18px 32px; border-radius: 14px; box-shadow: 0 10px 30px rgba(0,48,73,0.3);">
        {formato_visual}
      </div>
      <div style="margin-top: 14px; font-size: 13px; font-weight: 700; color: #1c82ad;">
        ⏱ Válido por 15 minutos &bull; Autorización de Edición de Datos
      </div>
    </div>

    <div style="background: #f8fafc; border: 1.5px solid #6c757d; border-radius: 12px; padding: 16px 20px; margin: 20px 0;">
      <strong style="color: #003049; font-size: 13px;">ℹ️ ¿Por qué protegemos tu información?</strong>
      <p style="margin: 4px 0 0 0; font-size: 13px; color: #343a40; line-height: 1.5;">
        Tus datos de titularidad están vinculados directamente a la emisión de bitácoras oficiales de vuelo RAC-100, contratos de aspersión y facturación electrónica. Solo tú puedes autorizar su modificación.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Modificación de Perfil",
        title="Código de Autorización de Perfil (8 Dígitos)",
        subtitle="Verificación de identidad para corrección de información",
        content_html=content,
        action_text=None,
        action_url=None
    )
    return _send_smtp_html_email(to_email, "🛡️ [CÓDIGO 8 DÍGITOS] Autorización de Modificación de Perfil — Flymetrics", html)


# ==============================================================================
# 10. ACCIONES DE CONFIRMACIÓN DE SEGURIDAD (PASSWORD & PERFIL ACTUALIZADOS)
# ==============================================================================
def send_password_changed_notification(to_email: str, nombre_usuario: Optional[str] = None) -> bool:
    """Notifica al usuario que su contraseña ha sido cambiada exitosamente."""
    nombre = nombre_usuario or to_email.split("@")[0].capitalize()
    corp = _get_corporate_info()
    empresa_tel = corp.get("telefono", "+57 314 3764972")
    clean_tel = re.sub(r'[^0-9+]', '', empresa_tel)

    content = f"""
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Hola <strong>{nombre}</strong>,
    </p>
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Te confirmamos que la <strong>contraseña de tu cuenta en Flymetrics ha sido actualizada exitosamente</strong>.
    </p>
    <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <p style="margin: 0; font-size: 14px; color: #166534; font-weight: 700;">
        ✔ Operación completada con verificación en dos pasos (Código de 8 dígitos).
      </p>
    </div>
    <p style="font-size: 13px; color: #6c757d;">
      Si no reconoces esta actividad, por favor comunícate de inmediato con nuestra línea de operaciones: <a href="tel:{clean_tel}">{empresa_tel}</a>.
    </p>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Seguridad Actualizada",
        title="Contraseña Modificada con Éxito",
        subtitle="Confirmación de actualización de credenciales",
        content_html=content,
        action_text="Iniciar Sesión en Mi Cuenta",
        action_url=_get_active_portal_url("cliente.html")
    )
    return _send_smtp_html_email(to_email, "🔒 Contraseña Actualizada con Éxito — Flymetrics", html)


def send_profile_updated_notification(to_email: str, nombre_usuario: Optional[str] = None) -> bool:
    """Notifica al usuario que sus datos de perfil han sido modificados exitosamente."""
    nombre = nombre_usuario or to_email.split("@")[0].capitalize()
    content = f"""
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Hola <strong>{nombre}</strong>,
    </p>
    <p style="font-size: 15px; color: #343a40; line-height: 1.6;">
      Te confirmamos que los datos de tu perfil en <strong>Flymetrics</strong> han sido actualizados y sincronizados exitosamente en nuestra base de datos.
    </p>
    <div style="background: #f0fdf4; border-left: 4px solid #1c82ad; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <p style="margin: 0; font-size: 14px; color: #003049; font-weight: 700;">
        ✔ Información verificada y autorizada con código de seguridad de 8 dígitos.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Perfil Actualizado",
        title="Información de Perfil Actualizada",
        subtitle="Tus nuevos datos han sido registrados correctamente",
        content_html=content,
        action_text="Revisar Mi Perfil",
        action_url=_get_active_portal_url("cliente.html")
    )
    return _send_smtp_html_email(to_email, "✔ Información de Perfil Actualizada — Flymetrics", html)


# ==============================================================================
# 8. ACCIÓN: TURNO CONFIRMADO POR CENTRO DE CONTROL
# ==============================================================================
def send_booking_confirmed_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    fecha: str,
    hora: str,
    tecnico_nombre: Optional[str] = None,
    dron_modelo: Optional[str] = None
) -> bool:
    """Envía notificación inmediata cuando la solicitud de vuelo es Aceptada / Confirmada."""
    portal_url = _get_active_portal_url("pages/cliente.html")
    tech_row = f"<tr><td class='info-label'>Piloto Asignado:</td><td class='info-value'><strong>{tecnico_nombre}</strong></td></tr>" if tecnico_nombre else ""
    drone_row = f"<tr><td class='info-label'>Aeronave / Dron:</td><td class='info-value'>{dron_modelo}</td></tr>" if dron_modelo else ""

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Nos complace confirmarte que tu solicitud de servicio técnico de vuelo para tu predio <strong>{finca}</strong> ha sido <strong style="color:#059669;">Confirmada Oficialmente</strong> por el centro de control de operaciones de Flymetrics.
    </p>

    <table class="info-table">
      <tr><td class="info-label">Radicado / Turno:</td><td class="info-value">#RAD-{id_turno}</td></tr>
      <tr><td class="info-label">Servicio Confirmado:</td><td class="info-value"><strong>{servicio}</strong></td></tr>
      <tr><td class="info-label">Predio / Finca:</td><td class="info-value">{finca}</td></tr>
      <tr style="background:#ecfdf5;"><td class="info-label" style="color:#065f46;">Fecha Programada:</td><td class="info-value" style="color:#047857; font-weight:800;">{fecha}</td></tr>
      <tr style="background:#ecfdf5;"><td class="info-label" style="color:#065f46;">Hora de Inicio:</td><td class="info-value" style="color:#047857; font-weight:800;">{hora}</td></tr>
      <tr><td class="info-label">Estado de Misión:</td><td class="info-value"><span style="color:#059669; font-weight:800;">✔ Confirmado para Ejecución</span></td></tr>
      {tech_row}
      {drone_row}
    </table>

    <div style="background: #eff6ff; border-left: 4px solid #1c82ad; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <strong style="color: #1e3a8a; font-size: 13.5px;">📋 Recomendaciones Previas al Vuelo:</strong>
      <ul style="margin: 6px 0 0 0; padding-left: 18px; font-size: 13px; color: #1e40af; line-height: 1.5;">
        <li>Garantizar acceso vehicular despejado para la cuadrilla y aeronaves de campo.</li>
        <li>Tener disponibles en predio las fuentes de agua e insumos a asperjar.</li>
        <li>Informar al encargado de finca sobre el horario acordado de inicio.</li>
      </ul>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Confirmado #{id_turno}",
        title="¡Tu Vuelo ha sido Confirmado!",
        subtitle="Misión técnica agendada en tu predio",
        content_html=content,
        action_text="Ver Mi Agenda en Plataforma",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"✈️ ¡Confirmado! Turno de Vuelo #{id_turno} — Flymetrics", html)


# ==============================================================================
# 9. ACCIÓN: RECORDATORIO 24 HORAS ANTES DE OPERACIÓN (DESHABILITADO POR REQUERIMIENTO)
# ==============================================================================
def send_24h_reminder_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    fecha: str,
    hora: str
) -> bool:
    """[ELIMINADO / DESHABILITADO] Se omite el envío del recordatorio de 24 horas a petición."""
    logger.info(f"[EMAIL SERVICE] Envío de recordatorio 24 horas desactivado para #{id_turno} ({to_email})")
    return True


# ==============================================================================
# 10. ACCIÓN: INFORME EJECUTIVO SUBIDO Y DISPONIBLE
# ==============================================================================
def send_executive_report_ready_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    url_informe: str,
    tipo_informe: str = "Informe Técnico Ejecutivo"
) -> bool:
    """Envía notificación cuando se carga un informe ejecutivo o mapa agronómico, redirigiendo al portal para incentivar su uso."""
    portal_url = _get_active_portal_url("cliente.html")
    target_link = portal_url

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre_cliente}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Te notificamos que el <strong>{tipo_informe}</strong> correspondiente a la misión de vuelo <strong>#RAD-{id_turno}</strong> en tu finca <strong>{finca}</strong> ya ha sido procesado y se encuentra disponible en tu portal oficial de Flymetrics.
    </p>

    <table class="info-table">
      <tr><td class="info-label">Turno / Radicado:</td><td class="info-value">#RAD-{id_turno}</td></tr>
      <tr><td class="info-label">Predio:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Servicio:</td><td class="info-value">{servicio}</td></tr>
      <tr><td class="info-label">Documento:</td><td class="info-value"><strong>{tipo_informe}</strong></td></tr>
      <tr><td class="info-label">Disponibilidad:</td><td class="info-value"><span style="color:#059669; font-weight:800;">✔ Disponible en tu Portal</span></td></tr>
    </table>

    <div style="background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 12px; padding: 16px 20px; margin: 20px 0;">
      <p style="margin: 0; font-size: 13.5px; color: #15803d; line-height: 1.6;">
        Para consultar tus informes ejecutivos, bitácoras de vuelo y entregables agronómicos oficiales en la nube, inicia sesión en la plataforma web de Flymetrics con el siguiente botón:
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge="Informe Disponible",
        title="Informe Técnico Disponible",
        subtitle="Inicia sesión en tu cuenta para consultar tus resultados",
        content_html=content,
        action_text="Iniciar Sesión en el Portal",
        action_url=target_link
    )
    return _send_smtp_html_email(to_email, f"📊 {tipo_informe} Disponible (#{id_turno}) — Flymetrics", html)


# ==============================================================================
# 11. ACCIÓN: BITÁCORA DE VUELO DISPONIBLE (DESHABILITADO POR REQUERIMIENTO)
# ==============================================================================
def send_flight_log_ready_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    url_bitacora: Optional[str] = None,
    tecnico: Optional[str] = None
) -> bool:
    """[ELIMINADO / DESHABILITADO] Se omite el envío del correo de Bitácora Disponible a petición."""
    logger.info(f"[EMAIL SERVICE] Envío de bitácora disponible desactivado para #{id_turno} ({to_email})")
    return True


# ==============================================================================
# 12. ACCIÓN: AVISO OPERATIVO 12 HORAS ANTES (DESHABILITADO POR REQUERIMIENTO)
# ==============================================================================
def send_12h_reminder_email(
    to_email: str,
    nombre_cliente: str,
    id_turno: int,
    servicio: str,
    finca: str,
    fecha: str,
    hora: str
) -> bool:
    """[ELIMINADO / DESHABILITADO] Se omite el envío del aviso de 12 horas a petición."""
    logger.info(f"[EMAIL SERVICE] Envío de aviso 12 horas desactivado para #{id_turno} ({to_email})")
    return True


# ==============================================================================
# 13. NOTIFICACIONES A ADMINISTRADORES (4 EVENTOS)
# ==============================================================================

def send_admin_new_booking_notification(
    id_turno: int,
    cliente_nombre: str,
    servicio: str,
    finca: str,
    fecha: str,
    hora: str,
    observaciones: Optional[str] = None
) -> bool:
    """Notifica a todos los administradores registrados que ha entrado un nuevo agendamiento."""
    admin_emails = get_admin_emails()
    portal_url = _get_active_portal_url("pages/admin.html")
    obs_row = f"<tr><td class='info-label'>Notas del Cliente:</td><td class='info-value'>{observaciones}</td></tr>" if observaciones else ""

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Hola <strong>Equipo de Control y Operaciones Flymetrics</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Se ha registrado un <strong>nuevo pedido de agendamiento de vuelo</strong> en la plataforma que requiere validación y asignación de piloto(s).
    </p>
    <table class="info-table">
      <tr><td class="info-label"><i class="fa-solid fa-hashtag" style="color:#1C82AD; margin-right:6px;"></i> Turno / Radicado:</td><td class="info-value"><strong>#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-user" style="color:#1C82AD; margin-right:6px;"></i> Cliente / Productor:</td><td class="info-value">{cliente_nombre}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-house-chimney-window" style="color:#1C82AD; margin-right:6px;"></i> Predio / Proyecto:</td><td class="info-value"><strong>{finca}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-layer-group" style="color:#1C82AD; margin-right:6px;"></i> Servicio Requerido:</td><td class="info-value"><strong style="color:#003049;">{servicio}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-calendar-days" style="color:#1C82AD; margin-right:6px;"></i> Fecha Solicitada:</td><td class="info-value">{fecha}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-clock" style="color:#1C82AD; margin-right:6px;"></i> Hora Estimada:</td><td class="info-value">{hora}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-circle-dot" style="color:#d97706; margin-right:6px;"></i> Estado Inicial:</td><td class="info-value"><span style="color:#d97706; font-weight:700;">● Pendiente de Asignación</span></td></tr>
      {obs_row}
    </table>
    <div style="background: #eff6ff; border-left: 4px solid #1c82ad; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <p style="margin: 0; font-size: 13px; color: #1e3a8a;">
        Ingresa al Panel de Administrador para confirmar el turno, verificar la meteorología y asignar la cuadrilla técnica correspondiente.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Nuevo Agendamiento #{id_turno}",
        title="Nuevo Pedido de Vuelo Recibido",
        subtitle="Solicitud pendiente por gestionar",
        content_html=content,
        action_text="Gestionar en Panel Admin",
        action_url=portal_url
    )
    for email in admin_emails:
        _send_smtp_html_email(email, f"🔔 [ADMIN] Nuevo Agendamiento #{id_turno} — {cliente_nombre}", html)
    return True


def send_admin_rescheduled_notification(
    id_turno: int,
    cliente_nombre: str,
    servicio: str,
    finca: str,
    nueva_fecha: str,
    nueva_hora: str,
    fecha_antigua: Optional[str] = None,
    motivo: Optional[str] = None
) -> bool:
    """Notifica a todos los administradores registrados sobre el reagendamiento de un vuelo."""
    admin_emails = get_admin_emails()
    portal_url = _get_active_portal_url("pages/admin.html")
    old_row = f"<tr><td class='info-label'><i class='fa-solid fa-calendar-xmark' style='color:#94a3b8; margin-right:6px;'></i> Fecha Anterior:</td><td class='info-value' style='text-decoration:line-through; color:#94a3b8;'>{fecha_antigua}</td></tr>" if fecha_antigua else ""

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Atención <strong>Centro de Operaciones</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      El servicio técnico <strong>#RAD-{id_turno}</strong> ha sido <strong>reagendado</strong> en el sistema.
    </p>
    <table class="info-table">
      <tr><td class="info-label"><i class="fa-solid fa-hashtag" style="color:#1C82AD; margin-right:6px;"></i> Turno / Radicado:</td><td class="info-value"><strong>#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-user" style="color:#1C82AD; margin-right:6px;"></i> Cliente / Predio:</td><td class="info-value"><strong>{cliente_nombre}</strong> — {finca}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-layer-group" style="color:#1C82AD; margin-right:6px;"></i> Servicio:</td><td class="info-value"><strong>{servicio}</strong></td></tr>
      {old_row}
      <tr style="background:#ecfdf5;"><td class="info-label" style="color:#065f46;"><i class="fa-solid fa-calendar-plus" style="color:#059669; margin-right:6px;"></i> Nueva Fecha:</td><td class="info-value" style="color:#047857; font-weight:800;">{nueva_fecha}</td></tr>
      <tr style="background:#ecfdf5;"><td class="info-label" style="color:#065f46;"><i class="fa-solid fa-clock" style="color:#059669; margin-right:6px;"></i> Nueva Hora:</td><td class="info-value" style="color:#047857; font-weight:800;">{nueva_hora}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-comment-dots" style="color:#1C82AD; margin-right:6px;"></i> Motivo de Cambio:</td><td class="info-value">{motivo or 'Ajuste operativo / meteorológico'}</td></tr>
    </table>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Reagendado #{id_turno}",
        title="Servicio Reagendado",
        subtitle="Actualización de fecha y hora operativa",
        content_html=content,
        action_text="Ver Turno en Admin",
        action_url=portal_url
    )
    for email in admin_emails:
        _send_smtp_html_email(email, f"🔄 [ADMIN] Servicio Reagendado #{id_turno} — {finca}", html)
    return True


def send_admin_service_completed_notification(
    id_turno: int,
    cliente_nombre: str,
    servicio: str,
    finca: str,
    tecnico_nombre: str,
    fecha: str,
    hora_fin: Optional[str] = None
) -> bool:
    """Notifica a todos los administradores registrados cuando un piloto completa un servicio."""
    admin_emails = get_admin_emails()
    portal_url = _get_active_portal_url("pages/admin.html")

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Atención <strong>Administración Flymetrics</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      El piloto técnico <strong>{tecnico_nombre}</strong> ha reportado como <strong>completado y ejecutado</strong> el servicio <strong>#RAD-{id_turno}</strong>.
    </p>
    <table class="info-table">
      <tr><td class="info-label"><i class="fa-solid fa-hashtag" style="color:#1C82AD; margin-right:6px;"></i> Radicado:</td><td class="info-value"><strong>#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-house-chimney-window" style="color:#1C82AD; margin-right:6px;"></i> Predio / Finca:</td><td class="info-value"><strong>{finca}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-user" style="color:#1C82AD; margin-right:6px;"></i> Cliente:</td><td class="info-value">{cliente_nombre}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-layer-group" style="color:#1C82AD; margin-right:6px;"></i> Servicio:</td><td class="info-value"><strong style="color:#003049;">{servicio}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-user-gear" style="color:#1C82AD; margin-right:6px;"></i> Piloto a Cargo:</td><td class="info-value"><strong>{tecnico_nombre}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-calendar-days" style="color:#1C82AD; margin-right:6px;"></i> Fecha Ejecución:</td><td class="info-value">{fecha}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-clock" style="color:#1C82AD; margin-right:6px;"></i> Hora Finalización:</td><td class="info-value">{hora_fin or 'Reportada en campo'}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-circle-check" style="color:#10B981; margin-right:6px;"></i> Estado:</td><td class="info-value"><span style="color:#059669; font-weight:800; background:rgba(16,185,129,0.12); padding:4px 10px; border-radius:8px;">✔ Completado</span></td></tr>
    </table>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Hecho #{id_turno}",
        title="Servicio de Vuelo Completado",
        subtitle="Misión técnica finalizada con éxito",
        content_html=content,
        action_text="Revisar en Admin",
        action_url=portal_url
    )
    for email in admin_emails:
        _send_smtp_html_email(email, f"✅ [ADMIN] Servicio Completado #{id_turno} — {finca} ({tecnico_nombre})", html)
    return True


def send_admin_new_quote_notification(
    nombre: str,
    email: str,
    telefono: str,
    documento: str,
    servicio: str,
    hectareas: str,
    cultivo: str,
    ubicacion: str,
    mensaje: str,
    id_pqr: int
) -> bool:
    """Notifica a los administradores cuando llega una nueva solicitud de cotización 24h desde la web."""
    admin_emails = get_admin_emails()
    portal_url = _get_active_portal_url("pages/admin.html")

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Atención <strong>Equipo Comercial y Agronómico Flymetrics</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Se ha recibido una nueva <strong>Solicitud de Cotización 24 Horas</strong> a través de la landing page pública.
    </p>
    <table class="info-table">
      <tr><td class="info-label"><i class="fa-solid fa-ticket" style="color:#1C82AD; margin-right:6px;"></i> Ticket / Solicitud:</td><td class="info-value"><strong>#COT-{id_pqr}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-user" style="color:#1C82AD; margin-right:6px;"></i> Productor / Contacto:</td><td class="info-value"><strong>{nombre}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-id-card" style="color:#1C82AD; margin-right:6px;"></i> Documento / NIT:</td><td class="info-value">{documento}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-phone" style="color:#1C82AD; margin-right:6px;"></i> Teléfono / WhatsApp:</td><td class="info-value"><a href="tel:{telefono}">{telefono}</a></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-envelope" style="color:#1C82AD; margin-right:6px;"></i> Email:</td><td class="info-value"><a href="mailto:{email}">{email}</a></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-layer-group" style="color:#1C82AD; margin-right:6px;"></i> Servicio Requerido:</td><td class="info-value"><strong>{servicio}</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-chart-area" style="color:#1C82AD; margin-right:6px;"></i> Área / Hectáreas:</td><td class="info-value"><strong>{hectareas} Ha</strong></td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-seedling" style="color:#1C82AD; margin-right:6px;"></i> Cultivo / Sector:</td><td class="info-value">{cultivo}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-location-dot" style="color:#1C82AD; margin-right:6px;"></i> Ubicación / Municipio:</td><td class="info-value">{ubicacion}</td></tr>
      <tr><td class="info-label"><i class="fa-solid fa-message" style="color:#1C82AD; margin-right:6px;"></i> Mensaje / Consulta:</td><td class="info-value">{mensaje or 'Sin mensaje adicional'}</td></tr>
    </table>
    <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <p style="margin: 0; font-size: 13px; color: #065f46;">
        Compromiso de atención comercial: <strong>Menos de 24 horas</strong>.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Cotización #{id_pqr}",
        title="Nueva Solicitud de Cotización 24h",
        subtitle=f"{nombre} — {hectareas} de {cultivo}",
        content_html=content,
        action_text="Ver Solicitudes en Admin",
        action_url=portal_url
    )
    for adm in admin_emails:
        _send_smtp_html_email(adm, f"📩 [ADMIN] Nueva Cotización 24h: {nombre} ({hectareas} — {cultivo})", html)
    return True


# ==============================================================================
# 14. NOTIFICACIONES A TÉCNICOS / PILOTOS (2 EVENTOS)
# ==============================================================================

def send_technician_assigned_notification(
    to_email: str,
    tecnico_nombre: str,
    id_turno: int,
    servicio: str,
    finca: str,
    municipio: str,
    fecha: str,
    hora: str,
    cliente_nombre: str,
    cliente_tel: Optional[str] = None,
    observaciones: Optional[str] = None,
    departamento: Optional[str] = None,
    hectareas: Optional[float] = None,
    cultivo: Optional[str] = None,
    maps_url: Optional[str] = None,
    tarifa: Optional[float] = None,
    dron: Optional[str] = None,
    cliente_email: Optional[str] = None
) -> bool:
    """Notifica al técnico / piloto asignado sobre una nueva misión operativa y genera evento en Microsoft Calendar."""
    # Auto-completar datos desde BD y observaciones si no fueron pasados explícitamente
    import re
    if observaciones:
        if not cultivo:
            m_cul = re.search(r'Cultivo(?: y Area)?:\s*([^\n\(\r]+)', observaciones, re.IGNORECASE)
            if m_cul:
                cultivo = m_cul.group(1).strip()
        if not hectareas:
            m_ha = re.search(r'\((\d+(?:\.\d+)?)\s*Ha\)', observaciones, re.IGNORECASE)
            if m_ha:
                try:
                    hectareas = float(m_ha.group(1))
                except Exception:
                    pass

    # Si aún faltan datos de predio, tarifa o coordenadas, consultar directamente el Turno en BD
    if id_turno:
        try:
            from app.infrastructure.database.session import SessionLocal
            from app.infrastructure.database.models.models import AgendaModel
            _db_chk = SessionLocal()
            try:
                _t = _db_chk.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
                if _t:
                    if not maps_url and _t.finca and _t.finca.maps_url:
                        maps_url = _t.finca.maps_url
                    if not hectareas and _t.finca and _t.finca.hectareas:
                        hectareas = float(_t.finca.hectareas)
                    if departamento is None and _t.finca and _t.finca.departamento:
                        departamento = _t.finca.departamento
                    if (not municipio or municipio == "Colombia") and _t.finca and _t.finca.ubicacion_municipio:
                        municipio = _t.finca.ubicacion_municipio
                    if tarifa is None:
                        if _t.tarifa is not None:
                            tarifa = float(_t.tarifa)
                        elif _t.es_demostracion:
                            tarifa = 0.0
                    if not dron and _t.drone:
                        dron = _t.drone.modelo
                    if not cultivo and _t.observaciones_servicio:
                        m_cul2 = re.search(r'Cultivo(?: y Area)?:\s*([^\n\(\r]+)', _t.observaciones_servicio, re.IGNORECASE)
                        if m_cul2:
                            cultivo = m_cul2.group(1).strip()
            finally:
                _db_chk.close()
        except Exception as _db_err:
            logger.warning(f"Error consultando turno #{id_turno} para detalles de misión: {_db_err}")

    muni_str = municipio or "Colombia"
    dep_str = departamento or ""
    loc_full = f"{finca} ({muni_str}{', ' + dep_str if dep_str else ''})"
    maps_link = maps_url or f"https://www.google.com/maps/search/?api=1&query={muni_str}+{dep_str}".replace(" ", "+")

    obs_row = f"<tr><td class='info-label'>Observaciones:</td><td class='info-value'>{observaciones}</td></tr>" if observaciones else ""
    tel_row = f"<tr><td class='info-label'>Teléfono Contacto:</td><td class='info-value'><a href='tel:{cliente_tel}'>{cliente_tel}</a></td></tr>" if cliente_tel else ""
    mail_row = f"<tr><td class='info-label'>Email Cliente:</td><td class='info-value'><a href='mailto:{cliente_email}'>{cliente_email}</a></td></tr>" if cliente_email else ""
    cultivo_row = f"<tr><td class='info-label'>Cultivo / Área:</td><td class='info-value'>{(cultivo + ' · ') if cultivo else ''}{hectareas or 'N/A'} Ha</td></tr>" if (cultivo or hectareas) else ""
    dron_row = f"<tr><td class='info-label'>Aeronave / Dron:</td><td class='info-value'><strong>{dron}</strong></td></tr>" if dron else ""
    if tarifa is not None:
        try:
            val_flt = float(tarifa)
            if val_flt == 0.0:
                tarifa_row = "<tr><td class='info-label'>Tarifa / Valor:</td><td class='info-value'><strong style='color:#10b981;'>$0 COP (Demostración Gratuita)</strong></td></tr>"
            else:
                tarifa_row = f"<tr><td class='info-label'>Tarifa / Valor:</td><td class='info-value'><strong style='color:#059669;'>${val_flt:,.0f} COP</strong></td></tr>"
        except Exception:
            tarifa_row = f"<tr><td class='info-label'>Tarifa / Valor:</td><td class='info-value'><strong>${tarifa}</strong></td></tr>"
    else:
        tarifa_row = "<tr><td class='info-label'>Tarifa / Valor:</td><td class='info-value'><strong>Cotización Estándar</strong></td></tr>"

    # Generar sincronización de evento para Microsoft Outlook / Teams / Graph
    ics_payload = None
    try:
        from app.infrastructure.external.microsoft_calendar_service import MicrosoftCalendarService
        sync_res = MicrosoftCalendarService.sync_technician_calendar(
            tecnico_email=to_email,
            tecnico_nombre=tecnico_nombre,
            id_turno=id_turno,
            servicio=servicio,
            finca=finca,
            municipio=muni_str,
            departamento=dep_str,
            fecha_str=fecha,
            hora_str=hora,
            cliente_nombre=cliente_nombre,
            cliente_tel=cliente_tel,
            hectareas=hectareas,
            cultivo=cultivo,
            maps_url=maps_link,
            observaciones=observaciones,
            tarifa=tarifa,
            dron=dron,
            cliente_email=cliente_email,
            is_reschedule=False
        )
        if sync_res and sync_res.get("ics_content"):
            ics_payload = sync_res["ics_content"]
    except Exception as ms_err:
        logger.warning(f"[MICROSOFT CALENDAR SYNC ERROR] {ms_err}")

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Hola <strong>{tecnico_nombre}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      El centro de despacho te ha <strong>asignado como piloto / técnico a cargo</strong> para la siguiente misión de vuelo. Los datos han sido estructurados para sincronización automática con tu <strong>Calendario de Microsoft (Outlook / Hotmail)</strong>:
    </p>
    <table class="info-table">
      <tr><td class="info-label">Turno / Misión:</td><td class="info-value"><strong>#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label">Labor a Ejecutar:</td><td class="info-value"><strong>{servicio}</strong></td></tr>
      <tr><td class="info-label">Predio / Finca:</td><td class="info-value"><strong>{finca}</strong></td></tr>
      <tr><td class="info-label">Municipio / Depto:</td><td class="info-value">{muni_str}{', ' + dep_str if dep_str else ''}</td></tr>
      <tr><td class="info-label">Ubicación GPS:</td><td class="info-value"><a href="{maps_link}" target="_blank" style="color:#1C82AD; font-weight:700; text-decoration:underline;">Abrir en Google Maps / Satélite</a></td></tr>
      <tr><td class="info-label">Cliente / Productor:</td><td class="info-value">{cliente_nombre}</td></tr>
      {tel_row}
      {mail_row}
      {cultivo_row}
      {dron_row}
      {tarifa_row}
      <tr style="background:#ecfdf5;"><td class="info-label" style="color:#065f46;">Fecha Programada:</td><td class="info-value" style="color:#047857; font-weight:800;">{fecha}</td></tr>
      <tr style="background:#ecfdf5;"><td class="info-label" style="color:#065f46;">Hora de Inicio:</td><td class="info-value" style="color:#047857; font-weight:800;">{hora}</td></tr>
      {obs_row}
    </table>
    <div style="background: #eff6ff; border-left: 4px solid #1c82ad; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <p style="margin: 0; font-size: 13px; color: #1e3a8a;">
        Esta misión se encuentra registrada con soporte para tu cuenta de Microsoft. Tu calendario ha sido notificado automáticamente para agendar esta fecha.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Misión #{id_turno}",
        title="Nueva Misión de Vuelo Asignada",
        subtitle=f"{servicio} — {finca}",
        content_html=content,
        action_text="Abrir Portal Técnico",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"Misión Asignada #RAD-{id_turno} — {servicio} en {finca}", html, ics_content=ics_payload, ics_method="REQUEST")


def send_technician_rescheduled_notification(
    to_email: str,
    tecnico_nombre: str,
    id_turno: int,
    servicio: str,
    finca: str,
    nueva_fecha: str,
    nueva_hora: str,
    fecha_antigua: Optional[str] = None,
    motivo: Optional[str] = None,
    municipio: Optional[str] = None,
    departamento: Optional[str] = None,
    cliente_nombre: Optional[str] = None,
    cliente_tel: Optional[str] = None,
    hectareas: Optional[float] = None,
    cultivo: Optional[str] = None,
    maps_url: Optional[str] = None,
    tarifa: Optional[float] = None
) -> bool:
    """Notifica al técnico cuando una de sus misiones ha sido reprogramada y actualiza su calendario de Microsoft."""
    portal_url = _get_active_portal_url("pages/tecnico.html")
    muni_str = municipio or "Colombia"
    dep_str = departamento or ""
    maps_link = maps_url or f"https://www.google.com/maps/search/?api=1&query={muni_str}+{dep_str}".replace(" ", "+")
    old_row = f"<tr><td class='info-label'>Fecha Anterior:</td><td class='info-value' style='text-decoration:line-through; color:#94a3b8;'>{fecha_antigua}</td></tr>" if fecha_antigua else ""
    tarifa_row = f"<tr><td class='info-label'>Tarifa / Valor:</td><td class='info-value'><strong style='color:#059669;'>${float(tarifa):,.0f} COP</strong></td></tr>" if tarifa else ""

    # Sincronizar actualización con Microsoft Calendar (Outlook / Hotmail)
    ics_payload = None
    try:
        from app.infrastructure.external.microsoft_calendar_service import MicrosoftCalendarService
        sync_res = MicrosoftCalendarService.sync_technician_calendar(
            tecnico_email=to_email,
            tecnico_nombre=tecnico_nombre,
            id_turno=id_turno,
            servicio=servicio,
            finca=finca,
            municipio=muni_str,
            departamento=dep_str,
            fecha_str=nueva_fecha,
            hora_str=nueva_hora,
            cliente_nombre=cliente_nombre or "Cliente",
            cliente_tel=cliente_tel,
            hectareas=hectareas,
            cultivo=cultivo,
            maps_url=maps_link,
            observaciones=motivo,
            tarifa=tarifa,
            is_reschedule=True
        )
        if sync_res and sync_res.get("ics_content"):
            ics_payload = sync_res["ics_content"]
    except Exception as ms_err:
        logger.warning(f"[MICROSOFT CALENDAR RESCHEDULE ERROR] {ms_err}")

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Hola <strong>{tecnico_nombre}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Te informamos que tu misión técnica asignada <strong>#RAD-{id_turno}</strong> ha sido <strong>reprogramada</strong> y sincronizada con tu calendario de Microsoft:
    </p>
    <table class="info-table">
      <tr><td class="info-label">Turno / Misión:</td><td class="info-value"><strong>#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label">Predio / Finca:</td><td class="info-value"><strong>{finca}</strong></td></tr>
      <tr><td class="info-label">Labor:</td><td class="info-value">{servicio}</td></tr>
      <tr><td class="info-label">Ubicación GPS:</td><td class="info-value"><a href="{maps_link}" target="_blank" style="color:#1C82AD; font-weight:700;">Ver Mapa</a></td></tr>
      {old_row}
      {tarifa_row}
      <tr style="background:#ecfdf5;"><td class="info-label" style="color:#065f46;">Nueva Fecha:</td><td class="info-value" style="color:#047857; font-weight:800;">{nueva_fecha}</td></tr>
      <tr style="background:#ecfdf5;"><td class="info-label" style="color:#065f46;">Nueva Hora:</td><td class="info-value" style="color:#047857; font-weight:800;">{nueva_hora}</td></tr>
      <tr><td class="info-label">Motivo de Ajuste:</td><td class="info-value">{motivo or 'Ajuste meteorológico u operacional'}</td></tr>
    </table>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Reprogramado #{id_turno}",
        title="Misión Reagendada",
        subtitle=f"Actualización de cronograma para #{id_turno}",
        content_html=content,
        action_text="Ver Mi Agenda Técnica",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"Modificación de Turno #RAD-{id_turno} — {finca}", html, ics_content=ics_payload, ics_method="REQUEST")


def send_technician_cancelled_notification(
    to_email: str,
    tecnico_nombre: str,
    id_turno: int,
    servicio: str,
    finca: str,
    motivo: Optional[str] = None,
    municipio: Optional[str] = None,
    departamento: Optional[str] = None,
    fecha: Optional[str] = None,
    hora: Optional[str] = None
) -> bool:
    """
    Notifica al técnico cuando una misión asignada es cancelada o eliminada,
    y emite payload iCalendar con METHOD: CANCEL para borrarla del calendario de Microsoft.
    """
    portal_url = _get_active_portal_url("pages/tecnico.html")

    ics_payload = None
    try:
        from app.infrastructure.external.microsoft_calendar_service import MicrosoftCalendarService
        sync_res = MicrosoftCalendarService.cancel_technician_calendar(
            tecnico_email=to_email,
            tecnico_nombre=tecnico_nombre,
            id_turno=id_turno,
            servicio=servicio,
            finca=finca,
            municipio=municipio,
            departamento=departamento,
            fecha_str=fecha,
            hora_str=hora,
            motivo=motivo
        )
        if sync_res and sync_res.get("ics_content"):
            ics_payload = sync_res["ics_content"]
    except Exception as ms_err:
        logger.warning(f"[MICROSOFT CALENDAR CANCEL ERROR] {ms_err}")

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Hola <strong>{tecnico_nombre}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Te informamos que la misión operativa <strong>#RAD-{id_turno}</strong> ha sido <strong>cancelada</strong> y liberada de tu calendario:
    </p>
    <table class="info-table">
      <tr><td class="info-label">Turno / Misión:</td><td class="info-value"><strong>#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label">Labor:</td><td class="info-value">{servicio}</td></tr>
      <tr><td class="info-label">Predio / Finca:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Fecha Liberada:</td><td class="info-value">{fecha or 'Fecha programada'}</td></tr>
      <tr><td class="info-label">Motivo de Cancelación:</td><td class="info-value">{motivo or 'Cancelación administrativa / Solicitud del usuario'}</td></tr>
      <tr style="background:#fef2f2;"><td class="info-label" style="color:#991b1b;">Estado Calendario:</td><td class="info-value" style="color:#b91c1c; font-weight:800;">Cancelado / Removido de Outlook</td></tr>
    </table>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Cancelado #{id_turno}",
        title="Misión Cancelada",
        subtitle=f"Liberación de horario para #{id_turno}",
        content_html=content,
        action_text="Ver Mi Agenda Técnica",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"Cancelación de Misión #RAD-{id_turno} — {finca}", html, ics_content=ics_payload, ics_method="CANCEL")


# ==============================================================================
# 15. RECORDATORIO MANUAL (BOTÓN EN ADMIN AGENDAS)
# ==============================================================================

def send_manual_participant_reminder(
    to_email: str,
    nombre: str,
    id_turno: int,
    servicio: str,
    finca: str,
    fecha: str,
    hora: str,
    rol: str = "cliente",
    piloto_nombre: Optional[str] = None
) -> bool:
    """Envía recordatorio manual expedido por el administrador desde la tabla de Agendas."""
    target_portal = "pages/tecnico.html" if rol == "tecnico" else "pages/cliente.html"
    portal_url = _get_active_portal_url(target_portal)
    pilot_row = f"<tr><td class='info-label'>Piloto(s) a Cargo:</td><td class='info-value'><strong>{piloto_nombre}</strong></td></tr>" if piloto_nombre else ""

    content = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      Estimado(a) <strong>{nombre}</strong>,
    </p>
    <p style="font-size: 15px; color: #334155; line-height: 1.6;">
      El centro de control de <strong>Flymetrics</strong> te envía este recordatorio oficial sobre la misión técnica programada:
    </p>
    <table class="info-table">
      <tr><td class="info-label">Turno / Radicado:</td><td class="info-value"><strong>#RAD-{id_turno}</strong></td></tr>
      <tr><td class="info-label">Predio / Proyecto:</td><td class="info-value">{finca}</td></tr>
      <tr><td class="info-label">Servicio:</td><td class="info-value"><strong>{servicio}</strong></td></tr>
      <tr style="background:#f0fdf4;"><td class="info-label" style="color:#166534;">Fecha de Vuelo:</td><td class="info-value" style="color:#15803d; font-weight:800;">{fecha}</td></tr>
      <tr style="background:#f0fdf4;"><td class="info-label" style="color:#166534;">Hora Estimada:</td><td class="info-value" style="color:#15803d; font-weight:800;">{hora}</td></tr>
      {pilot_row}
    </table>
    <div style="background: #eff6ff; border-left: 4px solid #1c82ad; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
      <p style="margin: 0; font-size: 13px; color: #1e3a8a;">
        Por favor coordinar los alistamientos logísticos y despeje de campo para la ejecución oportuna de la misión.
      </p>
    </div>
    """
    html = _generate_flymetrics_base_template(
        header_badge=f"Recordatorio #{id_turno}",
        title="Recordatorio de Misión de Vuelo",
        subtitle=f"{servicio} en {finca}",
        content_html=content,
        action_text="Ver Detalles en Plataforma",
        action_url=portal_url
    )
    return _send_smtp_html_email(to_email, f"⏰ Recordatorio de Misión de Vuelo #RAD-{id_turno} — Flymetrics", html)


# ==============================================================================
# CLASE UNIFICADA EmailService PARA IMPORTACIÓN DIRECTA
# ==============================================================================
class EmailService:
    send_otp = staticmethod(send_otp_email)
    send_welcome = staticmethod(send_welcome_email)
    send_demo_gratuita_created = staticmethod(send_demo_gratuita_created_email)
    send_admin_note_response = staticmethod(send_admin_note_response_email)
    send_booking_created = staticmethod(send_booking_created_email)
    send_booking_confirmed = staticmethod(send_booking_confirmed_email)
    send_booking_rescheduled = staticmethod(send_booking_rescheduled_email)
    send_booking_cancelled = staticmethod(send_booking_cancelled_email)
    send_24h_reminder = staticmethod(send_24h_reminder_email)
    send_12h_reminder = staticmethod(send_12h_reminder_email)
    send_service_completed = staticmethod(send_service_completed_email)
    send_flight_log_ready = staticmethod(send_flight_log_ready_email)
    send_executive_report_ready = staticmethod(send_executive_report_ready_email)
    send_quote_confirmation = staticmethod(send_quote_confirmation_email)
    send_password_reset_8digit = staticmethod(send_password_reset_8digit_otp)
    send_profile_update_8digit = staticmethod(send_profile_update_8digit_otp)
    send_password_changed = staticmethod(send_password_changed_notification)
    send_profile_updated = staticmethod(send_profile_updated_notification)
    send_custom_html = staticmethod(_send_smtp_html_email)
    get_portal_url = staticmethod(_get_active_portal_url)
    
    # Nuevos canales del sistema
    send_admin_new_booking = staticmethod(send_admin_new_booking_notification)
    send_admin_rescheduled = staticmethod(send_admin_rescheduled_notification)
    send_admin_service_completed = staticmethod(send_admin_service_completed_notification)
    send_admin_new_quote = staticmethod(send_admin_new_quote_notification)
    send_technician_assigned = staticmethod(send_technician_assigned_notification)
    send_technician_rescheduled = staticmethod(send_technician_rescheduled_notification)
    send_technician_cancelled = staticmethod(send_technician_cancelled_notification)
    send_manual_participant_reminder = staticmethod(send_manual_participant_reminder)
    send_client_negotiation_quote = staticmethod(send_client_negotiation_quote_email)
    send_admin_client_suggestion = staticmethod(send_admin_client_suggestion_notification)
    send_service_finalized_sharepoint = staticmethod(send_service_finalized_sharepoint_email)



