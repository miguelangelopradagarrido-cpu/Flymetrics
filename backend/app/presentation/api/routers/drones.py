from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import FlotaUseCases
from app.presentation.api.dependencies.auth import RoleChecker
from app.infrastructure.database.models.models import UsuarioModel
from app.shared.responses.response import success_response

router = APIRouter(prefix="/drones", tags=["Flota de Drones"])

admin_required = RoleChecker(["administrador"])
admin_or_tech = RoleChecker(["administrador", "tecnico"])

@router.get("")
@router.get("/", include_in_schema=False)
def list_drones(
    estado: str = Query(None, description="Filtrar por disponible, en_vuelo, mantenimiento"),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """Retorna todos los drones registrados con su estado actual y técnico asignado. Solo administrador."""
    drones = FlotaUseCases.list_drones(db, estado)
    data = []
    for d in drones:
        item = schemas.DroneResponse.model_validate(d).model_dump()
        if d.tecnico_asignado:
            item["tecnico_nombre"] = f"{d.tecnico_asignado.nombre} {d.tecnico_asignado.apellido_1 or ''}".strip()
        else:
            item["tecnico_nombre"] = "Sin asignar"
        data.append(item)
    return success_response(message="Flota de drones obtenida exitosamente", data=data)

@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_drone(
    request: schemas.DroneCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Registra un nuevo dron en la flota. Solo administrador."""
    drone = FlotaUseCases.create_drone(db, request)
    data = schemas.DroneResponse.model_validate(drone).model_dump()
    return success_response(message="Dron registrado exitosamente", data=data, status_code=201)

@router.patch("/{id_drone}")
@router.put("/{id_drone}")
def update_drone(
    id_drone: int,
    request: schemas.DroneUpdate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Actualiza el estado operativo o modelo del dron. Solo administrador."""
    drone = FlotaUseCases.update_drone(db, id_drone, request)
    data = schemas.DroneResponse.model_validate(drone).model_dump()
    return success_response(message="Dron actualizado exitosamente", data=data)

@router.post("/{id_drone}/mantenimientos", status_code=status.HTTP_201_CREATED)
def registrar_mantenimiento(
    id_drone: int,
    request: schemas.MantenimientoCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Crea un registro de mantenimiento en la flota. Cambia el estado del dron a 'mantenimiento'. Solo administrador."""
    maint = FlotaUseCases.registrar_mantenimiento(db, id_drone, request)
    data = schemas.MantenimientoResponse.model_validate(maint).model_dump()
    return success_response(message="Registro de mantenimiento guardado. Dron puesto en estado 'mantenimiento'.", data=data, status_code=201)

@router.get("/mantenimientos/all")
def get_todos_mantenimientos(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Retorna el historial global de mantenimientos y gastos operativos de la flota. Solo administrador."""
    from app.infrastructure.database.models.models import MantenimientoModel
    historial = db.query(MantenimientoModel).order_by(MantenimientoModel.fecha_ingreso.desc()).all()
    data = []
    for m in historial:
        m_dict = schemas.MantenimientoResponse.model_validate(m).model_dump()
        m_dict["modelo_dron"] = m.drone.modelo if m.drone else "N/A"
        data.append(m_dict)
    return success_response(message="Historial global de mantenimientos y gastos obtenido exitosamente", data=data)

@router.get("/{id_drone}/mantenimientos")
def get_historial_mantenimientos(
    id_drone: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Retorna el historial de mantenimientos de un dron especifico. Solo administrador."""
    historial = FlotaUseCases.ver_historial_mantenimientos(db, id_drone)
    data = [schemas.MantenimientoResponse.model_validate(m).model_dump() for m in historial]
    return success_response(message="Historial de mantenimientos obtenido exitosamente", data=data)


@router.delete("/{id_drone}", status_code=status.HTTP_200_OK)
def delete_drone(
    id_drone: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Elimina un dron de la flota. Solo administrador."""
    from app.infrastructure.database.models.models import DroneModel, AgendaModel
    from app.shared.exceptions.exceptions import NotFoundException
    drone = db.query(DroneModel).filter(DroneModel.id_drone == id_drone).first()
    if not drone:
        raise NotFoundException("Dron no encontrado")
    db.query(AgendaModel).filter(AgendaModel.id_drone == id_drone).update({AgendaModel.id_drone: None})
    db.delete(drone)
    db.commit()
    return success_response(message="Dron eliminado exitosamente")


@router.put("/mantenimientos/{id_mantenimiento}")
def update_mantenimiento(
    id_mantenimiento: int,
    request: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Actualiza un registro de mantenimiento/gasto. Solo administrador."""
    from app.infrastructure.database.models.models import MantenimientoModel
    from app.shared.exceptions.exceptions import NotFoundException
    maint = db.query(MantenimientoModel).filter(MantenimientoModel.id_mantenimiento == id_mantenimiento).first()
    if not maint:
        raise NotFoundException("Registro de mantenimiento no encontrado")
    
    if "tipo_mantenimiento" in request:
        maint.tipo_mantenimiento = request["tipo_mantenimiento"]
    if "descripcion_falla" in request:
        maint.descripcion_falla = request["descripcion_falla"]
    if "costo_mantenimiento" in request:
        maint.costo_mantenimiento = float(request["costo_mantenimiento"])
    if "responsable_tecnico" in request:
        maint.responsable_tecnico = request["responsable_tecnico"]
    if "id_drone" in request and request["id_drone"]:
        maint.id_drone = int(request["id_drone"])
        
    db.commit()
    db.refresh(maint)
    m_dict = schemas.MantenimientoResponse.model_validate(maint).model_dump()
    m_dict["modelo_dron"] = maint.drone.modelo if maint.drone else "N/A"
    return success_response(message="Mantenimiento actualizado exitosamente", data=m_dict)


@router.delete("/mantenimientos/{id_mantenimiento}", status_code=status.HTTP_200_OK)
def delete_mantenimiento(
    id_mantenimiento: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Elimina un registro de mantenimiento/gasto. Solo administrador."""
    from app.infrastructure.database.models.models import MantenimientoModel
    from app.shared.exceptions.exceptions import NotFoundException
    maint = db.query(MantenimientoModel).filter(MantenimientoModel.id_mantenimiento == id_mantenimiento).first()
    if not maint:
        raise NotFoundException("Registro de mantenimiento no encontrado")
    db.delete(maint)
    db.commit()
    return success_response(message="Registro de mantenimiento eliminado exitosamente")


@router.patch("/{id_drone}/toggle-estado")
def toggle_drone_estado(
    id_drone: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Alterna el estado del dron entre 'Habilitado' (disponible) y 'Deshabilitado' (inactivo)."""
    from app.infrastructure.database.models.models import DroneModel
    from app.shared.exceptions.exceptions import NotFoundException

    drone = db.query(DroneModel).filter(DroneModel.id_drone == id_drone).first()
    if not drone:
        raise NotFoundException("Dron no encontrado")

    current = str(drone.estado or "").lower()
    if current in ["habilitado", "disponible", "activo"]:
        nuevo = "Deshabilitado"
    else:
        nuevo = "Habilitado"

    drone.estado = nuevo
    db.commit()
    db.refresh(drone)
    return success_response(message=f"Estado del dron #{id_drone} cambiado a {nuevo}", data={"id_drone": id_drone, "estado": nuevo})
