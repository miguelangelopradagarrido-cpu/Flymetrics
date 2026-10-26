import os
import imaplib
import email
from email.header import decode_header
import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("uvicorn")

def _clean_html_to_text(html_content: str) -> str:
    """Convierte cuerpo HTML de correo de Outlook/Power Automate a texto plano limpio."""
    # Reemplazar saltos de línea y párrafos HTML
    text = re.sub(r'<\s*br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
    text = re.sub(r'<\s*/?\s*p\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<\s*/?\s*div\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<\s*li\s*>', '\n• ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    # Reemplazar entidades HTML comunes
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()


def parse_email_body_to_dict(body_raw: str) -> Dict[str, Any]:
    """
    Parsea de forma ultra-flexible el cuerpo del correo proveniente de Power Automate.
    Soporta:
    1. Bloque JSON: {"tecnico": "...", "fecha": "..."}
    2. Texto línea por línea:
       Fecha: 2026-09-16
       Piloto: Juan Camilo
       Hora inicio: 07:00
       Hora fin: 08:30
       [eliminando corchetes opcionales]
    """
    clean_text = _clean_html_to_text(body_raw) if "<" in body_raw and ">" in body_raw else body_raw.strip()
    
    # 1. Intentar encontrar y parsear un bloque JSON si existe
    m_json = re.search(r'(\{[\s\S]*\})', clean_text)
    if m_json:
        try:
            parsed = json.loads(m_json.group(1))
            if isinstance(parsed, dict) and any(parsed.values()):
                return parsed
        except Exception:
            pass

    # 2. Parsear formato clave: valor línea por línea
    data: Dict[str, Any] = {}
    lines = clean_text.splitlines()
    for line in lines:
        line_s = line.strip()
        if not line_s or line_s.startswith(("#", "//", "<!--")):
            continue
        
        # Buscar "Clave: Valor" o "Clave = Valor"
        m = re.match(r'^([^:\-=]+)[:\-=]\s*(.+)$', line_s)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            # Quitar corchetes decorativos si el usuario dejó [ y ]
            val = re.sub(r'^[\[\(\{"\']+|[\]\)\}"\']+$', '', val).strip()
            if key and val:
                data[key] = val

    return data


def _get_storage_path():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent.parent
    scratch_dir = root / "scratch"
    if not scratch_dir.exists():
        scratch_dir = root / "app" / "data"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    return scratch_dir / "processed_bitacora_emails.json"

def _load_processed_ids() -> set:
    try:
        p = _get_storage_path()
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()

def _save_processed_id(msg_id_str: str):
    try:
        p = _get_storage_path()
        current = _load_processed_ids()
        current.add(msg_id_str)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(list(current), f)
    except Exception:
        pass

def sync_bitacoras_from_email(mark_as_read: bool = True) -> Dict[str, Any]:
    """
    Se conecta a Gmail vía IMAP, busca correos con asunto [FLYMETRICS-BITACORA],
    los parsea e ingesta automáticamente en la base de datos de Flymetrics.
    Usa un registro de persistencia para no re-procesar correos ya manejados, incluso si se abrieron en Gmail.
    """
    from app.infrastructure.config.settings import settings
    from app.infrastructure.database.session import SessionLocal
    from app.infrastructure.database.models.models import SystemConfigModel
    from app.presentation.api.routers.webhook import process_forms_flight_submission
    import asyncio

    results = []
    processed_ids = _load_processed_ids()

    smtp_user = getattr(settings, "SMTP_USER", "")
    smtp_pass = getattr(settings, "SMTP_PASSWORD", "")

    # Cargar credenciales activas desde la base de datos si existen
    try:
        with SessionLocal() as db_cfg:
            cfg_m = db_cfg.query(SystemConfigModel).filter(SystemConfigModel.clave == "config_correo_seguro").first()
            if cfg_m and cfg_m.valor:
                c_json = json.loads(cfg_m.valor)
                if c_json.get("smtp_user"):
                    smtp_user = c_json["smtp_user"]
                if c_json.get("smtp_password"):
                    smtp_pass = c_json["smtp_password"]
    except Exception as e_cfg:
        logger.debug(f"[EMAIL SYNC CFG DB] Fallback: {e_cfg}")

    # ── 1. CANAL OFICIAL: MICROSOFT GRAPH API (Dominio @flymetrics.com.co) ──
    ms_tenant = getattr(settings, "MICROSOFT_TENANT_ID", os.getenv("MICROSOFT_TENANT_ID", ""))
    ms_client = getattr(settings, "MICROSOFT_CLIENT_ID", os.getenv("MICROSOFT_CLIENT_ID", ""))
    ms_secret = getattr(settings, "MICROSOFT_CLIENT_SECRET", os.getenv("MICROSOFT_CLIENT_SECRET", ""))
    ms_mailbox = getattr(settings, "MICROSOFT_SENDER_EMAIL", os.getenv("MICROSOFT_SENDER_EMAIL", "luiscastaneda@flymetrics.com.co"))

    if ms_tenant and ms_client and ms_secret and ms_mailbox:
        try:
            import requests
            token_url = f"https://login.microsoftonline.com/{ms_tenant}/oauth2/v2.0/token"
            t_res = requests.post(token_url, data={
                "client_id": ms_client,
                "client_secret": ms_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            }, timeout=10)
            if t_res.ok:
                access_token = t_res.json().get("access_token")
                if access_token:
                    headers = {"Authorization": f"Bearer {access_token}"}
                    # Buscar mensajes recientes con FLYMETRICS-BITACORA en el asunto
                    graph_msg_url = f"https://graph.microsoft.com/v1.0/users/{ms_mailbox}/messages?$top=15&$orderby=receivedDateTime%20desc"
                    m_res = requests.get(graph_msg_url, headers=headers, timeout=10)
                    if m_res.ok:
                        msg_list = m_res.json().get("value", [])
                        matching = [
                            m for m in msg_list
                            if "FLYMETRICS-BITACORA" in (m.get("subject") or "").upper()
                            and m.get("id") not in processed_ids
                        ]
                        if matching:
                            logger.info(f"[MICROSOFT GRAPH SYNC] Se encontraron {len(matching)} correos con [FLYMETRICS-BITACORA].")
                            with SessionLocal() as db:
                                for msg in matching:
                                    m_id = msg.get("id")
                                    body_html = msg.get("body", {}).get("content", "")
                                    parsed_dict = parse_email_body_to_dict(body_html)
                                    logger.info(f"[MICROSOFT GRAPH SYNC] Datos extraídos de mensaje {m_id}: {parsed_dict}")
                                    if parsed_dict:
                                        try:
                                            res_webhook = asyncio.run(process_forms_flight_submission(request=parsed_dict, db=db))
                                        except RuntimeError:
                                            loop = asyncio.get_event_loop()
                                            res_webhook = loop.run_until_complete(process_forms_flight_submission(request=parsed_dict, db=db))
                                        results.append({
                                            "email_id": m_id,
                                            "source": "Microsoft Graph",
                                            "datos_extraidos": parsed_dict,
                                            "resultado": res_webhook
                                        })
                                    _save_processed_id(m_id)
                                    # Marcar como leído en Graph
                                    if mark_as_read:
                                        try:
                                            requests.patch(
                                                f"https://graph.microsoft.com/v1.0/users/{ms_mailbox}/messages/{m_id}",
                                                headers=headers,
                                                json={"isRead": True},
                                                timeout=5
                                            )
                                        except Exception:
                                            pass
                            if results:
                                return {"status": "ok", "procesados": len(results), "detalles": results}
        except Exception as ms_err:
            logger.warning(f"[MICROSOFT GRAPH SYNC ERROR] {ms_err}")

    # ── 2. CANAL SECUNDARIO: IMAP LEGACY ──
    if not smtp_user or not smtp_pass:
        return {"status": "ok" if results else "skipped", "procesados": len(results), "detalles": "Sin IMAP adicional."}

    if "@flymetrics." in smtp_user.lower() or "@outlook." in smtp_user.lower():
        return {"status": "ok" if results else "skipped", "procesados": len(results), "detalles": results or "Microsoft Graph gestionado."}

    # Detectar servidor IMAP según el dominio del correo
    imap_server = "imap.gmail.com"
    try:
        mail = imaplib.IMAP4_SSL(imap_server, timeout=10)
        mail.login(smtp_user, smtp_pass)
        mail.select('INBOX')

        # Buscar correos con asunto FLYMETRICS-BITACORA
        status, messages = mail.search(None, 'SUBJECT', 'FLYMETRICS-BITACORA')
        if status != 'OK' or not messages or not messages[0]:
            mail.logout()
            return {"status": "ok", "procesados": 0, "detalles": "No hay correos pendientes."}

        all_msg_ids = [m.decode() for m in messages[0].split()]
        # Filtrar los que no se hayan procesado aún
        pending_ids = [m for m in all_msg_ids if m not in processed_ids]
        if not pending_ids:
            mail.logout()
            return {"status": "ok", "procesados": 0, "detalles": "Todos los correos existentes ya fueron procesados."}

        logger.info(f"[EMAIL SYNC] Se encontraron {len(pending_ids)} correos pendientes con asunto FLYMETRICS-BITACORA.")

        with SessionLocal() as db:
            for m_id in pending_ids:
                res, data = mail.fetch(m_id, '(RFC822)')
                if res != 'OK':
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                msg_unique_id = msg.get("Message-ID") or m_id


                # Extraer cuerpo (texto o HTML)
                body_content = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disp = str(part.get('Content-Disposition'))
                        if content_type in ["text/plain", "text/html"] and "attachment" not in content_disp:
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset() or 'utf-8'
                                body_content = payload.decode(charset, errors='replace')
                                break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        charset = msg.get_content_charset() or 'utf-8'
                        body_content = payload.decode(charset, errors='replace')

                # Parsear los datos del formulario
                parsed_dict = parse_email_body_to_dict(body_content)
                logger.info(f"[EMAIL SYNC] Datos extraídos del correo ID {m_id}: {parsed_dict}")

                if not parsed_dict:
                    logger.warning(f"[EMAIL SYNC] No se pudieron extraer campos del correo ID {m_id}.")
                    _save_processed_id(m_id)
                    continue

                # Llamar al procesador de respuestas de formulario
                try:
                    res_webhook = asyncio.run(process_forms_flight_submission(request=parsed_dict, db=db))
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    res_webhook = loop.run_until_complete(process_forms_flight_submission(request=parsed_dict, db=db))

                results.append({
                    "email_id": m_id,
                    "datos_extraidos": parsed_dict,
                    "resultado": res_webhook
                })

                _save_processed_id(m_id)

                # Marcar como leído
                if mark_as_read:
                    try:
                        mail.store(m_id.encode() if isinstance(m_id, str) else m_id, '+FLAGS', '\\Seen')
                    except Exception:
                        pass

        mail.logout()
        return {"status": "ok", "procesados": len(results), "detalles": results}


    except imaplib.IMAP4.error as auth_err:
        logger.warning(f"[EMAIL SYNC WARNING] Autenticación IMAP omitida para {smtp_user} (requiere OAuth2 o permiso IMAP en buzón): {auth_err}")
        return {"status": "auth_failed", "mensaje": "Autenticación IMAP rechazada por el servidor de correo."}
    except Exception as e:
        logger.warning(f"[EMAIL SYNC WARNING] Error en lectura de buzón: {e}")
        return {"status": "error", "mensaje": str(e)}
