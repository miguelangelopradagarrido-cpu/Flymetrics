from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session, joinedload
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import TecnicoUseCases
from app.presentation.api.dependencies.auth import get_current_user, RoleChecker
from app.infrastructure.database.models.models import UsuarioModel, TecnicoModel
from app.shared.responses.response import success_response

router = APIRouter(prefix="/tecnicos", tags=["Técnicos"])

# Solo el administrador puede crear perfiles de técnico y listar a todos
admin_required = RoleChecker(["administrador"])

@router.get("")
def list_all(
    solo_activos: bool = Query(False, description="Si es True, excluye a los pilotos deshabilitados/inactivos"),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Retorna la lista de todos los técnicos del sistema con usuario precargado."""
    try:
        query = db.query(TecnicoModel).options(joinedload(TecnicoModel.usuario))
        if solo_activos:
            query = query.filter(TecnicoModel.estado.notin_(["Deshabilitado", "Inactivo", "deshabilitado", "inactivo"]))
        tecnicos = query.all()
        data = []
        for t in tecnicos:
            try:
                item = schemas.TecnicoResponse.model_validate(t).model_dump()
            except Exception:
                item = {
                    "id_tecnico": t.id_tecnico,
                    "id_usuario": t.id_usuario,
                    "nombre": t.nombre or "",
                    "apellido_1": t.apellido_1 or "",
                    "apellido_2": t.apellido_2 or "",
                    "certificacion": t.certificacion or "RAC-100",
                    "estado": t.estado or "disponible",
                    "telefono": t.telefono or "",
                    "servicios_capacitados": t.servicios_capacitados or "1,2,3"
                }
            item["email"] = t.usuario.email if t.usuario else getattr(t, "email", "")
            data.append(item)
        return success_response(message="Lista de técnicos obtenida exitosamente", data=data)
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").error(f"[ERROR LISTAR TECNICOS] {e}", exc_info=True)
        return success_response(message="Lista de técnicos obtenida", data=[])

class TecnicoRegisterRequest(schemas.UsuarioCreate):
    rol: Optional[str] = "tecnico"
    certificacion: Optional[str] = None

@router.post("", status_code=status.HTTP_201_CREATED)
def create_tecnico(request: TecnicoRegisterRequest, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(admin_required)):
    """Crea un nuevo usuario con rol tecnico y su perfil."""
    from app.application.use_cases.use_cases import AuthUseCases
    user_req = schemas.UsuarioCreate(
        email=request.email,
        contraseña=request.contraseña,
        rol="tecnico",
        nombre=request.nombre,
        apellido_1=request.apellido_1,
        apellido_2=request.apellido_2,
        telefono=request.telefono
    )
    user = AuthUseCases.register_user(db, user_req)
    
    # Update certificacion in the profile created by AuthUseCases
    tecnico = TecnicoUseCases.get_by_id(db, user.tecnico.id_tecnico)
    update_req = schemas.TecnicoUpdate(certificacion=request.certificacion)
    TecnicoUseCases.update_profile(db, tecnico.id_tecnico, update_req)
    
    return success_response(message="Técnico creado exitosamente", data={"id": user.tecnico.id_tecnico}, status_code=201)

@router.get("/mis-turnos")
def list_mis_turnos_tecnico(
    fecha: date = Query(None),
    estado: str = Query(None),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(RoleChecker(["tecnico", "administrador"]))
):
    """Consulta de turnos asignados al técnico actual."""
    return get_tecnico_agenda(fecha=fecha, estado=estado, db=db, current_user=current_user)

@router.get("/operaciones")
def list_operaciones_tecnico(
    fecha: date = Query(None),
    estado: str = Query(None),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(RoleChecker(["tecnico", "administrador"]))
):
    """Listado operacional para el técnico en campo."""
    return get_tecnico_agenda(fecha=fecha, estado=estado, db=db, current_user=current_user)

@router.get("/{id_tecnico}")
def get_by_id(id_tecnico: int, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Detalle de un técnico específico. Protegido por JWT."""
    tecnico = TecnicoUseCases.get_by_id(db, id_tecnico)
    data = schemas.TecnicoResponse.model_validate(tecnico).model_dump()
    return success_response(message="Detalle de técnico obtenido", data=data)

@router.put("/{id_tecnico}")
def update_profile(id_tecnico: int, request: schemas.TecnicoUpdate, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Actualiza datos del perfil del técnico. El propio técnico o un administrador pueden editarlo."""
    from app.shared.exceptions.exceptions import UnauthorizedException
    is_admin = current_user.rol == "administrador"
    is_self = current_user.rol == "tecnico" and current_user.tecnico and current_user.tecnico.id_tecnico == id_tecnico
    if not (is_admin or is_self):
        raise UnauthorizedException("No tienes permisos para modificar este perfil de técnico.")
    tecnico = TecnicoUseCases.update_profile(db, id_tecnico, request)
    data = schemas.TecnicoResponse.model_validate(tecnico).model_dump()
    return success_response(message="Perfil de técnico actualizado", data=data)

@router.get("/{id_tecnico}/calendario-ocupacion")
def get_calendario_ocupacion(
    id_tecnico: int,
    anio: int = Query(...),
    mes: int = Query(...),
    id_finca: int = Query(None),
    id_servicio: int = Query(None),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Consulta la mapa de ocupación del técnico por mes."""
    from app.infrastructure.database.models.models import AgendaModel
    import calendar
    from datetime import date

    _, num_days = calendar.monthrange(anio, mes)
    start_date = date(anio, mes, 1)
    end_date = date(anio, mes, num_days)

    turnos = db.query(AgendaModel).filter(
        AgendaModel.id_tecnico == id_tecnico,
        AgendaModel.fecha_de_turno >= start_date,
        AgendaModel.fecha_de_turno <= end_date,
        AgendaModel.estado.in_(["Confirmado", "En Proceso", "Pendiente"])
    ).all()

    ocupados_por_fecha = {}
    for t in turnos:
        d_str = str(t.fecha_de_turno)
        ocupados_por_fecha[d_str] = ocupados_por_fecha.get(d_str, 0) + 1

    result = {}
    for day in range(1, num_days + 1):
        d_str = f"{anio}-{mes:02d}-{day:02d}"
        count = ocupados_por_fecha.get(d_str, 0)
        estado = "libre" if count == 0 else ("parcial" if count < 3 else "ocupado")
        result[d_str] = estado

    return success_response(message="Calendario de ocupación obtenido", data=result)


@router.get("/{id_tecnico}/disponibilidad")
def get_disponibilidad_tecnico(
    id_tecnico: int,
    fecha: date = Query(...),
    id_finca: int = Query(...),
    id_servicio: int = Query(...),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Consulta los slots de tiempo disponibles para un técnico en una fecha específica."""
    from app.infrastructure.database.models.models import FincaModel, AgendaModel
    finca = db.query(FincaModel).filter(FincaModel.id_finca == id_finca).first()
    hectareas = float(finca.hectareas or 1.0) if finca else 1.0
    duracion_horas = max(1.0, round(hectareas / 5.0, 1))

    turnos = db.query(AgendaModel).filter(
        AgendaModel.id_tecnico == id_tecnico,
        AgendaModel.fecha_de_turno == fecha,
        AgendaModel.estado.in_(["Confirmado", "En Proceso", "Pendiente"])
    ).all()

    busy_intervals = []
    for t in turnos:
        if t.hora_inicio_estimada and t.hora_fin_estimada:
            h_start = t.hora_inicio_estimada.hour * 60 + t.hora_inicio_estimada.minute
            h_end = t.hora_fin_estimada.hour * 60 + t.hora_fin_estimada.minute
            busy_intervals.append((h_start, h_end))

    start_min = 360  # 06:00 AM
    end_min = 1080   # 06:00 PM
    dur_min = int(duracion_horas * 60)

    slots_disponibles = []
    for current in range(start_min, end_min - dur_min + 1, 30):
        slot_end = current + dur_min
        overlap = False
        for b_start, b_end in busy_intervals:
            if current < b_end and slot_end > b_start:
                overlap = True
                break
        if not overlap:
            h = current // 60
            m = current % 60
            slots_disponibles.append(f"{h:02d}:{m:02d}:00")

    data = {
        "duracion_horas": duracion_horas,
        "slots_disponibles": slots_disponibles
    }
    return success_response(message="Disponibilidad obtenida exitosamente", data=data)


@router.delete("/{id_tecnico}")
def delete_tecnico(id_tecnico: int, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(admin_required)):
    """Elimina un técnico. Solo administrador."""
    TecnicoUseCases.delete_tecnico(db, id_tecnico)
    return success_response(message="Técnico eliminado exitosamente")


@router.patch("/{id_tecnico}/toggle-estado")
def toggle_tecnico_estado(
    id_tecnico: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Alterna el estado operativo del técnico entre 'Habilitado' (activo) y 'Deshabilitado' (inactivo)."""
    from app.infrastructure.database.models.models import TecnicoModel
    from app.shared.exceptions.exceptions import NotFoundException

    tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == id_tecnico).first()
    if not tecnico:
        raise NotFoundException("Técnico no encontrado")

    current = str(tecnico.estado or "").lower()
    if current in ["habilitado", "activo", "disponible"]:
        nuevo = "Deshabilitado"
    else:
        nuevo = "Habilitado"

    tecnico.estado = nuevo
    db.commit()
    db.refresh(tecnico)
    return success_response(message=f"Estado del técnico #{id_tecnico} cambiado a {nuevo}", data={"id_tecnico": id_tecnico, "estado": nuevo})

# ─────────────────────────────────────────────────────────────────────────────
# RUTAS OPERATIVAS DEL TÉCNICO (AGENDA, CHECKIN, CHECKOUT, COMPLETAR)
# ─────────────────────────────────────────────────────────────────────────────
from app.application.use_cases.use_cases import BitacoraUseCases

tecnico_ops_router = APIRouter(prefix="", tags=["Operaciones de Campo del Técnico"])
tecnico_required = RoleChecker(["tecnico", "administrador"])

@tecnico_ops_router.get("/tecnico/agenda")
def get_tecnico_agenda(
    fecha: date = Query(None, description="Fecha YYYY-MM-DD. Por defecto es hoy."),
    estado: str = Query(None, description="Filtrar por: Pendiente, Confirmado, En Proceso"),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(tecnico_required)
):
    """Retorna los turnos asignados al técnico autenticado para la fecha solicitada."""
    turnos = BitacoraUseCases.get_tecnico_agenda(db, current_user, fecha, estado)
    data = []
    for t in turnos:
        item = {
            "id_turno": t.id_turno,
            "id_finca": t.id_finca,
            "id_servicio": t.id_servicio,
            "id_drone": t.id_drone,
            "id_tecnico": t.id_tecnico,
            "fecha_de_turno": t.fecha_de_turno.isoformat() if t.fecha_de_turno else None,
            "hora_inicio_estimada": str(t.hora_inicio_estimada) if t.hora_inicio_estimada else "10:00:00",
            "hora_fin_estimada": str(t.hora_fin_estimada) if t.hora_fin_estimada else "12:00:00",
            "tipo_turno": t.tipo_turno.value if hasattr(t.tipo_turno, 'value') else str(t.tipo_turno or 'Fumigación'),
            "estado": t.estado or "Pendiente",
            "tarifa": float(t.tarifa or 0.0),
            "costo_logistico": float(t.costo_logistico or 0.0),
            "observaciones_servicio": t.observaciones_servicio or "",
            "notas": t.observaciones_servicio or ""
        }
        obs_text = t.observaciones_servicio or ""
        import re
        m_cul = re.search(r'(?:Cultivo y Area|Cultivo):\s*([^\(\n\r]+)', obs_text, re.IGNORECASE)
        cultivo_real = m_cul.group(1).strip() if m_cul else "Agrícola"

        m_ver = re.search(r'(?:Vereda / Corregimiento|Vereda):\s*([^\n\r]+)', obs_text, re.IGNORECASE)
        vereda_real = m_ver.group(1).strip() if m_ver else ""

        m_dir = re.search(r'(?:Direccion / Coordenadas|Dirección|Ubicación):\s*([^\n\r]+)', obs_text, re.IGNORECASE)
        dir_real = m_dir.group(1).strip() if m_dir else ""

        m_cli_notas = re.search(r'(?:Notas Adicionales|Observaciones Adicionales):\s*([^\n\r]+(?:\n[^\n\r\-•]+)*)', obs_text, re.IGNORECASE)
        notas_cliente = m_cli_notas.group(1).strip() if m_cli_notas else ""

        item["tipo_cultivo"] = cultivo_real
        item["cultivo"] = cultivo_real
        item["notas_cliente"] = notas_cliente
        item["motivo_reagendamiento"] = t.motivo_reagendamiento or ""

        if t.finca:
            item["id_finca"] = t.finca.id_finca
            item["finca_nombre"] = t.finca.nombre_finca
            item["ubicacion_municipio"] = t.finca.ubicacion_municipio or "Colombia"
            item["departamento"] = t.finca.departamento or ""
            item["hectareas"] = float(t.finca.hectareas or 10.0)
            item["latitud"] = float(t.finca.latitud) if t.finca.latitud is not None else None
            item["longitud"] = float(t.finca.longitud) if t.finca.longitud is not None else None
            from app.shared.utils.maps_helper import parse_and_normalize_maps
            f_maps = (getattr(t.finca, 'maps_url', None) or '').strip()
            if not f_maps:
                m_url = re.search(r'https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|www\.google\.com/maps|maps\.google\.com)[^\s\n\r"\'<>\]\)]+', obs_text)
                if m_url:
                    f_maps = m_url.group(0).strip()
                else:
                    m_coord = re.search(r'[-+]?\d{1,3}\.\d+[,\s]+[-+]?\d{1,3}\.\d+', obs_text)
                    if m_coord:
                        f_maps = m_coord.group(0).strip()

            norm_url, _, _ = parse_and_normalize_maps(f_maps)

            if not norm_url and t.finca.latitud is not None and t.finca.longitud is not None:
                is_dummy_yopal = abs(float(t.finca.latitud) - 5.337750) < 0.001 and abs(float(t.finca.longitud) - (-72.395870)) < 0.001
                mun_is_yopal = str(t.finca.ubicacion_municipio or '').strip().lower() == 'yopal'
                if not (is_dummy_yopal and not mun_is_yopal):
                    norm_url = f"https://www.google.com/maps?q={float(t.finca.latitud):.6f},{float(t.finca.longitud):.6f}"

            item["maps_url"] = norm_url or ""

            if t.finca.latitud is not None and t.finca.longitud is not None:
                item["coordenadas"] = f"{t.finca.latitud}, {t.finca.longitud}"
            elif dir_real and dir_real != "N/A":
                item["coordenadas"] = f"{dir_real} ({t.finca.ubicacion_municipio or ''} {t.finca.departamento or ''})".strip()
            else:
                loc_parts = [vereda_real, t.finca.ubicacion_municipio, t.finca.departamento]
                item["coordenadas"] = ", ".join([p for p in loc_parts if p]) or "Colombia"

            if t.finca.cliente:
                c = t.finca.cliente
                item["id_cliente"] = c.id_cliente
                apellidos = f"{c.apellido_1 or ''} {c.apellido_2 or ''}".strip()
                item["cliente_nombre"] = f"{c.nombre} {apellidos}".strip()
                item["cliente_telefono"] = c.telefono or ""
                item["cliente_cedula"] = c.numero_documento or ""
                item["cliente_verificado"] = bool(c.verificado)
                item["verificado"] = bool(c.verificado)
                if c.usuario:
                    item["cliente_email"] = c.usuario.email
                else:
                    item["cliente_email"] = ""
            else:
                item["id_cliente"] = None
                item["cliente_nombre"] = "Sin cliente asociado"
                item["cliente_telefono"] = ""
                item["cliente_email"] = ""
                item["cliente_cedula"] = ""
                item["cliente_verificado"] = False
                item["verificado"] = False
        else:
            item["id_finca"] = None
            item["finca_nombre"] = "Finca no asignada"
            item["ubicacion_municipio"] = "Colombia"
            item["departamento"] = ""
            item["hectareas"] = 10.0
            item["latitud"] = None
            item["longitud"] = None
            item["coordenadas"] = "Colombia"
            item["maps_url"] = ""
            item["id_cliente"] = None
            item["cliente_nombre"] = "Sin cliente asociado"
            item["cliente_telefono"] = ""
            item["cliente_email"] = ""
            item["cliente_cedula"] = ""

        m_svcs = re.search(r'\[Servicios:\s*([^\]]+)\]', obs_text, re.IGNORECASE)
        if m_svcs:
            svcs_raw = m_svcs.group(1).strip()
            item["servicio_nombre"] = svcs_raw
            item["servicios_list"] = [s.strip() for s in svcs_raw.split("+") if s.strip()]
        elif t.servicio:
            item["servicio_nombre"] = t.servicio.nombre_servicio
            item["servicios_list"] = [t.servicio.nombre_servicio]
        else:
            item["servicio_nombre"] = "Vuelo Agrícola"
            item["servicios_list"] = ["Vuelo Agrícola"]
        item["servicio_descripcion"] = t.servicio.descripcion if t.servicio else ""

        if t.drone:
            item["dron_nombre"] = f"{t.drone.modelo} (Serie: {t.drone.numero_serie or 'N/A'})"
        else:
            from app.infrastructure.database.models.models import DroneModel
            tec_drone = db.query(DroneModel).filter(DroneModel.id_tecnico_asignado == t.id_tecnico).first() if t.id_tecnico else None
            if tec_drone:
                item["dron_nombre"] = f"{tec_drone.modelo} (Serie: {tec_drone.numero_serie or 'N/A'}) [Asignado]"
            else:
                item["dron_nombre"] = None

        if t.tecnico:
            item["tecnico_nombre"] = f"{t.tecnico.nombre} {t.tecnico.apellido_1 or ''}".strip()
            item["tecnico_telefono"] = t.tecnico.telefono or ""
        else:
            item["tecnico_nombre"] = "Piloto Principal Flymetrics"
            item["tecnico_telefono"] = ""

        url_ent = ""
        if t.entregables:
            for e in t.entregables:
                if e.url_archivo:
                    url_ent = e.url_archivo
                    break
        if not url_ent and t.finca and t.finca.cliente and t.finca.cliente.link_sharepoint:
            url_ent = t.finca.cliente.link_sharepoint

        item["url_entregable"] = url_ent or ""
        item["sharepoint_url"] = url_ent or ""
        item["link_sharepoint"] = url_ent or ""
        item["tiene_sharepoint"] = bool(url_ent)

        data.append(item)

    return success_response(message="Agenda del técnico obtenida exitosamente", data=data)

@tecnico_ops_router.patch("/tecnico/agenda/{id_turno}/decision")
def registrar_decision(
    id_turno: int,
    request: schemas.AgendaDecisionRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(tecnico_required)
):
    """El técnico confirma (true) o rechaza (false) un turno asignado. Requiere justificación al rechazar."""
    turno = BitacoraUseCases.registrar_decision(db, id_turno, request, current_user)
    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(message=f"Decisión registrada. Estado del turno: {turno.estado}", data=data)

@tecnico_ops_router.patch("/tecnico/agenda/{id_turno}/checkin")
def checkin(
    id_turno: int,
    request: schemas.CheckinRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(tecnico_required)
):
    """El técnico registra la hora de llegada al terreno. Estado del turno -> 'En Proceso'."""
    turno = BitacoraUseCases.checkin(db, id_turno, request, current_user)
    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(message="Check-in registrado. Turno en proceso.", data=data)

@tecnico_ops_router.patch("/tecnico/agenda/{id_turno}/checkout")
def checkout(
    id_turno: int,
    request: schemas.CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(tecnico_required)
):
    """El técnico cierra el turno y llena el reporte RAC 100 de la Aerocivil. Crea registro en tabla_reportes_vuelo."""
    reporte = BitacoraUseCases.checkout(db, id_turno, request, current_user)
    data = schemas.ReporteVueloResponse.model_validate(reporte).model_dump()
    return success_response(message="Checkout registrado y bitácora guardada. Turno completado.", data=data)

@tecnico_ops_router.patch("/tecnico/agenda/{id_turno}/completar")
def completar_turno_directo(
    id_turno: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(tecnico_required)
):
    """Marca directamente el turno como Completado y despacha notificación al cliente de forma asíncrona."""
    from datetime import datetime
    from app.infrastructure.database.models.models import AgendaModel
    from app.shared.utils.email_service import EmailService
    from app.shared.exceptions.exceptions import NotFoundException
    import threading

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise NotFoundException(f"Turno #{id_turno} no encontrado")

    hora_fin_real = datetime.now().time()
    turno.hora_fin_real = hora_fin_real
    turno.estado = "Completado"
    db.commit()
    db.refresh(turno)

    finca = turno.finca
    cli = finca.cliente if finca else None
    dest_email = cli.usuario.email if (cli and cli.usuario and cli.usuario.email) else None
    cli_nom = f"{cli.nombre} {cli.apellido_1 or ''}".strip() if cli else "Cliente"
    serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola"
    finca_nom = finca.nombre_finca if finca else "Predio Registrado"
    tec_nom = f"{turno.tecnico.nombre}".strip() if turno.tecnico else "Piloto Flymetrics Certificado"

    def _async_notify():
        try:
            EmailService.send_admin_service_completed(
                id_turno=turno.id_turno,
                cliente_nombre=cli_nom,
                servicio=serv_nom,
                finca=finca_nom,
                tecnico_nombre=tec_nom,
                fecha=str(turno.fecha_de_turno),
                hora_fin=str(turno.hora_fin_real or '')[:5]
            )
            if dest_email:
                EmailService.send_service_completed(
                    to_email=dest_email,
                    nombre_cliente=cli_nom,
                    id_turno=turno.id_turno,
                    servicio=serv_nom,
                    finca=finca_nom,
                    tecnico=tec_nom,
                    hora_finalizacion=str(turno.hora_fin_real or '')[:5],
                    fecha=str(turno.fecha_de_turno)
                )
        except Exception as e:
            print(f"[ASYNC NOTIFY ERROR] {e}")

    threading.Thread(target=_async_notify, daemon=True).start()

    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(message="Turno marcado como Completado exitosamente.", data=data)


