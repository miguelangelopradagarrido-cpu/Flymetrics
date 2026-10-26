from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import ServicioUseCases
from app.presentation.api.dependencies.auth import RoleChecker
from app.infrastructure.database.models.models import UsuarioModel, ServicioModel
from app.shared.responses.response import success_response
from app.shared.exceptions.exceptions import NotFoundException

router = APIRouter(prefix="/servicios", tags=["Servicios y Cotizacion"])

admin_required = RoleChecker(["administrador"])

@router.get("")
@router.get("/", include_in_schema=False)
def list_servicios(
    include_inactive: bool = Query(False, description="Si es True, incluye servicios desactivados (Admin)"),
    db: Session = Depends(get_db)
):
    """Retorna los servicios del catalogo. Endpoint publico filtra activos; admin puede solicitar todos."""
    servicios = ServicioUseCases.list_all(db, only_active=not include_inactive)
    data = [schemas.ServicioResponse.model_validate(s).model_dump() for s in servicios]
    return success_response(message="Catalogo de servicios obtenido exitosamente", data=data)

@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_servicio(request: schemas.ServicioCreate, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(admin_required)):
    """El administrador anade un nuevo tipo de servicio al catalogo."""
    servicio = ServicioUseCases.create_servicio(db, request)
    data = schemas.ServicioResponse.model_validate(servicio).model_dump()
    return success_response(message="Servicio creado exitosamente", data=data, status_code=201)

@router.put("/{id_servicio}")
def update_servicio(
    id_servicio: int,
    request: schemas.ServicioUpdate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """El administrador actualiza un servicio existente del catálogo."""
    servicio = db.query(ServicioModel).filter(ServicioModel.id_servicio == id_servicio).first()
    from app.presentation.api.routers.media import delete_physical_upload
    if not servicio:
        raise NotFoundException("Servicio no encontrado")
    data = request.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(servicio, key, value)
    db.commit()
    db.refresh(servicio)
    return success_response(message="Servicio actualizado exitosamente", data=schemas.ServicioResponse.model_validate(servicio).model_dump())

@router.delete("/{id_servicio}", status_code=status.HTTP_200_OK)
def delete_servicio(
    id_servicio: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """El administrador elimina un servicio del catalogo permanentemente."""
    from app.infrastructure.database.models.models import AgendaModel
    from app.presentation.api.routers.media import delete_physical_upload
    servicio = db.query(ServicioModel).filter(ServicioModel.id_servicio == id_servicio).first()
    if not servicio:
        raise NotFoundException("Servicio no encontrado")
    
    turnos_count = db.query(AgendaModel).filter(AgendaModel.id_servicio == id_servicio).count()
    if turnos_count > 0:
        otro_servicio = db.query(ServicioModel).filter(
            ServicioModel.id_servicio != id_servicio,
            ServicioModel.activo == True
        ).first()
        if otro_servicio:
            db.query(AgendaModel).filter(AgendaModel.id_servicio == id_servicio).update(
                {"id_servicio": otro_servicio.id_servicio},
                synchronize_session=False
            )
            db.commit()
            if servicio.imagen_url: delete_physical_upload(servicio.imagen_url)
            if servicio.video_url: delete_physical_upload(servicio.video_url)
            db.delete(servicio)
            db.commit()
            return success_response(message=f"Servicio eliminado del catálogo. {turnos_count} turnos asociados fueron reasignados al servicio '{otro_servicio.nombre_servicio}'.")
        else:
            servicio.activo = False
            db.commit()
            return success_response(message="El servicio fue desactivado del catálogo para proteger el historial de turnos existentes.")
    
    if servicio.imagen_url: delete_physical_upload(servicio.imagen_url)
    if servicio.video_url: delete_physical_upload(servicio.video_url)
    db.delete(servicio)
    db.commit()
    return success_response(message="Servicio eliminado exitosamente del catálogo")

@router.post("/cotizar")
def cotizar_servicio(request: schemas.CotizacionRequest, db: Session = Depends(get_db)):
    """Calcula el precio base, costo logistico y total para un servicio."""
    cotizacion = ServicioUseCases.calculate_cotizacion(db, request)
    return success_response(message="Cotizacion calculada exitosamente", data=cotizacion)
