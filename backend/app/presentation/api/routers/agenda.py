from fastapi import APIRouter, Depends, status, Query, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import date, datetime
from app.infrastructure.database.session import get_db
from app.infrastructure.config.settings import settings
from app.application.dto import schemas
from app.application.use_cases.use_cases import AgendaUseCases
from app.presentation.api.dependencies.auth import get_current_user, RoleChecker
from app.infrastructure.database.models.models import UsuarioModel, AgendaModel
from app.shared.responses.response import success_response

router = APIRouter(prefix="/agenda", tags=["Agendamiento y Reservas"])


def _build_demo_accept_token(turno_id: int) -> str:
    import hashlib
    import hmac
    secret = getattr(settings, "SECRET_KEY", None) or getattr(settings, "JWT_SECRET", None) or "flymetrics_super_secret_key_2025_prod_local_key_hash"
    return hmac.new(secret.encode("utf-8"), f"demo:{turno_id}".encode("utf-8"), hashlib.sha256).hexdigest()


def _build_demo_accept_url(turno_id: int) -> str:
    base_url = getattr(settings, "PORTAL_CLIENTE_URL", "http://localhost:3000")
    clean_base = base_url.rstrip("/")
    return f"{clean_base}/api/v1/agenda/aceptar/{turno_id}/{_build_demo_accept_token(turno_id)}"

# Dependencias de roles
cliente_or_admin = RoleChecker(["cliente", "administrador"])
admin_required = RoleChecker(["administrador"])

def _dispatch_email_async(fn, *args, **kwargs):
    """Ejecuta el despacho de correos en segundo plano de forma no bloqueante."""
    import threading
    def _run():
        try:
            fn(*args, **kwargs)
        except Exception as _err:
            print(f"[ASYNC EMAIL DISPATCH ERROR] {_err}")
    threading.Thread(target=_run, daemon=True).start()


@router.get("/lookup-cliente", status_code=status.HTTP_200_OK)
def lookup_cliente_por_documento(
    documento: str = Query(None, description="Número de documento o NIT del cliente"),
    finca: str = Query(None, description="Nombre del predio o finca"),
    db: Session = Depends(get_db)
):
    """
    Busca si existe un cliente registrado por su documento o cédula/NIT, o si una finca ya tuvo demo previa.
    Retorna sus datos de contacto y sus fincas registradas para autocompletar el formulario de agendamiento.
    """
    from app.infrastructure.database.models.models import ClienteModel, UsuarioModel, FincaModel
    import re
    
    clean_doc = re.sub(r'\D', '', documento or '') if documento else ''
    
    cliente = None
    if clean_doc or (documento and documento.strip()):
        # Buscar por documento en ClienteModel
        cliente = db.query(ClienteModel).filter(
            (ClienteModel.numero_documento == clean_doc) | 
            (ClienteModel.numero_documento == (documento or '').strip())
        ).first()

        if not cliente and len(clean_doc) >= 7:
            # Intentar buscar por teléfono si el documento coincide con un teléfono registrado
            cliente = db.query(ClienteModel).filter(ClienteModel.telefono == clean_doc).first()

    # Verificar si el cliente ya utilizó su demostración gratuita previa
    ya_tuvo_demo = False
    fincas_list = []
    full_name = ""
    email = ""

    if cliente:
        full_name = f"{cliente.nombre} {cliente.apellido_1 or ''}".strip()
        if cliente.id_usuario:
            u = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == cliente.id_usuario).first()
            if u and u.email and not u.email.endswith("@flymetrics.co"):
                email = u.email

        fincas = db.query(FincaModel).filter(FincaModel.id_cliente == cliente.id_cliente).all()
        for f in fincas:
            fincas_list.append({
                "id_finca": f.id_finca,
                "nombre_finca": f.nombre_finca,
                "departamento": f.departamento or "",
                "municipio": f.ubicacion_municipio or getattr(f, "municipio", "") or "",
                "hectareas": float(f.hectareas) if f.hectareas else None,
                "maps_url": f.maps_url or ""
            })

        demo_turno = db.query(AgendaModel).join(FincaModel, AgendaModel.id_finca == FincaModel.id_finca).filter(
            FincaModel.id_cliente == cliente.id_cliente,
            (AgendaModel.es_demostracion == True) | (AgendaModel.tarifa == 0) | (AgendaModel.observaciones_servicio.ilike("%DEMOSTRACION%"))
        ).first()
        if demo_turno:
            ya_tuvo_demo = True

    # Verificar también si el predio / finca especificado ya tuvo demostración
    if finca and finca.strip() and not ya_tuvo_demo:
        demo_finca = db.query(AgendaModel).join(FincaModel, AgendaModel.id_finca == FincaModel.id_finca).filter(
            FincaModel.nombre_finca.ilike(finca.strip()),
            (AgendaModel.es_demostracion == True) | (AgendaModel.tarifa == 0) | (AgendaModel.observaciones_servicio.ilike("%DEMOSTRACION%"))
        ).first()
        if demo_finca:
            ya_tuvo_demo = True

    if not cliente and not ya_tuvo_demo:
        return success_response(
            message="No se encontró registro previo",
            data={"encontrado": False, "ya_tuvo_demo": False}
        )

    return success_response(
        message="Consulta realizada exitosamente",
        data={
            "encontrado": bool(cliente),
            "id_cliente": cliente.id_cliente if cliente else None,
            "nombre_completo": full_name,
            "telefono": cliente.telefono if cliente else "",
            "email": email,
            "numero_documento": cliente.numero_documento if cliente else (clean_doc or ""),
            "fincas": fincas_list,
            "ya_tuvo_demo": ya_tuvo_demo
        }
    )

@router.post("/reserva-rapida", status_code=status.HTTP_201_CREATED)
def crear_reserva_rapida_publica(request: schemas.ReservaRapidaCreate, db: Session = Depends(get_db)):
    """Endpoint público (sin autenticación previa) para agendamiento directo de vuelos agrícolas por parte de finqueros."""
    resultado = AgendaUseCases.crear_reserva_rapida(db, request)

    # Notificación por Correo Electrónico Asíncrona
    try:
        from app.shared.utils.email_service import EmailService
        if request.email and "@" in request.email:
            if resultado.get("es_demo_gratis", False):
                accept_url = _build_demo_accept_url(resultado.get("id_turno", 1))
                _dispatch_email_async(
                    EmailService.send_demo_gratuita_created,
                    to_email=request.email.strip().lower(),
                    nombre_cliente=request.nombre_completo.strip(),
                    id_turno=resultado.get("id_turno", 1),
                    servicio=resultado.get("servicio", "Análisis del Terreno"),
                    finca=request.nombre_finca or "Predio Registrado",
                    fecha=str(request.fecha_deseada),
                    hora="08:00 AM",
                    observaciones=request.observaciones,
                    aceptacion_url=accept_url
                )
            else:
                _dispatch_email_async(
                    EmailService.send_booking_created,
                    to_email=request.email.strip().lower(),
                    nombre_cliente=request.nombre_completo.strip(),
                    id_turno=resultado.get("id_turno", 1),
                    servicio=resultado.get("servicio", "Vuelo Agrícola"),
                    finca=request.nombre_finca or "Predio Registrado",
                    fecha=str(request.fecha_deseada),
                    hora="08:00 AM",
                    observaciones=request.observaciones
                )
        # Notificar a los administradores del sistema (1er correo al administrador)
        _dispatch_email_async(
            EmailService.send_admin_new_booking,
            id_turno=resultado.get("id_turno", 1),
            cliente_nombre=request.nombre_completo.strip(),
            servicio=resultado.get("servicio", "Vuelo Agrícola"),
            finca=request.nombre_finca or "Predio Registrado",
            fecha=str(request.fecha_deseada),
            hora="08:00 AM",
            observaciones=request.observaciones
        )
    except Exception as mail_err:
        print(f"[AGENDA RESERVA RAPIDA EMAIL ERROR] {mail_err}")

    return success_response(message=resultado["mensaje"], data=resultado, status_code=201)

@router.get("/aceptar/{id_turno}/{token}")
def aceptar_solicitud_demo(id_turno: int, token: str, db: Session = Depends(get_db)):
    """Acepta una demostración gratuita desde un enlace de correo único."""
    from app.infrastructure.database.models.models import AgendaModel
    import hmac

    expected = _build_demo_accept_token(id_turno)
    if not hmac.compare_digest(str(token), str(expected)):
        return RedirectResponse(url="/index.html?demo_error=token_invalido", status_code=302)

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        return RedirectResponse(url="/index.html?demo_error=turno_no_encontrado", status_code=302)

    if turno.estado == "Cancelado":
        return RedirectResponse(url=f"/index.html?demo_error=cancelado&id_turno={id_turno}", status_code=302)

    turno.estado = "Confirmado"
    if turno.tarifa is None:
        turno.tarifa = 0
    turno.observaciones_servicio = (turno.observaciones_servicio or "") + "\n- Aceptación por correo confirmada por el cliente."
    db.commit()
    db.refresh(turno)

    # Notificar al técnico asignado cuando la demostración fue agendada/confirmada por el cliente
    if turno.id_tecnico:
        from app.infrastructure.database.models.models import TecnicoModel
        from app.shared.utils.email_service import EmailService
        tec = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == turno.id_tecnico).first()
        if tec and (tec.email or (tec.usuario and tec.usuario.email)):
            tec_email = tec.email or tec.usuario.email
            finca_nom = turno.finca.nombre_finca if turno.finca else "Predio Registrado"
            serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Demostración Gratuita"
            cli = turno.finca.cliente if turno.finca else None
            cli_nom = f"{cli.nombre} {cli.apellido_1 or ''}".strip() if cli else "Cliente"
            muni_nom = (getattr(turno.finca, 'ubicacion_municipio', None) or getattr(turno.finca, 'municipio', None)) if turno.finca else "Ubicación registrada"
            dep_nom = getattr(turno.finca, 'departamento', "") or ""
            maps_nom = getattr(turno.finca, 'maps_url', None)
            ha_nom = float(turno.finca.hectareas) if (turno.finca and turno.finca.hectareas) else None

            # Extraer cultivo de observaciones si está presente
            import re
            cul_val = None
            if turno.observaciones_servicio:
                m_c = re.search(r'Cultivo(?: y Area)?:\s*([^\n\(\r]+)', turno.observaciones_servicio, re.IGNORECASE)
                if m_c:
                    cul_val = m_c.group(1).strip()
            if not cul_val:
                cul_val = "Demostración Agrícola" if turno.es_demostracion else "Misión Operativa"

            tar_val = float(turno.tarifa) if turno.tarifa is not None else (0.0 if turno.es_demostracion else None)

            _dispatch_email_async(
                EmailService.send_technician_assigned,
                to_email=tec_email.strip().lower(),
                tecnico_nombre=f"{tec.nombre} {tec.apellido_1 or ''}".strip(),
                id_turno=turno.id_turno,
                servicio=serv_nom,
                finca=finca_nom,
                municipio=muni_nom,
                fecha=str(turno.fecha_de_turno),
                hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                cliente_nombre=cli_nom,
                cliente_tel=cli.telefono if cli else None,
                observaciones=turno.observaciones_servicio,
                departamento=dep_nom,
                hectareas=ha_nom,
                cultivo=cul_val,
                maps_url=maps_nom,
                tarifa=tar_val
            )

    return RedirectResponse(url=f"/index.html?demo_aceptada=1&id_turno={id_turno}", status_code=302)


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/reservar", status_code=status.HTTP_201_CREATED)
def create_reserva(request: schemas.AgendaCreate, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(cliente_or_admin)):
    """Crea un turno de agendamiento (Cliente o Administrador)."""
    turno = AgendaUseCases.create_turno(db, request, current_user)
    data = schemas.AgendaResponse.model_validate(turno).model_dump()

    # Notificación por Correo Electrónico (Solo si es un turno nuevo y no duplicado)
    if not getattr(turno, '_is_duplicate', False):
        try:
            from app.shared.utils.email_service import EmailService
            finca_nom = turno.finca.nombre_finca if turno.finca else "Predio"
            import re
            obs_full = getattr(turno, "observaciones_servicio", None) or getattr(turno, "observaciones_del_cliente", None) or ""
            m_svc = re.search(r'\[Servicios:\s*([^\]]+)\]', obs_full, re.IGNORECASE)
            serv_nom = m_svc.group(1).strip() if m_svc else (turno.servicio.nombre_servicio if turno.servicio else "Vuelo con Dron")
            cli_nom = turno.finca.cliente.nombre if (turno.finca and turno.finca.cliente) else "Cliente"
            _dispatch_email_async(
                EmailService.send_booking_created,
                to_email=current_user.email,
                nombre_cliente=cli_nom,
                id_turno=turno.id_turno,
                servicio=serv_nom,
                finca=finca_nom,
                fecha=str(turno.fecha_de_turno),
                hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                observaciones=getattr(turno, "observaciones_servicio", None) or getattr(turno, "observaciones_del_cliente", None)
            )
            # Notificar a los administradores del sistema (1er correo al administrador)
            _dispatch_email_async(
                EmailService.send_admin_new_booking,
                id_turno=turno.id_turno,
                cliente_nombre=cli_nom,
                servicio=serv_nom,
                finca=finca_nom,
                fecha=str(turno.fecha_de_turno),
                hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                observaciones=getattr(turno, "observaciones_servicio", None) or getattr(turno, "observaciones_del_cliente", None)
            )
        except Exception as mail_err:
            print(f"[AGENDA CREATE EMAIL ERROR] {mail_err}")

    return success_response(message="Solicitud de reserva procesada exitosamente", data=data, status_code=201)

@router.get("/mis-turnos")
def get_mis_turnos(
    estado: str = Query(None, description="Filtrar por estado: Pendiente, Confirmado, En Proceso, Hecho, Cancelado"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(cliente_or_admin)
):
    """Retorna todos los turnos del cliente autenticado con nombres enriquecidos."""
    turnos = AgendaUseCases.list_mis_turnos(db, current_user, estado, page, limit)
    data = []
    for t in turnos:
        item = schemas.AgendaResponse.model_validate(t).model_dump()
        if t.finca:
            item["finca_nombre"] = t.finca.nombre_finca
            item["nombre_finca"] = t.finca.nombre_finca
            item["ubicacion_municipio"] = t.finca.ubicacion_municipio or ""
            item["departamento"] = t.finca.departamento or ""
            item["hectareas"] = float(t.finca.hectareas or 0)
            item["maps_url"] = t.finca.maps_url or ""
            item["latitud"] = float(t.finca.latitud) if t.finca.latitud is not None else None
            item["longitud"] = float(t.finca.longitud) if t.finca.longitud is not None else None
        else:
            item["finca_nombre"] = "Finca Registrada"
            item["nombre_finca"] = "Finca Registrada"
            item["ubicacion_municipio"] = ""
            item["departamento"] = ""
            item["hectareas"] = 0
            item["maps_url"] = ""
            item["latitud"] = None
            item["longitud"] = None
            
        obs_raw = t.observaciones_servicio or ""
        import re
        m_svc = re.search(r'\[Servicios:\s*([^\]]+)\]', obs_raw, re.IGNORECASE)
        if m_svc:
            item["servicio_nombre"] = m_svc.group(1).strip()
            item["nombre_servicio"] = m_svc.group(1).strip()
        elif t.servicio:
            item["servicio_nombre"] = t.servicio.nombre_servicio
            item["nombre_servicio"] = t.servicio.nombre_servicio
        else:
            item["servicio_nombre"] = "Servicio Dron"
            item["nombre_servicio"] = "Servicio Dron"
            
        if t.tecnico:
            item["tecnico_nombre"] = f"{t.tecnico.nombre} {t.tecnico.apellido_1 or ''}".strip()
            item["tecnico"] = f"{t.tecnico.nombre} {t.tecnico.apellido_1 or ''}".strip()
        else:
            item["tecnico_nombre"] = "Por asignar"
            item["tecnico"] = "Por asignar"

        item["sugerencia_cliente"] = t.sugerencia_cliente or ""
        item["token_confirmacion"] = t.token_confirmacion or ""
        item["historial_negociacion"] = t.historial_negociacion or ""
        item["es_demostracion"] = bool(t.es_demostracion)
        item["tarifa"] = float(t.tarifa) if t.tarifa is not None else None
            
        data.append(item)
    return success_response(message="Lista de turnos del cliente obtenida", data=data)

@router.get("/estado/{id_turno}")
def get_estado_publico(id_turno: int, db: Session = Depends(get_db)):
    """Consulta de estado pública para uso del chatbot de WhatsApp."""
    result = AgendaUseCases.get_estado_publico(db, id_turno)
    return success_response(message="Estado del turno obtenido", data=result)

@router.get("/{id_turno}")
def get_turno(id_turno: int, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Retorna el detalle completo de un turno (técnico asignado, dron, tiempos estimados y reales)."""
    turno = AgendaUseCases.get_by_id(db, id_turno, current_user)
    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(message="Detalle del turno obtenido exitosamente", data=data)

@router.delete("/{id_turno}")
def cancelar_turno(id_turno: int, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """El cliente cancela su reserva. Solo se permite en estado 'Pendiente' o 'Confirmado'."""
    from app.infrastructure.database.models.models import AgendaModel
    turno_prev = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    finca_nom = turno_prev.finca.nombre_finca if (turno_prev and turno_prev.finca) else "Predio"
    serv_nom = turno_prev.servicio.nombre_servicio if (turno_prev and turno_prev.servicio) else "Vuelo con Dron"
    cli_nom = turno_prev.finca.cliente.nombre if (turno_prev and turno_prev.finca and turno_prev.finca.cliente) else "Cliente"
    dest_email = current_user.email
    if turno_prev and turno_prev.finca and turno_prev.finca.cliente and turno_prev.finca.cliente.usuario:
        dest_email = turno_prev.finca.cliente.usuario.email or dest_email

    AgendaUseCases.cancelar_turno(db, id_turno, current_user)

    # Notificación por Correo Electrónico Asíncrona (Gmail API OAuth2 y Microsoft Outlook Calendar)
    try:
        from app.shared.utils.email_service import EmailService
        from app.infrastructure.database.models.models import TecnicoModel

        # 1. Al cliente
        _dispatch_email_async(
            EmailService.send_booking_cancelled,
            to_email=dest_email,
            nombre_cliente=cli_nom,
            id_turno=id_turno,
            servicio=serv_nom,
            finca=finca_nom,
            motivo="Cancelación solicitada por el usuario"
        )

        # 2. A todos los técnicos asignados (liberando evento de Microsoft Calendar)
        if turno_prev:
            pilotos_objs = []
            if turno_prev.id_tecnico:
                t1 = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == turno_prev.id_tecnico).first()
                if t1:
                    pilotos_objs.append(t1)
            if turno_prev.tecnicos_adicionales:
                for extra_id in str(turno_prev.tecnicos_adicionales).split(","):
                    if extra_id.strip().isdigit():
                        t_extra = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == int(extra_id.strip())).first()
                        if t_extra:
                            pilotos_objs.append(t_extra)

            muni_val = getattr(turno_prev.finca, 'ubicacion_municipio', None) or getattr(turno_prev.finca, 'municipio', None) if turno_prev.finca else "Colombia"
            dep_val = getattr(turno_prev.finca, 'departamento', "") if turno_prev.finca else ""
            f_str = str(turno_prev.fecha_de_turno) if turno_prev.fecha_de_turno else None
            h_str = str(turno_prev.hora_inicio_estimada or "08:00 AM")

            for p_obj in pilotos_objs:
                p_mail = getattr(p_obj, "email", None) or (p_obj.usuario.email if getattr(p_obj, "usuario", None) else None)
                if p_mail:
                    _dispatch_email_async(
                        EmailService.send_technician_cancelled,
                        to_email=p_mail.strip().lower(),
                        tecnico_nombre=f"{p_obj.nombre} {p_obj.apellido_1 or ''}".strip(),
                        id_turno=id_turno,
                        servicio=serv_nom,
                        finca=finca_nom,
                        motivo="El cliente ha cancelado la reservación",
                        municipio=muni_val,
                        departamento=dep_val,
                        fecha=f_str,
                        hora=h_str
                    )
    except Exception as mail_err:
        print(f"[AGENDA CANCEL EMAIL ERROR] {mail_err}")

    return success_response(message="Turno cancelado exitosamente")

@router.put("/{id_turno}")
@router.patch("/{id_turno}")
def update_turno(
    id_turno: int,
    request: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Actualiza la fecha de muestreo, estado u observaciones de un turno agendado."""
    from app.infrastructure.database.models.models import AgendaModel
    from app.shared.exceptions.exceptions import NotFoundException
    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise NotFoundException("Turno no encontrado")

    # Validación de propiedad para clientes (Previene IDOR)
    if current_user.rol == "cliente":
        if not (turno.finca and turno.finca.cliente and turno.finca.cliente.id_usuario == current_user.id_usuarios):
            from app.shared.exceptions.exceptions import ForbiddenException
            raise ForbiddenException("No tienes permiso para modificar este agendamiento.")

    # Regla de negocio: Un agendamiento completado, finalizado o cancelado no se puede modificar ni reagendar
    if turno.estado in ["Completado", "Finalizado", "Cancelado"]:
        from app.shared.exceptions.exceptions import BadRequestException
        raise BadRequestException(f"Este turno ya se encuentra {turno.estado.lower()} y no se puede modificar ni reagendar.")

    # Regla de negocio: Si el turno ya está Confirmado o En Proceso, se bloquea la modificación de datos
    # estructurales (finca, cliente, tarifa, hectáreas), pero SÍ se permite REAGENDAR (fecha, hora, motivo, estado).
    if turno.estado in ["Confirmado", "En Proceso"]:
        structural_fields = {"id_finca", "finca", "id_cliente", "cliente", "tarifa", "precio", "monto", "hectareas"}
        modifying_structural = any(f in request for f in structural_fields if request.get(f) is not None)
        if modifying_structural and str(current_user.rol).lower() not in ["administrador", "admin", "staff"]:
            from app.shared.exceptions.exceptions import BadRequestException
            raise BadRequestException("Este agendamiento ya ha sido confirmado y sus datos base están protegidos. Para cambiar la fecha u hora del vuelo, utiliza la opción Reagendar.")
    
    orig_fecha = turno.fecha_de_turno
    orig_hora = turno.hora_inicio_estimada
    orig_estado = turno.estado

    # 1. Fecha de turno / fecha
    new_fecha_val = request.get("fecha_de_turno") or request.get("fecha") or request.get("nueva_fecha")
    new_date = None
    if new_fecha_val:
        if isinstance(new_fecha_val, str):
            new_date = datetime.strptime(new_fecha_val.strip()[:10], "%Y-%m-%d").date()
        else:
            new_date = new_fecha_val
        if current_user.rol != "administrador" and new_date < date.today():
            from app.shared.exceptions.exceptions import BadRequestException
            raise BadRequestException("No es posible reprogramar un turno para fechas anteriores a hoy.")
        turno.fecha_de_turno = new_date

    # 2. Hora de inicio estimada / hora
    new_hora_val = request.get("hora_inicio_estimada") or request.get("hora") or request.get("nueva_hora")
    h_obj = None
    if new_hora_val:
        from datetime import time as time_cls, timedelta
        if isinstance(new_hora_val, str):
            parts = new_hora_val.strip().split(":")
            h_obj = time_cls(int(parts[0]), int(parts[1]))
        else:
            h_obj = new_hora_val
        turno.hora_inicio_estimada = h_obj

        # Recalcular hora_fin_estimada según hectáreas (máximo 4 horas por jornada de vuelo en un solo día)
        ha = float(turno.finca.hectareas or 10.0) if turno.finca else 10.0
        dur_horas = min(4.0, max(1.0, round(ha / 5.0, 1)))
        base_d = turno.fecha_de_turno or date.today()
        st_dt = datetime.combine(base_d, h_obj)
        end_dt = st_dt + timedelta(hours=dur_horas)
        turno.hora_fin_estimada = end_dt.time()

    # 3. Motivo de Reagendamiento (Campo independiente en BD)
    new_motivo = request.get("motivo_reagendamiento") or request.get("motivo") or request.get("motivo_cambio")
    if new_motivo is not None and str(new_motivo).strip():
        turno.motivo_reagendamiento = str(new_motivo).strip()

    # 4. Observaciones generales (solo si se envían explícitamente y no son vacías)
    new_obs = request.get("observaciones_servicio")
    if new_obs is not None and str(new_obs).strip():
        turno.observaciones_servicio = str(new_obs).strip()

    # 5. Estado y Detección de Reagendamiento
    new_estado = request.get("estado")
    est_lower = str(new_estado or "").strip().lower()

    fecha_changed = (new_date is not None and orig_fecha is not None and new_date != orig_fecha)
    hora_changed = (h_obj is not None and orig_hora is not None and (h_obj.hour, h_obj.minute) != (orig_hora.hour, orig_hora.minute))
    is_reschedule = (est_lower == "reagendado") or fecha_changed or hora_changed or bool(new_motivo and str(new_motivo).strip())

    if new_estado:
        turno.estado = str(new_estado).strip()
    elif is_reschedule:
        turno.estado = "Reagendado"

    # 6. Recursos y llaves foráneas
    if "id_finca" in request and request["id_finca"]:
        turno.id_finca = int(request["id_finca"])
    if "id_servicio" in request and request["id_servicio"]:
        turno.id_servicio = int(request["id_servicio"])
    if "tecnicos_ids" in request and request["tecnicos_ids"]:
        t_ids = request["tecnicos_ids"]
        if isinstance(t_ids, list) and len(t_ids) > 0:
            turno.id_tecnico = int(t_ids[0])
            turno.tecnicos_adicionales = ",".join(str(x) for x in t_ids[1:]) if len(t_ids) > 1 else None
    elif "id_tecnico" in request:
        turno.id_tecnico = int(request["id_tecnico"]) if request["id_tecnico"] else None
    if "tecnicos_adicionales" in request:
        turno.tecnicos_adicionales = request["tecnicos_adicionales"]

    if "id_drone" in request:
        turno.id_drone = int(request["id_drone"]) if request["id_drone"] else None
    if "hectareas" in request and request["hectareas"] and turno.finca:
        try:
            turno.finca.hectareas = float(request["hectareas"])
        except Exception:
            pass
    if "maps_url" in request and request["maps_url"] and turno.finca:
        from app.shared.utils.maps_helper import parse_and_normalize_maps
        clean_maps = str(request["maps_url"]).strip()
        norm_url, lat_f, lng_f = parse_and_normalize_maps(clean_maps)
        if norm_url:
            turno.finca.maps_url = norm_url
            if lat_f is not None and lng_f is not None:
                from decimal import Decimal
                turno.finca.latitud = Decimal(str(lat_f))
                turno.finca.longitud = Decimal(str(lng_f))
        else:
            turno.finca.maps_url = clean_maps.rstrip('])>,.;:\'\"')

    if "cultivo" in request and request["cultivo"] and str(request["cultivo"]).strip():
        new_cul = str(request["cultivo"]).strip()
        curr_obs = turno.observaciones_servicio or ""
        import re
        if re.search(r'Cultivo:\s*[^\n\r]+', curr_obs, re.IGNORECASE):
            curr_obs = re.sub(r'Cultivo:\s*[^\n\r]+', f'Cultivo: {new_cul}', curr_obs, flags=re.IGNORECASE)
        else:
            curr_obs = f"Cultivo: {new_cul}\n{curr_obs}".strip()
        turno.observaciones_servicio = curr_obs

    # Multi-service persistence
    if "servicios_nombres" in request and request["servicios_nombres"]:
        svcs_str = request["servicios_nombres"] if isinstance(request["servicios_nombres"], str) else " + ".join(str(s) for s in request["servicios_nombres"])
        import re
        curr_obs = turno.observaciones_servicio or ""
        if "[Servicios:" in curr_obs:
            curr_obs = re.sub(r'\[Servicios:\s*[^\]]+\]', f'[Servicios: {svcs_str}]', curr_obs)
        else:
            curr_obs = f"[Servicios: {svcs_str}] {curr_obs}".strip()
        turno.observaciones_servicio = curr_obs
    
    db.commit()
    db.refresh(turno)

    # Notificaciones Automáticas Asíncronas por Correo Electrónico
    try:
        from app.shared.utils.email_service import EmailService
        from app.infrastructure.database.models.models import TecnicoModel
        finca_nom = turno.finca.nombre_finca if turno.finca else "Predio"
        serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo con Dron"
        cli_nom = f"{turno.finca.cliente.nombre} {turno.finca.cliente.apellido_1 or ''}".strip() if (turno.finca and turno.finca.cliente) else "Cliente"
        dron_mod = turno.drone.modelo if turno.drone else "DJI AGRAS T40"
        dest_email = current_user.email
        if turno.finca and turno.finca.cliente and turno.finca.cliente.usuario:
            dest_email = turno.finca.cliente.usuario.email or dest_email

        # Recopilar todos los pilotos asignados (principal + adicionales)
        pilotos_nombres = []
        pilotos_objs = []
        if turno.id_tecnico:
            t1 = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == turno.id_tecnico).first()
            if t1:
                pilotos_objs.append(t1)
                pilotos_nombres.append(f"{t1.nombre} {t1.apellido_1 or ''}".strip())
        if turno.tecnicos_adicionales:
            for extra_id in str(turno.tecnicos_adicionales).split(","):
                if extra_id.strip().isdigit():
                    t_extra = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == int(extra_id.strip())).first()
                    if t_extra:
                        pilotos_objs.append(t_extra)
                        pilotos_nombres.append(f"{t_extra.nombre} {t_extra.apellido_1 or ''}".strip())
        tec_nom = ", ".join(pilotos_nombres) if pilotos_nombres else "Piloto asignado por despacho"

        current_est_lower = str(turno.estado or "").strip().lower()

        if current_est_lower == "cancelado" or est_lower == "cancelado":
            # 1. Al cliente
            _dispatch_email_async(
                EmailService.send_booking_cancelled,
                to_email=dest_email,
                nombre_cliente=cli_nom,
                id_turno=turno.id_turno,
                servicio=serv_nom,
                finca=finca_nom,
                motivo=turno.motivo_reagendamiento or "Cancelación de reserva"
            )
            # 2. A todos los técnicos asignados (con eliminación/cancelación en su calendario Microsoft)
            muni_val = getattr(turno.finca, 'ubicacion_municipio', None) or getattr(turno.finca, 'municipio', None) or "Ubicación Registrada"
            dep_val = getattr(turno.finca, 'departamento', "") or ""
            for p_obj in pilotos_objs:
                p_mail = getattr(p_obj, "email", None) or (p_obj.usuario.email if getattr(p_obj, "usuario", None) else None)
                if p_mail:
                    _dispatch_email_async(
                        EmailService.send_technician_cancelled,
                        to_email=p_mail.strip().lower(),
                        tecnico_nombre=f"{p_obj.nombre} {p_obj.apellido_1 or ''}".strip(),
                        id_turno=turno.id_turno,
                        servicio=serv_nom,
                        finca=finca_nom,
                        motivo=turno.motivo_reagendamiento or "Misión cancelada desde administración",
                        municipio=muni_val,
                        departamento=dep_val,
                        fecha=str(turno.fecha_de_turno),
                        hora=str(turno.hora_inicio_estimada or "08:00 AM")
                    )
        elif is_reschedule:
            # 1. Al cliente
            _dispatch_email_async(
                EmailService.send_booking_rescheduled,
                to_email=dest_email,
                nombre_cliente=cli_nom,
                id_turno=turno.id_turno,
                servicio=serv_nom,
                finca=finca_nom,
                nueva_fecha=str(turno.fecha_de_turno),
                nueva_hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                motivo=turno.motivo_reagendamiento or "Ajuste operacional de agenda"
            )
            # 2. A los administradores (2do correo a admin)
            _dispatch_email_async(
                EmailService.send_admin_rescheduled,
                id_turno=turno.id_turno,
                cliente_nombre=cli_nom,
                servicio=serv_nom,
                finca=finca_nom,
                nueva_fecha=str(turno.fecha_de_turno),
                nueva_hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                fecha_antigua=str(orig_fecha) if orig_fecha else None,
                motivo=turno.motivo_reagendamiento
            )
            # 3. A todos los técnicos asignados (2do correo al técnico con Microsoft Calendar Sync)
            muni_val = getattr(turno.finca, 'ubicacion_municipio', None) or getattr(turno.finca, 'municipio', None) or "Ubicación Registrada"
            dep_val = getattr(turno.finca, 'departamento', "") or ""
            maps_val = getattr(turno.finca, 'maps_url', None)
            ha_val = float(turno.finca.hectareas) if (turno.finca and turno.finca.hectareas) else None

            for p_obj in pilotos_objs:
                if p_obj.email:
                    _dispatch_email_async(
                        EmailService.send_technician_rescheduled,
                        to_email=p_obj.email.strip().lower(),
                        tecnico_nombre=f"{p_obj.nombre} {p_obj.apellido_1 or ''}".strip(),
                        id_turno=turno.id_turno,
                        servicio=serv_nom,
                        finca=finca_nom,
                        nueva_fecha=str(turno.fecha_de_turno),
                        nueva_hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                        fecha_antigua=str(orig_fecha) if orig_fecha else None,
                        motivo=turno.motivo_reagendamiento,
                        municipio=muni_val,
                        departamento=dep_val,
                        cliente_nombre=cli_nom,
                        cliente_tel=turno.finca.cliente.telefono if (turno.finca and turno.finca.cliente) else None,
                        hectareas=ha_val,
                        maps_url=maps_val,
                        tarifa=float(turno.tarifa or 0.0) if turno.tarifa else None
                    )
        elif current_est_lower in ["hecho", "completado"] or est_lower in ["hecho", "completado"]:
            # Notificar a los administradores del sistema (3er correo al administrador)
            _dispatch_email_async(
                EmailService.send_admin_service_completed,
                id_turno=turno.id_turno,
                cliente_nombre=cli_nom,
                servicio=serv_nom,
                finca=finca_nom,
                tecnico_nombre=tec_nom,
                fecha=str(turno.fecha_de_turno),
                hora_fin=str(turno.hora_fin_real or "17:00")[:5]
            )
            # Notificar al cliente
            if dest_email:
                _dispatch_email_async(
                    EmailService.send_service_completed,
                    to_email=dest_email,
                    nombre_cliente=cli_nom,
                    id_turno=turno.id_turno,
                    servicio=serv_nom,
                    finca=finca_nom,
                    tecnico=tec_nom,
                    hora_finalizacion=str(turno.hora_fin_real or "17:00")[:5],
                    fecha=str(turno.fecha_de_turno)
                )
        elif (current_est_lower == "confirmado" or est_lower == "confirmado") and orig_estado != "Confirmado":
            # 1. Al cliente con nombres de pilotos confirmados
            _dispatch_email_async(
                EmailService.send_booking_confirmed,
                to_email=dest_email,
                nombre_cliente=cli_nom,
                id_turno=turno.id_turno,
                servicio=serv_nom,
                finca=finca_nom,
                fecha=str(turno.fecha_de_turno),
                hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                tecnico_nombre=tec_nom,
                dron_modelo=dron_mod
            )
            # 2. A los técnicos asignados SOLO cuando el servicio fue agendado/confirmado por el cliente
            if current_user.rol == "cliente":
                muni_nom = (getattr(turno.finca, 'ubicacion_municipio', None) or getattr(turno.finca, 'municipio', None)) if turno.finca else "Ubicación registrada"
                dep_nom = getattr(turno.finca, 'departamento', "") or ""
                maps_nom = getattr(turno.finca, 'maps_url', None)
                ha_nom = float(turno.finca.hectareas) if (turno.finca and turno.finca.hectareas) else None
                cli_tel = turno.finca.cliente.telefono if (turno.finca and turno.finca.cliente) else None
                # Extraer cultivo de observaciones si está presente
                import re
                cul_val = None
                if turno.observaciones_servicio:
                    m_c = re.search(r'Cultivo(?: y Area)?:\s*([^\n\(\r]+)', turno.observaciones_servicio, re.IGNORECASE)
                    if m_c:
                        cul_val = m_c.group(1).strip()
                if not cul_val:
                    cul_val = "Demostración Agrícola" if turno.es_demostracion else "Misión Operativa"

                tar_val = float(turno.tarifa) if turno.tarifa is not None else (0.0 if turno.es_demostracion else None)

                for p_obj in pilotos_objs:
                    if p_obj.email:
                        _dispatch_email_async(
                            EmailService.send_technician_assigned,
                            to_email=p_obj.email.strip().lower(),
                            tecnico_nombre=f"{p_obj.nombre} {p_obj.apellido_1 or ''}".strip(),
                            id_turno=turno.id_turno,
                            servicio=serv_nom,
                            finca=finca_nom,
                            municipio=muni_nom,
                            fecha=str(turno.fecha_de_turno),
                            hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                            cliente_nombre=cli_nom,
                            cliente_tel=cli_tel,
                            observaciones=turno.observaciones_servicio,
                            departamento=dep_nom,
                            hectareas=ha_nom,
                            cultivo=cul_val,
                            maps_url=maps_nom,
                            tarifa=tar_val
                        )
    except Exception as mail_err:
        print(f"[AGENDA UPDATE EMAIL DISPATCH ERROR] {mail_err}")

    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(message="Turno actualizado exitosamente", data=data)


@router.get("")
@router.get("/", include_in_schema=False)
def list_agenda_alias(
    estado: str = Query(None),
    id_tecnico: int = Query(None),
    fecha: date = Query(None),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Alias para listar turnos de agenda sin error 404."""
    if current_user.rol == "cliente":
        turnos = AgendaUseCases.list_mis_turnos(db, current_user, estado)
    else:
        turnos = AgendaUseCases.list_all_admin(db, estado, id_tecnico, fecha)
        
    data = []
    for t in turnos:
        item = schemas.AgendaResponse.model_validate(t).model_dump()
        if t.finca:
            item["nombre_finca"] = t.finca.nombre_finca
        if t.servicio:
            item["nombre_servicio"] = t.servicio.nombre_servicio
        if t.tecnico:
            item["tecnico"] = f"{t.tecnico.nombre} {t.tecnico.apellido_1 or ''}".strip()
        url_ent = getattr(t, 'url_entregable_drive', None) or ""
        if not url_ent and t.entregables:
            for e in t.entregables:
                if e.url_archivo:
                    url_ent = e.url_archivo
                    break
        if not url_ent and t.finca and t.finca.cliente and t.finca.cliente.link_sharepoint:
            url_ent = t.finca.cliente.link_sharepoint
        item["url_entregable"] = url_ent or ""
        item["url_entregable_drive"] = url_ent or ""
        item["sharepoint_url"] = url_ent or ""
        item["link_sharepoint"] = url_ent or ""
        item["tiene_sharepoint"] = bool(url_ent)
        data.append(item)
    return success_response(message="Lista de turnos obtenida", data=data)

# ==========================================
# RUTAS DE ADMINISTRADOR PARA AGENDA
# ==========================================

# Definimos las rutas de administrador de la agenda aquí
admin_router = APIRouter(prefix="/admin/agenda", tags=["Administración de Agenda"])

@admin_router.get("")
@admin_router.get("/", include_in_schema=False)
def admin_list_agenda(
    estado: str = Query(None),
    id_tecnico: int = Query(None),
    fecha: date = Query(None),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Vista completa de todos los turnos del sistema con nombres. Solo administrador."""
    turnos = AgendaUseCases.list_all_admin(db, estado, id_tecnico, fecha)
    data = []
    for t in turnos:
        item = schemas.AgendaResponse.model_validate(t).model_dump()
        # Enrich with names, email, phone and farm details
        obs_raw = t.observaciones_servicio or ""
        import re

        if t.finca:
            item["finca_nombre"] = t.finca.nombre_finca
            item["hectareas"] = float(t.finca.hectareas) if t.finca.hectareas else 0.0
            item["ubicacion_municipio"] = t.finca.ubicacion_municipio or ""
            item["departamento"] = t.finca.departamento or ""
            item["responsable_campo"] = t.finca.responsable_campo or ""
            item["telefono_admin"] = t.finca.telefono_admin or ""
            
            # Resolver link de google maps
            from app.shared.utils.maps_helper import parse_and_normalize_maps
            f_maps = (getattr(t.finca, 'maps_url', None) or '').strip()
            if not f_maps:
                m_url = re.search(r'https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|www\.google\.com/maps|maps\.google\.com)[^\s\n\r"\'<>\]\)]+', obs_raw)
                if m_url:
                    f_maps = m_url.group(0).strip()
                else:
                    m_coord = re.search(r'[-+]?\d{1,3}\.\d+[,\s]+[-+]?\d{1,3}\.\d+', obs_raw)
                    if m_coord:
                        f_maps = m_coord.group(0).strip()

            norm_url, _, _ = parse_and_normalize_maps(f_maps)

            if not norm_url and t.finca.latitud is not None and t.finca.longitud is not None:
                is_dummy_yopal = abs(float(t.finca.latitud) - 5.337750) < 0.001 and abs(float(t.finca.longitud) - (-72.395870)) < 0.001
                mun_is_yopal = str(t.finca.ubicacion_municipio or '').strip().lower() == 'yopal'
                if not (is_dummy_yopal and not mun_is_yopal):
                    norm_url = f"https://www.google.com/maps?q={float(t.finca.latitud):.6f},{float(t.finca.longitud):.6f}"

            item["maps_url"] = norm_url or ""

            if t.finca.cliente:
                c = t.finca.cliente
                item["cliente_nombre"] = f"{c.nombre} {c.apellido_1 or ''}".strip()
                item["cliente_telefono"] = c.telefono or t.cel or ""
                item["cel"] = c.telefono or t.cel or ""
                item["cliente_email"] = c.usuario.email if (c.usuario and c.usuario.email) else ""
                item["numero_documento"] = c.numero_documento or "Sin registrar"
                item["cliente_documento"] = c.numero_documento or "Sin registrar"
                item["verificado"] = bool(c.verificado)
                item["cliente_verificado"] = bool(c.verificado)

                # Clasificación Persona Jurídica o Natural
                doc_str = str(c.numero_documento or "").strip()
                nom_upper = str(c.nombre or "").upper()
                is_juridica = "-" in doc_str or (doc_str.isdigit() and len(doc_str) >= 9 and doc_str.startswith(("8", "9"))) or any(w in nom_upper for w in ["SAS", "S.A.S", "S.A", "LTDA", "AGRO", "HACIENDA", "FINCA", "INVERSIONES", "CORP", "SOCIEDAD"])
                item["tipo_persona"] = "Persona Jurídica (NIT)" if is_juridica else "Persona Natural (Cédula CC)"
                item["cliente_tipo_persona"] = item["tipo_persona"]
            else:
                item["cliente_nombre"] = ""
                item["cliente_telefono"] = t.cel or ""
                item["cliente_email"] = ""
                item["cliente_documento"] = "Sin registrar"
                item["cliente_verificado"] = False
                item["cliente_tipo_persona"] = "Persona Natural"
        else:
            item["finca_nombre"] = ""
            item["cliente_nombre"] = ""
            item["cliente_email"] = ""
            item["cliente_telefono"] = t.cel or ""
            item["cliente_documento"] = "Sin registrar"
            item["cliente_verificado"] = False
            item["cliente_tipo_persona"] = "Persona Natural"
            item["hectareas"] = 0.0
            item["maps_url"] = ""

        # Cultivo
        m_cul = re.search(r'(?:Cultivo y Area|Cultivo):\s*([^\(\n\r]+)', obs_raw, re.IGNORECASE)
        item["cultivo"] = m_cul.group(1).strip() if m_cul else "Agrícola General"

        # Multi-service name resolver
        m_svc = re.search(r'\[Servicios:\s*([^\]]+)\]', obs_raw, re.IGNORECASE)
        if m_svc:
            svcs_raw = m_svc.group(1).strip()
            item["servicio_nombre"] = svcs_raw
            item["servicios_list"] = [s.strip() for s in svcs_raw.split("+") if s.strip()]
        elif t.servicio:
            item["servicio_nombre"] = t.servicio.nombre_servicio
            item["servicios_list"] = [t.servicio.nombre_servicio]
        else:
            item["servicio_nombre"] = "Servicio Dron"
            item["servicios_list"] = ["Servicio Dron"]

        # Dron
        if t.drone:
            item["dron_nombre"] = f"{t.drone.modelo} (Serie: {t.drone.numero_serie or 'N/A'})"
        else:
            from app.infrastructure.database.models.models import DroneModel
            tec_drone = db.query(DroneModel).filter(DroneModel.id_tecnico_asignado == t.id_tecnico).first() if t.id_tecnico else None
            if tec_drone:
                item["dron_nombre"] = f"{tec_drone.modelo} (Serie: {tec_drone.numero_serie or 'N/A'})"
            else:
                item["dron_nombre"] = None

        if t.tecnico:
            item["tecnico_nombre"] = f"{t.tecnico.nombre} {t.tecnico.apellido_1 or ''}".strip()
            item["tecnico_telefono"] = t.tecnico.telefono or ""
        else:
            item["tecnico_nombre"] = ""
            item["tecnico_telefono"] = ""
        # Detección robusta de demostración gratuita
        is_demo_flag = bool(t.es_demostracion) or "demostracion" in obs_raw.lower() or "sin costo" in obs_raw.lower() or "demo" in str(item.get("servicio_nombre", "")).lower()
        item["es_demostracion"] = is_demo_flag
        if is_demo_flag:
            item["tarifa"] = 0.0
        else:
            item["tarifa"] = float(t.tarifa) if t.tarifa is not None else None
        item["sugerencia_cliente"] = t.sugerencia_cliente or ""
        item["token_confirmacion"] = t.token_confirmacion or ""
        item["historial_negociacion"] = t.historial_negociacion or ""

        # SharePoint y Entregables vinculados
        url_ent = getattr(t, 'url_entregable_drive', None) or ""
        if not url_ent and t.entregables:
            for e in t.entregables:
                if e.url_archivo:
                    url_ent = e.url_archivo
                    break
        if not url_ent and t.finca and t.finca.cliente and t.finca.cliente.link_sharepoint:
            url_ent = t.finca.cliente.link_sharepoint

        item["url_entregable"] = url_ent or ""
        item["url_entregable_drive"] = url_ent or ""
        item["sharepoint_url"] = url_ent or ""
        item["link_sharepoint"] = url_ent or ""
        item["tiene_sharepoint"] = bool(url_ent)

        data.append(item)
    return success_response(message="Historial completo de turnos obtenido por el administrador", data=data)

@admin_router.patch("/{id_turno}/estado")
def admin_force_estado(
    id_turno: int,
    request: schemas.AgendaForceEstadoRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """El administrador cambia manualmente el estado de cualquier turno."""
    turno = AgendaUseCases.force_estado_admin(db, id_turno, request)

    # Notificaciones automáticas por Correo Electrónico al cliente y administradores
    try:
        from app.shared.utils.email_service import EmailService
        if turno.finca and turno.finca.cliente and turno.finca.cliente.usuario:
            dest_email = turno.finca.cliente.usuario.email
            finca_nom = turno.finca.nombre_finca
            serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo con Dron"
            cli_nom = f"{turno.finca.cliente.nombre} {turno.finca.cliente.apellido_1 or ''}".strip()
            tec_nom = f"{turno.tecnico.nombre} {turno.tecnico.apellido_1 or ''}".strip() if turno.tecnico else "Piloto Principal Flymetrics"
            dron_mod = turno.drone.modelo if turno.drone else "DJI AGRAS T40"

            est_lower = str(request.estado or "").strip().lower()
            if request.motivo_admin and request.motivo_admin.strip() and request.motivo_admin.strip() != "Modificado por el administrador":
                if dest_email:
                    _dispatch_email_async(
                        EmailService.send_admin_note_response,
                        to_email=dest_email,
                        nombre_cliente=cli_nom,
                        id_turno=turno.id_turno,
                        servicio=serv_nom,
                        finca=finca_nom,
                        estado=request.estado,
                        mensaje_admin=request.motivo_admin.strip(),
                        tarifa=float(request.tarifa) if request.tarifa is not None else None
                    )
            if est_lower == "confirmado":
                if dest_email:
                    _dispatch_email_async(
                        EmailService.send_booking_confirmed,
                        to_email=dest_email,
                        nombre_cliente=cli_nom,
                        id_turno=turno.id_turno,
                        servicio=serv_nom,
                        finca=finca_nom,
                        fecha=str(turno.fecha_de_turno),
                        hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                        tecnico_nombre=tec_nom,
                        dron_modelo=dron_mod
                    )
            elif est_lower == "completado" or est_lower == "hecho":
                # 3er correo: Notificar a todos los administradores
                _dispatch_email_async(
                    EmailService.send_admin_service_completed,
                    id_turno=turno.id_turno,
                    cliente_nombre=cli_nom,
                    servicio=serv_nom,
                    finca=finca_nom,
                    tecnico_nombre=tec_nom,
                    fecha=str(turno.fecha_de_turno),
                    hora_fin=str(turno.hora_fin_real or '')
                )
                if dest_email:
                    _dispatch_email_async(
                        EmailService.send_service_completed,
                        to_email=dest_email,
                        nombre_cliente=cli_nom,
                        id_turno=turno.id_turno,
                        servicio=serv_nom,
                        finca=finca_nom,
                        tecnico=tec_nom,
                        hora_finalizacion=str(turno.hora_fin_real or "17:00")[:5],
                        fecha=str(turno.fecha_de_turno)
                    )
            elif est_lower == "reagendado":
                if dest_email:
                    _dispatch_email_async(
                        EmailService.send_booking_rescheduled,
                        to_email=dest_email,
                        nombre_cliente=cli_nom,
                        id_turno=turno.id_turno,
                        servicio=serv_nom,
                        finca=finca_nom,
                        nueva_fecha=str(turno.fecha_de_turno),
                        nueva_hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                        motivo=request.motivo_admin or "Ajuste operacional de agenda por administración"
                    )
            elif est_lower == "cancelado":
                if dest_email:
                    _dispatch_email_async(
                        EmailService.send_booking_cancelled,
                        to_email=dest_email,
                        nombre_cliente=cli_nom,
                        id_turno=turno.id_turno,
                        servicio=serv_nom,
                        finca=finca_nom,
                        motivo=request.motivo_admin or "Cancelación administrativa"
                    )
                # Notificar a los técnicos para remover de su calendario Microsoft
                pilotos_objs = []
                if turno.id_tecnico:
                    t1 = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == turno.id_tecnico).first()
                    if t1:
                        pilotos_objs.append(t1)
                if turno.tecnicos_adicionales:
                    for extra_id in str(turno.tecnicos_adicionales).split(","):
                        if extra_id.strip().isdigit():
                            t_extra = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == int(extra_id.strip())).first()
                            if t_extra:
                                pilotos_objs.append(t_extra)

                muni_val = getattr(turno.finca, 'ubicacion_municipio', None) or getattr(turno.finca, 'municipio', None) or "Ubicación Registrada"
                dep_val = getattr(turno.finca, 'departamento', "") or ""
                for p_obj in pilotos_objs:
                    p_mail = getattr(p_obj, "email", None) or (p_obj.usuario.email if getattr(p_obj, "usuario", None) else None)
                    if p_mail:
                        _dispatch_email_async(
                            EmailService.send_technician_cancelled,
                            to_email=p_mail.strip().lower(),
                            tecnico_nombre=f"{p_obj.nombre} {p_obj.apellido_1 or ''}".strip(),
                            id_turno=turno.id_turno,
                            servicio=serv_nom,
                            finca=finca_nom,
                            motivo=request.motivo_admin or "Cancelación administrativa",
                            municipio=muni_val,
                            departamento=dep_val,
                            fecha=str(turno.fecha_de_turno),
                            hora=str(turno.hora_inicio_estimada or "08:00 AM")
                        )
    except Exception as mail_err:
        print(f"[ADMIN FORCE ESTADO EMAIL ERROR] {mail_err}")

    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(message="Estado del turno forzado por el administrador exitosamente", data=data)

@admin_router.post("/{id_turno}/reenviar-aceptacion")
def admin_reenviar_aceptacion(
    id_turno: int,
    request: schemas.AgendaReenvioAceptacionRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Reenvía la solicitud de aceptación pendiente a un cliente y deja constancia del administrador responsable."""
    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    admin_label = ""
    if request.id_admin_responsable:
        admin_user = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == int(request.id_admin_responsable)).first()
        if admin_user:
            admin_label = admin_user.email or f"Admin #{admin_user.id_usuarios}"
            turno.observaciones_servicio = f"{turno.observaciones_servicio or ''} | Responsable de reenvío: {admin_label}".strip()

    if request.nota_admin and request.nota_admin.strip():
        turno.observaciones_servicio = f"{turno.observaciones_servicio or ''} | Nota de reenvío: {request.nota_admin.strip()}".strip()

    if turno.finca and turno.finca.cliente and turno.finca.cliente.usuario and turno.finca.cliente.usuario.email:
        from app.shared.utils.email_service import EmailService
        accept_url = _build_demo_accept_url(turno.id_turno)
        _dispatch_email_async(
            EmailService.send_demo_gratuita_created,
            to_email=turno.finca.cliente.usuario.email.strip().lower(),
            nombre_cliente=f"{turno.finca.cliente.nombre} {turno.finca.cliente.apellido_1 or ''}".strip(),
            id_turno=turno.id_turno,
            servicio=turno.servicio.nombre_servicio if turno.servicio else "Demostración Gratuita",
            finca=turno.finca.nombre_finca or "Predio Registrado",
            fecha=str(turno.fecha_de_turno),
            hora=str(turno.hora_inicio_estimada or "08:00 AM"),
            observaciones=turno.observaciones_servicio,
            aceptacion_url=accept_url
        )

    db.commit()
    db.refresh(turno)
    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(message="Aceptación pendiente reenviada correctamente al cliente", data=data)

@admin_router.post("", status_code=status.HTTP_201_CREATED)
def admin_create_agenda(
    request: schemas.AgendaCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(RoleChecker(["administrador"]))
):
    """Permite al administrador crear un turno directamente en la agenda."""
    turno = AgendaUseCases.create_turno(db, request, current_user)
    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(message="Turno creado exitosamente por el administrador", data=data, status_code=201)

@admin_router.patch("/{id_turno}/asignar")
def admin_asignar_recursos(
    id_turno: int,
    request: schemas.AgendaAsignarRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """El administrador asigna o reasigna el técnico y el dron para un turno."""
    turno = AgendaUseCases.asignar_tecnico_drone(db, id_turno, request)
    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(message="Asignación de técnico y dron completada", data=data)


@router.post("/{id_turno}/notificar-manual", status_code=status.HTTP_200_OK)
@admin_router.post("/{id_turno}/notificar-manual", status_code=status.HTTP_200_OK)
def notificar_manual_turno(
    id_turno: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    Despacha recordatorio manual oficial tanto al cliente como a todos los técnicos asignados a este turno.
    """
    from app.infrastructure.database.models.models import AgendaModel, TecnicoModel
    from app.shared.exceptions.exceptions import NotFoundException
    from app.shared.utils.email_service import EmailService

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise NotFoundException("Turno no encontrado")

    finca_nom = turno.finca.nombre_finca if turno.finca else "Predio Registrado"
    serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo con Dron"
    cli_nom = f"{turno.finca.cliente.nombre} {turno.finca.cliente.apellido_1 or ''}".strip() if (turno.finca and turno.finca.cliente) else "Cliente"
    dest_email = turno.finca.cliente.usuario.email if (turno.finca and turno.finca.cliente and turno.finca.cliente.usuario) else None

    # Recopilar todos los pilotos asignados
    pilotos_nombres = []
    pilotos_objs = []
    if turno.id_tecnico:
        t1 = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == turno.id_tecnico).first()
        if t1:
            pilotos_objs.append(t1)
            pilotos_nombres.append(f"{t1.nombre} {t1.apellido_1 or ''}".strip())
    if turno.tecnicos_adicionales:
        for extra_id in str(turno.tecnicos_adicionales).split(","):
            if extra_id.strip().isdigit():
                t_extra = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == int(extra_id.strip())).first()
                if t_extra:
                    pilotos_objs.append(t_extra)
                    pilotos_nombres.append(f"{t_extra.nombre} {t_extra.apellido_1 or ''}".strip())
    tec_nom = ", ".join(pilotos_nombres) if pilotos_nombres else "Piloto asignado por despacho"

    fecha_str = str(turno.fecha_de_turno)
    hora_str = str(turno.hora_inicio_estimada or "08:00 AM")
    notificados = []

    # 1. Notificar al cliente
    if dest_email:
        _dispatch_email_async(
            EmailService.send_manual_participant_reminder,
            to_email=dest_email,
            nombre=cli_nom,
            id_turno=turno.id_turno,
            servicio=serv_nom,
            finca=finca_nom,
            fecha=fecha_str,
            hora=hora_str,
            rol="cliente",
            piloto_nombre=tec_nom
        )
        notificados.append(f"Cliente ({dest_email})")

    # 2. Notificar a los técnicos
    for p_obj in pilotos_objs:
        p_email = getattr(p_obj, "email", None) or (p_obj.usuario.email if getattr(p_obj, "usuario", None) else None)
        if p_email:
            _dispatch_email_async(
                EmailService.send_manual_participant_reminder,
                to_email=p_email.strip().lower(),
                nombre=f"{p_obj.nombre} {p_obj.apellido_1 or ''}".strip(),
                id_turno=turno.id_turno,
                servicio=serv_nom,
                finca=finca_nom,
                fecha=fecha_str,
                hora=hora_str,
                rol="tecnico",
                piloto_nombre=tec_nom
            )
            notificados.append(f"Piloto {p_obj.nombre} ({p_email})")

    return success_response(
        message=f"Recordatorio manual enviado exitosamente a: {', '.join(notificados) if notificados else 'sin destinatarios válidos'}.",
        data={"id_turno": id_turno, "destinatarios": notificados}
    )


# ==============================================================================
# FLUJO DE COTIZACIÓN Y CICLO INFINITO DE NEGOCIACIÓN
# ==============================================================================

@admin_router.post("/{id_turno}/cotizar")
def admin_cotizar_turno(
    id_turno: int,
    request: schemas.AgendaCotizarRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    El administrador adjunta precio obligatorio y asigna técnico obligatorio al turno.
    Cambia estado a 'Pendiente por confirmar' y envía notificación al cliente con enlace para revisar.
    """
    import json
    import secrets
    from datetime import datetime
    from app.infrastructure.database.models.models import TecnicoModel
    from app.shared.exceptions.exceptions import NotFoundException, BadRequestException
    from app.shared.utils.email_service import EmailService

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise NotFoundException("Turno no encontrado")

    if not request.tarifa or float(request.tarifa) <= 0:
        raise BadRequestException("Debe adjuntar un precio válido mayor a 0.")

    if not request.id_tecnico:
        raise BadRequestException("Debe seleccionar obligatoriamente un técnico a cargo.")

    tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == request.id_tecnico).first()
    if not tecnico:
        raise NotFoundException("El técnico seleccionado no existe en el sistema.")

    turno.tarifa = request.tarifa
    turno.id_tecnico = request.id_tecnico
    if request.tecnicos_adicionales is not None:
        turno.tecnicos_adicionales = request.tecnicos_adicionales
    turno.estado = "Pendiente por confirmar"

    if not turno.token_confirmacion:
        turno.token_confirmacion = secrets.token_urlsafe(32)

    # Actualizar historial de negociación
    historial = []
    if turno.historial_negociacion:
        try:
            historial = json.loads(turno.historial_negociacion)
        except Exception:
            historial = []

    admin_nom = current_user.email or f"Admin #{current_user.id_usuarios}"
    historial.append({
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "emisor": "admin",
        "tipo": "cotizacion",
        "tarifa": float(request.tarifa),
        "tecnico_id": request.id_tecnico,
        "tecnico_nombre": f"{tecnico.nombre} {tecnico.apellido_1 or ''}".strip(),
        "mensaje": request.mensaje_admin or f"Cotización formal enviada por administración ({admin_nom})"
    })
    turno.historial_negociacion = json.dumps(historial, ensure_ascii=False)

    db.commit()
    db.refresh(turno)

    # Enviar correo al cliente con detalles y botón de acción
    if turno.finca and turno.finca.cliente and turno.finca.cliente.usuario and turno.finca.cliente.usuario.email:
        dest_email = turno.finca.cliente.usuario.email.strip().lower()
        cli_nom = f"{turno.finca.cliente.nombre} {turno.finca.cliente.apellido_1 or ''}".strip()
        finca_nom = turno.finca.nombre_finca or "Predio Registrado"
        obs_cot = getattr(turno, "observaciones_servicio", None) or getattr(turno, "observaciones_del_cliente", None) or ""
        import re
        m_svc_cot = re.search(r'\[Servicios:\s*([^\]]+)\]', obs_cot, re.IGNORECASE)
        serv_nom = m_svc_cot.group(1).strip() if m_svc_cot else (turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola")
        
        revisar_url = EmailService.get_portal_url(f"pages/index.html?revisar_turno={turno.id_turno}&token={turno.token_confirmacion}")

        _dispatch_email_async(
            EmailService.send_client_negotiation_quote,
            to_email=dest_email,
            nombre_cliente=cli_nom,
            id_turno=turno.id_turno,
            servicio=serv_nom,
            finca=finca_nom,
            tarifa=float(request.tarifa),
            fecha=str(turno.fecha_de_turno),
            hora=str(turno.hora_inicio_estimada or "08:00 AM"),
            revisar_url=revisar_url,
            mensaje_admin=request.mensaje_admin
        )

    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(
        message="Cotización enviada exitosamente al cliente. Estado cambiado a 'Pendiente por confirmar'.",
        data=data
    )


@router.get("/revisar/{id_turno}/{token}")
def public_revisar_turno(id_turno: int, token: str, db: Session = Depends(get_db)):
    """
    Endpoint público que permite al cliente revisar los datos de la solicitud y propuesta de precio.
    """
    import json
    from app.shared.exceptions.exceptions import NotFoundException, BadRequestException

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise NotFoundException("Turno no encontrado")

    if not turno.token_confirmacion or turno.token_confirmacion != token:
        raise BadRequestException("Enlace de confirmación inválido o expirado.")

    finca = turno.finca
    cli = finca.cliente if finca else None
    tec = turno.tecnico

    historial = []
    if turno.historial_negociacion:
        try:
            historial = json.loads(turno.historial_negociacion)
        except Exception:
            historial = []

    res_data = {
        "id_turno": turno.id_turno,
        "estado": turno.estado,
        "es_demostracion": bool(turno.es_demostracion),
        "tarifa": float(turno.tarifa) if turno.tarifa is not None else 0.0,
        "sugerencia_cliente": turno.sugerencia_cliente,
        "fecha": str(turno.fecha_de_turno),
        "hora": str(turno.hora_inicio_estimada or "08:00 AM"),
        "servicio": turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola",
        "finca": finca.nombre_finca if finca else "Predio Registrado",
        "finca_nombre": finca.nombre_finca if finca else "Predio Registrado",
        "finca_maps_url": finca.maps_url if finca else "",
        "maps_url": finca.maps_url if finca else "",
        "hectareas": float(finca.hectareas) if (finca and finca.hectareas) else 0.0,
        "municipio": finca.ubicacion_municipio if finca else "",
        "cliente_nombre": f"{cli.nombre} {cli.apellido_1 or ''}".strip() if cli else "Cliente",
        "cliente_documento": (cli.numero_documento or "") if cli else "",
        "numero_documento": (cli.numero_documento or "") if cli else "",
        "cliente_email": cli.usuario.email if (cli and cli.usuario) else "",
        "cliente_telefono": cli.telefono if cli else "",
        "tecnico_nombre": f"{tec.nombre} {tec.apellido_1 or ''}".strip() if tec else "Piloto por asignar",
        "historial": historial
    }

    return success_response(message="Detalle de cotización obtenido", data=res_data)


@router.post("/revisar/{id_turno}/{token}/responder")
def public_responder_propuesta(
    id_turno: int,
    token: str,
    request: schemas.AgendaResponderPropuestaRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint público donde el cliente acepta la cotización o propone modificaciones (máximo 500 caracteres).
    Si acepta: cambia a 'Confirmado' y despacha correo al técnico asignado.
    Si modifica: guarda la sugerencia en BD, añade al historial y notifica al administrador.
    """
    import json
    from datetime import datetime
    from app.infrastructure.database.models.models import TecnicoModel
    from app.shared.exceptions.exceptions import NotFoundException, BadRequestException
    from app.shared.utils.email_service import EmailService

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise NotFoundException("Turno no encontrado")

    import hmac
    if not turno.token_confirmacion or not hmac.compare_digest(str(turno.token_confirmacion), str(token)):
        raise BadRequestException("Token de confirmación no coincide o no es válido.")

    accion = str(request.accion or "").strip().lower()
    historial = []
    if turno.historial_negociacion:
        try:
            historial = json.loads(turno.historial_negociacion)
        except Exception:
            historial = []

    finca = turno.finca
    cli = finca.cliente if finca else None
    cli_nom = f"{cli.nombre} {cli.apellido_1 or ''}".strip() if cli else "Cliente"
    finca_nom = finca.nombre_finca if finca else "Predio Registrado"
    serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola"

    if accion == "aceptar":
        historial.append({
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "emisor": "cliente",
            "tipo": "aceptacion",
            "tarifa": float(turno.tarifa or 0.0),
            "mensaje": "El cliente ha aceptado satisfactoriamente la cotización y términos del servicio."
        })
        turno.historial_negociacion = json.dumps(historial, ensure_ascii=False)
        turno.estado = "Confirmado"

        db.commit()
        db.refresh(turno)

        # ── Notificar al técnico asignado cuando el servicio está Confirmado ──
        if turno.id_tecnico:
            tec = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == turno.id_tecnico).first()
            if tec and (tec.email or (tec.usuario and tec.usuario.email)):
                tec_email = tec.email or tec.usuario.email
                dron_mod = turno.drone.modelo if turno.drone else "DJI AGRAS T40"
                muni_nom = finca.ubicacion_municipio if finca else "Ubicación registrada"
                dep_nom = getattr(finca, "departamento", "") or ""
                maps_link = getattr(finca, "maps_url", None)
                ha_val = float(finca.hectareas) if (finca and finca.hectareas) else None
                cul_val = getattr(finca, "cultivo_principal", None) or getattr(finca, "tipo_cultivo", None) or None
                cli_email = cli.usuario.email if (cli and cli.usuario) else None

                _dispatch_email_async(
                    EmailService.send_technician_assigned,
                    to_email=tec_email.strip().lower(),
                    tecnico_nombre=f"{tec.nombre} {tec.apellido_1 or ''}".strip(),
                    id_turno=turno.id_turno,
                    servicio=serv_nom,
                    finca=finca_nom,
                    municipio=muni_nom,
                    fecha=str(turno.fecha_de_turno),
                    hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                    cliente_nombre=cli_nom,
                    cliente_tel=cli.telefono if cli else None,
                    observaciones=turno.observaciones_servicio,
                    tarifa=float(turno.tarifa or 0.0) if turno.tarifa else None,
                    departamento=dep_nom,
                    hectareas=ha_val,
                    cultivo=cul_val,
                    maps_url=maps_link,
                    dron=dron_mod,
                    cliente_email=cli_email
                )

        # Notificar también al cliente la confirmación
        if cli and cli.usuario and cli.usuario.email:
            tec_nombre = f"{turno.tecnico.nombre} {turno.tecnico.apellido_1 or ''}".strip() if turno.tecnico else "Piloto asignado"
            _dispatch_email_async(
                EmailService.send_booking_confirmed,
                to_email=cli.usuario.email.strip().lower(),
                nombre_cliente=cli_nom,
                id_turno=turno.id_turno,
                servicio=serv_nom,
                finca=finca_nom,
                fecha=str(turno.fecha_de_turno),
                hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                tecnico_nombre=tec_nombre,
                dron_modelo=turno.drone.modelo if turno.drone else "DJI AGRAS T40"
            )

        return success_response(
            message="Servicio aceptado y confirmado exitosamente. El equipo técnico ha sido notificado.",
            data={"id_turno": turno.id_turno, "estado": turno.estado}
        )

    elif accion == "modificar":
        sug = str(request.sugerencia or "").strip()
        if not sug:
            raise BadRequestException("Debe ingresar una sugerencia o contrapropuesta.")
        if len(sug) > 500:
            raise BadRequestException("La sugerencia no puede exceder los 500 caracteres.")

        turno.sugerencia_cliente = sug
        # Estado se mantiene en Pendiente por confirmar mientras se resuelve la negociación
        turno.estado = "Pendiente por confirmar"

        historial.append({
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "emisor": "cliente",
            "tipo": "sugerencia",
            "tarifa": float(turno.tarifa or 0.0),
            "mensaje": sug
        })
        turno.historial_negociacion = json.dumps(historial, ensure_ascii=False)
        db.commit()
        db.refresh(turno)

        # Notificar al administrador por correo
        _dispatch_email_async(
            EmailService.send_admin_client_suggestion,
            id_turno=turno.id_turno,
            cliente_nombre=cli_nom,
            finca=finca_nom,
            servicio=serv_nom,
            sugerencia=sug,
            tarifa_actual=float(turno.tarifa or 0.0)
        )

        return success_response(
            message="Tu sugerencia fue enviada exitosamente al administrador. Te notificaremos la respuesta a la brevedad.",
            data={"id_turno": turno.id_turno, "estado": turno.estado, "sugerencia": sug}
        )
    else:
        raise BadRequestException("Acción inválida. Debe ser 'aceptar' o 'modificar'.")


@router.post("/{id_turno}/negociar")
def cliente_negociar_turno(
    id_turno: int,
    request: schemas.AgendaResponderPropuestaRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(cliente_or_admin)
):
    """
    Endpoint autenticado para que el cliente acepte o negocie una cotización desde su portal.
    """
    import json
    from datetime import datetime
    from app.infrastructure.database.models.models import TecnicoModel
    from app.shared.exceptions.exceptions import NotFoundException, BadRequestException, ForbiddenException
    from app.shared.utils.email_service import EmailService

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise NotFoundException("Turno no encontrado")

    if current_user.rol == "cliente":
        if not turno.finca or not turno.finca.cliente or turno.finca.cliente.id_usuario != current_user.id_usuarios:
            raise ForbiddenException("No tienes permisos para negociar este turno.")

    accion = str(request.accion or "").strip().lower()
    historial = []
    if turno.historial_negociacion:
        try:
            historial = json.loads(turno.historial_negociacion)
        except Exception:
            historial = []

    finca = turno.finca
    cli = finca.cliente if finca else None
    cli_nom = f"{cli.nombre} {cli.apellido_1 or ''}".strip() if cli else "Cliente"
    finca_nom = finca.nombre_finca if finca else "Predio Registrado"
    serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola"

    if accion == "aceptar":
        historial.append({
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "emisor": "cliente",
            "tipo": "aceptacion",
            "tarifa": float(turno.tarifa or 0.0),
            "mensaje": "El cliente ha aceptado la cotización y términos desde el Portal de Clientes."
        })
        turno.historial_negociacion = json.dumps(historial, ensure_ascii=False)
        turno.estado = "Confirmado"

        db.commit()
        db.refresh(turno)

        # Notificar al técnico asignado
        if turno.id_tecnico:
            tec = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == turno.id_tecnico).first()
            if tec and (tec.email or (tec.usuario and tec.usuario.email)):
                tec_email = tec.email or tec.usuario.email
                dep_nom = getattr(finca, "departamento", "") or ""
                maps_link = getattr(finca, "maps_url", None)
                ha_val = float(finca.hectareas) if (finca and finca.hectareas) else None
                tar_val = float(turno.tarifa) if turno.tarifa is not None else (0.0 if turno.es_demostracion else None)

                # Extraer cultivo de observaciones si está presente
                import re
                cul_val = None
                if turno.observaciones_servicio:
                    m_c = re.search(r'Cultivo(?: y Area)?:\s*([^\n\(\r]+)', turno.observaciones_servicio, re.IGNORECASE)
                    if m_c:
                        cul_val = m_c.group(1).strip()
                if not cul_val:
                    cul_val = "Demostración Agrícola" if turno.es_demostracion else "Misión Operativa"

                _dispatch_email_async(
                    EmailService.send_technician_assigned,
                    to_email=tec_email.strip().lower(),
                    tecnico_nombre=f"{tec.nombre} {tec.apellido_1 or ''}".strip(),
                    id_turno=turno.id_turno,
                    servicio=serv_nom,
                    finca=finca_nom,
                    municipio=muni_nom,
                    fecha=str(turno.fecha_de_turno),
                    hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                    cliente_nombre=cli_nom,
                    cliente_tel=cli.telefono if cli else None,
                    observaciones=turno.observaciones_servicio,
                    departamento=dep_nom,
                    hectareas=ha_val,
                    cultivo=cul_val,
                    maps_url=maps_link,
                    tarifa=tar_val
                )

        if cli and cli.usuario and cli.usuario.email:
            tec_nombre = f"{turno.tecnico.nombre} {turno.tecnico.apellido_1 or ''}".strip() if turno.tecnico else "Piloto asignado"
            _dispatch_email_async(
                EmailService.send_booking_confirmed,
                to_email=cli.usuario.email.strip().lower(),
                nombre_cliente=cli_nom,
                id_turno=turno.id_turno,
                servicio=serv_nom,
                finca=finca_nom,
                fecha=str(turno.fecha_de_turno),
                hora=str(turno.hora_inicio_estimada or "08:00 AM"),
                tecnico_nombre=tec_nombre,
                dron_modelo=turno.drone.modelo if turno.drone else "DJI AGRAS T40"
            )

        return success_response(
            message="Servicio aceptado y confirmado exitosamente.",
            data={"id_turno": turno.id_turno, "estado": turno.estado}
        )

    elif accion == "modificar":
        sug = str(request.sugerencia or "").strip()
        if not sug:
            raise BadRequestException("Debe ingresar una sugerencia o contrapropuesta.")
        if len(sug) > 500:
            raise BadRequestException("La sugerencia no puede exceder los 500 caracteres.")

        turno.sugerencia_cliente = sug
        turno.estado = "Pendiente por confirmar"

        historial.append({
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "emisor": "cliente",
            "tipo": "sugerencia",
            "tarifa": float(turno.tarifa or 0.0),
            "mensaje": sug
        })
        turno.historial_negociacion = json.dumps(historial, ensure_ascii=False)
        db.commit()
        db.refresh(turno)

        _dispatch_email_async(
            EmailService.send_admin_client_suggestion,
            id_turno=turno.id_turno,
            cliente_nombre=cli_nom,
            finca=finca_nom,
            servicio=serv_nom,
            sugerencia=sug,
            tarifa_actual=float(turno.tarifa or 0.0)
        )

        return success_response(
            message="Tu sugerencia fue enviada exitosamente al administrador. Te notificaremos la respuesta a la brevedad.",
            data={"id_turno": turno.id_turno, "estado": turno.estado, "sugerencia": sug}
        )
    else:
        raise BadRequestException("Acción inválida. Debe ser 'aceptar' o 'modificar'.")


@admin_router.post("/{id_turno}/aceptar-directo")
def admin_aceptar_directo_servicio(
    id_turno: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    El administrador acepta directamente el servicio atendiendo a la solicitud o sugerencia del cliente.
    Establece el estado en 'Confirmado' y notifica al técnico asignado.
    """
    import json
    from datetime import datetime
    from app.infrastructure.database.models.models import TecnicoModel
    from app.shared.exceptions.exceptions import NotFoundException, BadRequestException
    from app.shared.utils.email_service import EmailService

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise NotFoundException("Turno no encontrado")

    if not turno.id_tecnico:
        raise BadRequestException("El turno no tiene un técnico asignado. Asigne un técnico antes de confirmar.")

    turno.estado = "Confirmado"
    historial = []
    if turno.historial_negociacion:
        try:
            historial = json.loads(turno.historial_negociacion)
        except Exception:
            historial = []

    admin_nom = current_user.email or f"Admin #{current_user.id_usuarios}"
    historial.append({
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "emisor": "admin",
        "tipo": "aceptacion_directa",
        "tarifa": float(turno.tarifa or 0.0),
        "mensaje": f"Aceptado directamente por la administración ({admin_nom})"
    })
    turno.historial_negociacion = json.dumps(historial, ensure_ascii=False)
    db.commit()
    db.refresh(turno)

    finca = turno.finca
    cli = finca.cliente if finca else None
    cli_nom = f"{cli.nombre} {cli.apellido_1 or ''}".strip() if cli else "Cliente"
    finca_nom = finca.nombre_finca if finca else "Predio Registrado"
    serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola"

    # Notificar al técnico asignado
    tec = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == turno.id_tecnico).first()
    if tec and (tec.email or (tec.usuario and tec.usuario.email)):
        tec_email = tec.email or tec.usuario.email
        dron_mod = turno.drone.modelo if turno.drone else "DJI AGRAS T40"
        muni_nom = finca.ubicacion_municipio if finca else "Ubicación registrada"
        dep_nom = getattr(finca, "departamento", "") or ""
        maps_link = getattr(finca, "maps_url", None)
        ha_val = float(finca.hectareas) if (finca and finca.hectareas) else None
        cul_val = getattr(finca, "cultivo_principal", None) or getattr(finca, "tipo_cultivo", None) or None
        cli_email = cli.usuario.email if (cli and cli.usuario) else None

        _dispatch_email_async(
            EmailService.send_technician_assigned,
            to_email=tec_email.strip().lower(),
            tecnico_nombre=f"{tec.nombre} {tec.apellido_1 or ''}".strip(),
            id_turno=turno.id_turno,
            servicio=serv_nom,
            finca=finca_nom,
            municipio=muni_nom,
            fecha=str(turno.fecha_de_turno),
            hora=str(turno.hora_inicio_estimada or "08:00 AM"),
            cliente_nombre=cli_nom,
            cliente_tel=cli.telefono if cli else None,
            observaciones=turno.observaciones_servicio,
            tarifa=float(turno.tarifa or 0.0) if turno.tarifa else None,
            departamento=dep_nom,
            hectareas=ha_val,
            cultivo=cul_val,
            maps_url=maps_link,
            dron=dron_mod,
            cliente_email=cli_email
        )

    # Notificar al cliente
    if cli and cli.usuario and cli.usuario.email:
        tec_nombre = f"{tec.nombre} {tec.apellido_1 or ''}".strip() if tec else "Piloto Flymetrics"
        _dispatch_email_async(
            EmailService.send_booking_confirmed,
            to_email=cli.usuario.email.strip().lower(),
            nombre_cliente=cli_nom,
            id_turno=turno.id_turno,
            servicio=serv_nom,
            finca=finca_nom,
            fecha=str(turno.fecha_de_turno),
            hora=str(turno.hora_inicio_estimada or "08:00 AM"),
            tecnico_nombre=tec_nombre,
            dron_modelo=turno.drone.modelo if turno.drone else "DJI AGRAS T40"
        )

    data = schemas.AgendaResponse.model_validate(turno).model_dump()
    return success_response(
        message="Servicio aceptado directamente por el administrador y confirmado. Piloto notificado.",
        data=data
    )
