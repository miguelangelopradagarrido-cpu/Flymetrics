from fastapi import APIRouter, Depends, status, Request, Response
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.infrastructure.config.settings import settings
from app.application.dto import schemas
from app.application.use_cases.use_cases import AuthUseCases
from app.presentation.api.dependencies.auth import get_current_user
from app.infrastructure.database.models.models import UsuarioModel
from app.shared.responses.response import success_response
from app.shared.exceptions.exceptions import BadRequestException

router = APIRouter(prefix="/auth", tags=["Autenticación"])

async def get_login_credentials(request: Request) -> tuple:
    """Extrae las credenciales del cuerpo de la petición (JSON o Formulario).
    Retorna una tupla (UsuarioLogin, es_formulario).
    """
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form_data = await request.form()
        email = form_data.get("username")
        contraseña = form_data.get("password")
        if not email or not contraseña:
            raise BadRequestException("Credenciales incompletas en formulario de login")
        return schemas.UsuarioLogin(email=email, contraseña=contraseña), True
    else:
        try:
            body = await request.json()
            if "password" in body and "contraseña" not in body:
                body["contraseña"] = body.pop("password")
            return schemas.UsuarioLogin(**body), False
        except Exception:
            raise BadRequestException("Cuerpo de solicitud de login inválido (se esperaba JSON o Form)")

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    """Crea un nuevo registro en tabla_usuarios. Por seguridad, el registro público siempre asigna rol 'cliente'."""
    request.rol = "cliente"
    user = AuthUseCases.register_user(db, request)
    data = {
        "id_usuarios": user.id_usuarios,
        "email": user.email,
        "rol": user.rol,
        "fecha_de_creacion": user.fecha_de_creacion.isoformat() if user.fecha_de_creacion else None
    }

    # Despachar correo de bienvenida corporativo (Gmail API OAuth2)
    try:
        from app.shared.utils.email_service import EmailService
        EmailService.send_welcome(
            to_email=user.email,
            nombre_cliente=user.email.split('@')[0].capitalize()
        )
    except Exception as mail_err:
        print(f"[AUTH REGISTER EMAIL ERROR] {mail_err}")

    return success_response(message="Usuario registrado exitosamente", data=data, status_code=201)

@router.post("/login")
def login(
    response: Response,
    credentials_data: tuple = Depends(get_login_credentials),
    db: Session = Depends(get_db)
):
    """Valida credenciales y retorna un JWT firmado (HS256) con expiración de 8h y cookie segura HttpOnly."""
    credentials, es_formulario = credentials_data
    auth_data = AuthUseCases.login_user(db, credentials)
    
    # Fijar cookie segura HttpOnly para protección total contra robo de tokens por XSS
    jwt_token = auth_data.get("token")
    if jwt_token:
        is_prod = getattr(settings, "ENVIRONMENT", "development") == "production"
        response.set_cookie(
            key="fm_access_token",
            value=jwt_token,
            httponly=True,
            samesite="lax",
            secure=is_prod,
            max_age=getattr(settings, "JWT_EXPIRE_MINUTES", 480) * 60,
            path="/"
        )

    if es_formulario:
        # Formato estándar de OAuth2 para Swagger UI
        return {
            "access_token": auth_data["token"],
            "token_type": "bearer"
        }
    
    return success_response(message="Inicio de sesión exitoso", data=auth_data)

@router.post("/google")
def google_login(
    response: Response,
    request: schemas.GoogleLoginRequest,
    db: Session = Depends(get_db)
):
    """Simula el inicio de sesión con Google OAuth. Retorna un token JWT y fija cookie HttpOnly."""
    auth_data = AuthUseCases.login_google(db, request)
    jwt_token = auth_data.get("token")
    if jwt_token:
        is_prod = getattr(settings, "ENVIRONMENT", "development") == "production"
        response.set_cookie(
            key="fm_access_token",
            value=jwt_token,
            httponly=True,
            samesite="lax",
            secure=is_prod,
            max_age=getattr(settings, "JWT_EXPIRE_MINUTES", 480) * 60,
            path="/"
        )
    return success_response(message="Autenticación con Google exitosa", data=auth_data)

@router.get("/google-config")
def get_google_config():
    """Retorna el Client ID oficial de Google configurado en el servidor para evitar discrepancias de origen/credencial."""
    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "") or "1044490043488-n2l2jjvnpq2mn8km4ag62r4t4af10vb6.apps.googleusercontent.com"
    return success_response(
        message="Configuración pública de Google OAuth obtenida",
        data={"client_id": client_id}
    )

@router.post("/google-completar-perfil")
def google_completar_perfil(
    payload: dict,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Guarda los datos de teléfono y cédula/NIT del usuario cliente registrado vía Google."""
    from app.infrastructure.database.models.models import ClienteModel
    cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
    telefono = str(payload.get("telefono", "")).strip()
    numero_documento = str(payload.get("numero_documento", "")).strip()
    departamento = str(payload.get("departamento", "")).strip()
    nombre = str(payload.get("nombre", "")).strip()

    if not cliente:
        cliente = ClienteModel(
            id_usuario=current_user.id_usuarios,
            nombre=nombre or current_user.email.split('@')[0],
            apellido_1="",
            apellido_2="",
            telefono=telefono,
            numero_documento=numero_documento,
            departamento=departamento,
            verificado=True
        )
        db.add(cliente)
    else:
        if telefono:
            cliente.telefono = telefono
        if numero_documento:
            cliente.numero_documento = numero_documento
        if departamento:
            cliente.departamento = departamento
        if nombre:
            cliente.nombre = nombre
        cliente.verificado = True
    db.commit()
    db.refresh(cliente)
    return success_response(
        message="Perfil completado exitosamente",
        data={
            "completado": True,
            "nombre": cliente.nombre,
            "telefono": cliente.telefono,
            "numero_documento": cliente.numero_documento
        }
    )

@router.post("/logout")
def logout_endpoint(response: Response):
    """Revoca la cookie HttpOnly de sesión activa en el navegador."""
    response.delete_cookie(key="fm_access_token", path="/", httponly=True, samesite="lax")
    return success_response(message="Sesión cerrada exitosamente", data={"logged_out": True})

@router.get("/me")
def get_me(current_user: UsuarioModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retorna datos del usuario activo según el JWT recibido enriquecido con perfil."""
    data = {
        "id_usuarios": current_user.id_usuarios,
        "email": current_user.email,
        "rol": current_user.rol,
        "fecha_de_creacion": current_user.fecha_de_creacion.isoformat() if current_user.fecha_de_creacion else None
    }
    
    if current_user.rol == "tecnico":
        from app.infrastructure.database.models.models import TecnicoModel
        tec = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
        if not tec:
            tec = db.query(TecnicoModel).filter(TecnicoModel.email == current_user.email).first()
        if tec:
            data["id_tecnico"] = tec.id_tecnico
            data["nombre"] = tec.nombre
            data["apellido_1"] = tec.apellido_1 or ""
            data["telefono"] = tec.telefono or ""
            data["certificacion"] = tec.certificacion or "RPAS-A-102030"
            data["estado"] = tec.estado or "disponible"
        else:
            default_nom = current_user.email.split('@')[0].capitalize()
            data["nombre"] = default_nom
            data["apellido_1"] = "Piloto"
            data["telefono"] = ""
            data["certificacion"] = "RPAS-A-102030"
            data["estado"] = "disponible"
    elif current_user.rol == "cliente":
        if current_user.cliente:
            c = current_user.cliente
            data["id_cliente"] = c.id_cliente
            data["nombre"] = c.nombre
            data["apellido_1"] = c.apellido_1 or ""
            data["telefono"] = c.telefono or ""
            data["numero_documento"] = c.numero_documento or ""
            data["link_alegra"] = getattr(c, 'link_alegra', None)
            data["link_sharepoint"] = getattr(c, 'link_sharepoint', None)
            data["verificado"] = bool(c.verificado)
            # Detectar si es primer ingreso o clave no personalizada
            data["primer_ingreso"] = not bool(c.verificado and c.numero_documento and c.telefono)
        else:
            data["nombre"] = current_user.email.split('@')[0].capitalize()
            data["apellido_1"] = "Cliente"
            data["primer_ingreso"] = True
    elif current_user.rol == "administrador":
        data["nombre"] = "Administrador"
        data["apellido_1"] = "Flymetrics"
        data["primer_ingreso"] = False

    return success_response(message="Usuario obtenido exitosamente", data=data)

import random

@router.post("/enviar-codigo-verificacion")
def enviar_codigo_verificacion(
    request: schemas.SolicitudCodigoRequest,
    db: Session = Depends(get_db)
):
    """Genera y guarda un código OTP numérico de 6 dígitos para el correo del usuario."""
    from app.infrastructure.database.models.models import ClienteModel
    user = db.query(UsuarioModel).filter(UsuarioModel.email == request.email).first()
    if not user:
        raise BadRequestException("El correo especificado no se encuentra registrado en el sistema.")
    
    # Generar OTP de 6 dígitos
    codigo = f"{random.randint(100000, 999999)}"
    
    if user.cliente:
        user.cliente.codigo_verificacion = codigo
    else:
        cliente = ClienteModel(
            id_usuario=user.id_usuarios,
            nombre=user.email.split('@')[0],
            apellido_1="Cliente",
            codigo_verificacion=codigo,
            verificado=False
        )
        db.add(cliente)
    
    db.commit()
    
    # Enviar correo real / SMTP con la plantilla de verificación
    from app.shared.utils.email_service import send_otp_email
    send_otp_email(request.email, codigo)
    
    return success_response(
        message=f"Código de verificación enviado exitosamente a {request.email}",
        data={"enviado": True, "email": request.email}
    )

@router.post("/verificar-codigo-correo")
def verificar_codigo_correo(
    request: schemas.VerificacionCodigoRequest,
    db: Session = Depends(get_db)
):
    """Valida el código OTP de 6 dígitos ingresado por el usuario."""
    user = db.query(UsuarioModel).filter(UsuarioModel.email == request.email).first()
    if not user or not user.cliente:
        raise BadRequestException("No se encontró el registro de la cuenta.")
    
    if not user.cliente.codigo_verificacion or user.cliente.codigo_verificacion != request.codigo.strip():
        raise BadRequestException("El código ingresado es incorrecto o ha expirado.")
    
    # Quemar el código para uso único (single-use OTP)
    user.cliente.codigo_verificacion = None
    db.commit()

    return success_response(
        message="Correo electrónico confirmado. Procede a registrar tu Cédula, Nombre Completo y Fecha de Nacimiento.",
        data={"verificado_correo": True, "email": request.email}
    )

@router.post("/change-password")
@router.post("/cambiar-contrasena")
def change_password(
    request: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Permite a cualquier usuario autenticado cambiar su contraseña en la base de datos."""
    from app.infrastructure.security.jwt_handler import hash_password, verify_password
    current_pwd = request.get("current_password") or request.get("contrasena_actual") or request.get("current_pwd")
    new_pwd = request.get("new_password") or request.get("nueva_contrasena") or request.get("contraseña") or request.get("password")
    
    if not new_pwd or len(str(new_pwd).strip()) < 6:
        raise BadRequestException("La nueva contraseña debe tener al menos 6 caracteres")
        
    if current_pwd and not verify_password(current_pwd, current_user.contraseña):
        raise BadRequestException("La contraseña actual es incorrecta")
        
    current_user.contraseña = hash_password(str(new_pwd).strip())
    db.commit()
    db.refresh(current_user)
    return success_response(message="Contraseña actualizada exitosamente en la base de datos")


# ==============================================================================
# SISTEMA DE SEGURIDAD: VERIFICACIÓN DE 8 DÍGITOS PARA CONTRASEÑA
# ==============================================================================
@router.post("/solicitar-codigo-password")
def solicitar_codigo_password(request: dict, db: Session = Depends(get_db)):
    """Genera y envía un código numérico de 8 dígitos de alta seguridad al correo para recuperar o cambiar contraseña."""
    from app.shared.seguridad.otp_service import Otp8Service
    from app.shared.utils.email_service import EmailService

    email = str(request.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise BadRequestException("Por favor proporciona un correo electrónico válido")

    user = db.query(UsuarioModel).filter(UsuarioModel.email == email).first()
    if not user:
        # Por seguridad contra enumeración, respondemos con éxito genérico
        return success_response(
            message=f"Si el correo está registrado, recibirás un código de seguridad de 8 dígitos en breve.",
            data={"email": email}
        )

    # Obtener nombre del usuario
    nombre_user = email.split("@")[0].capitalize()
    if user.cliente and user.cliente.nombre:
        nombre_user = user.cliente.nombre
    elif user.tecnico and user.tecnico.nombre:
        nombre_user = user.tecnico.nombre

    # Generar código criptográfico de 8 dígitos
    codigo_8 = Otp8Service.generar_codigo(email=email, proposito="password")

    # Despachar correo oficial mediante Gmail API OAuth2
    try:
        EmailService.send_password_reset_8digit(
            to_email=email,
            codigo_8_digitos=codigo_8,
            nombre_usuario=nombre_user
        )
    except Exception as mail_err:
        print(f"[ERROR EMAIL OTP 8 DÍGITOS] {mail_err}")

    return success_response(
        message=f"Código de seguridad de 8 dígitos enviado exitosamente a {email}",
        data={"email": email, "validez_minutos": 15}
    )


@router.post("/verificar-codigo-password")
def verificar_codigo_password(request: dict):
    """Verifica si el código de 8 dígitos ingresado por el usuario es correcto y está vigente."""
    from app.shared.seguridad.otp_service import Otp8Service

    email = str(request.get("email") or "").strip().lower()
    codigo = str(request.get("codigo") or "").strip()

    if not email or not codigo:
        raise BadRequestException("Correo y código de 8 dígitos son requeridos")

    resultado = Otp8Service.verificar_codigo(email=email, codigo_ingresado=codigo, proposito="password", quemar=False)
    if not resultado["valido"]:
        raise BadRequestException(resultado["mensaje"])

    return success_response(
        message=resultado["mensaje"],
        data={"email": email, "codigo_verificado": True}
    )


@router.post("/restablecer-password-seguro")
def restablecer_password_seguro(request: dict, db: Session = Depends(get_db)):
    """Valida el código de 8 dígitos y actualiza de forma segura la nueva contraseña hasheada con Bcrypt."""
    from app.shared.seguridad.otp_service import Otp8Service
    from app.shared.utils.email_service import EmailService
    from app.infrastructure.security.jwt_handler import hash_password

    email = str(request.get("email") or "").strip().lower()
    codigo = str(request.get("codigo") or "").strip()
    nueva_pwd = str(request.get("nueva_contrasena") or request.get("new_password") or request.get("password") or "").strip()
    confirmar_pwd = str(request.get("confirmar_contrasena") or request.get("confirm_password") or "").strip()

    if not email or not codigo:
        raise BadRequestException("Correo y código de 8 dígitos son requeridos")

    if not nueva_pwd or len(nueva_pwd) < 6:
        raise BadRequestException("La nueva contraseña debe tener al menos 6 caracteres")

    if confirmar_pwd and nueva_pwd != confirmar_pwd:
        raise BadRequestException("Las contraseñas ingresadas no coinciden")

    # Validar y quemar el código de 8 dígitos (single-use)
    resultado = Otp8Service.verificar_codigo(email=email, codigo_ingresado=codigo, proposito="password", quemar=True)
    if not resultado["valido"]:
        raise BadRequestException(resultado["mensaje"])

    user = db.query(UsuarioModel).filter(UsuarioModel.email == email).first()
    if not user:
        raise BadRequestException("No se encontró el usuario en el sistema")

    user.contraseña = hash_password(nueva_pwd)
    db.commit()
    db.refresh(user)

    # Notificación de confirmación de cambio de contraseña
    try:
        nombre_user = user.cliente.nombre if (user.cliente and user.cliente.nombre) else email.split("@")[0].capitalize()
        EmailService.send_password_changed(to_email=email, nombre_usuario=nombre_user)
    except Exception as mail_err:
        print(f"[ERROR CONFIRMACION PWD EMAIL] {mail_err}")

    return success_response(
        message="¡Contraseña actualizada exitosamente! Ya puedes iniciar sesión con tu nueva clave.",
        data={"email": email, "actualizado": True}
    )


@router.post("/primer-ingreso-completar")
def primer_ingreso_completar(
    request: dict,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Flujo de seguridad obligatorio para clientes de primera vez (Demo Gratuita o nueva cuenta):
    1. Modifica la contraseña inicial por una segura elegida por el cliente.
    2. Verifica y actualiza datos de coherencia (nombre, teléfono, cédula/NIT).
    3. Carga o vincula automáticamente la finca de su demostración.
    """
    from app.shared.exceptions.exceptions import BadRequestException
    from app.infrastructure.security.jwt_handler import hash_password
    from app.infrastructure.database.models.models import ClienteModel, FincaModel

    nueva_contrasena = str(request.get("nueva_contrasena") or request.get("contrasena") or "").strip()
    nombre = str(request.get("nombre") or "").strip()
    telefono = str(request.get("telefono") or "").strip()
    numero_documento = str(request.get("numero_documento") or "").strip()

    if not nueva_contrasena or len(nueva_contrasena) < 6:
        raise BadRequestException("La nueva contraseña debe tener al menos 6 caracteres.")

    # 1. Actualizar contraseña
    current_user.contraseña = hash_password(nueva_contrasena)

    # 2. Actualizar o crear ClienteModel
    cliente = current_user.cliente
    if not cliente:
        cliente = ClienteModel(
            id_usuario=current_user.id_usuarios,
            nombre=nombre or current_user.email.split('@')[0].capitalize(),
            telefono=telefono,
            numero_documento=numero_documento,
            verificado=True
        )
        db.add(cliente)
        db.flush()
    else:
        if nombre:
            cliente.nombre = nombre
        if telefono:
            cliente.telefono = telefono
        if numero_documento:
            cliente.numero_documento = numero_documento
        cliente.verificado = True

    # 3. Autocargar o asociar fincas pendientes si existen huérfanas con el mismo doc o teléfono
    if cliente.id_cliente:
        fincas_cliente = db.query(FincaModel).filter(FincaModel.id_cliente == cliente.id_cliente).all()
        # Si no tiene fincas asignadas directamente, intentar vincular predios creados en reservas rápidas por teléfono
        if not fincas_cliente and telefono:
            otros_clientes = db.query(ClienteModel).filter(
                ClienteModel.telefono == telefono,
                ClienteModel.id_cliente != cliente.id_cliente
            ).all()
            for oc in otros_clientes:
                f_huerfanas = db.query(FincaModel).filter(FincaModel.id_cliente == oc.id_cliente).all()
                for fh in f_huerfanas:
                    fh.id_cliente = cliente.id_cliente

    db.commit()
    db.refresh(current_user)

    # Retornar datos de finca autocargada
    fincas_activas = db.query(FincaModel).filter(FincaModel.id_cliente == cliente.id_cliente).all()
    finca_data = [{
        "id_finca": f.id_finca,
        "nombre_finca": f.nombre_finca,
        "municipio": f.ubicacion_municipio or "",
        "hectareas": float(f.hectareas) if f.hectareas else 0.0
    } for f in fincas_activas]

    return success_response(
        message="Perfil verificado y contraseña establecida exitosamente.",
        data={
            "completado": True,
            "id_cliente": cliente.id_cliente,
            "nombre": cliente.nombre,
            "fincas": finca_data
        }
    )



