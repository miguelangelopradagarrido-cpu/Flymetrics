from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.infrastructure.database.models.models import SolicitudTecnicoModel, TecnicoModel, AgendaModel, UsuarioModel
from app.presentation.api.dependencies.auth import RoleChecker
from app.shared.responses.response import success_response
from app.application.dto.schemas import SolicitudTecnicoCreate, SolicitudTecnicoResponder

router = APIRouter(prefix="", tags=["Peticiones & Autorizaciones de Técnicos"])

tecnico_required = RoleChecker(["tecnico", "administrador"])
admin_required = RoleChecker(["administrador"])

@router.post("/tecnico/solicitudes", status_code=status.HTTP_201_CREATED)
def crear_solicitud_tecnico(
    request: SolicitudTecnicoCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(tecnico_required)
):
    """El técnico envía una solicitud de autorización al Administrador."""
    tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
    if not tecnico:
        raise HTTPException(status_code=404, detail="Perfil de técnico no encontrado")

    nueva = SolicitudTecnicoModel(
        id_tecnico=tecnico.id_tecnico,
        id_turno=request.id_turno,
        tipo_solicitud=request.tipo_solicitud,
        titulo=request.titulo,
        justificacion=request.justificacion,
        estado="Pendiente"
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    return success_response(
        message="Solicitud de autorización enviada al administrador exitosamente",
        data={
            "id_solicitud": nueva.id_solicitud,
            "id_tecnico": nueva.id_tecnico,
            "id_turno": nueva.id_turno,
            "tipo_solicitud": nueva.tipo_solicitud,
            "titulo": nueva.titulo,
            "estado": nueva.estado,
            "fecha_creacion": nueva.fecha_creacion.isoformat() if nueva.fecha_creacion else None
        },
        status_code=201
    )

@router.get("/tecnico/solicitudes")
def listar_solicitudes_propia(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(tecnico_required)
):
    """Listado de solicitudes enviadas por el técnico autenticado."""
    tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
    if not tecnico:
        return success_response(message="Sin solicitudes", data=[])

    solicitudes = db.query(SolicitudTecnicoModel).filter(
        SolicitudTecnicoModel.id_tecnico == tecnico.id_tecnico
    ).order_by(SolicitudTecnicoModel.id_solicitud.desc()).all()

    data = []
    for s in solicitudes:
        data.append({
            "id_solicitud": s.id_solicitud,
            "id_tecnico": s.id_tecnico,
            "id_turno": s.id_turno,
            "tipo_solicitud": s.tipo_solicitud,
            "titulo": s.titulo,
            "justificacion": s.justificacion,
            "estado": s.estado,
            "respuesta_admin": s.respuesta_admin,
            "fecha_creacion": s.fecha_creacion.isoformat() if s.fecha_creacion else None
        })

    return success_response(message="Solicitudes del técnico obtenidas", data=data)

@router.get("/admin/solicitudes-tecnico")
def listar_todas_solicitudes_admin(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """El Administrador visualiza todas las solicitudes y peticiones enviadas por los técnicos."""
    solicitudes = db.query(SolicitudTecnicoModel).order_by(SolicitudTecnicoModel.id_solicitud.desc()).all()

    data = []
    for s in solicitudes:
        tec_name = f"{s.tecnico.nombre} {s.tecnico.apellido_1}" if s.tecnico else "Técnico"
        data.append({
            "id_solicitud": s.id_solicitud,
            "id_tecnico": s.id_tecnico,
            "tecnico_nombre": tec_name,
            "id_turno": s.id_turno,
            "tipo_solicitud": s.tipo_solicitud,
            "titulo": s.titulo,
            "justificacion": s.justificacion,
            "estado": s.estado,
            "respuesta_admin": s.respuesta_admin,
            "fecha_creacion": s.fecha_creacion.isoformat() if s.fecha_creacion else None
        })

    return success_response(message="Solicitudes recibidas obtenidas", data=data)

@router.patch("/admin/solicitudes-tecnico/{id_solicitud}/responder")
def responder_solicitud_admin(
    id_solicitud: int,
    request: SolicitudTecnicoResponder,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """El Administrador aprueba ('Aprobado') o rechaza ('Rechazado') la solicitud del técnico."""
    sol = db.query(SolicitudTecnicoModel).filter(SolicitudTecnicoModel.id_solicitud == id_solicitud).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    sol.estado = request.estado
    sol.respuesta_admin = request.respuesta_admin

    # Si se aprueba una solicitud de cancelación de turno, actualizar automáticamente el estado del turno
    if request.estado == "Aprobado" and sol.id_turno:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == sol.id_turno).first()
        if turno:
            if sol.tipo_solicitud == "Cancelacion":
                turno.estado = "Cancelado"
                turno.observaciones_servicio = f"{turno.observaciones_servicio or ''} | Cancelación aprobada por admin: {sol.justificacion}".strip()

    db.commit()
    db.refresh(sol)

    return success_response(
        message=f"Solicitud #{id_solicitud} {sol.estado} correctamente",
        data={
            "id_solicitud": sol.id_solicitud,
            "estado": sol.estado,
            "respuesta_admin": sol.respuesta_admin
        }
    )
