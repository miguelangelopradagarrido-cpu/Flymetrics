from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import PQRUseCases
from app.presentation.api.dependencies.auth import get_current_user
from app.infrastructure.database.models.models import UsuarioModel
from app.shared.responses.response import success_response

router = APIRouter(prefix="/pqrs", tags=["Quejas, Reclamos y Soporte (PQRs)"])

@router.post("", status_code=status.HTTP_201_CREATED)
def crear_pqr(
    request: schemas.PQRCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Abre un nuevo ticket de soporte de tipo Petición, Queja o Reclamo. Envía correo automático al administrador."""
    pqr = PQRUseCases.crear_pqr(db, request, current_user)
    # Convertir a esquema de respuesta
    data = schemas.PQRResponse.model_validate(pqr).model_dump()
    return success_response(message="Ticket PQR abierto exitosamente", data=data, status_code=201)

@router.get("")
def listar_pqrs(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Lista todos los tickets de soporte. Los administradores ven todos los casos, los clientes solo ven los propios."""
    pqrs = PQRUseCases.listar_pqrs(db, current_user)
    data = [schemas.PQRResponse.model_validate(p).model_dump() for p in pqrs]
    return success_response(message="Listado de tickets obtenido exitosamente", data=data)

@router.get("/{id_pqr}")
def obtener_pqr(
    id_pqr: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Muestra el detalle y conversación de una PQR específica. Solo accesible para el creador del ticket o administradores."""
    pqr = PQRUseCases.obtener_pqr(db, id_pqr, current_user)
    data = schemas.PQRResponse.model_validate(pqr).model_dump()
    return success_response(message="Detalle de ticket obtenido exitosamente", data=data)

@router.post("/{id_pqr}/mensajes", status_code=status.HTTP_201_CREATED)
def responder_pqr(
    id_pqr: int,
    request: schemas.MensajePQRCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Envía un mensaje en el chat privado del ticket. Si responde el admin, notifica al cliente creador por correo y viceversa."""
    msg = PQRUseCases.responder_pqr(db, id_pqr, request, current_user)
    data = schemas.MensajePQRResponse.model_validate(msg).model_dump()
    return success_response(message="Mensaje enviado al chat de soporte", data=data, status_code=201)

@router.post("/{id_pqr}/cerrar")
def cerrar_pqr(
    id_pqr: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Marca el ticket PQR como Cerrado/Resuelto. Envía correo automático de resolución al cliente. Solo Administradores."""
    pqr = PQRUseCases.cerrar_pqr(db, id_pqr, current_user)
    data = schemas.PQRResponse.model_validate(pqr).model_dump()
    return success_response(message="Ticket de soporte cerrado exitosamente por el administrador", data=data)

