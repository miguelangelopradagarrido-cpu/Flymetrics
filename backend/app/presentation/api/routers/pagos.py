from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from datetime import date
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import PagoUseCases
from app.presentation.api.dependencies.auth import get_current_user, RoleChecker
from app.infrastructure.database.models.models import UsuarioModel
from app.shared.responses.response import success_response
from app.shared.exceptions.exceptions import BadRequestException

router = APIRouter(prefix="", tags=["Pagos"])

cliente_required = RoleChecker(["cliente"])
admin_required = RoleChecker(["administrador"])
admin_or_tec_required = RoleChecker(["administrador", "tecnico"])

ALLOWED_COMPROBANTE_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

@router.post("/pagos", status_code=status.HTTP_201_CREATED)
def registrar_pago(
    request: schemas.PagoCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tec_required)
):
    """Registra el pago de un servicio completado. Administradores y Técnicos."""
    pago = PagoUseCases.registrar_pago(db, request)
    data = schemas.PagoResponse.model_validate(pago).model_dump()
    return success_response(message="Pago registrado exitosamente", data=data, status_code=201)

@router.get("/pagos/mis-pagos")
def get_mis_pagos(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(cliente_required)
):
    """El cliente consulta su historial personal de pagos realizados."""
    pagos = PagoUseCases.ver_mis_pagos(db, current_user, page, limit)
    data = []
    for p in pagos:
        item = schemas.PagoResponse.model_validate(p).model_dump()
        actual_estado = p.estado_pago or "Pendiente"
        item["estado_pago"] = actual_estado
        item["estado"] = actual_estado
        item["metodo"] = p.metodo_pago or "Transferencia"
        item["metodo_pago"] = p.metodo_pago or "Transferencia"
        item["fecha"] = (p.fecha_pago or p.created_at).isoformat() if (p.fecha_pago or p.created_at) else ""
        item["url_comprobante"] = p.url_comprobante
        item["url_cotizacion"] = p.url_cotizacion
        
        if p.turno:
            if p.turno.finca:
                item["finca_nombre"] = p.turno.finca.nombre_finca
            if p.turno.servicio:
                item["servicio_nombre"] = p.turno.servicio.nombre_servicio
            else:
                item["servicio_nombre"] = "Servicio Dron"
        else:
            item["servicio_nombre"] = "Servicio Dron"
        data.append(item)
    return success_response(message="Historial de pagos obtenido exitosamente", data=data)

@router.get("/admin/pagos")
def list_todos_pagos(
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None),
    metodo_pago: str = Query(None, description="Efectivo, Transferencia, Tarjeta, Pendiente"),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tec_required)
):
    """Vista completa de todos los pagos registrados en el sistema. Solo administrador."""
    pagos = PagoUseCases.list_all_pagos(db, fecha_inicio, fecha_fin, metodo_pago)
    data = []
    for p in pagos:
        item = schemas.PagoResponse.model_validate(p).model_dump()
        actual_estado = p.estado_pago or "Pendiente"
        item["estado_pago"] = actual_estado
        item["estado"] = actual_estado
        item["metodo"] = p.metodo_pago or "Transferencia"
        item["metodo_pago"] = p.metodo_pago or "Transferencia"
        item["fecha"] = (p.fecha_pago or p.created_at).isoformat() if (p.fecha_pago or p.created_at) else ""
        item["url_comprobante"] = p.url_comprobante
        item["url_cotizacion"] = p.url_cotizacion
        
        if p.turno:
            if p.turno.finca and p.turno.finca.cliente:
                c = p.turno.finca.cliente
                item["cliente_nombre"] = f"{c.nombre} {c.apellido_1 or ''}".strip()
            else:
                item["cliente_nombre"] = "Cliente Flymetrics"
            if p.turno.servicio:
                item["servicio_nombre"] = p.turno.servicio.nombre_servicio
            else:
                item["servicio_nombre"] = "Servicio Dron"
        else:
            item["cliente_nombre"] = "Cliente Flymetrics"
            item["servicio_nombre"] = "Servicio Dron"
        data.append(item)
    return success_response(message="Historial general de pagos obtenido exitosamente", data=data)

from pydantic import BaseModel, Field
from fastapi import File, UploadFile, Form
import os, uuid
from datetime import datetime

class SubirComprobanteSchema(BaseModel):
    url_comprobante: str = Field(..., max_length=255)
    referencia_transaccion: str = Field(None, max_length=100)

class PagoUpdateSchema(BaseModel):
    estado: str = Field(None, description="Pagado, Pendiente, Rechazado, Enviado")
    estado_pago: str = Field(None)
    metodo: str = Field(None, description="Transferencia, Efectivo, Tarjeta, Convenio")
    metodo_pago: str = Field(None)
    monto: float = Field(None)
    url_comprobante: str = Field(None)
    url_cotizacion: str = Field(None)
    referencia_transaccion: str = Field(None)

@router.get("/pagos")
def list_pagos_alias(
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None),
    metodo_pago: str = Query(None),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Alias para listar pagos."""
    pagos = PagoUseCases.list_all_pagos(db, fecha_inicio, fecha_fin, metodo_pago)
    data = []
    for p in pagos:
        item = schemas.PagoResponse.model_validate(p).model_dump()
        actual_estado = p.estado_pago or "Pendiente"
        item["estado_pago"] = actual_estado
        item["estado"] = actual_estado
        item["metodo"] = p.metodo_pago or "Transferencia"
        item["metodo_pago"] = p.metodo_pago or "Transferencia"
        item["fecha"] = (p.fecha_pago or p.created_at).isoformat() if (p.fecha_pago or p.created_at) else ""
        item["url_comprobante"] = p.url_comprobante
        item["url_cotizacion"] = p.url_cotizacion
        
        if p.turno:
            if p.turno.finca and p.turno.finca.cliente:
                c = p.turno.finca.cliente
                item["cliente_nombre"] = f"{c.nombre} {c.apellido_1 or ''}".strip()
            else:
                item["cliente_nombre"] = "Cliente Flymetrics"
            if p.turno.servicio:
                item["servicio_nombre"] = p.turno.servicio.nombre_servicio
            else:
                item["servicio_nombre"] = "Servicio Dron"
        else:
            item["cliente_nombre"] = "Cliente Flymetrics"
            item["servicio_nombre"] = "Servicio Dron"
        data.append(item)
    return success_response(message="Lista de pagos obtenida", data=data)

@router.put("/pagos/{id_pago}")
@router.patch("/pagos/{id_pago}")
def actualizar_pago(
    id_pago: int,
    request: PagoUpdateSchema,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Actualiza el estado o método de pago (Administrador / Técnico)."""
    from app.infrastructure.database.models.models import PagoModel
    from app.shared.exceptions.exceptions import NotFoundException

    pago = db.query(PagoModel).filter(PagoModel.id_pago == id_pago).first()
    if not pago:
        raise NotFoundException("Registro de pago no encontrado")

    nuevo_estado = request.estado or request.estado_pago
    nuevo_metodo = request.metodo or request.metodo_pago

    if nuevo_estado:
        pago.estado_pago = nuevo_estado
        if nuevo_estado == "Pagado" and not pago.fecha_pago:
            pago.fecha_pago = datetime.utcnow()
    if nuevo_metodo:
        from app.infrastructure.database.models.models import MetodoPagoEnum
        try:
            pago.metodo_pago = MetodoPagoEnum(nuevo_metodo)
        except ValueError:
            pago.metodo_pago = MetodoPagoEnum.Transferencia
    if request.monto is not None:
        pago.monto = request.monto
    if request.url_comprobante:
        pago.url_comprobante = request.url_comprobante
    if request.url_cotizacion:
        pago.url_cotizacion = request.url_cotizacion
    if request.referencia_transaccion:
        pago.referencia_transaccion = request.referencia_transaccion

    db.commit()
    db.refresh(pago)
    
    item = schemas.PagoResponse.model_validate(pago).model_dump()
    actual_estado = pago.estado_pago or "Pendiente"
    item["estado_pago"] = actual_estado
    item["estado"] = actual_estado
    item["metodo"] = pago.metodo_pago or "Transferencia"
    item["metodo_pago"] = pago.metodo_pago or "Transferencia"
    item["fecha"] = (pago.fecha_pago or pago.created_at).isoformat() if (pago.fecha_pago or pago.created_at) else ""
    return success_response(message="Pago actualizado exitosamente", data=item)

@router.delete("/pagos/{id_pago}")
def eliminar_pago(
    id_pago: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Elimina o revoca un registro de pago."""
    from app.infrastructure.database.models.models import PagoModel
    from app.shared.exceptions.exceptions import NotFoundException

    pago = db.query(PagoModel).filter(PagoModel.id_pago == id_pago).first()
    if not pago:
        raise NotFoundException("Registro de pago no encontrado")

    db.delete(pago)
    db.commit()
    return success_response(message="Registro de pago eliminado exitosamente")

@router.post("/pagos/upload-comprobante")
async def upload_comprobante_archivo(
    id_pago: int = Form(...),
    id_turno: int = Form(None),
    referencia: str = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Sube un archivo de comprobante de pago físico directamente a la plataforma."""
    from app.infrastructure.database.models.models import PagoModel, AgendaModel, MetodoPagoEnum
    from app.shared.exceptions.exceptions import NotFoundException
    from decimal import Decimal

    pago = db.query(PagoModel).filter(PagoModel.id_pago == id_pago).first()
    
    if not pago and id_turno:
        pago = db.query(PagoModel).filter(PagoModel.id_turno == id_turno).first()
        
    if not pago:
        # Buscar el turno si id_pago era en realidad un id_turno o si vino id_turno
        target_turno_id = id_turno or id_pago
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == target_turno_id).first()
        if not turno:
            raise NotFoundException(f"No se encontró un turno ni registro de pago asociado con ID #{target_turno_id}.")

        # Validación de propiedad para clientes
        if current_user.rol == "cliente":
            if not (turno.finca and turno.finca.cliente and turno.finca.cliente.id_usuario == current_user.id_usuarios):
                from app.shared.exceptions.exceptions import ForbiddenException
                raise ForbiddenException("No tienes permiso para registrar pagos en este servicio.")
        
        monto_calc = Decimal("850000.00")
        if turno and turno.finca and turno.finca.hectareas and turno.servicio and turno.servicio.precio_base_m2:
            monto_calc = Decimal(str(round(float(turno.finca.hectareas) * 10000.0 * float(turno.servicio.precio_base_m2), 2)))
            
        pago = PagoModel(
            id_turno=turno.id_turno,
            monto=monto_calc,
            metodo_pago=MetodoPagoEnum.Transferencia,
            estado_pago="Enviado",
            referencia_transaccion=referencia or "Comprobante Subido por Cliente"
        )
        db.add(pago)
        db.flush()
    else:
        # Validar propiedad del pago existente
        if current_user.rol == "cliente":
            t = pago.turno
            if not (t and t.finca and t.finca.cliente and t.finca.cliente.id_usuario == current_user.id_usuarios):
                from app.shared.exceptions.exceptions import ForbiddenException
                raise ForbiddenException("No tienes permiso para registrar comprobantes en este pago.")

    safe_filename = os.path.basename(file.filename or "")
    ext = (os.path.splitext(safe_filename)[1] or "").lower()
    if ext not in ALLOWED_COMPROBANTE_EXTS:
        raise BadRequestException(f"Extensión '{ext}' no permitida. Solo se aceptan imágenes o PDFs ({', '.join(sorted(ALLOWED_COMPROBANTE_EXTS))}).")

    base_frontend = "frontend"
    if not os.path.isdir(base_frontend):
        base_frontend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    uploads_dir = os.path.join(base_frontend, "uploads", "comprobantes")
    os.makedirs(uploads_dir, exist_ok=True)
    
    unique_name = f"comprobante_{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(uploads_dir, unique_name)
    
    total_size = 0
    max_size = 20 * 1024 * 1024  # 20MB
    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size:
                    f.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise BadRequestException("El comprobante supera el tamaño máximo de 20 MB.")
                f.write(chunk)
    except BadRequestException:
        raise
    except Exception as stream_err:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise BadRequestException(f"Error al procesar el archivo: {str(stream_err)}")

    relative_url = f"/uploads/comprobantes/{unique_name}"
    pago.url_comprobante = relative_url
    if referencia:
        pago.referencia_transaccion = referencia
    pago.estado_pago = "Enviado"

    db.commit()
    db.refresh(pago)
    
    data = schemas.PagoResponse.model_validate(pago).model_dump()
    return success_response(message="Comprobante de pago subido y registrado correctamente", data=data)

@router.post("/pagos/{id_pago}/subir-comprobante")
def subir_comprobante_pago(
    id_pago: int,
    request: SubirComprobanteSchema,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Permite al cliente adjuntar el comprobante o soporte del pago realizado."""
    from app.infrastructure.database.models.models import PagoModel
    from app.shared.exceptions.exceptions import NotFoundException
    
    pago = db.query(PagoModel).filter(PagoModel.id_pago == id_pago).first()
    if not pago:
        raise NotFoundException("Pago no encontrado")
        
    pago.url_comprobante = request.url_comprobante
    if request.referencia_transaccion:
        pago.referencia_transaccion = request.referencia_transaccion
    pago.estado_pago = "Enviado"
    
    db.commit()
    db.refresh(pago)
    
    data = {
        "id_pago": pago.id_pago,
        "monto": float(pago.monto),
        "url_comprobante": pago.url_comprobante,
        "estado_pago": pago.estado_pago,
        "referencia_transaccion": pago.referencia_transaccion
    }
    return success_response(message="Comprobante de pago subido exitosamente.", data=data)
