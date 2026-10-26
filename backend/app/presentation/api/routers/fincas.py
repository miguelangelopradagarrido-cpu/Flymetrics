from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import FincaUseCases
from app.presentation.api.dependencies.auth import get_current_user
from app.infrastructure.database.models.models import UsuarioModel
from app.shared.responses.response import success_response

router = APIRouter(prefix="/fincas", tags=["Fincas / Predios"])

@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def register_finca(request: schemas.FincaCreate, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Crea una nueva finca asociada al cliente. Las hectáreas y coordenadas se usan para cotizaciones."""
    finca = FincaUseCases.register_finca(db, request, current_user)
    data = schemas.FincaResponse.model_validate(finca).model_dump()
    return success_response(message="Finca registrada exitosamente", data=data, status_code=201)

@router.get("")
@router.get("/", include_in_schema=False)
def list_fincas(db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Retorna todas las fincas del cliente autenticado."""
    fincas = FincaUseCases.list_by_client(db, current_user)
    data = [schemas.FincaResponse.model_validate(f).model_dump() for f in fincas]
    return success_response(message="Lista de fincas obtenida exitosamente", data=data)

@router.get("/{id_finca}")
def get_finca(id_finca: int, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Retorna el detalle de una finca específica. Verifica que pertenezca al usuario."""
    finca = FincaUseCases.get_by_id(db, id_finca, current_user)
    data = schemas.FincaResponse.model_validate(finca).model_dump()
    return success_response(message="Detalle de finca obtenido", data=data)

@router.put("/{id_finca}")
def update_finca(id_finca: int, request: schemas.FincaUpdate, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Actualiza los datos de ubicación, hectáreas o coordenadas GPS de una finca."""
    finca = FincaUseCases.update_finca(db, id_finca, request, current_user)
    data = schemas.FincaResponse.model_validate(finca).model_dump()
    return success_response(message="Finca actualizada exitosamente", data=data)

@router.delete("/{id_finca}")
def delete_finca(id_finca: int, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Elimina una finca de la base de datos si no tiene turnos activos en agenda."""
    FincaUseCases.delete_finca(db, id_finca, current_user)
    return success_response(message="Finca eliminada exitosamente")
