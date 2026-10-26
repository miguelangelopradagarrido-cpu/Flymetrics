from typing import Optional
from decimal import Decimal
import re
from fastapi import APIRouter, Depends, Query, Request, Response, Header, status
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.infrastructure.config.settings import settings
from app.infrastructure.database.models.models import AgendaModel, ReporteVueloModel, EntregableModel
from app.infrastructure.external.whatsapp_service import WhatsAppService
from app.shared.responses.response import success_response
from app.shared.exceptions.exceptions import ForbiddenException, NotFoundException, AppException

import hmac
import hashlib

router = APIRouter(prefix="/webhook", tags=["Webhooks & Integraciones"])

@router.get("/whatsapp")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Endpoint de verificación GET requerido por Meta.
    Valida el token de verificación y retorna el challenge recibido.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        print("[WHATSAPP WEBHOOK] Verificación de Webhook exitosa.")
        return Response(content=hub_challenge, media_type="text/plain")
    else:
        raise ForbiddenException("Token de verificación incorrecto o modo inválido")

@router.post("/whatsapp")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint POST para recibir mensajes de clientes enviados por Meta con validación criptográfica de firma HMAC.
    """
    try:
        raw_body = await request.body()
        sig_header = request.headers.get("X-Hub-Signature-256")
        if sig_header and getattr(settings, "WEBHOOK_SECRET", None):
            expected_sig = sig_header[7:] if sig_header.startswith("sha256=") else sig_header
            computed_sig = hmac.new(settings.WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_sig, computed_sig):
                raise ForbiddenException("Firma criptográfica de Meta inválida en webhook.")

        import json
        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        print(f"[WHATSAPP WEBHOOK] Mensaje recibido: {body}")
        
        # Validar formato estándar de webhook de Meta
        if body.get("object") != "whatsapp_business_account":
            return success_response(message="Evento omitido (no es de cuenta business)", data={})
            
        entry_list = body.get("entry", [])
        for entry in entry_list:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for msg in messages:
                    sender_phone = msg.get("from")
                    text_obj = msg.get("text", {})
                    msg_body = text_obj.get("body", "").strip()
                    
                    if not sender_phone or not msg_body:
                        continue
                        
                    # Procesar mensaje. Buscar números (ej: id_turno)
                    # Expresión regular para buscar números de reserva
                    numbers = re.findall(r"\b\d+\b", msg_body)
                    
                    if numbers:
                        turno_id = int(numbers[0])
                        # Consultar el turno en base de datos
                        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == turno_id).first()
                        
                        if turno:
                            tecnico_nombre = "No asignado aún"
                            if turno.tecnico:
                                tecnico_nombre = f"{turno.tecnico.nombre} {turno.tecnico.apellido_1}"
                                
                            reply = (
                                f"Hola, el estado de tu reserva #{turno.id_turno} es *{turno.estado}*.\n"
                                f"Detalles:\n"
                                f"- Fecha: {turno.fecha_de_turno}\n"
                                f"- Piloto asignado: {tecnico_nombre}\n"
                                f"- Servicio: {turno.servicio.nombre_servicio}\n"
                                f"- Finca: {turno.finca.nombre_finca}"
                            )
                        else:
                            reply = f"El número de reserva #{turno_id} no se encuentra en nuestro sistema."
                    else:
                        # Fallback con menú interactivo
                        reply = (
                            "¡Hola! Bienvenido al bot de Flymetrics Command Center. 🛸\n\n"
                            "Si deseas consultar el estado de tu servicio de drones, por favor escribe el número de tu reserva.\n"
                            "Ejemplo: *'Estado de mi turno 5'*\n\n"
                            "Para otras consultas, puedes comunicarte con soporte al (+57) 305 406 1764."
                        )
                        
                    # Enviar respuesta simulada a través de Meta
                    WhatsAppService.send_text_message(sender_phone, reply)
                    
    except (ForbiddenException, AppException):
        raise
    except Exception as e:
        print(f"[WHATSAPP WEBHOOK ERROR] Error procesando webhook: {e}")
        return success_response(message="Webhook recibido pero con fallos internos")


# ==============================================================================
# INGESTA AUTOMÁTICA DE FORMULARIO DE VUELO DESDE FORMS (MARCA TURNO COMPLETADO)
# ==============================================================================
from app.presentation.api.dependencies.auth import RoleChecker
from app.infrastructure.database.models.models import UsuarioModel

webhook_forms_router = APIRouter(prefix="", tags=["Sincronización Automática de Formularios y Correo"])
admin_required = RoleChecker(["administrador"])

async def process_forms_flight_submission(request: dict, db: Session):
    """
    Procesa las respuestas de formularios de vuelo (Google / Microsoft Forms vía Power Automate / Webhook).
    - Localiza el turno de vuelo programado por radicado, piloto o fecha/ubicación.
    - Marca el turno como 'Completado' / 'Finalizado' en la base de datos.
    - Registra entregables y enlaces de SharePoint / Drive.
    - Despacha notificaciones de correo de servicio completado al cliente y administradores de forma asíncrona.
    """
    import re
    import threading
    from datetime import date, datetime, time, timedelta
    from app.infrastructure.database.models.models import AgendaModel, ReporteVueloModel, EntregableModel, TecnicoModel, FincaModel
    from app.shared.utils.email_service import EmailService

    if not request or not isinstance(request, dict) or not any(str(v).strip() for v in request.values() if v is not None):
        return success_response(
            message="Webhook recibido pero el cuerpo está vacío. No se realizaron cambios en la agenda.",
            data={"procesado": False}
        )

    def extract_field_flexible(data: dict, patterns: list) -> str:
        if not isinstance(data, dict):
            return ""
        for pat in patterns:
            for k, v in data.items():
                if v is not None and re.search(pat, str(k), re.IGNORECASE):
                    val_str = str(v).strip()
                    if val_str and val_str.lower() not in [
                        "no se proporciona ninguna respuesta.", 
                        "no se proporciona ninguna respuesta", 
                        "ninguna", "n/a", "none", "null"
                    ]:
                        return val_str
        return ""

    raw_tecnico = extract_field_flexible(request, [
        r"17\.\s*piloto", r"\bpiloto\b", r"t[eé]cnico", r"responsable", r"nombre.*piloto", r"nombre.*t[eé]cnico"
    ]) or request.get("tecnico") or request.get("piloto") or ""

    tecnico_obj = None
    tecnico_nombre = "Piloto Flymetrics Certificado"
    if raw_tecnico:
        raw_tec_clean = str(raw_tecnico).strip()
        if raw_tec_clean.isdigit():
            tecnico_obj = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == int(raw_tec_clean)).first()
        if not tecnico_obj and "@" in raw_tec_clean:
            from app.infrastructure.database.models.models import UsuarioModel
            tecnico_obj = db.query(TecnicoModel).join(TecnicoModel.usuario).filter(UsuarioModel.email.ilike(f"%{raw_tec_clean}%")).first()
        if not tecnico_obj:
            tecnico_obj = db.query(TecnicoModel).filter(TecnicoModel.nombre.ilike(f"%{raw_tec_clean}%")).first()
        if not tecnico_obj:
            words = [w for w in raw_tec_clean.split() if len(w) > 2]
            for w in words:
                tecnico_obj = db.query(TecnicoModel).filter(TecnicoModel.nombre.ilike(f"%{w}%")).first()
                if tecnico_obj:
                    break
        if tecnico_obj:
            tecnico_nombre = tecnico_obj.nombre.strip()
        else:
            tecnico_nombre = raw_tec_clean

    raw_date = extract_field_flexible(request, [
        r"1\.\s*fecha", r"fecha.*vuelo", r"fecha.*ejecuci[oó]n", r"\bfecha\b", r"\bdate\b"
    ]) or request.get("fecha") or ""

    candidate_dates = []
    if raw_date:
        m_iso_d = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', raw_date)
        if m_iso_d:
            try: candidate_dates.append(date(int(m_iso_d.group(1)), int(m_iso_d.group(2)), int(m_iso_d.group(3))))
            except Exception: pass
        else:
            m_d = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', raw_date)
            if m_d:
                d1, d2, y = int(m_d.group(1)), int(m_d.group(2)), int(m_d.group(3))
                try: candidate_dates.append(date(y, d2, d1))
                except Exception: pass
                try: candidate_dates.append(date(y, d1, d2))
                except Exception: pass
    if not candidate_dates:
        candidate_dates = [date.today()]

    target_date = candidate_dates[0]

    def extract_time(val):
        if not val: return None
        s = str(val).strip()
        # 1. Standard HH:MM(:SS) [AM/PM]
        m_t = re.search(r'(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp][Mm])?', s)
        if m_t:
            h, mi = int(m_t.group(1)), int(m_t.group(2))
            ampm = m_t.group(3)
            if ampm:
                if ampm.upper() == 'PM' and h < 12: h += 12
                elif ampm.upper() == 'AM' and h == 12: h = 0
            return time(h, mi)
        # 2. Military format HHMM e.g. 0700, 1430
        m_mil = re.search(r'\b(\d{2})(\d{2})\b', s)
        if m_mil:
            h, mi = int(m_mil.group(1)), int(m_mil.group(2))
            if 0 <= h <= 23 and 0 <= mi <= 59:
                return time(h, mi)
        return None

    raw_h_ini = extract_field_flexible(request, [
        r"4\.\s*hora.*inicio", r"hora.*inicio", r"hora.*operaci[oó]n", r"start.*time"
    ]) or request.get("hora_inicio") or ""
    time_ini = extract_time(raw_h_ini)

    raw_h_fin = extract_field_flexible(request, [
        r"13\.\s*hora.*fin", r"hora.*fin(alizaci[oó]n)?", r"hora.*env[ií]o", r"submission.*time", r"completion.*time", r"end.*time"
    ]) or request.get("hora_fin") or request.get("hora") or ""
    time_fin = extract_time(raw_h_fin)

    target_time = time_fin or time_ini or datetime.now().time()
    hora_envio = target_time.strftime("%I:%M %p")

    raw_id = extract_field_flexible(request, [
        r"radicado", r"turno", r"id_turno", r"c[oó]digo"
    ])
    m_id = re.search(r'\d+', str(raw_id)) if raw_id else None
    id_turno = int(m_id.group(0)) if m_id else None

    turno = None
    if id_turno:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()

    VALID_HEURISTIC_STATUSES = ["Confirmado", "En Proceso"]
    tec_id = tecnico_obj.id_tecnico if tecnico_obj else None

    if not turno and tec_id:
        turnos_candidatos = db.query(AgendaModel).filter(
            AgendaModel.id_tecnico == tec_id,
            AgendaModel.fecha_de_turno.in_(candidate_dates),
            AgendaModel.estado.in_(VALID_HEURISTIC_STATUSES)
        ).all()
        if turnos_candidatos:
            if len(turnos_candidatos) == 1:
                turno = turnos_candidatos[0]
            elif time_ini:
                def diff_mins(t):
                    if not t.hora_inicio_estimada: return 9999
                    return abs((t.hora_inicio_estimada.hour * 60 + t.hora_inicio_estimada.minute) - (time_ini.hour * 60 + time_ini.minute))
                turno = min(turnos_candidatos, key=diff_mins)
            else:
                turno = turnos_candidatos[0]

    raw_ubicacion = extract_field_flexible(request, [
        r"2\.\s*ubicaci[oó]n", r"ubicaci[oó]n", r"coordenadas", r"finca", r"predio"
    ])
    if not turno and raw_ubicacion and len(raw_ubicacion.strip()) >= 3:
        turnos_finca = db.query(AgendaModel).join(AgendaModel.finca).filter(
            FincaModel.nombre_finca.ilike(f"%{raw_ubicacion.strip()}%"),
            AgendaModel.fecha_de_turno.in_(candidate_dates),
            AgendaModel.estado.in_(VALID_HEURISTIC_STATUSES)
        ).order_by(AgendaModel.id_turno.desc()).first()
        if turnos_finca:
            turno = turnos_finca

    if not turno and candidate_dates:
        turnos_fecha = db.query(AgendaModel).filter(
            AgendaModel.fecha_de_turno.in_(candidate_dates),
            AgendaModel.estado.in_(VALID_HEURISTIC_STATUSES)
        ).all()
        if turnos_fecha:
            if len(turnos_fecha) == 1:
                turno = turnos_fecha[0]
            elif time_ini:
                def diff_mins(t):
                    if not t.hora_inicio_estimada: return 9999
                    return abs((t.hora_inicio_estimada.hour * 60 + t.hora_inicio_estimada.minute) - (time_ini.hour * 60 + time_ini.minute))
                closest = min(turnos_fecha, key=diff_mins)
                if diff_mins(closest) <= 150:
                    turno = closest

    if not turno:
        return success_response(
            message="No se encontró ningún turno agendado activo que coincida con el radicado, piloto o fecha de este formulario. No se modificó ningún vuelo.",
            data={"procesado": False}
        )

    if tecnico_obj and (not turno.id_tecnico or turno.id_tecnico != tecnico_obj.id_tecnico):
        turno.id_tecnico = tecnico_obj.id_tecnico

    if time_ini:
        turno.hora_inicio_real = time_ini
    elif not turno.hora_inicio_real and turno.hora_inicio_estimada:
        turno.hora_inicio_real = turno.hora_inicio_estimada

    turno.hora_fin_real = time_fin or target_time

    url_sharepoint = extract_field_flexible(request, [
        r"sharepoint", r"enlace.*informe", r"url.*informe", r"drive", r"link"
    ]) or request.get("url_informe_sharepoint") or request.get("url_informe") or ""

    obs_campo = extract_field_flexible(request, [
        r"observaciones", r"novedades", r"comentarios"
    ]) or f"Servicio ejecutado bajo norma RAC-100 por {tecnico_nombre} a las {hora_envio}."

    recom_agro = extract_field_flexible(request, [
        r"recomendaciones"
    ]) or "Monitorear cobertura foliar a las 48 horas post-aplicación."

    # Marcar el servicio como Completado en la base de datos
    turno.estado = "Completado"

    reporte = db.query(ReporteVueloModel).filter(ReporteVueloModel.id_turno == turno.id_turno).first()
    if not reporte:
        reporte = ReporteVueloModel(
            id_turno=turno.id_turno,
            insumos_litros_aplicados=15.0,
            agua_litros=120.0,
            baterias_utilizadas=4,
            cumple_rac100=1,
            url_entregable_drive=url_sharepoint or None,
            observaciones_campo=obs_campo,
            recomendaciones_agronomicas=recom_agro
        )
        db.add(reporte)
    else:
        if url_sharepoint:
            reporte.url_entregable_drive = url_sharepoint
        reporte.observaciones_campo = obs_campo
        reporte.recomendaciones_agronomicas = recom_agro
        reporte.cumple_rac100 = 1

    if url_sharepoint and str(url_sharepoint).strip():
        url_clean = str(url_sharepoint).strip()
        entregable = db.query(EntregableModel).filter(
            EntregableModel.id_turno == turno.id_turno,
            EntregableModel.url_archivo == url_clean
        ).first()
        if not entregable:
            entregable = EntregableModel(
                id_turno=turno.id_turno,
                tipo_archivo="Informe Técnico Ejecutivo",
                url_archivo=url_clean,
                nombre_archivo=f"Informe de Vuelo #{turno.id_turno} (SharePoint)"
            )
            db.add(entregable)

    db.commit()
    db.refresh(turno)

    # Notificaciones asíncronas
    finca_nom = turno.finca.nombre_finca if turno.finca else "Predio Registrado"
    serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Servicio de Vuelo Agrícola"
    cli_nom = turno.finca.cliente.nombre if (turno.finca and turno.finca.cliente) else "Cliente"
    dest_email = None
    if turno.finca and turno.finca.cliente and turno.finca.cliente.usuario:
        dest_email = turno.finca.cliente.usuario.email
    if not dest_email:
        dest_email = request.get("email_cliente") or request.get("correo") or "comercial@flymetrics.com.co"

    turno_id_val = turno.id_turno
    fecha_val_str = turno.fecha_de_turno.strftime("%d/%m/%Y") if (turno.fecha_de_turno and hasattr(turno.fecha_de_turno, 'strftime')) else str(turno.fecha_de_turno or '')

    def _async_webhook_notifications():
        try:
            EmailService.send_service_completed(
                to_email=dest_email,
                nombre_cliente=cli_nom,
                id_turno=turno_id_val,
                servicio=serv_nom,
                finca=finca_nom,
                tecnico=tecnico_nombre,
                hora_finalizacion=hora_envio,
                fecha=fecha_val_str,
                url_informe=url_sharepoint or None,
                insumos="15.0 L",
                agua="120.0 L"
            )
            EmailService.send_admin_service_completed(
                id_turno=turno_id_val,
                cliente_nombre=cli_nom,
                servicio=serv_nom,
                finca=finca_nom,
                tecnico_nombre=tecnico_nombre,
                fecha=fecha_val_str,
                hora_fin=hora_envio
            )
        except Exception as mail_err:
            print(f"[WEBHOOK ASYNC NOTIF ERROR] {mail_err}")

    threading.Thread(target=_async_webhook_notifications, daemon=True).start()

    return success_response(
        message="Formulario procesado exitosamente. Turno marcado como Completado y notificaciones enviadas.",
        data={
            "id_turno": turno.id_turno,
            "estado": turno.estado,
            "finca": finca_nom,
            "cliente_notificado": dest_email,
            "reporte_id": reporte.id_reporte if reporte else None
        }
    )

@webhook_forms_router.post("/bitacora/webhook-forms")
@webhook_forms_router.post("/bitacoras/webhook-forms")
@webhook_forms_router.post("/webhook/forms")
async def webhook_forms_endpoint(
    request: dict,
    db: Session = Depends(get_db)
):
    """Recibe formularios de vuelo (Forms / Power Automate) y marca el servicio como Completado."""
    return await process_forms_flight_submission(request=request, db=db)

@webhook_forms_router.get("/bitacora/sync-email")
@webhook_forms_router.post("/bitacora/sync-email")
@webhook_forms_router.get("/webhook/sync-email")
@webhook_forms_router.post("/webhook/sync-email")
def sync_email_forms_endpoint(
    current_user: UsuarioModel = Depends(admin_required)
):
    """Sincroniza los correos de formularios de vuelo recibidos y marca los servicios como Completados."""
    from app.shared.utils.forms_email_sync import sync_bitacoras_from_email
    res = sync_bitacoras_from_email(mark_as_read=True)
    return success_response(
        message="Sincronización de correos de formularios ejecutada. Servicios marcados como Completados.",
        data=res
    )

@router.post("/microsoft-forms", status_code=status.HTTP_201_CREATED)
async def receive_microsoft_forms_bitacora(
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret")
):
    """Webhook para ingesta de formularios desde Microsoft Forms / Power Automate."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    secret_token = x_webhook_secret or body.get("secret_token") or body.get("token")
    if settings.WEBHOOK_SECRET and secret_token and secret_token != settings.WEBHOOK_SECRET:
        raise ForbiddenException("Token de webhook no autorizado")

    return await process_forms_flight_submission(request=body, db=db)

