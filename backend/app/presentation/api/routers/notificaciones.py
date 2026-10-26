from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import NotificacionUseCases
from app.presentation.api.dependencies.auth import get_current_user, RoleChecker
from app.infrastructure.database.models.models import UsuarioModel
from app.shared.responses.response import success_response

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])

admin_required = RoleChecker(["administrador"])

@router.get("")
def list_notificaciones(
    leido: int = Query(None, description="0 = no leídas, 1 = leídas. Omitir para todas."),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Retorna el listado de notificaciones para el usuario autenticado."""
    leido_bool = None
    if leido is not None:
        leido_bool = True if leido == 1 else False
        
    notifs = NotificacionUseCases.ver_notificaciones(db, current_user, leido_bool)
    data = [schemas.NotificacionResponse.model_validate(n).model_dump() for n in notifs]
    return success_response(message="Notificaciones obtenidas exitosamente", data=data)

@router.patch("/{id_notificacion}/leer")
def marcar_leida(
    id_notificacion: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Marca la notificación indicada como leída (leido = 1)."""
    notif = NotificacionUseCases.marcar_leida(db, id_notificacion, current_user)
    data = schemas.NotificacionResponse.model_validate(notif).model_dump()
    return success_response(message="Notificación marcada como leída", data=data)

@router.post("", status_code=status.HTTP_201_CREATED)
def crear_notificacion(
    request: schemas.NotificacionCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Crea y envía una notificación a un usuario. Solo administrador o sistema."""
    notif = NotificacionUseCases.crear_notificacion(db, request)
    data = schemas.NotificacionResponse.model_validate(notif).model_dump()
    return success_response(message="Notificación enviada exitosamente", data=data, status_code=201)

@router.delete("/clear-all")
def borrar_todas_notificaciones(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Elimina todas las notificaciones del usuario autenticado (o todas si es administrador)."""
    from app.infrastructure.database.models.models import NotificacionModel
    if current_user.rol == "administrador":
        rows = db.query(NotificacionModel).delete()
    else:
        rows = db.query(NotificacionModel).filter(NotificacionModel.id_usuario == current_user.id_usuarios).delete()
    db.commit()
    return success_response(message=f"Se eliminaron {rows} notificaciones exitosamente")

@router.delete("/{id_notificacion}")
def borrar_notificacion(
    id_notificacion: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Elimina una notificación específica."""
    from app.infrastructure.database.models.models import NotificacionModel
    from app.shared.exceptions.exceptions import NotFoundException
    query = db.query(NotificacionModel).filter(NotificacionModel.id_notificacion == id_notificacion)
    if current_user.rol != "administrador":
        query = query.filter(NotificacionModel.id_usuario == current_user.id_usuarios)
    notif = query.first()
    if not notif:
        raise NotFoundException("Notificación no encontrada")
    db.delete(notif)
    db.commit()
    return success_response(message="Notificación eliminada exitosamente")


# ==============================================================================
# DISPARO DE CORREOS TRANSACCIONALES POR ACCIÓN (CLIENTES & OPERACIONES)
# ==============================================================================
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.shared.utils.email_service import EmailService
from app.shared.exceptions.exceptions import BadRequestException

class EmailAccionRequest(BaseModel):
    accion: str  # 'registro_bienvenida', 'reserva_creada', 'reagendamiento', 'cancelacion', 'servicio_completado'
    to_email: EmailStr
    nombre_cliente: Optional[str] = "Cliente"
    id_turno: Optional[int] = None
    servicio: Optional[str] = "Aplicación Aérea con Dron"
    finca: Optional[str] = "Predio Agropecuario"
    fecha: Optional[str] = None
    hora: Optional[str] = None
    nueva_fecha: Optional[str] = None
    nueva_hora: Optional[str] = None
    motivo: Optional[str] = None
    observaciones: Optional[str] = None
    url_informe: Optional[str] = None
    insumos: Optional[str] = None
    agua: Optional[str] = None
    empresa: Optional[str] = None
    password_temporal: Optional[str] = None

@router.post("/email-accion", status_code=status.HTTP_200_OK)
def enviar_email_por_accion(
    request: EmailAccionRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """
    Endpoint para disparo manual o automatizado de correos a clientes según la acción operativa:
    - 'registro_bienvenida': Bienvenida tras creación de cuenta y credenciales.
    - 'reserva_creada': Confirmación de agendamiento de vuelo con radicado.
    - 'reagendamiento': Aviso de nueva fecha/hora y motivo de reprogramación.
    - 'cancelacion': Notificación formal de anulación del turno.
    - 'servicio_completado': Informe técnico disponible y bitácora RAC-100.
    """
    accion = request.accion.strip().lower()
    dest = str(request.to_email)
    nombre = request.nombre_cliente or "Cliente"
    t_id = request.id_turno or 1
    srv = request.servicio or "Aplicación Aérea con Dron"
    fnc = request.finca or "Predio Registrado"

    enviado = False
    if accion in ["registro_bienvenida", "bienvenida", "registro", "creacion_cuenta"]:
        enviado = EmailService.send_welcome(
            to_email=dest,
            nombre_cliente=nombre,
            empresa=request.empresa,
            password_temporal=request.password_temporal
        )
    elif accion in ["reserva_creada", "agendamiento", "nueva_reserva"]:
        enviado = EmailService.send_booking_created(
            to_email=dest,
            nombre_cliente=nombre,
            id_turno=t_id,
            servicio=srv,
            finca=fnc,
            fecha=request.fecha or "Fecha por confirmar",
            hora=request.hora or "08:00 AM",
            observaciones=request.observaciones
        )
    elif accion in ["reagendamiento", "reprogramacion", "cambio_fecha"]:
        enviado = EmailService.send_booking_rescheduled(
            to_email=dest,
            nombre_cliente=nombre,
            id_turno=t_id,
            servicio=srv,
            finca=fnc,
            nueva_fecha=request.nueva_fecha or request.fecha or "Nueva fecha acordada",
            nueva_hora=request.nueva_hora or request.hora or "08:00 AM",
            motivo=request.motivo
        )
    elif accion in ["cancelacion", "cancelado", "cancelar"]:
        enviado = EmailService.send_booking_cancelled(
            to_email=dest,
            nombre_cliente=nombre,
            id_turno=t_id,
            servicio=srv,
            finca=fnc,
            motivo=request.motivo
        )
    elif accion in ["servicio_completado", "completado", "entrega_informe"]:
        enviado = EmailService.send_service_completed(
            to_email=dest,
            nombre_cliente=nombre,
            id_turno=t_id,
            servicio=srv,
            finca=fnc,
            url_informe=request.url_informe,
            insumos=request.insumos,
            agua=request.agua
        )
    else:
        raise BadRequestException(
            f"Acción '{request.accion}' no reconocida. Opciones disponibles: "
            "'registro_bienvenida', 'reserva_creada', 'reagendamiento', 'cancelacion', 'servicio_completado'"
        )

    return success_response(
        message=f"Correo transaccional '{accion}' procesado exitosamente para {dest}",
        data={
            "accion": accion,
            "destinatario": dest,
            "enviado": enviado
        }
    )


# ==============================================================================
# DIAGNÓSTICO Y PRUEBA DIRECTA DE GMAIL API (OAUTH2)
# ==============================================================================
class TestGmailRequest(BaseModel):
    destinatario: EmailStr
    asunto: Optional[str] = "Prueba de Conexión Gmail API — Flymetrics"
    mensaje: Optional[str] = "Este es un correo de prueba enviado mediante la API de Gmail y OAuth2 de Google Cloud."

@router.get("/status-gmail")
def estado_gmail_api(
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    Verifica el estado de configuración y conectividad con Gmail API y OAuth2.
    Solo administradores.
    """
    from app.infrastructure.external.gmail_api_service import GmailApiService
    diag = GmailApiService.test_connection()
    return success_response(
        message="Diagnóstico de Gmail API completado",
        data=diag
    )

@router.post("/test-gmail")
def enviar_prueba_gmail_api(
    request: TestGmailRequest,
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    Envía un correo de prueba utilizando directamente el cliente de Gmail API con OAuth2.
    Solo administradores.
    """
    from app.infrastructure.external.gmail_api_service import GmailApiService
    from app.shared.utils.email_service import _generate_flymetrics_base_template

    html_body = _generate_flymetrics_base_template(
        header_badge="Diagnóstico Gmail API",
        title="Verificación de Conexión Exitosa",
        subtitle=f"Despachado desde {GmailApiService.get_sender_info()['formatted']}",
        content_html=f"""
        <p style="font-size: 15px; line-height: 1.6; color: #334155;">
          Hola, este mensaje confirma que el servicio de correos corporativos de <strong>Flymetrics</strong> 
          está operando correctamente a través de la <strong>API REST de Gmail con autenticación OAuth 2.0</strong>.
        </p>
        <div style="background: #f8fafc; border-left: 4px solid #10b981; padding: 14px 18px; border-radius: 8px; margin: 20px 0;">
          <p style="margin: 0; font-size: 14px; color: #065f46; font-weight: 600;">
            ✔ Canal: Google Cloud Console (OAuth2 Refresh Token)<br>
            ✔ Remitente: {GmailApiService.get_sender_info()['formatted']}<br>
            ✔ Mensaje: {request.mensaje}
          </p>
        </div>
        """,
        action_text="Ir al Sistema Flymetrics"
    )

    resultado = GmailApiService.send_email(
        to_email=str(request.destinatario),
        subject=request.asunto,
        html_body=html_body,
        text_body=request.mensaje
    )

    return success_response(
        message="Solicitud de envío procesada",
        data=resultado
    )

