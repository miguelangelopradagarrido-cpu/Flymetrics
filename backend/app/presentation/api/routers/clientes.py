from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session, joinedload, selectinload
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import ClienteUseCases
from app.presentation.api.dependencies.auth import get_current_user, RoleChecker
from app.infrastructure.database.models.models import UsuarioModel, ClienteModel, FincaModel, AgendaModel
from app.shared.responses.response import success_response

router = APIRouter(prefix="/clientes", tags=["Clientes"])

admin_or_tech = RoleChecker(["administrador", "tecnico"])
admin_required = RoleChecker(["administrador"])

@router.get("")
def list_clientes(db: Session = Depends(get_db), current_user: UsuarioModel = Depends(admin_or_tech)):
    """Lista todos los clientes con su email asociado y conteos con carga impaciente anti-N+1."""
    clientes = db.query(ClienteModel).options(
        joinedload(ClienteModel.usuario),
        selectinload(ClienteModel.fincas)
    ).all()
    data = []
    for c in clientes:
        item = schemas.ClienteResponse.model_validate(c).model_dump()
        item["email"] = c.usuario.email if c.usuario else ""
        item["fincas_count"] = len(c.fincas) if c.fincas else 0
        data.append(item)
    return success_response(message="Lista de clientes obtenida", data=data)

@router.post("", status_code=status.HTTP_201_CREATED)
def create_cliente_admin(
    request: schemas.ClienteAdminCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Crear cliente desde el panel administrador con o sin correo."""
    from app.infrastructure.security.jwt_handler import hash_password
    from app.infrastructure.database.models.models import FincaModel
    import uuid

    clean_email = (request.email or "").strip().lower()
    clean_nombre = (request.nombre or "").strip().upper()
    clean_tel = (request.telefono or "").strip()

    id_usuario = None
    if clean_email:
        # Si se proporcionó email, verificar que no esté repetido
        existing_user = db.query(UsuarioModel).filter(UsuarioModel.email == clean_email).first()
        if existing_user:
            from app.shared.exceptions.exceptions import BadRequestException
            raise BadRequestException(f"El correo '{clean_email}' ya está registrado en el sistema")
        
        pwd = request.contraseña or "Flymetrics123!"
        new_user = UsuarioModel(
            email=clean_email,
            contraseña=hash_password(pwd),
            rol="cliente"
        )
        db.add(new_user)
        db.flush()
        id_usuario = new_user.id_usuarios

    # Crear el perfil de Cliente
    cliente = ClienteModel(
        id_usuario=id_usuario,
        nombre=clean_nombre,
        apellido_1="",
        apellido_2="",
        telefono=clean_tel or None,
        verificado=True
    )
    db.add(cliente)
    db.flush()

    # Si se especificó nombre de finca o ubicación, crear finca asociada
    if request.nombre_finca or request.ubicacion_municipio or request.departamento:
        finca = FincaModel(
            id_cliente=cliente.id_cliente,
            nombre_finca=request.nombre_finca or "Finca Principal",
            departamento=request.departamento or "Cundinamarca",
            ubicacion_municipio=request.ubicacion_municipio or "Municipio Principal",
            hectareas=request.hectareas or 10.0
        )
        db.add(finca)

    db.commit()
    db.refresh(cliente)

    data = schemas.ClienteResponse.model_validate(cliente).model_dump()
    return success_response(message="Cliente registrado exitosamente", data=data, status_code=201)

@router.get("/me")
def get_me(db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Retorna el perfil del cliente autenticado según su JWT. Crea el perfil si no existe aún."""
    cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
    if not cliente:
        name = current_user.email.split('@')[0]
        cliente = ClienteModel(
            id_usuario=current_user.id_usuarios,
            nombre=name,
            apellido_1='Cliente',
            telefono='',
            verificado=False
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
    data = schemas.ClienteResponse.model_validate(cliente).model_dump()
    data["email"] = current_user.email
    return success_response(message="Perfil obtenido exitosamente", data=data)

@router.get("/{id_cliente}")
def get_cliente_detail(
    id_cliente: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Detalle completo de un cliente incluyendo sus fincas y correo de acceso."""
    from app.shared.exceptions.exceptions import NotFoundException
    if current_user.rol == "cliente":
        cliente = db.query(ClienteModel).options(
            joinedload(ClienteModel.usuario),
            selectinload(ClienteModel.fincas).selectinload(FincaModel.turnos).joinedload(AgendaModel.servicio)
        ).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
    else:
        cliente = db.query(ClienteModel).options(
            joinedload(ClienteModel.usuario),
            selectinload(ClienteModel.fincas).selectinload(FincaModel.turnos).joinedload(AgendaModel.servicio)
        ).filter(ClienteModel.id_cliente == id_cliente).first()
    if not cliente:
        raise NotFoundException("Cliente no encontrado")
    
    fincas_data = []
    for f in cliente.fincas:
        maps_link = f.maps_url
        if not maps_link and f.latitud is not None and f.longitud is not None:
            maps_link = f"https://www.google.com/maps?q={float(f.latitud):.6f},{float(f.longitud):.6f}"
        
        turnos_list = []
        for t in getattr(f, 'turnos', []) or []:
            turnos_list.append({
                "id_turno": t.id_turno,
                "servicio": t.servicio.nombre_servicio if t.servicio else "Vuelo Agrícola",
                "fecha": str(t.fecha_de_turno) if t.fecha_de_turno else "",
                "hora": str(t.hora_inicio_estimada) if t.hora_inicio_estimada else "",
                "estado": t.estado,
                "tarifa": float(t.tarifa) if t.tarifa is not None else None,
                "es_demostracion": bool(t.es_demostracion)
            })
        turnos_list.sort(key=lambda x: x["id_turno"], reverse=True)

        fincas_data.append({
            "id_finca": f.id_finca,
            "nombre_finca": f.nombre_finca,
            "ubicacion_municipio": f.ubicacion_municipio,
            "departamento": f.departamento,
            "hectareas": float(f.hectareas or 0),
            "maps_url": maps_link or "",
            "latitud": float(f.latitud) if f.latitud is not None else None,
            "longitud": float(f.longitud) if f.longitud is not None else None,
            "tipo_cultivo": getattr(f, 'tipo_cultivo', '') or '',
            "turnos": turnos_list
        })
        
    data = {
        "id_cliente": cliente.id_cliente,
        "id_usuario": cliente.id_usuario,
        "email": cliente.usuario.email if cliente.usuario else None,
        "nombre": cliente.nombre,
        "apellido_1": cliente.apellido_1,
        "apellido_2": cliente.apellido_2,
        "telefono": cliente.telefono,
        "numero_documento": cliente.numero_documento,
        "ciudad_expedicion": cliente.ciudad_expedicion,
        "fecha_expedicion": cliente.fecha_expedicion,
        "fecha_nacimiento": getattr(cliente, 'fecha_nacimiento', None),
        "created_at": str(cliente.created_at) if getattr(cliente, 'created_at', None) else None,
        "verificado": cliente.verificado,
        "link_alegra": cliente.link_alegra,
        "link_sharepoint": cliente.link_sharepoint,
        "fincas": fincas_data
    }
    return success_response(message="Detalle de cliente obtenido", data=data)

@router.put("/{id_cliente}/alegra")
def set_cliente_alegra_link(
    id_cliente: int,
    request: schemas.ClienteAlegraRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Vincula el enlace del portal/factura de Alegra para un cliente específico. Solo administrador."""
    cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == id_cliente).first()
    if not cliente:
        from app.shared.exceptions.exceptions import NotFoundException
        raise NotFoundException("Cliente no encontrado")
    cliente.link_alegra = (request.link_alegra or "").strip()
    db.commit()
    db.refresh(cliente)
    data = schemas.ClienteResponse.model_validate(cliente).model_dump()
    return success_response(message="Enlace de facturación Alegra vinculado exitosamente", data=data)

@router.put("/{id_cliente}/sharepoint")
def set_cliente_sharepoint_link(
    id_cliente: int,
    request: schemas.ClienteSharePointRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Vincula el enlace oficial de SharePoint / Informes Ejecutivos para un cliente específico. Solo administrador.
    Si se suministra un enlace, marca los turnos activos o completados como Finalizados y despacha la notificación oficial por correo."""
    from datetime import datetime
    import threading
    from app.shared.utils.email_service import EmailService

    cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == id_cliente).first()
    if not cliente:
        from app.shared.exceptions.exceptions import NotFoundException
        raise NotFoundException("Cliente no encontrado")

    sp_url = (request.link_sharepoint or "").strip()
    cliente.link_sharepoint = sp_url

    # Si hay un link de SharePoint válido, actualizar los turnos del cliente a Finalizado
    turnos_actualizados = []
    if sp_url:
        fincas_ids = [f.id_finca for f in cliente.fincas] if cliente.fincas else []
        if fincas_ids:
            turnos_cliente = db.query(AgendaModel).filter(
                AgendaModel.id_finca.in_(fincas_ids),
                AgendaModel.estado.in_(["Confirmado", "En Progreso", "Completado"])
            ).all()

            for t in turnos_cliente:
                t.estado = "Finalizado"
                if not t.hora_fin_real:
                    t.hora_fin_real = datetime.now().time()
                turnos_actualizados.append(t)

    db.commit()
    db.refresh(cliente)

    # Notificar al cliente con el enlace de SharePoint
    if sp_url and cliente.usuario and cliente.usuario.email:
        dest_email = cliente.usuario.email
        nom_cliente = f"{cliente.nombre} {cliente.apellido_1 or ''}".strip() or "Apreciado Cliente"
        
        # Tomar datos del turno más reciente si existe
        ultimo_turno = turnos_actualizados[-1] if turnos_actualizados else None
        id_t = ultimo_turno.id_turno if ultimo_turno else 0
        serv_nom = ultimo_turno.servicio.nombre_servicio if (ultimo_turno and ultimo_turno.servicio) else "Servicio de Vuelo Agrícola Especializado"
        finca_nom = ultimo_turno.finca.nombre_finca if (ultimo_turno and ultimo_turno.finca) else "Predio Registrado"
        tecnico_nom = f"{ultimo_turno.tecnico.usuario.nombre} {ultimo_turno.tecnico.usuario.apellido_1 or ''}".strip() if (ultimo_turno and ultimo_turno.tecnico and ultimo_turno.tecnico.usuario) else "Equipo de Operaciones Flymetrics"

        def _send_sp_notification():
            try:
                EmailService.send_service_finalized_sharepoint(
                    to_email=dest_email,
                    nombre_cliente=nom_cliente,
                    id_turno=id_t,
                    servicio=serv_nom,
                    finca=finca_nom,
                    url_sharepoint=sp_url,
                    tecnico=tecnico_nom
                )
            except Exception as e:
                print(f"[SHAREPOINT CLIENT NOTIF ERROR] {e}")

        threading.Thread(target=_send_sp_notification, daemon=True).start()

    data = schemas.ClienteResponse.model_validate(cliente).model_dump()
    return success_response(
        message="Enlace de SharePoint vinculado exitosamente y servicios actualizados a Finalizado",
        data=data
    )

@router.put("/{id_cliente}/admin-verificar")
@router.patch("/{id_cliente}/verificar")
def admin_verificar_cliente(
    id_cliente: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """El administrador marca un cliente como verificado directamente. Solo administrador."""
    cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == id_cliente).first()
    if not cliente:
        from app.shared.exceptions.exceptions import NotFoundException
        raise NotFoundException("Cliente no encontrado")
    cliente.verificado = True
    db.commit()
    db.refresh(cliente)
    data = schemas.ClienteResponse.model_validate(cliente).model_dump()
    return success_response(message="Cliente verificado exitosamente", data=data)

@router.post("/completar-verificacion")
def completar_verificacion_cliente(
    request: schemas.CompletarVerificacionClienteRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Guarda Cédula/NIT, Nombre Completo y Fecha de Nacimiento del cliente autenticado y marca verificado=True.
    Si el NIT ya pertenece a otra cuenta, solicita autenticación/contraseña de la cuenta anterior para transferirlo.
    """
    from app.infrastructure.security.jwt_handler import verify_password
    from app.shared.exceptions.exceptions import ConflictException, UnauthorizedException, BadRequestException

    raw_n = (request.nombre or "").strip()
    raw_a1 = (request.apellido_1 or "").strip()
    full_name = " ".join([p for p in [raw_n, raw_a1] if p]).strip() or "Cliente"

    num_doc = (request.numero_documento or request.cedula or "").strip()
    if num_doc and len(num_doc) > 20:
        raise BadRequestException("El número de documento no puede exceder los 20 caracteres.")

    if request.telefono and len(str(request.telefono).strip()) > 20:
        raise BadRequestException("El número de teléfono no puede exceder los 20 caracteres.")

    tipo_doc = (request.tipo_documento or "CC").upper()
    tipo_nombre = "Cédula de Ciudadanía" if tipo_doc == "CC" else ("NIT" if tipo_doc == "NIT" else "Documento")
    fecha_doc = request.fecha_expedicion or request.fecha_nacimiento

    cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
    if not cliente:
        cliente = ClienteModel(
            id_usuario=current_user.id_usuarios,
            nombre=full_name,
            apellido_1="",
            apellido_2="",
            numero_documento=num_doc,
            fecha_expedicion=fecha_doc,
            fecha_nacimiento=fecha_doc,
            telefono=request.telefono,
            verificado=False
        )
        db.add(cliente)
        db.flush()

    if num_doc:
        # Buscar si el documento / Cédula / NIT pertenece a otro cliente
        other_cliente = db.query(ClienteModel).filter(
            ClienteModel.numero_documento == num_doc,
            ClienteModel.id_cliente != cliente.id_cliente
        ).first()

        if other_cliente:
            other_user = other_cliente.usuario
            nombre_titular = other_cliente.nombre or "Titular Anterior"
            email_titular = other_user.email if other_user else "cuenta_anterior@flymetrics.co"

            if not request.transfer_password:
                # Lanzar conflicto con los detalles de la cuenta anterior
                raise ConflictException(
                    f"El documento ({tipo_nombre}) '{num_doc}' ya se encuentra registrado y verificado en la cuenta de '{nombre_titular}' ({email_titular}). "
                    f"Para transferir la titularidad a tu cuenta actual, por favor confirma la contraseña de la cuenta anterior.",
                    errors=[{
                        "nit": num_doc,
                        "documento": num_doc,
                        "tipo_documento": tipo_doc,
                        "nombre_titular": nombre_titular,
                        "email_titular": email_titular,
                        "requires_transfer_auth": True
                    }]
                )
            else:
                # Validar la contraseña del titular anterior
                if not other_user or not verify_password(request.transfer_password, other_user.contraseña):
                    raise UnauthorizedException(
                        f"La contraseña ingresada para la cuenta anterior es incorrecta. No se pudo autorizar la transferencia del documento ({tipo_nombre})."
                    )

                # Autorizado: desasociar documento de la cuenta anterior
                other_cliente.numero_documento = None
                other_cliente.verificado = False
                db.add(other_cliente)
                db.flush()

    cliente.numero_documento = num_doc
    cliente.nombre = full_name
    cliente.apellido_1 = ""
    cliente.apellido_2 = ""
    if fecha_doc:
        cliente.fecha_expedicion = fecha_doc
        cliente.fecha_nacimiento = fecha_doc
    if request.telefono:
        cliente.telefono = str(request.telefono).strip()
    cliente.verificado = True
        
    db.commit()
    db.refresh(cliente)
    
    data = {
        "id_cliente": cliente.id_cliente,
        "id_usuario": cliente.id_usuario,
        "email": current_user.email,
        "nombre": cliente.nombre,
        "apellido_1": "",
        "apellido_2": "",
        "tipo_documento": tipo_doc,
        "numero_documento": cliente.numero_documento,
        "fecha_expedicion": cliente.fecha_expedicion,
        "fecha_nacimiento": cliente.fecha_nacimiento,
        "telefono": cliente.telefono,
        "verificado": True
    }
    return success_response(message="✓ Verificación de datos personales completada con éxito.", data=data)




@router.put("/me")
def update_my_profile(
    request: schemas.ClienteUpdate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Actualiza el perfil del cliente autenticado directamente."""
    cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
    if not cliente:
        name = current_user.email.split('@')[0]
        cliente = ClienteModel(id_usuario=current_user.id_usuarios, nombre=name, verificado=False)
        db.add(cliente)
        db.flush()
    updated = ClienteUseCases.update_profile(db, cliente.id_cliente, request, current_user)
    data = schemas.ClienteResponse.model_validate(updated).model_dump()
    return success_response(message="Perfil de cliente actualizado exitosamente", data=data)

@router.put("/{id_cliente}")
def update_profile(id_cliente: int, request: schemas.ClienteUpdate, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Actualiza los datos del perfil de cliente."""
    cliente = ClienteUseCases.update_profile(db, id_cliente, request, current_user)
    data = schemas.ClienteResponse.model_validate(cliente).model_dump()
    return success_response(message="Perfil de cliente actualizado", data=data)

@router.post("/{id_cliente}/verificar-cc")
def verify_cc(id_cliente: int, request: schemas.ClienteVerifyRequest, db: Session = Depends(get_db), current_user: UsuarioModel = Depends(get_current_user)):
    """Valida los datos de cédula (CC) con el bot de IA de Flymetrics y marca el cliente como verificado."""
    result = ClienteUseCases.verify_document_ia(db, id_cliente, request, current_user)
    return success_response(message="Verificación de documento completada", data=result)


# ==============================================================================
# SEGURIDAD DE PERFIL: MODIFICACIÓN CON CÓDIGO DE 8 DÍGITOS
# ==============================================================================
@router.post("/seguridad/solicitar-codigo-perfil")
def solicitar_codigo_modificacion_perfil(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Genera y despacha código de 8 dígitos al correo del titular para autorizar cambio de información."""
    from app.shared.seguridad.otp_service import Otp8Service
    from app.shared.utils.email_service import EmailService

    email = current_user.email
    nombre = current_user.cliente.nombre if (current_user.cliente and current_user.cliente.nombre) else email.split("@")[0].capitalize()

    codigo_8 = Otp8Service.generar_codigo(email=email, proposito="perfil")

    try:
        EmailService.send_profile_update_8digit(
            to_email=email,
            codigo_8_digitos=codigo_8,
            nombre_usuario=nombre
        )
    except Exception as mail_err:
        print(f"[ERROR EMAIL OTP PERFIL] {mail_err}")

    return success_response(
        message=f"Código de seguridad de 8 dígitos enviado a {email}. Válido por 15 minutos.",
        data={"email": email, "validez_minutos": 15}
    )


@router.post("/seguridad/verificar-codigo-perfil")
def verificar_codigo_perfil(
    request: dict,
    current_user: UsuarioModel = Depends(get_current_user)
):
    """
    Paso 1: Valida el código de 8 dígitos sin quemarlo para autorizar
    el despliegue del formulario de edición de datos sensibles.
    """
    from app.shared.seguridad.otp_service import Otp8Service
    from app.shared.exceptions.exceptions import BadRequestException

    email = current_user.email
    codigo = str(request.get("codigo_8_digitos") or request.get("codigo") or "").strip()

    if not codigo:
        raise BadRequestException("El código de autorización de 8 dígitos es obligatorio.")

    res_otp = Otp8Service.verificar_codigo(email=email, codigo_ingresado=codigo, proposito="perfil", quemar=False)
    if not res_otp["valido"]:
        raise BadRequestException(res_otp["mensaje"])

    return success_response(
        message="Código de seguridad verificado correctamente. Puedes continuar modificando tu información.",
        data={"valido": True, "email": email}
    )


@router.put("/seguridad/perfil-seguro")
@router.patch("/seguridad/perfil-seguro")
def actualizar_perfil_seguro(
    request: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Paso 2: Valida y quema el código de 8 dígitos, aplicando las correcciones al perfil del cliente."""
    from app.shared.seguridad.otp_service import Otp8Service
    from app.shared.utils.email_service import EmailService
    from app.shared.exceptions.exceptions import BadRequestException
    from app.infrastructure.database.models.models import ClienteModel

    email = current_user.email
    codigo = str(request.get("codigo_8_digitos") or request.get("codigo") or "").strip()

    if not codigo:
        raise BadRequestException("El código de autorización de 8 dígitos es obligatorio para modificar tus datos de perfil.")

    # Validar y quemar el código
    res_otp = Otp8Service.verificar_codigo(email=email, codigo_ingresado=codigo, proposito="perfil", quemar=True)
    if not res_otp["valido"]:
        raise BadRequestException(res_otp["mensaje"])

    cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
    if not cliente:
        raise BadRequestException("Perfil de cliente no encontrado.")

    # Modificar correo electrónico si se suministra uno nuevo (autorizado con OTP de 8 dígitos)
    nuevo_email = str(request.get("email") or request.get("nuevo_email") or "").strip().lower()
    email_changed = False
    if nuevo_email and nuevo_email != email and "@" in nuevo_email:
        existe_email = db.query(UsuarioModel).filter(UsuarioModel.email == nuevo_email, UsuarioModel.id_usuarios != current_user.id_usuarios).first()
        if existe_email:
            raise BadRequestException(f"El correo electrónico '{nuevo_email}' ya se encuentra registrado en otra cuenta.")
        current_user.email = nuevo_email
        email = nuevo_email
        email_changed = True

    # Modificar campos autorizados existentes en ClienteModel (la contraseña NUNCA se modifica aquí)
    if "nombre" in request and request["nombre"]:
        cliente.nombre = str(request["nombre"]).strip().upper()
    if "apellido_1" in request and request["apellido_1"]:
        cliente.apellido_1 = str(request["apellido_1"]).strip().upper()
    if "empresa" in request and request["empresa"] is not None:
        pass  # Empresa se refleja en observaciones o campos extendidos
    
    # Validar documento sin desbordar columna String(20) en MySQL
    raw_doc = str(request.get("cedula_o_nit") or request.get("numero_documento") or "").strip()
    if raw_doc:
        if len(raw_doc) > 20:
            raise BadRequestException("El número de documento no puede exceder los 20 caracteres.")
        # Verificar que no pertenezca a otra cuenta
        other_c = db.query(ClienteModel).filter(
            ClienteModel.numero_documento == raw_doc,
            ClienteModel.id_cliente != cliente.id_cliente
        ).first()
        if other_c:
            raise BadRequestException(f"El documento '{raw_doc}' ya se encuentra registrado en otra cuenta.")
        cliente.numero_documento = raw_doc

    if "telefono" in request and request["telefono"]:
        raw_tel = str(request["telefono"]).strip()
        if len(raw_tel) > 20:
            raise BadRequestException("El número de teléfono no puede exceder los 20 caracteres.")
        cliente.telefono = raw_tel
    if "fecha_expedicion" in request and request["fecha_expedicion"]:
        cliente.fecha_expedicion = str(request["fecha_expedicion"]).strip()[:10]

    db.commit()
    db.refresh(cliente)

    # Generar nuevo token JWT si el correo fue actualizado para que la sesión permanezca activa
    new_token = None
    if email_changed:
        from app.infrastructure.security.jwt_handler import create_access_token
        new_token = create_access_token(
            data={"sub": current_user.email, "id": current_user.id_usuarios, "rol": current_user.rol}
        )

    # Enviar correo de auditoría y confirmación
    try:
        EmailService.send_profile_updated(to_email=email, nombre_usuario=cliente.nombre)
    except Exception as mail_err:
        print(f"[ERROR CONFIRMACION PERFIL EMAIL] {mail_err}")

    data = schemas.ClienteResponse.model_validate(cliente).model_dump()
    data["email"] = current_user.email
    if new_token:
        data["new_token"] = new_token

    return success_response(
        message="¡Información de perfil actualizada y verificada exitosamente!",
        data=data
    )


@router.delete("/{id_cliente}")
def delete_cliente(
    id_cliente: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Elimina un cliente y todos sus registros asociados. Solo administradores."""
    ClienteUseCases.delete_profile(db, id_cliente)
    return success_response(message="Cliente eliminado exitosamente")


