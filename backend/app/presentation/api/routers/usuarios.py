from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import AdminUsuarioUseCases, AuthUseCases
from app.presentation.api.dependencies.auth import RoleChecker
from app.infrastructure.database.models.models import UsuarioModel
from app.shared.responses.response import success_response

router = APIRouter(prefix="/admin/usuarios", tags=["Administración de Usuarios"])

# Restringir router exclusivamente a Administradores
admin_required = RoleChecker(["administrador"])

@router.get("")
def list_usuarios(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Lista todos los usuarios del sistema junto con sus perfiles de forma detallada. Solo administradores."""
    usuarios = AdminUsuarioUseCases.list_all_users(db)
    
    # Construir respuesta detallada con perfiles asociados
    data = []
    for u in usuarios:
        profile_data = None
        if u.rol == "cliente" and u.cliente:
            profile_data = {
                "id_cliente": u.cliente.id_cliente,
                "nombre": u.cliente.nombre,
                "apellido_1": u.cliente.apellido_1,
                "apellido_2": u.cliente.apellido_2,
                "telefono": u.cliente.telefono,
                "ciudad_expedicion": u.cliente.ciudad_expedicion,
                "fecha_expedicion": u.cliente.fecha_expedicion,
                "verificado": u.cliente.verificado
            }
        elif u.rol == "tecnico" and u.tecnico:
            profile_data = {
                "id_tecnico": u.tecnico.id_tecnico,
                "nombre": u.tecnico.nombre,
                "apellido_1": u.tecnico.apellido_1,
                "apellido_2": u.tecnico.apellido_2,
                "telefono": u.tecnico.telefono,
                "certificacion": u.tecnico.certificacion,
                "estado": u.tecnico.estado
            }
            
        data.append({
            "id_usuarios": u.id_usuarios,
            "email": u.email,
            "rol": u.rol,
            "fecha_de_creacion": u.fecha_de_creacion.isoformat() if u.fecha_de_creacion else None,
            "perfil": profile_data
        })
        
    return success_response(message="Listado de usuarios obtenido", data=data)

@router.post("", status_code=status.HTTP_201_CREATED)
def crear_usuario_por_admin(
    request: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Permite al administrador registrar directamente cualquier tipo de cuenta (Admin, Técnico o Cliente)."""
    user = AuthUseCases.register_user(db, request)
    data = {
        "id_usuarios": user.id_usuarios,
        "email": user.email,
        "rol": user.rol,
        "fecha_de_creacion": user.fecha_de_creacion.isoformat() if user.fecha_de_creacion else None
    }
    return success_response(message="Usuario creado exitosamente por el administrador", data=data, status_code=201)

@router.put("/{id_usuario}")
def actualizar_usuario_por_admin(
    id_usuario: int,
    payload: dict = None,
    email: str = Query(None, description="Nuevo correo electrónico"),
    rol: str = Query(None, description="Nuevo rol: cliente, tecnico, administrador"),
    contraseña: str = Query(None, description="Nueva contraseña (mínimo 6 caracteres)"),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Permite al administrador actualizar email, rol y/o contraseña de cualquier usuario."""
    if payload:
        email = payload.get("email", email)
        rol = payload.get("rol", rol)
        contraseña = payload.get("contraseña", payload.get("nueva_contrasena", contraseña))

    user = AdminUsuarioUseCases.update_user_by_admin(db, id_usuario, email, rol)
    
    if contraseña:
        AdminUsuarioUseCases.reset_password_by_admin(db, id_usuario, contraseña)
    
    data = {
        "id_usuarios": user.id_usuarios,
        "email": user.email,
        "rol": user.rol
    }
    return success_response(message="Usuario actualizado exitosamente", data=data)

@router.put("/{id_usuario}/rol")
def actualizar_rol_usuario(
    id_usuario: int,
    request: schemas.UsuarioUpdateRol,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    user = AdminUsuarioUseCases.update_user_by_admin(db, id_usuario, rol=request.rol)
    return success_response(message="Rol de usuario actualizado exitosamente", data={"id_usuarios": user.id_usuarios, "rol": user.rol})

@router.put("/{id_usuario}/password")
@router.post("/{id_usuario}/password")
def restablecer_password_usuario(
    id_usuario: int,
    request: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    nueva_pass = request.get("nueva_contrasena") or request.get("contraseña") or request.get("password") or request.get("nueva_contraseña")
    if not nueva_pass or len(str(nueva_pass).strip()) < 6:
        from app.shared.exceptions.exceptions import ValidationException
        raise ValidationException("La contraseña debe tener al menos 6 caracteres.")
    
    user = AdminUsuarioUseCases.reset_password_by_admin(db, id_usuario, str(nueva_pass).strip())
    return success_response(message="Contraseña restablecida exitosamente", data={"id_usuarios": user.id_usuarios})

@router.get("/config/sistema")
def get_system_config(
    db: Session = Depends(get_db)
):
    """Obtiene la configuración corporativa persistida en base de datos (público para sincronización de canales)."""
    from app.infrastructure.database.models.models import SystemConfigModel
    config_record = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "perfil_corporativo").first()
    import json
    default_data = {
        "empresa": "Flymetrics Colombia S.A.S.",
        "nit": "900.123.456-7",
        "telefono": "+57 314 3764972",
        "whatsapp": "+57 314 3764972",
        "email": "comercial@flymetrics.com.co",
        "direccion": "Avenida El Dorado #68b-70, Bogotá D.C.",
        "wa_template_24h": "Hola {nombre}, te contactamos desde Flymetrics Colombia sobre tu solicitud de cotización para {servicio}.",
        "wa_template_agendar": "Hola Flymetrics Colombia, acabo de agendar una solicitud de servicio / demostración:\nRadicado: {radicado}\nProductor: {nombre} (CC/NIT: {cedula})\nFinca: {finca} en {municipio} ({departamento})\nCultivo: {cultivo} ({hectareas} Ha)\nServicio: {servicio}\nFecha programada: {fecha}\nUbicación / Maps: {ubicacion_maps}\nDeseo coordinar detalles técnicos de campo con el piloto.",
        "wa_template_general": "Hola Flymetrics, deseo solicitar asesoría e información técnica sobre sus servicios de drones agrícolas.",
        "zonas_mayor_presencia": [
            {"nombre": "Cundinamarca", "tag": "Base Central", "lat": 4.7110, "lng": -74.0721, "descripcion": "Sabana de Bogotá, Facatativá, Chía, Madrid — Flores, Papa y Hortalizas", "servicio": "Monitoreo Multiespectral, Cartografía y Aspersión", "demanda": "Base Central y Operaciones Sabana"},
            {"nombre": "Meta", "tag": "Operación Continua", "lat": 4.1420, "lng": -73.6266, "descripcion": "Villavicencio, Puerto López, Granada — Palma, Soya, Maíz y Ganadería", "servicio": "Fumigación de Palma, Soya, Maíz y Ganadería", "demanda": "Operación Continua Llanos"},
            {"nombre": "Huila", "tag": "Laderas y Valles", "lat": 2.9273, "lng": -75.2819, "descripcion": "Neiva, Campoalegre, Pitalito — Café de Especialidad, Arroz y Frutales", "servicio": "Aspersión en Café de Especialidad, Arroz y Frutales", "demanda": "Laderas y Valles Andinos"},
            {"nombre": "Tolima", "tag": "Planicies de Riego", "lat": 4.1420, "lng": -74.8880, "descripcion": "Espinal, Ibagué, Saldaña — Arroz, Maíz, Algodón y Pasturas", "servicio": "Fumigación y Fertilización de Arroz, Maíz y Pastos", "demanda": "Planicies de Riego"}
        ]
    }
    data = json.loads(config_record.valor) if config_record and config_record.valor else {}
    if isinstance(data, dict):
        merged = {**default_data, **data}
        if not merged.get("zonas_mayor_presencia"):
            merged["zonas_mayor_presencia"] = default_data["zonas_mayor_presencia"]
        data = merged
    else:
        data = default_data
    return success_response(message="Configuración del sistema obtenida", data=data)

@router.put("/config/sistema")
def save_system_config(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Guarda y persiste la configuración corporativa en la base de datos."""
    from app.infrastructure.database.models.models import SystemConfigModel
    import json
    config_record = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "perfil_corporativo").first()
    if not config_record:
        config_record = SystemConfigModel(clave="perfil_corporativo", valor=json.dumps(payload))
        db.add(config_record)
    else:
        config_record.valor = json.dumps(payload)
    db.commit()
    return success_response(message="Configuración corporativa guardada exitosamente en la base de datos", data=payload)

@router.post("/zonas")
def agregar_zona_admin(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Agrega una nueva zona de mayor demanda y presencia a la base de datos."""
    from fastapi import HTTPException
    try:
        lat_f = float(payload.get("lat") if payload.get("lat") is not None else payload.get("latitud", 4.711))
        lng_f = float(payload.get("lng") if payload.get("lng") is not None else payload.get("longitud", -74.072))
        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
            raise ValueError()
        payload["lat"] = lat_f
        payload["lng"] = lng_f
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Coordenadas inválidas. La latitud debe estar entre -90 y 90, y longitud entre -180 y 180.")

    from app.infrastructure.database.models.models import SystemConfigModel
    import json
    config_record = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "perfil_corporativo").first()
    cfg = json.loads(config_record.valor) if config_record and config_record.valor else {}
    zonas = cfg.get("zonas_mayor_presencia", [])
    zonas.append(payload)
    cfg["zonas_mayor_presencia"] = zonas
    if not config_record:
        config_record = SystemConfigModel(clave="perfil_corporativo", valor=json.dumps(cfg))
        db.add(config_record)
    else:
        config_record.valor = json.dumps(cfg)
    db.commit()
    return success_response(message="Zona de mayor demanda agregada exitosamente a la base de datos", data=zonas)

@router.put("/zonas/{index}")
def actualizar_zona_admin(
    index: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Actualiza una zona de mayor demanda por su índice en la base de datos."""
    from fastapi import HTTPException
    try:
        lat_f = float(payload.get("lat") if payload.get("lat") is not None else payload.get("latitud", 4.711))
        lng_f = float(payload.get("lng") if payload.get("lng") is not None else payload.get("longitud", -74.072))
        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
            raise ValueError()
        payload["lat"] = lat_f
        payload["lng"] = lng_f
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Coordenadas inválidas. La latitud debe estar entre -90 y 90, y longitud entre -180 y 180.")

    from app.infrastructure.database.models.models import SystemConfigModel
    import json
    config_record = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "perfil_corporativo").first()
    cfg = json.loads(config_record.valor) if config_record and config_record.valor else {}
    zonas = cfg.get("zonas_mayor_presencia", [])
    if 0 <= index < len(zonas):
        zonas[index] = payload
    else:
        zonas.append(payload)
    cfg["zonas_mayor_presencia"] = zonas
    config_record.valor = json.dumps(cfg)
    db.commit()
    return success_response(message="Zona de mayor demanda modificada exitosamente en la base de datos", data=zonas)

@router.delete("/zonas/{index}")
def eliminar_zona_admin(
    index: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Elimina una zona de mayor demanda de la base de datos."""
    from app.infrastructure.database.models.models import SystemConfigModel
    import json
    config_record = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "perfil_corporativo").first()
    cfg = json.loads(config_record.valor) if config_record and config_record.valor else {}
    zonas = cfg.get("zonas_mayor_presencia", [])
    if 0 <= index < len(zonas):
        zonas.pop(index)
        cfg["zonas_mayor_presencia"] = zonas
        config_record.valor = json.dumps(cfg)
        db.commit()
    return success_response(message="Zona eliminada exitosamente de la base de datos", data=zonas)

@router.delete("/{id_usuario}")
def eliminar_usuario_por_admin(
    id_usuario: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Elimina una cuenta de usuario y sus perfiles de cliente/técnico asociados en cascada. Solo administradores."""
    from app.shared.exceptions.exceptions import BadRequestException
    if current_user.id_usuarios == id_usuario:
        raise BadRequestException("No puedes eliminar tu propia cuenta de administrador en sesión activa.")
    AdminUsuarioUseCases.delete_user_by_admin(db, id_usuario)
    return success_response(message="Usuario y perfiles asociados eliminados exitosamente")


# ==============================================================================
# CONFIGURACIÓN DE CORREOS CORPORATIVOS & REDIRECCIÓN DE BOTONES CON CLAVE MAESTRA
# ==============================================================================
from app.infrastructure.security.jwt_handler import hash_password, verify_password

@router.post("/config-correo/verificar-clave")
def verificar_clave_maestra_correo(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    Verifica la contraseña maestra antes de acceder a las credenciales de correo y URLs.
    Si es la primera vez (no existe clave guardada), la crea y la registra.
    """
    from app.infrastructure.database.models.models import SystemConfigModel
    from app.shared.exceptions.exceptions import BadRequestException, UnauthorizedException
    
    clave_ingresada = (payload.get("clave_maestra") or "").strip()
    if len(clave_ingresada) < 4:
        raise BadRequestException("La contraseña maestra debe tener al menos 4 caracteres.")

    rec_clave = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "clave_maestra_correo").first()
    if not rec_clave:
        # Primera vez: crearla
        rec_clave = SystemConfigModel(clave="clave_maestra_correo", valor=hash_password(clave_ingresada))
        db.add(rec_clave)
        db.commit()
        return success_response(message="Contraseña maestra creada y autorizada exitosamente", data={"autorizado": True, "primera_vez": True})

    # Ya existe: validar
    if not verify_password(clave_ingresada, rec_clave.valor):
        raise BadRequestException("Contraseña maestra incorrecta. Por favor verifica e intenta nuevamente.")

    return success_response(message="Acceso concedido a la configuración de correos", data={"autorizado": True, "primera_vez": False})


@router.get("/config-correo")
def get_config_correo_admin(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Obtiene la configuración actual de servidor de correos y enlaces de redirección."""
    from app.infrastructure.database.models.models import SystemConfigModel
    from app.infrastructure.config.settings import settings
    import json

    rec = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "config_correo_seguro").first()
    default_cfg = {
        "smtp_host": getattr(settings, "SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(getattr(settings, "SMTP_PORT", 587)),
        "smtp_user": getattr(settings, "SMTP_USER", "comercial@flymetrics.com.co"),
        "sender_name": getattr(settings, "GMAIL_SENDER_NAME", "Flymetrics Colombia"),
        "url_botones_correo": getattr(settings, "PORTAL_CLIENTE_URL", "http://localhost:3000/pages/cliente.html"),
        "tiene_password": bool(getattr(settings, "SMTP_PASSWORD", "")),
        "tiene_clave_maestra": bool(db.query(SystemConfigModel).filter(SystemConfigModel.clave == "clave_maestra_correo").first())
    }

    if rec and rec.valor:
        try:
            stored = json.loads(rec.valor)
            if isinstance(stored, dict):
                # No exponer el password en plano
                has_pwd = bool(stored.get("smtp_password"))
                stored["tiene_password"] = has_pwd or default_cfg["tiene_password"]
                stored.pop("smtp_password", None)
                default_cfg.update(stored)
        except Exception:
            pass

    return success_response(message="Configuración de correo obtenida", data=default_cfg)


@router.post("/config-correo")
def save_config_correo_admin(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Guarda las credenciales de correo y la URL de redirección de botones en base de datos."""
    from app.infrastructure.database.models.models import SystemConfigModel
    from app.shared.exceptions.exceptions import BadRequestException
    import json

    rec = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "config_correo_seguro").first()
    data = {}
    if rec and rec.valor:
        try:
            data = json.loads(rec.valor)
        except Exception:
            data = {}

    smtp_host = payload.get("smtp_host", data.get("smtp_host", "smtp.gmail.com")).strip()
    smtp_port = int(payload.get("smtp_port", data.get("smtp_port", 587)))
    smtp_user = payload.get("smtp_user", data.get("smtp_user", "")).strip()
    sender_name = payload.get("sender_name", data.get("sender_name", "Flymetrics Colombia")).strip()
    url_botones = payload.get("url_botones_correo", data.get("url_botones_correo", "http://localhost:3000")).strip()
    if url_botones and not url_botones.startswith("http://") and not url_botones.startswith("https://"):
        url_botones = f"https://{url_botones}"
    nueva_clave_maestra = payload.get("nueva_clave_maestra", "").strip()

    data["smtp_host"] = smtp_host
    data["smtp_port"] = smtp_port
    data["smtp_user"] = smtp_user
    data["sender_name"] = sender_name
    data["url_botones_correo"] = url_botones

    # Si viene password SMTP nuevo, actualizarlo (evitar que contraseñas dummy o de prueba como '12345678' sobrescriban la de producción)
    smtp_pass = payload.get("smtp_password")
    if smtp_pass and str(smtp_pass).strip():
        clean_pwd = str(smtp_pass).strip()
        # Si es un password genérico de prueba pero el entorno o BD ya tienen la contraseña de aplicación oficial de 16 caracteres, no sobrescribir
        if clean_pwd in ["12345678", "password", "123456", "admin", "test"]:
            pass
        else:
            data["smtp_password"] = clean_pwd

    if not rec:
        rec = SystemConfigModel(clave="config_correo_seguro", valor=json.dumps(data))
        db.add(rec)
    else:
        rec.valor = json.dumps(data)

    # Actualizar clave maestra si se solicitó
    if nueva_clave_maestra:
        if len(nueva_clave_maestra) < 4:
            raise BadRequestException("La nueva clave maestra debe tener al menos 4 caracteres.")
        rec_m = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "clave_maestra_correo").first()
        if not rec_m:
            rec_m = SystemConfigModel(clave="clave_maestra_correo", valor=hash_password(nueva_clave_maestra))
            db.add(rec_m)
        else:
            rec_m.valor = hash_password(nueva_clave_maestra)

    db.commit()
    return success_response(message="Configuración de correo y redirección de botones guardada exitosamente")

