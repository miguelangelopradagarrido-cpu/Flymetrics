import logging
import threading
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, or_
from datetime import datetime, time, timedelta, date
from decimal import Decimal
import random

logger = logging.getLogger(__name__)

from app.infrastructure.database.models.models import (
    UsuarioModel, ClienteModel, TecnicoModel, FincaModel,
    ServicioModel, AgendaModel, ReporteVueloModel, DroneModel,
    MantenimientoModel, EntregableModel, PagoModel, NotificacionModel,
    PQRModel, MensajePQRModel
)
from app.application.dto import schemas
from app.infrastructure.security.jwt_handler import hash_password, verify_password, create_access_token
from app.infrastructure.external.google_maps import GoogleMapsService
from app.infrastructure.external.ai_verifier import AIVerifierService
from app.infrastructure.external.whatsapp_service import WhatsAppService
from app.infrastructure.external.google_auth import GoogleAuthService
from app.shared.exceptions.exceptions import (
    NotFoundException, BadRequestException, ConflictException, UnauthorizedException, ForbiddenException
)

# ==========================================
# UTILIDADES DE LIMPIEZA DE NOMBRES
# ==========================================
GENERIC_ROLE_WORDS = {"tecnico", "técnico", "piloto", "cliente", "registrado", "usuario"}

def deduplicate_name_phrase(name_str: str) -> str:
    """Elimina duplicaciones de frases o palabras consecutivas/sufijos en nombres."""
    if not name_str:
        return ""
    words = name_str.strip().split()
    n = len(words)
    if n <= 1:
        return " ".join(words)
    for k in range(n // 2, 0, -1):
        for start in range(n - 2 * k + 1):
            chunk1 = [w.lower() for w in words[start : start + k]]
            chunk2 = [w.lower() for w in words[start + k : start + 2 * k]]
            if chunk1 == chunk2:
                del words[start + k : start + 2 * k]
                return deduplicate_name_phrase(" ".join(words))
    for suffix_len in range(n - 1, 0, -1):
        suffix = [w.lower() for w in words[-suffix_len:]]
        prefix = [w.lower() for w in words[:-suffix_len]]
        if len(prefix) >= suffix_len and prefix[-suffix_len:] == suffix:
            del words[-suffix_len:]
            return deduplicate_name_phrase(" ".join(words))
    return " ".join(words)

def clean_person_name(nombre: str = "", apellido_1: str = "", apellido_2: str = "", default: str = "") -> str:
    """Limpia palabras de rol genéricas ('Técnico', 'Piloto', etc.) y deduplica frases repetidas."""
    raw_parts = [nombre or "", apellido_1 or "", apellido_2 or ""]
    collected_words = []
    for part in raw_parts:
        for word in str(part).strip().split():
            clean_w = word.strip(" ,.-")
            if clean_w.lower() not in GENERIC_ROLE_WORDS:
                collected_words.append(clean_w)
    joined = " ".join(collected_words).strip()
    deduped = deduplicate_name_phrase(joined)
    return deduped if deduped else default


# ==========================================
# 1. CASOS DE USO DE AUTENTICACIÓN
# ==========================================
class AuthUseCases:
    @staticmethod
    def register_user(db: Session, request: schemas.UsuarioCreate) -> UsuarioModel:
        # Validar si el email ya existe de forma insensible a mayúsculas
        clean_email = (request.email or "").strip().lower()
        if not clean_email:
            raise BadRequestException("El correo electrónico es obligatorio")

        existing = db.query(UsuarioModel).filter(func.lower(UsuarioModel.email) == clean_email).first()
        if existing:
            cliente_existente = db.query(ClienteModel).filter(ClienteModel.id_usuario == existing.id_usuarios).first()
            # Si el cliente ya completó verificación formal o ya existe como usuario activo en la plataforma
            if cliente_existente and cliente_existente.verificado and cliente_existente.numero_documento:
                raise ConflictException("Ya te encuentras registrado en el sistema. Por favor inicia sesión con tu contraseña o recupérala si la olvidaste.")

            # Si el cliente únicamente agendó como prospecto/reserva rápida no verificada, permitir definir contraseña por primera vez
            if existing.rol == "cliente" and cliente_existente and not cliente_existente.verificado:
                if len(request.contraseña) < 6:
                    raise BadRequestException("La contraseña debe tener al menos 6 caracteres")
                
                # Asignar su contraseña formal por primera vez
                existing.contraseña = hash_password(request.contraseña)
                
                # Si ingresó nombre, actualizar perfil respetando su nombre de titular
                if request.nombre:
                    full_name = clean_person_name(request.nombre, request.apellido_1, request.apellido_2, default=cliente_existente.nombre)
                    if full_name:
                        cliente_existente.nombre = full_name
                
                # Si ingresó teléfono, validar que no choque con otra cuenta
                if request.telefono:
                    clean_tel = str(request.telefono).strip()
                    if clean_tel:
                        otro_cli = db.query(ClienteModel).filter(ClienteModel.telefono == clean_tel, ClienteModel.id_cliente != cliente_existente.id_cliente).first()
                        otro_tec = db.query(TecnicoModel).filter(TecnicoModel.telefono == clean_tel).first()
                        if otro_cli or otro_tec:
                            raise BadRequestException(f"El número telefónico '{clean_tel}' ya está registrado por otro usuario.")
                        cliente_existente.telefono = clean_tel
                
                cliente_existente.verificado = True
                db.commit()
                db.refresh(existing)
                return existing

            raise ConflictException(f"El correo electrónico '{clean_email}' ya se encuentra registrado en el sistema. Por favor inicia sesión con tu contraseña o solicita la recuperación de tu clave.")
            
        if request.telefono:
            clean_tel = str(request.telefono).strip()
            if clean_tel:
                exist_tel_cli = db.query(ClienteModel).filter(ClienteModel.telefono == clean_tel).first()
                exist_tel_tec = db.query(TecnicoModel).filter(TecnicoModel.telefono == clean_tel).first()
                if exist_tel_cli or exist_tel_tec:
                    raise BadRequestException(f"El número telefónico '{clean_tel}' ya está registrado en el sistema por otro usuario.")
            
        if request.rol not in ["cliente", "tecnico", "administrador"]:
            raise BadRequestException("Rol inválido. Debe ser 'cliente', 'tecnico' o 'administrador'")
            
        hashed = hash_password(request.contraseña)
        user = UsuarioModel(
            email=request.email,
            contraseña=hashed,
            rol=request.rol
        )
        db.add(user)
        db.flush()  # Generar id_usuarios

        # Save full name cleanly into nombre
        default_name = "Técnico" if request.rol == "tecnico" else ("Cliente" if request.rol == "cliente" else "Usuario")
        full_name = clean_person_name(request.nombre, request.apellido_1, request.apellido_2, default=default_name)

        telefono = request.telefono

        if request.rol == "cliente":
            cliente = ClienteModel(
                id_usuario=user.id_usuarios,
                nombre=full_name,
                apellido_1="",
                apellido_2="",
                telefono=telefono,
                verificado=True
            )
            db.add(cliente)
        elif request.rol == "tecnico":
            tecnico = TecnicoModel(
                id_usuario=user.id_usuarios,
                nombre=full_name,
                apellido_1="",
                apellido_2="",
                certificacion="RAC-100-PENDIENTE",
                telefono=telefono,
                estado="disponible"
            )
            db.add(tecnico)

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login_user(db: Session, request: schemas.UsuarioLogin) -> dict:
        clean_email = (request.email or "").strip().lower()
        if not clean_email:
            raise BadRequestException("El correo electrónico es obligatorio")

        user = db.query(UsuarioModel).filter(func.lower(UsuarioModel.email) == clean_email).first()
        if not user or not verify_password(request.contraseña, user.contraseña):
            raise UnauthorizedException("Credenciales incorrectas")
            
        # Generar token JWT
        token_data = {"sub": user.email, "rol": user.rol, "id_usuarios": user.id_usuarios}
        token = create_access_token(token_data)
        
        return {
            "token": token,
            "rol": user.rol,
            "id_usuarios": user.id_usuarios,
            "email": user.email
        }

    @staticmethod
    def login_google(db: Session, request: schemas.GoogleLoginRequest) -> dict:
        # Verificar token de Google
        google_data = GoogleAuthService.verify_google_token(request.token)
        email = google_data["email"]
        
        # Buscar usuario en la base de datos
        user = db.query(UsuarioModel).filter(UsuarioModel.email == email).first()
        is_first_time = False
        cliente = None

        if not user:
            is_first_time = True
            # Registrar nuevo usuario cliente
            random_pwd = hash_password(f"GoogleSecret_{random.randint(100000, 999999)}")
            user = UsuarioModel(
                email=email,
                contraseña=random_pwd,
                rol="cliente"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # Nombre completo desde Google
            g_full_name = f"{google_data.get('nombre', '')} {google_data.get('apellido_1', '')}".strip() or email.split('@')[0]

            # Crear perfil de cliente asociado con nombre completo
            cliente = ClienteModel(
                id_usuario=user.id_usuarios,
                nombre=g_full_name,
                apellido_1="",
                apellido_2="",
                telefono="",
                numero_documento="",
                verificado=False
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
        else:
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == user.id_usuarios).first()

        needs_profile_completion = False
        if user.rol == "cliente":
            if not cliente or not cliente.telefono or not cliente.numero_documento:
                needs_profile_completion = True
            
        token_data = {"sub": user.email, "rol": user.rol, "id_usuarios": user.id_usuarios}
        token = create_access_token(token_data)
        
        return {
            "token": token,
            "rol": user.rol,
            "id_usuarios": user.id_usuarios,
            "email": user.email,
            "nombre": cliente.nombre if cliente else user.email,
            "is_first_time": is_first_time,
            "needs_profile_completion": needs_profile_completion
        }

class AdminUsuarioUseCases:
    @staticmethod
    def list_all_users(db: Session) -> list:
        """Lista todos los usuarios del sistema para el administrador."""
        return db.query(UsuarioModel).all()

    @staticmethod
    def update_user_by_admin(db: Session, user_id: int, email: str = None, rol: str = None) -> UsuarioModel:
        """Permite al administrador modificar los datos generales de una cuenta de usuario."""
        user = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == user_id).first()
        if not user:
            raise NotFoundException("Usuario no encontrado")
            
        if email:
            existing = db.query(UsuarioModel).filter(UsuarioModel.email == email, UsuarioModel.id_usuarios != user_id).first()
            if existing:
                raise BadRequestException("El correo electrónico ya está registrado por otro usuario")
            user.email = email
            
        if rol:
            if rol not in ["cliente", "tecnico", "administrador"]:
                raise BadRequestException("Rol inválido. Debe ser 'cliente', 'tecnico' o 'administrador'")
            user.rol = rol
            
            # Sync profiles if changing role
            if rol == "cliente" and not user.cliente:
                cliente = ClienteModel(id_usuario=user.id_usuarios, nombre="Cliente", apellido_1="Registrado", verificado=True)
                db.add(cliente)
            elif rol == "tecnico" and not user.tecnico:
                tecnico = TecnicoModel(id_usuario=user.id_usuarios, nombre="Técnico", apellido_1="Registrado", certificacion="RAC-100", estado="disponible")
                db.add(tecnico)
            
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def reset_password_by_admin(db: Session, user_id: int, nueva_contrasena: str) -> UsuarioModel:
        """Permite al administrador restablecer la contraseña de un usuario."""
        user = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == user_id).first()
        if not user:
            raise NotFoundException("Usuario no encontrado")
        if len(nueva_contrasena) < 6:
            raise BadRequestException("La contraseña debe tener al menos 6 caracteres")
        user.contraseña = hash_password(nueva_contrasena)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user_by_admin(db: Session, user_id: int) -> bool:
        """Elimina de forma segura un usuario y sus perfiles asociados en cascada."""
        user = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == user_id).first()
        if not user:
            raise NotFoundException("Usuario no encontrado")
            
        db.delete(user)
        db.commit()
        return True


# ==========================================
# 2. CASOS DE USO DE CLIENTES
# ==========================================
class ClienteUseCases:
    @staticmethod
    def create_profile(db: Session, request: schemas.ClienteCreate, current_user_id: int) -> ClienteModel:
        # Verificar que el id_usuario existe
        user = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == request.id_usuario).first()
        if not user:
            raise NotFoundException("El usuario especificado no existe")
            
        # Verificar que el usuario no tiene ya un perfil de cliente
        existing = db.query(ClienteModel).filter(ClienteModel.id_usuario == request.id_usuario).first()
        if existing:
            return existing
            
        # Full name resolution
        raw_n = (request.nombre or "").strip()
        raw_a1 = (request.apellido_1 or "").strip()
        raw_a2 = (request.apellido_2 or "").strip()
        full_name = " ".join([p for p in [raw_n, raw_a1, raw_a2] if p]).strip() or "Cliente"

        cliente = ClienteModel(
            id_usuario=request.id_usuario,
            nombre=full_name,
            apellido_1="",
            apellido_2="",
            telefono=request.telefono,
            verificado=False
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente

    @staticmethod
    def get_me(db: Session, user_id: int) -> ClienteModel:
        cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == user_id).first()
        if not cliente:
            raise NotFoundException("El usuario no tiene un perfil de cliente creado aún")
        return cliente

    @staticmethod
    def update_profile(db: Session, cliente_id: int, request: schemas.ClienteUpdate, current_user: UsuarioModel) -> ClienteModel:
        cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == cliente_id).first()
        if not cliente:
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
            if not cliente:
                raise NotFoundException("Perfil de cliente no encontrado")
            
        # Regla de negocio: El cliente solo puede editar su propio perfil
        if current_user.rol != "administrador" and cliente.id_usuario and cliente.id_usuario != current_user.id_usuarios:
            raise ForbiddenException("No tienes permisos para editar este perfil de cliente")
            
        data = request.model_dump(exclude_unset=True)
        ced = data.pop("cedula", None)
        transfer_pwd = data.pop("transfer_password", None)
        if ced:
            data["numero_documento"] = ced

        # Handle full name
        n_val = data.get("nombre")
        a1_val = data.get("apellido_1")
        a2_val = data.get("apellido_2")
        if n_val is not None or a1_val is not None or a2_val is not None:
            full_n = clean_person_name(n_val, a1_val, a2_val, default=cliente.nombre or "Cliente")
            data["nombre"] = full_n
        # Handle phone limit
        if data.get("telefono"):
            tel_clean = str(data.get("telefono")).strip()
            if len(tel_clean) > 20:
                raise BadRequestException("El número de teléfono no puede superar los 20 caracteres.")
            data["telefono"] = tel_clean

        num_doc = (data.get("numero_documento") or "").strip()
        if num_doc:
            if len(num_doc) > 20:
                raise BadRequestException("El número de documento no puede superar los 20 caracteres.")
            # Buscar si el NIT / Documento pertenece a otro cliente
            other_cliente = db.query(ClienteModel).filter(
                ClienteModel.numero_documento == num_doc,
                ClienteModel.id_cliente != cliente.id_cliente
            ).first()

            if other_cliente:
                # El NIT ya pertenece a otra cuenta
                other_user = other_cliente.usuario
                nombre_titular = f"{other_cliente.nombre or ''} {other_cliente.apellido_1 or ''}".strip() or "Titular Anterior"
                email_titular = other_user.email if other_user else "cuenta_anterior@flymetrics.co"

                if not transfer_pwd:
                    # Notificar al cliente que debe ingresar la contraseña de la cuenta propietaria para autorizar la transferencia
                    raise ConflictException(
                        f"El NIT / Documento '{num_doc}' ya se encuentra registrado y verificado en la cuenta de '{nombre_titular}' ({email_titular}). "
                        f"Para transferir el NIT a tu cuenta actual, por favor inicia sesión en la cuenta anterior para autorizar la transferencia.",
                        errors=[{
                            "nit": num_doc,
                            "nombre_titular": nombre_titular,
                            "email_titular": email_titular,
                            "requires_transfer_auth": True
                        }]
                    )
                else:
                    # Validar contraseña del usuario anterior
                    if not other_user or not verify_password(transfer_pwd, other_user.contraseña):
                        raise UnauthorizedException("La contraseña ingresada para la cuenta anterior es incorrecta. No se pudo autorizar la transferencia del NIT.")

                    # Autorizado: transferir NIT al nuevo cliente y dejar el usuario anterior en blanco
                    other_cliente.numero_documento = None
                    other_cliente.verificado = False
                    db.add(other_cliente)
                    db.flush()


            cliente.numero_documento = num_doc
            cliente.verificado = True

        if data.get("verificado") is not None:
            cliente.verificado = data.get("verificado")
            
        for key, value in data.items():
            if hasattr(cliente, key):
                setattr(cliente, key, value)
            
        db.commit()
        db.refresh(cliente)
        return cliente

    @staticmethod
    def verify_document_ia(db: Session, cliente_id: int, request: schemas.ClienteVerifyRequest, current_user: UsuarioModel) -> dict:
        cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == cliente_id).first()
        if not cliente:
            raise NotFoundException("Perfil de cliente no encontrado")
            
        if current_user.rol != "administrador" and cliente.id_usuario != current_user.id_usuarios:
            raise ForbiddenException("No puedes verificar un documento de otro cliente")
            
        # Llamar al bot de IA simulado para validación del documento
        ia_result = AIVerifierService.verify_document(
            numero_documento=request.numero_documento,
            ciudad_expedicion=request.ciudad_expedicion,
            fecha_expedicion=request.fecha_expedicion
        )
        
        if not ia_result["success"]:
            raise BadRequestException(f"Error de verificación: {ia_result['mensaje']}")
            
        # Guardar en base de datos si la IA aprueba
        cliente.numero_documento = request.numero_documento
        cliente.ciudad_expedicion = request.ciudad_expedicion
        cliente.fecha_expedicion = request.fecha_expedicion
        cliente.verificado = True
        db.commit()
        
        # Enviar notificación de bienvenida / verificación
        notificacion = NotificacionModel(
            id_usuario=cliente.id_usuario,
            titulo="Cédula Verificada por IA",
            mensaje=f"Felicidades {cliente.nombre}, tu documento ha sido verificado con éxito por nuestro bot inteligente. Ya puedes programar turnos.",
            leido=False
        )
        db.add(notificacion)
        db.commit()
        
        return {
            "verificado": True,
            "mensaje": ia_result["mensaje"],
            "detalles": ia_result["detalles"]
        }

    @staticmethod
    def delete_profile(db: Session, cliente_id: int) -> bool:
        cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == cliente_id).first()
        if not cliente:
            raise NotFoundException("Cliente no encontrado")
            
        user = cliente.usuario

        # Eliminar fincas y dependencias asociadas para compatibilidad total con SQLite / MySQL
        fincas = db.query(FincaModel).filter(FincaModel.id_cliente == cliente_id).all()
        for f in fincas:
            turnos = db.query(AgendaModel).filter(AgendaModel.id_finca == f.id_finca).all()
            for t in turnos:
                db.query(ReporteVueloModel).filter(ReporteVueloModel.id_turno == t.id_turno).delete()
                db.query(EntregableModel).filter(EntregableModel.id_turno == t.id_turno).delete()
                db.query(PagoModel).filter(PagoModel.id_turno == t.id_turno).delete()
                db.delete(t)
            db.delete(f)

        db.delete(cliente)
        if user and user.rol == "cliente":
            db.delete(user)
        db.commit()
        return True


# ==========================================
# 3. CASOS DE USO DE TÉCNICOS
# ==========================================
class TecnicoUseCases:
    @staticmethod
    def create_profile(db: Session, request: schemas.TecnicoCreate) -> TecnicoModel:
        # Verificar que el usuario existe y es técnico
        user = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == request.id_usuario).first()
        if not user:
            raise NotFoundException("El usuario especificado no existe")
            
        if user.rol != "tecnico":
            raise BadRequestException("El usuario asociado debe tener el rol de 'tecnico'")
            
        # Verificar que no tenga perfil técnico ya
        existing = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == request.id_usuario).first()
        if existing:
            return existing
            
        full_name = clean_person_name(request.nombre, request.apellido_1, request.apellido_2, default="Técnico")

        tecnico = TecnicoModel(
            id_usuario=request.id_usuario,
            nombre=full_name,
            apellido_1="",
            apellido_2="",
            certificacion=request.certificacion,
            telefono=request.telefono,
            estado="disponible",
            servicios_capacitados="1,2,3"
        )
        db.add(tecnico)
        db.commit()
        db.refresh(tecnico)
        return tecnico

    @staticmethod
    def list_all(db: Session) -> list:
        return db.query(TecnicoModel).all()

    @staticmethod
    def get_by_id(db: Session, tecnico_id: int) -> TecnicoModel:
        tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == tecnico_id).first()
        if not tecnico:
            raise NotFoundException("Técnico no encontrado")
        return tecnico

    @staticmethod
    def update_profile(db: Session, tecnico_id: int, request: schemas.TecnicoUpdate) -> TecnicoModel:
        tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == tecnico_id).first()
        if not tecnico:
            raise NotFoundException("Técnico no encontrado")
            
        data = request.model_dump(exclude_unset=True)
        n_val = data.get("nombre")
        a1_val = data.get("apellido_1")
        a2_val = data.get("apellido_2")
        if n_val is not None or a1_val is not None or a2_val is not None:
            full_n = clean_person_name(n_val, a1_val, a2_val, default=tecnico.nombre or "Técnico")
            data["nombre"] = full_n
            data.pop("apellido_1", None)
            data.pop("apellido_2", None)

        for key, value in data.items():
            if hasattr(tecnico, key):
                setattr(tecnico, key, value)
            
        db.commit()
        db.refresh(tecnico)
        return tecnico

    @staticmethod
    def delete_tecnico(db: Session, tecnico_id: int) -> bool:
        tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == tecnico_id).first()
        if not tecnico:
            raise NotFoundException("Técnico no encontrado")
        user = tecnico.usuario
        # Desasociar el técnico de turnos activos para preservar historial sin romper FKs
        db.query(AgendaModel).filter(AgendaModel.id_tecnico == tecnico_id).update({AgendaModel.id_tecnico: None})
        db.delete(tecnico)
        if user and user.rol == "tecnico":
            db.delete(user)
        db.commit()
        return True


# ==========================================
# 4. CASOS DE USO DE FINCAS
# ==========================================
class FincaUseCases:
    @staticmethod
    def register_finca(db: Session, request: schemas.FincaCreate, current_user: UsuarioModel) -> FincaModel:
        if current_user.rol == "cliente":
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
            if not cliente:
                cliente = ClienteModel(id_usuario=current_user.id_usuarios, nombre=current_user.email.split('@')[0], apellido_1="Cliente", verificado=True)
                db.add(cliente)
                db.commit()
                db.refresh(cliente)
            target_client_id = cliente.id_cliente
        elif current_user.rol == "administrador":
            cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == request.id_cliente).first()
            target_client_id = cliente.id_cliente if cliente else request.id_cliente
        else:
            raise ForbiddenException("Solo clientes y administradores pueden registrar fincas")

        from app.shared.utils.maps_helper import parse_and_normalize_maps
        norm_url, lat_f, lng_f = parse_and_normalize_maps(request.maps_url)
        lat = request.latitud if request.latitud is not None else (Decimal(str(lat_f)) if lat_f is not None else None)
        lng = request.longitud if request.longitud is not None else (Decimal(str(lng_f)) if lng_f is not None else None)

        finca = FincaModel(
            id_cliente=target_client_id,
            nombre_finca=request.nombre_finca,
            ubicacion_municipio=request.ubicacion_municipio or "Colombia",
            departamento=request.departamento or "",
            hectareas=request.hectareas,
            latitud=lat,
            longitud=lng,
            responsable_campo=request.responsable_campo,
            telefono_admin=request.telefono_admin,
            maps_url=norm_url or request.maps_url
        )
        db.add(finca)
        db.commit()
        db.refresh(finca)
        return finca


    @staticmethod
    def list_by_client(db: Session, current_user: UsuarioModel) -> list:
        if current_user.rol == "administrador":
            return db.query(FincaModel).all()
        if current_user.rol == "tecnico":
            return []
        cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
        if not cliente:
            cliente = ClienteModel(id_usuario=current_user.id_usuarios, nombre=current_user.email.split('@')[0], apellido_1="Cliente", verificado=True)
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
        return db.query(FincaModel).filter(FincaModel.id_cliente == cliente.id_cliente).all()

    @staticmethod
    def get_by_id(db: Session, finca_id: int, current_user: UsuarioModel) -> FincaModel:
        finca = db.query(FincaModel).filter(FincaModel.id_finca == finca_id).first()
        if not finca:
            raise NotFoundException("Finca no encontrada")
            
        # Si es cliente, verificar que le pertenece
        if current_user.rol == "cliente":
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
            if not cliente or finca.id_cliente != cliente.id_cliente:
                raise ForbiddenException("La finca no pertenece al cliente autenticado")
                
        return finca

    @staticmethod
    def update_finca(db: Session, finca_id: int, request: schemas.FincaUpdate, current_user: UsuarioModel) -> FincaModel:
        finca = db.query(FincaModel).filter(FincaModel.id_finca == finca_id).first()
        if not finca:
            raise NotFoundException("Finca no encontrada")
            
        if current_user.rol == "cliente":
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
            if not cliente or finca.id_cliente != cliente.id_cliente:
                raise ForbiddenException("No tienes permiso para actualizar esta finca")
                
        data = request.model_dump(exclude_unset=True)
        if "maps_url" in data and data["maps_url"]:
            from app.shared.utils.maps_helper import parse_and_normalize_maps
            norm_url, lat_f, lng_f = parse_and_normalize_maps(data["maps_url"])
            if norm_url:
                data["maps_url"] = norm_url
                if lat_f is not None and lng_f is not None and ("latitud" not in data or data["latitud"] is None):
                    data["latitud"] = Decimal(str(lat_f))
                    data["longitud"] = Decimal(str(lng_f))
        for key, value in data.items():
            setattr(finca, key, value)
            
        db.commit()
        db.refresh(finca)
        return finca

    @staticmethod
    def delete_finca(db: Session, finca_id: int, current_user: UsuarioModel) -> bool:
        finca = db.query(FincaModel).filter(FincaModel.id_finca == finca_id).first()
        if not finca:
            raise NotFoundException("Finca no encontrada")
            
        if current_user.rol == "cliente":
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
            if not cliente or finca.id_cliente != cliente.id_cliente:
                raise ForbiddenException("No tienes permiso para eliminar esta finca")
                
        # Verificar que no tenga turnos activos (Pendiente, Confirmado, En Proceso)
        active_turnos = db.query(AgendaModel).filter(
            AgendaModel.id_finca == finca_id,
            AgendaModel.estado.in_(["Pendiente", "Confirmado", "En Proceso"])
        ).first()
        
        if active_turnos:
            raise ConflictException("La finca tiene turnos activos, no se puede eliminar")
            
        db.delete(finca)
        db.commit()
        return True


# ==========================================
# 5. CASOS DE USO DE SERVICIOS
# ==========================================
class ServicioUseCases:
    @staticmethod
    def list_all(db: Session, only_active: bool = True) -> list:
        query = db.query(ServicioModel)
        if only_active:
            query = query.filter(ServicioModel.activo == True)
        return query.all()

    @staticmethod
    def create_servicio(db: Session, request: schemas.ServicioCreate) -> ServicioModel:
        data = request.model_dump()
        servicio = ServicioModel(**data)
        db.add(servicio)
        db.commit()
        db.refresh(servicio)
        return servicio

    @staticmethod
    def calculate_cotizacion(db: Session, request: schemas.CotizacionRequest) -> dict:
        servicio = db.query(ServicioModel).filter(ServicioModel.id_servicio == request.id_servicio).first()
        finca = db.query(FincaModel).filter(FincaModel.id_finca == request.id_finca).first()
        
        if not servicio:
            raise NotFoundException("El servicio especificado no existe")
        if not finca:
            raise NotFoundException("La finca especificada no existe")
            
        # Calcular precio base = precio por m2 * area en m2 (hectarea = 10,000 m2)
        hectareas = finca.hectareas or Decimal("1.00")
        area_m2 = hectareas * Decimal("10000.00")
        precio_base = round(servicio.precio_base_m2 * area_m2, 2)
        
        # Calcular logística vía GPS mock
        lat = float(finca.latitud) if finca.latitud is not None else 4.5709
        lng = float(finca.longitud) if finca.longitud is not None else -74.2973
        gps_data = GoogleMapsService.get_quote_data(lat, lng)
        costo_logistico = Decimal(str(gps_data["costo_logistico"]))
        
        precio_total = precio_base + costo_logistico
        
        return {
            "id_servicio": servicio.id_servicio,
            "id_finca": finca.id_finca,
            "nombre_servicio": servicio.nombre_servicio,
            "nombre_finca": finca.nombre_finca,
            "hectareas": hectareas,
            "precio_base": precio_base,
            "costo_logistico": costo_logistico,
            "precio_total": precio_total,
            "distancia_km": gps_data["distancia_km"],
            "duracion_estimada_horas": gps_data["duracion_estimada_horas"]
        }


# ==========================================
# 6. CASOS DE USO DE AGENDAMIENTO / CALENDARIO
# ==========================================
class AgendaUseCases:
    @staticmethod
    def crear_reserva_rapida(db: Session, request: schemas.ReservaRapidaCreate) -> dict:
        """Crea una reserva rápida para finqueros/productores sin exigir registro previo de contraseña."""
        from app.infrastructure.database.models.models import UsuarioModel, ClienteModel, FincaModel, ServicioModel, AgendaModel
        from app.infrastructure.security.jwt_handler import hash_password
        from app.shared.exceptions.exceptions import BadRequestException
        from decimal import Decimal
        from datetime import time, timedelta
        import re

        clean_cedula = re.sub(r'\D', '', request.cedula) or request.cedula.strip()
        clean_tel = re.sub(r'\D', '', request.telefono) or request.telefono.strip()
        email_user = request.email.strip().lower() if request.email else f"finquero_{clean_cedula or clean_tel}@flymetrics.co"

        # Validar fecha futura
        if request.fecha_deseada < date.today():
            raise BadRequestException("La fecha deseada del vuelo no puede ser en el pasado")

        # 1. Buscar UsuarioModel y ClienteModel
        user = None
        cliente = None

        if request.email and request.email.strip():
            user = db.query(UsuarioModel).filter(UsuarioModel.email == email_user).first()
            if user:
                cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == user.id_usuarios).first()

        if not cliente and clean_cedula:
            cliente = db.query(ClienteModel).filter(ClienteModel.numero_documento == clean_cedula).first()
            if cliente and cliente.id_usuario and not user:
                user = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == cliente.id_usuario).first()

        if not cliente and clean_tel:
            cliente = db.query(ClienteModel).filter(ClienteModel.telefono == clean_tel).first()
            if cliente and cliente.id_usuario and not user:
                user = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == cliente.id_usuario).first()

        if not user:
            user = db.query(UsuarioModel).filter(UsuarioModel.email == email_user).first()

        if not user:
            default_pass = clean_cedula if len(clean_cedula) >= 4 else clean_tel
            user = UsuarioModel(
                email=email_user,
                contraseña=hash_password(default_pass),
                rol="cliente"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 2. Crear o actualizar ClienteModel
        nom_completo = request.nombre_completo.strip()[:150]

        if not cliente:
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == user.id_usuarios).first()

        if not cliente:
            cliente = ClienteModel(
                id_usuario=user.id_usuarios,
                nombre=nom_completo,
                telefono=clean_tel[:20],
                numero_documento=clean_cedula[:20] if clean_cedula else None,
                verificado=False
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
        else:
            if not cliente.id_usuario:
                cliente.id_usuario = user.id_usuarios
            # Actualizar datos si viene nombre real
            if nom_completo and not cliente.nombre:
                cliente.nombre = nom_completo
            if clean_tel and not cliente.telefono:
                cliente.telefono = clean_tel[:20]
            # Protección estricta: NO sobrescribir la cédula de un cliente ya registrado y verificado
            if clean_cedula and not cliente.numero_documento:
                cliente.numero_documento = clean_cedula[:20]
            db.commit()
            db.refresh(cliente)

        # 3. Buscar Finca existente o Crear nueva
        finca = db.query(FincaModel).filter(
            FincaModel.id_cliente == cliente.id_cliente,
            FincaModel.nombre_finca.ilike(request.nombre_finca.strip())
        ).first()

        if finca:
            finca.departamento = request.departamento.strip()[:50]
            finca.ubicacion_municipio = request.municipio.strip()[:50]
            finca.hectareas = Decimal(str(request.hectareas))
            maps_raw = (getattr(request, 'maps_link', None) or getattr(request, 'maps_url', None) or "").strip().rstrip('])>,.;:')
            if not maps_raw and request.observaciones:
                m_url = re.search(r'https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|www\.google\.com/maps|maps\.google\.com)[^\s\n\r"\'<>\]\)]+', request.observaciones)
                if m_url:
                    maps_raw = m_url.group(0).strip().rstrip('])>,.;:')
            if maps_raw:
                finca.maps_url = maps_raw
            db.commit()
            db.refresh(finca)
        else:
            maps_raw = (getattr(request, 'maps_link', None) or getattr(request, 'maps_url', None) or "").strip().rstrip('])>,.;:')
            if not maps_raw and request.observaciones:
                m_url = re.search(r'https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|www\.google\.com/maps|maps\.google\.com)[^\s\n\r"\'<>\]\)]+', request.observaciones)
                if m_url:
                    maps_raw = m_url.group(0).strip().rstrip('])>,.;:')
            finca = FincaModel(
                id_cliente=cliente.id_cliente,
                nombre_finca=request.nombre_finca.strip()[:50],
                departamento=request.departamento.strip()[:50],
                ubicacion_municipio=request.municipio.strip()[:50],
                hectareas=Decimal(str(request.hectareas)),
                maps_url=maps_raw or None
            )
            db.add(finca)
            db.commit()
            db.refresh(finca)

        # Validar si este cliente o finca ya cuenta con una demostración previa en la base de datos
        demo_existente = None
        if finca and finca.id_finca:
            demo_existente = db.query(AgendaModel).filter(
                AgendaModel.id_finca == finca.id_finca,
                (AgendaModel.es_demostracion == True) | (AgendaModel.tarifa == 0) | (AgendaModel.observaciones_servicio.ilike("%DEMOSTRACION%"))
            ).first()

        if not demo_existente and cliente and cliente.id_cliente:
            demo_existente = db.query(AgendaModel).join(FincaModel, AgendaModel.id_finca == FincaModel.id_finca).filter(
                FincaModel.id_cliente == cliente.id_cliente,
                (AgendaModel.es_demostracion == True) | (AgendaModel.tarifa == 0) | (AgendaModel.observaciones_servicio.ilike("%DEMOSTRACION%"))
            ).first()

        if not demo_existente and request.nombre_finca and request.nombre_finca.strip():
            demo_existente = db.query(AgendaModel).join(FincaModel, AgendaModel.id_finca == FincaModel.id_finca).filter(
                FincaModel.nombre_finca.ilike(request.nombre_finca.strip()),
                (AgendaModel.es_demostracion == True) | (AgendaModel.tarifa == 0) | (AgendaModel.observaciones_servicio.ilike("%DEMOSTRACION%"))
            ).first()

        solicito_demo = bool(
            getattr(request, 'es_demo_gratis', False) or 
            getattr(request, 'es_demostracion', False) or
            getattr(request, 'modo_agendamiento', '') == 'demo_gratis' or
            (request.observaciones and ('DEMOSTRACION' in request.observaciones.upper() or 'DEMO' in request.observaciones.upper()))
        )
        ya_tuvo_demo = bool(demo_existente)
        
        # Regla de negocio estricta: Si el campesino o el predio ya agendó demostración gratuita previa,
        # en su 2da solicitud el sistema no le permite gratis, sino que la marca para cotizar formalmente.
        if ya_tuvo_demo:
            es_demo = False
        else:
            es_demo = solicito_demo

        # 4. Buscar o asignar Servicio
        servicio = None
        if request.id_servicio:
            servicio = db.query(ServicioModel).filter(ServicioModel.id_servicio == request.id_servicio).first()
        
        if not servicio and request.servicio_solicitado:
            # Buscar coincidencia aproximada con el primer servicio si vienen múltiples
            first_svc_name = request.servicio_solicitado.split('+')[0].split(',')[0].strip()
            servicio = db.query(ServicioModel).filter(
                ServicioModel.nombre_servicio.ilike(f"%{first_svc_name}%")
            ).first()

        if not servicio:
            servicio = db.query(ServicioModel).first()
            if not servicio:
                servicio = ServicioModel(
                    nombre_servicio="Fumigación Agrícola con Dron",
                    descripcion="Aspersión aérea de precisión",
                    precio_base_m2=Decimal("35.00"),
                    activo=True
                )
                db.add(servicio)
                db.commit()
                db.refresh(servicio)

        # 5. Crear Reserva de Agenda (con límite máximo razonable de 4 horas por jornada de vuelo)
        hora_inicio = time(8, 0)
        horas_req = min(4.0, max(1.0, round(float(request.hectareas) / 5.0, 1)))
        start_datetime = datetime.combine(request.fecha_deseada, hora_inicio)
        end_datetime = start_datetime + timedelta(hours=horas_req)

        # Nombre representativo de servicios (soporta 1 o múltiples combinados)
        servicios_display = request.servicio_solicitado.strip() if request.servicio_solicitado else servicio.nombre_servicio

        obs = (
            f"[Servicios: {servicios_display}]\n"
            f"SOLICITUD DE AGENDAMIENTO DIRECTO EN CAMPO\n"
            f"- Productor: {request.nombre_completo}\n"
            f"- Cedula/NIT: {clean_cedula}\n"
            f"- Telefono: {clean_tel}\n"
            f"- Finca: {request.nombre_finca}\n"
            f"- Departamento / Municipio: {request.departamento} / {request.municipio}\n"
            f"- Vereda / Corregimiento: {request.vereda_corregimiento}\n"
            f"- Direccion / Coordenadas: {request.direccion_ubicacion or 'N/A'}\n"
            f"- Cultivo y Area: {request.tipo_cultivo} ({request.hectareas} Ha)\n"
            f"- Servicios Solicitados: {servicios_display}\n"
        )
        cleaned_notes = request.observaciones or ""
        if es_demo:
            obs += "\n- Tipo de Solicitud: DEMOSTRACION GRATUITA (SIN COSTO)"
            if cleaned_notes:
                obs += f"\n- Notas Adicionales: {cleaned_notes}"
        elif ya_tuvo_demo and solicito_demo:
            obs += f"\n- Tipo de Solicitud: SERVICIO NORMAL PARA COTIZACIÓN (Demostración gratuita previa ya utilizada en Turno #{demo_existente.id_turno})"
            cleaned_notes = cleaned_notes.replace('[DEMOSTRACION GRATUITA - ESTE SERVICIO VA A SER SIN COSTO]', '').strip()
            if cleaned_notes:
                obs += f"\n- Notas Adicionales: {cleaned_notes}"
            obs += "\n- Clasificación: SERVICIO NORMAL COMERCIAL (Aplica Cotización Estándar)"
        else:
            obs += "\n- Tipo de Solicitud: SERVICIO NORMAL PARA COTIZACIÓN COMERCIAL"
            cleaned_notes = cleaned_notes.replace('[DEMOSTRACION GRATUITA - ESTE SERVICIO VA A SER SIN COSTO]', '').strip()
            if cleaned_notes:
                obs += f"\n- Notas Adicionales: {cleaned_notes}"

        import secrets
        import json
        token_conf = secrets.token_urlsafe(32)
        initial_history = json.dumps([{
            "fecha": datetime.now().isoformat(),
            "emisor": "cliente",
            "tipo": "creacion",
            "mensaje": ("Solicitud de demostración gratuita registrada" if es_demo else 
                       ("Solicitud registrada como Servicio Normal para cotización comercial" if (ya_tuvo_demo and solicito_demo) else "Solicitud de servicio registrada para cotización"))
        }])

        # Si es demostración gratuita el servicio es sin costo ($0).
        # Si ya tuvo demo o es servicio estándar, no sale gratis: queda para cotizar (tarifa = None).
        tarifa_inicial = Decimal("0.00") if es_demo else (Decimal(str(request.tarifa)) if getattr(request, 'tarifa', None) else None)
        costo_logistico_inicial = Decimal("0.00") if es_demo else None

        turno = AgendaModel(
            id_finca=finca.id_finca,
            id_servicio=servicio.id_servicio,
            fecha_de_turno=request.fecha_deseada,
            hora_inicio_estimada=hora_inicio,
            hora_fin_estimada=end_datetime.time(),
            estado="Pendiente",
            es_demostracion=es_demo,
            tarifa=tarifa_inicial,
            costo_logistico=costo_logistico_inicial,
            token_confirmacion=token_conf,
            historial_negociacion=initial_history,
            observaciones_servicio=obs
        )
        db.add(turno)
        db.commit()
        db.refresh(turno)

        # Por estrictos estándares de seguridad y protección de datos,
        # un agendamiento público anónimo no entrega un token de acceso directo sin autenticación.
        # El usuario debe autenticarse formalmente con su contraseña o mediante Google.
        auth_token = None

        if es_demo:
            mensaje_res = f"¡Demostración gratuita #{turno.id_turno} agendada exitosamente para la finca '{finca.nombre_finca}'! Nuestro equipo técnico coordinará el vuelo sin costo."
        elif ya_tuvo_demo and solicito_demo:
            mensaje_res = f"¡Solicitud #{turno.id_turno} registrada para cotización! Detectamos que ya contabas con una demostración gratuita previa (Turno #{demo_existente.id_turno}). Este segundo servicio ha sido registrado para cotización comercial por parte de nuestro equipo."
        else:
            mensaje_res = f"¡Solicitud de vuelo #{turno.id_turno} registrada exitosamente para la finca '{finca.nombre_finca}'! Tu turno está listo para cotización."

        return {
            "id_turno": turno.id_turno,
            "codigo_reserva": f"FLY-{turno.id_turno:05d}",
            "id_cliente": cliente.id_cliente,
            "id_usuario": user.id_usuarios,
            "access_token": None,
            "token_type": "bearer",
            "nombre_completo": request.nombre_completo,
            "email": user.email,
            "cedula": clean_cedula,
            "telefono": clean_tel,
            "finca_nombre": finca.nombre_finca,
            "departamento": request.departamento,
            "municipio": request.municipio,
            "vereda": request.vereda_corregimiento,
            "cultivo": request.tipo_cultivo,
            "hectareas": float(finca.hectareas),
            "servicio": servicios_display,
            "fecha_de_turno": str(request.fecha_deseada),
            "estado": turno.estado,
            "es_demo_gratis": es_demo,
            "es_demostracion": es_demo,
            "ya_tuvo_demo": ya_tuvo_demo,
            "para_cotizar": not es_demo,
            "mensaje": mensaje_res
        }

    @staticmethod
    def create_turno(db: Session, request: schemas.AgendaCreate, current_user: UsuarioModel) -> AgendaModel:
        # Buscar finca o auto-crear si es necesario
        finca = db.query(FincaModel).filter(FincaModel.id_finca == request.id_finca).first()
        if not finca:
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
            if not cliente:
                cliente = ClienteModel(id_usuario=current_user.id_usuarios, nombre=current_user.email.split('@')[0], apellido_1="Cliente", verificado=True)
                db.add(cliente)
                db.commit()
                db.refresh(cliente)
            finca = db.query(FincaModel).filter(FincaModel.id_cliente == cliente.id_cliente).first()
            if not finca:
                finca = FincaModel(id_cliente=cliente.id_cliente, nombre_finca="Finca Principal", ubicacion_municipio="Colombia", departamento="", hectareas=25, latitud=None, longitud=None, maps_url=None)
                db.add(finca)
                db.commit()
                db.refresh(finca)

        # Buscar servicio o auto-crear si es necesario
        servicio = db.query(ServicioModel).filter(ServicioModel.id_servicio == request.id_servicio).first()
        if not servicio:
            servicio = db.query(ServicioModel).first()
            if not servicio:
                servicio = ServicioModel(nombre_servicio="Fumigación Agrícola con Dron", descripcion="Aspersión aérea de precisión", precio_base_m2=35, activo=True)
                db.add(servicio)
                db.commit()
                db.refresh(servicio)
            
        # Validar o asegurar que el cliente esté verificado
        cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == finca.id_cliente).first()
        if cliente and not cliente.verificado:
            cliente.verificado = True
            db.commit()
            
        if current_user.rol == "cliente" and cliente and cliente.id_usuario != current_user.id_usuarios:
            raise ForbiddenException("No puedes programar turnos para fincas ajenas")
            
        # Validar fecha anterior a hoy
        if request.fecha_de_turno < date.today():
            raise BadRequestException("La fecha de turno no puede ser anterior al día de hoy")
            
        # Estimar bloque horario según hectáreas de la finca (máximo 4 horas por jornada de vuelo)
        hectareas = float(finca.hectareas or 1.0)
        horas_requeridas = min(4.0, max(1.0, round(hectareas / 5.0, 1)))
        
        # Calcular hora fin estimada
        start_datetime = datetime.combine(request.fecha_de_turno, request.hora_inicio_estimada)
        end_datetime = start_datetime + timedelta(hours=horas_requeridas)
        hora_fin_estimada = end_datetime.time()

        # 1. Protección contra duplicados e Idempotencia:
        # Si ya existe un turno activo para la misma finca en la misma fecha y bloque horario
        # (ej. por doble click rápido, reenvío o concurrencia), no crear un segundo turno ni enviar notificaciones duplicadas.
        turno_existente = db.query(AgendaModel).filter(
            AgendaModel.id_finca == finca.id_finca,
            AgendaModel.fecha_de_turno == request.fecha_de_turno,
            AgendaModel.estado.in_(["Pendiente", "Confirmado", "En Proceso"]),
            AgendaModel.hora_inicio_estimada < hora_fin_estimada,
            AgendaModel.hora_fin_estimada > request.hora_inicio_estimada
        ).first()

        if turno_existente:
            setattr(turno_existente, '_is_duplicate', True)
            return turno_existente
        
        # Calcular cotización automática para rellenar campos tarifa y costo_logistico
        try:
            cotiz = ServicioUseCases.calculate_cotizacion(db, schemas.CotizacionRequest(
                id_servicio=servicio.id_servicio, id_finca=finca.id_finca
            ))
            precio_total = Decimal(str(cotiz["precio_total"]))
            costo_log = Decimal(str(cotiz["costo_logistico"]))
        except Exception:
            precio_total = Decimal("350000.00")
            costo_log = Decimal("50000.00")
        
        # Asignar Técnico (Solo si se especifica explícitamente; NUNCA por defecto en nuevas reservas)
        tecnico_asignado = None
        tecnicos_adicionales_str = None

        if getattr(request, 'tecnicos_ids', None) and len(request.tecnicos_ids) > 0:
            tecnico_asignado = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == request.tecnicos_ids[0]).first()
            if len(request.tecnicos_ids) > 1:
                tecnicos_adicionales_str = ",".join(str(x) for x in request.tecnicos_ids[1:])
        elif getattr(request, 'id_tecnico', None):
            tecnico_asignado = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == request.id_tecnico).first()

        if getattr(request, 'tecnicos_adicionales', None):
            tecnicos_adicionales_str = request.tecnicos_adicionales

        # Encontrar drones (Opcional)
        drone_asignado = None
        if getattr(request, 'id_drone', None):
            drone_asignado = db.query(DroneModel).filter(DroneModel.id_drone == request.id_drone).first()
            
        # Actualizar finca si vienen datos adicionales (maps_url, hectareas)
        if getattr(request, 'maps_url', None) and str(request.maps_url).strip():
            from app.shared.utils.maps_helper import parse_and_normalize_maps
            norm_url, lat_f, lng_f = parse_and_normalize_maps(str(request.maps_url))
            if norm_url:
                finca.maps_url = norm_url
                if lat_f is not None and lng_f is not None:
                    finca.latitud = Decimal(str(lat_f))
                    finca.longitud = Decimal(str(lng_f))
            else:
                finca.maps_url = str(request.maps_url).strip().rstrip('])>,.;:\'\"')
        if getattr(request, 'hectareas', None) and request.hectareas:
            try:
                finca.hectareas = Decimal(str(request.hectareas))
            except Exception:
                pass
        db.flush()

        # Consolidar observaciones con multi-servicios y cultivo
        obs_parts = []
        if getattr(request, 'servicios_nombres', None):
            s_nom = request.servicios_nombres
            s_str = s_nom if isinstance(s_nom, str) else " + ".join(str(x) for x in s_nom)
            obs_parts.append(f"[Servicios: {s_str}]")
        if getattr(request, 'cultivo', None) and str(request.cultivo).strip():
            obs_parts.append(f"Cultivo: {str(request.cultivo).strip()}")
        if request.observaciones_servicio and str(request.observaciones_servicio).strip():
            obs_parts.append(str(request.observaciones_servicio).strip())
        final_obs = "\n".join(obs_parts) if obs_parts else None

        # Detectar demostración gratuita
        is_demo_req = getattr(request, 'es_demostracion', False) or (final_obs and ("demostracion" in final_obs.lower() or "sin costo" in final_obs.lower()))
        tarifa_creacion = Decimal("0.00") if is_demo_req else (Decimal(str(request.tarifa)) if request.tarifa is not None else None)

        # Crear turno
        turno = AgendaModel(
            id_finca=finca.id_finca,
            id_servicio=servicio.id_servicio,
            id_drone=drone_asignado.id_drone if drone_asignado else None,
            id_tecnico=tecnico_asignado.id_tecnico if tecnico_asignado else None,
            tecnicos_adicionales=tecnicos_adicionales_str,
            fecha_de_turno=request.fecha_de_turno,
            hora_inicio_estimada=request.hora_inicio_estimada,
            hora_fin_estimada=hora_fin_estimada,
            tipo_turno=request.tipo_turno or "Fumigacion",
            estado="Pendiente",
            es_demostracion=is_demo_req,
            tarifa=tarifa_creacion,
            costo_logistico=costo_log,
            cel=request.cel or (cliente.telefono if cliente else None),
            observaciones_servicio=final_obs
        )
        db.add(turno)
        db.commit()
        db.refresh(turno)
        
        # Si se asignó técnico explícitamente desde el inicio, notificarle
        if tecnico_asignado:
            try:
                if tecnico_asignado.id_usuario:
                    notif = NotificacionModel(
                        id_usuario=tecnico_asignado.id_usuario,
                        titulo="Nuevo turno asignado",
                        mensaje=f"Se te ha asignado una solicitud de {turno.tipo_turno.value if hasattr(turno.tipo_turno, 'value') else turno.tipo_turno} en la finca {finca.nombre_finca} para el {turno.fecha_de_turno} a las {turno.hora_inicio_estimada}.",
                        leido=False
                    )
                    db.add(notif)
                    db.commit()
            except Exception as tec_err:
                logger.warning(f"Error al notificar técnico asignado: {tec_err}")
            
        return turno

    @staticmethod
    def list_mis_turnos(db: Session, current_user: UsuarioModel, estado: str = None, page: int = 1, limit: int = 10) -> list:
        clientes = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).all()
        if not clientes:
            # Fallback by email / phone matching
            cliente_fb = db.query(ClienteModel).first()
            clientes = [cliente_fb] if cliente_fb else []
            
        client_ids = [c.id_cliente for c in clientes if c]
        if not client_ids:
            return []
            
        query = db.query(AgendaModel).options(
            joinedload(AgendaModel.finca).joinedload(FincaModel.cliente).joinedload(ClienteModel.usuario),
            joinedload(AgendaModel.servicio),
            joinedload(AgendaModel.tecnico).joinedload(TecnicoModel.usuario),
            joinedload(AgendaModel.drone)
        ).join(FincaModel).filter(FincaModel.id_cliente.in_(client_ids))
        if estado:
            query = query.filter(AgendaModel.estado == estado)
            
        offset = (page - 1) * limit
        return query.order_by(AgendaModel.id_turno.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def get_by_id(db: Session, turno_id: int, current_user: UsuarioModel) -> AgendaModel:
        turno = db.query(AgendaModel).options(
            joinedload(AgendaModel.finca).joinedload(FincaModel.cliente).joinedload(ClienteModel.usuario),
            joinedload(AgendaModel.servicio),
            joinedload(AgendaModel.tecnico).joinedload(TecnicoModel.usuario),
            joinedload(AgendaModel.drone)
        ).filter(AgendaModel.id_turno == turno_id).first()
        if not turno:
            raise NotFoundException("Turno no encontrado")
            
        # Autorización por roles
        if current_user.rol == "cliente":
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
            finca = db.query(FincaModel).filter(FincaModel.id_finca == turno.id_finca).first()
            if not cliente or not finca or finca.id_cliente != cliente.id_cliente:
                raise ForbiddenException("El turno no pertenece al usuario autenticado")
        elif current_user.rol == "tecnico":
            tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
            if not tecnico or turno.id_tecnico != tecnico.id_tecnico:
                raise ForbiddenException("No estás asignado a este turno")
                
        return turno

    @staticmethod
    def get_estado_publico(db: Session, turno_id: int) -> dict:
        """Endpoint público para el bot de WhatsApp."""
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == turno_id).first()
        if not turno:
            raise NotFoundException("El número de reserva no se encuentra en nuestro sistema.")
            
        tecnico_nombre = "No asignado"
        if turno.tecnico:
            tecnico_nombre = f"{turno.tecnico.nombre} {turno.tecnico.apellido_1}"
            
        return {
            "id_turno": turno.id_turno,
            "estado": turno.estado,
            "fecha_de_turno": str(turno.fecha_de_turno),
            "tecnico_nombre": tecnico_nombre
        }

    @staticmethod
    def cancelar_turno(db: Session, turno_id: int, current_user: UsuarioModel) -> bool:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == turno_id).first()
        if not turno:
            raise NotFoundException("Turno no encontrado")
            
        # Validar pertenencia si es cliente
        if current_user.rol == "cliente":
            cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
            finca = db.query(FincaModel).filter(FincaModel.id_finca == turno.id_finca).first()
            if not cliente or not finca or finca.id_cliente != cliente.id_cliente:
                raise ForbiddenException("El turno no pertenece al cliente")
                
        # Solo se permite cancelar en estado 'Pendiente', 'Confirmado' o 'Reagendado'
        if turno.estado not in ["Pendiente", "Confirmado", "Reagendado"]:
            raise ConflictException(f"El turno ya está '{turno.estado}', no se puede cancelar")
            
        turno.estado = "Cancelado"
        db.commit()
        
        # Si tenía técnico asignado, notificarle
        if turno.tecnico and turno.tecnico.id_usuario:
            notif = NotificacionModel(
                id_usuario=turno.tecnico.id_usuario,
                titulo="Turno Cancelado por Cliente",
                mensaje=f"El turno del {turno.fecha_de_turno} ha sido cancelado por el cliente.",
                leido=False
            )
            db.add(notif)
            db.commit()
            
        return True

    @staticmethod
    def list_all_admin(db: Session, estado: str = None, id_tecnico: int = None, fecha: date = None) -> list:
        query = db.query(AgendaModel).options(
            joinedload(AgendaModel.finca).joinedload(FincaModel.cliente).joinedload(ClienteModel.usuario),
            joinedload(AgendaModel.servicio),
            joinedload(AgendaModel.tecnico).joinedload(TecnicoModel.usuario),
            joinedload(AgendaModel.drone)
        )
        if estado:
            query = query.filter(AgendaModel.estado == estado)
        if id_tecnico:
            query = query.filter(AgendaModel.id_tecnico == id_tecnico)
        if fecha:
            query = query.filter(AgendaModel.fecha_de_turno == fecha)
        return query.order_by(AgendaModel.fecha_de_turno.desc(), AgendaModel.id_turno.desc()).all()

    @staticmethod
    def force_estado_admin(db: Session, turno_id: int, request: schemas.AgendaForceEstadoRequest) -> AgendaModel:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == turno_id).first()
        if not turno:
            raise NotFoundException("Turno no encontrado")

        # Regla de negocio: No se puede confirmar sin haber cotizado antes y sin respuesta del cliente (salvo demostración gratuita)
        from app.shared.exceptions.exceptions import BadRequestException
        if request.estado == "Confirmado" and not turno.es_demostracion:
            tarifa_val = turno.tarifa if turno.tarifa is not None else request.tarifa
            if not tarifa_val or float(tarifa_val) <= 0:
                raise BadRequestException("No se puede confirmar el servicio sin haber acordado y cotizado una tarifa con el cliente.")

            import json
            historial = []
            if turno.historial_negociacion:
                try:
                    historial = json.loads(turno.historial_negociacion)
                except Exception:
                    historial = []
            cliente_respondio = any(h.get("emisor") == "cliente" for h in historial)
            if not cliente_respondio:
                raise BadRequestException("El cliente aún no ha respondido a la cotización enviada. Debe esperar su respuesta o aceptación antes de confirmar el agendamiento.")

        turno.estado = request.estado
        if request.tarifa is not None:
            try:
                from decimal import Decimal
                turno.tarifa = Decimal(str(request.tarifa))
            except Exception:
                pass

        if request.id_admin_responsable:
            admin = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == int(request.id_admin_responsable)).first()
            if admin:
                admin_label = admin.email or f"Admin #{admin.id_usuarios}"
                turno.observaciones_servicio = f"{turno.observaciones_servicio or ''} | Responsable de gestión: {admin_label}".strip()

        if request.motivo_admin and request.motivo_admin != "Modificado por el administrador":
            turno.observaciones_servicio = f"{turno.observaciones_servicio or ''} | Nota Admin: {request.motivo_admin}".strip()
            
        db.commit()
        db.refresh(turno)
        return turno

    @staticmethod
    def asignar_tecnico_drone(db: Session, turno_id: int, request: schemas.AgendaAsignarRequest) -> AgendaModel:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == turno_id).first()
        if not turno:
            raise NotFoundException("Turno no encontrado")
            
        # Comprobar técnicos (soporte multi-técnico 1, 2 o 3 pilotos)
        nuevos_ids = []
        if getattr(request, 'tecnicos_ids', None) and len(request.tecnicos_ids) > 0:
            nuevos_ids = [int(x) for x in request.tecnicos_ids]
        elif getattr(request, 'id_tecnico', None):
            nuevos_ids = [int(request.id_tecnico)]

        if nuevos_ids:
            # Validar cruce de horario para técnicos asignados en servicios Confirmados o En Proceso
            if turno.hora_inicio_estimada and turno.hora_fin_estimada:
                from sqlalchemy import or_
                for tid in nuevos_ids:
                    cruces_tec = db.query(AgendaModel).filter(
                        or_(
                            AgendaModel.id_tecnico == tid,
                            AgendaModel.tecnicos_adicionales.like(f"%{tid}%")
                        ),
                        AgendaModel.fecha_de_turno == turno.fecha_de_turno,
                        AgendaModel.id_turno != turno_id,
                        AgendaModel.estado.in_(["Confirmado", "En Proceso"]),
                        AgendaModel.hora_inicio_estimada < turno.hora_fin_estimada,
                        AgendaModel.hora_fin_estimada > turno.hora_inicio_estimada
                    ).first()
                    if cruces_tec:
                        tec_obj = db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == tid).first()
                        tec_nombre = f"{tec_obj.nombre} {tec_obj.apellido_1 or ''}".strip() if tec_obj else f"ID {tid}"
                        raise ConflictException(f"El técnico {tec_nombre} ya tiene un servicio asignado en ese bloque horario ({cruces_tec.hora_inicio_estimada} - {cruces_tec.hora_fin_estimada})")

            turno.id_tecnico = nuevos_ids[0]
            turno.tecnicos_adicionales = ",".join(str(x) for x in nuevos_ids[1:]) if len(nuevos_ids) > 1 else None
            
            # Notificar a todos los técnicos asignados por WhatsApp y Correo SOLO si el servicio está Confirmado
            # (Si está en Cotización o Pendiente, NO se envía correo al técnico hasta confirmación del cliente)
            if str(turno.estado or "").strip().lower() == "confirmado":
                finca_nom = turno.finca.nombre_finca if (turno.finca and turno.finca.nombre_finca) else "Finca Registrada"
                muni_nom = (getattr(turno.finca, 'ubicacion_municipio', None) or getattr(turno.finca, 'municipio', None)) if turno.finca else "Ubicación registrada"
                serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo con Dron"
                cli_nom = f"{turno.finca.cliente.nombre} {turno.finca.cliente.apellido_1 or ''}".strip() if (turno.finca and turno.finca.cliente) else "Cliente"
                cli_tel = turno.finca.cliente.telefono if (turno.finca and turno.finca.cliente) else None
                turno_id_val = turno.id_turno
                fecha_str = str(turno.fecha_de_turno)
                hora_str = str(turno.hora_inicio_estimada or "08:00 AM")
                obs_str = turno.observaciones_servicio

                finca_dep = getattr(turno.finca, 'departamento', "") or "" if turno.finca else ""
                finca_ha = float(turno.finca.hectareas) if (turno.finca and turno.finca.hectareas) else None
                finca_maps = getattr(turno.finca, 'maps_url', None) if turno.finca else None
                turno_tarifa = float(turno.tarifa) if turno.tarifa is not None else (0.0 if turno.es_demostracion else None)

                # Extraer cultivo de observaciones si está presente
                import re
                turno_cultivo = None
                if turno.observaciones_servicio:
                    m_cul = re.search(r'Cultivo(?: y Area)?:\s*([^\n\(\r]+)', turno.observaciones_servicio, re.IGNORECASE)
                    if m_cul:
                        turno_cultivo = m_cul.group(1).strip()
                if not turno_cultivo:
                    turno_cultivo = "Demostración Agrícola" if turno.es_demostracion else "Misión Operativa"

                def _notify_pilotos_bg(ids_list, t_id, f_nom, m_nom, s_nom, c_nom, c_tel, f_str, h_str, o_str, dep_str, ha_val, cul_val, maps_val, tar_val):
                    from app.infrastructure.database.session import SessionLocal
                    from app.shared.utils.email_service import EmailService
                    bg_db = SessionLocal()
                    try:
                        for tid in ids_list:
                            tec_obj = bg_db.query(TecnicoModel).filter(TecnicoModel.id_tecnico == tid).first()
                            if tec_obj:
                                try:
                                    if tec_obj.email:
                                        EmailService.send_technician_assigned(
                                            to_email=tec_obj.email.strip().lower(),
                                            tecnico_nombre=f"{tec_obj.nombre} {tec_obj.apellido_1 or ''}".strip(),
                                            id_turno=t_id,
                                            servicio=s_nom,
                                            finca=f_nom,
                                            municipio=m_nom,
                                            fecha=f_str,
                                            hora=h_str,
                                            cliente_nombre=c_nom,
                                            cliente_tel=c_tel,
                                            observaciones=o_str,
                                            departamento=dep_str,
                                            hectareas=ha_val,
                                            cultivo=cul_val,
                                            maps_url=maps_val,
                                            tarifa=tar_val
                                        )
                                except Exception as tec_err:
                                    logger.warning(f"Error al notificar técnico {tid}: {tec_err}")
                    except Exception as bg_err:
                        logger.warning(f"Error en notificación en segundo plano a técnicos: {bg_err}")
                    finally:
                        bg_db.close()

                threading.Thread(
                    target=_notify_pilotos_bg,
                    args=(list(nuevos_ids), turno_id_val, finca_nom, muni_nom, serv_nom, cli_nom, cli_tel, fecha_str, hora_str, obs_str, finca_dep, finca_ha, turno_cultivo, finca_maps, turno_tarifa),
                    daemon=True
                ).start()
        elif getattr(request, 'tecnicos_adicionales', None):
            turno.tecnicos_adicionales = request.tecnicos_adicionales

        # Comprobar dron de forma desacoplada si se especifica
        if request.id_drone:
            drone = db.query(DroneModel).filter(DroneModel.id_drone == request.id_drone).first()
            if not drone:
                raise NotFoundException("Dron no encontrado")
                
            if turno.hora_inicio_estimada and turno.hora_fin_estimada:
                cruces_drone = db.query(AgendaModel).filter(
                    AgendaModel.id_drone == request.id_drone,
                    AgendaModel.fecha_de_turno == turno.fecha_de_turno,
                    AgendaModel.id_turno != turno_id,
                    AgendaModel.estado.in_(["Confirmado", "En Proceso", "Pendiente"]),
                    AgendaModel.hora_inicio_estimada < turno.hora_fin_estimada,
                    AgendaModel.hora_fin_estimada > turno.hora_inicio_estimada
                ).first()
                
                if cruces_drone:
                    raise ConflictException("El dron seleccionado ya está en uso en ese bloque horario")
                
            turno.id_drone = request.id_drone
            
        db.commit()
        db.refresh(turno)
        return turno


# ==========================================
# 7. CASOS DE USO DE BITÁCORA DEL TÉCNICO
# ==========================================
class BitacoraUseCases:
    @staticmethod
    def get_tecnico_agenda(db: Session, current_user: UsuarioModel, fecha: date = None, estado: str = None) -> list:
        if current_user.rol == "administrador":
            query = db.query(AgendaModel)
        else:
            tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
            if not tecnico:
                tecnico = db.query(TecnicoModel).filter(TecnicoModel.email == current_user.email).first()
            if tecnico:
                query = db.query(AgendaModel).filter(
                    or_(
                        AgendaModel.id_tecnico == tecnico.id_tecnico,
                        AgendaModel.tecnicos_adicionales.like(f"%{tecnico.id_tecnico}%")
                    )
                )
            else:
                # Si el usuario no tiene perfil técnico vinculado, no filtrar turnos de otros
                query = db.query(AgendaModel).filter(AgendaModel.id_tecnico == -9999)

        if fecha:
            query = query.filter(AgendaModel.fecha_de_turno == fecha)
            
        if estado:
            query = query.filter(AgendaModel.estado == estado)
            
        return query.order_by(AgendaModel.id_turno.desc()).all()

    @staticmethod
    def registrar_decision(db: Session, turno_id: int, request: schemas.AgendaDecisionRequest, current_user: UsuarioModel) -> AgendaModel:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == turno_id).first()
        if not turno:
            raise NotFoundException("Turno no encontrado")
            
        tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
        if current_user.rol != "administrador":
            if not tecnico:
                raise ForbiddenException("No tienes un perfil técnico asignado")
            if turno.id_tecnico and turno.id_tecnico != tecnico.id_tecnico:
                adic = str(turno.tecnicos_adicionales or "")
                if str(tecnico.id_tecnico) not in adic.split(","):
                    raise ForbiddenException("No eres uno de los técnicos asignados a este turno")
            if not turno.id_tecnico:
                turno.id_tecnico = tecnico.id_tecnico

        if request.decision:
            import json
            from datetime import datetime
            historial = []
            if turno.historial_negociacion:
                try:
                    historial = json.loads(turno.historial_negociacion) if isinstance(turno.historial_negociacion, str) else turno.historial_negociacion
                    if not isinstance(historial, list):
                        historial = []
                except Exception:
                    historial = []

            # Evitar registrar aceptación duplicada si ya aceptó previamente
            ya_acepto = any(h.get("emisor") == "tecnico" and h.get("tipo") in ["aceptacion", "aceptacion_piloto"] for h in historial)
            if not ya_acepto:
                historial.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "emisor": "tecnico",
                    "tipo": "aceptacion_piloto",
                    "tecnico_id": tecnico.id_tecnico if tecnico else turno.id_tecnico,
                    "tecnico_nombre": f"{tecnico.nombre} {tecnico.apellido_1 or ''}".strip() if tecnico else "Piloto",
                    "mensaje": "El piloto asignado ha aceptado la misión y disponibilidad del vuelo."
                })
                turno.historial_negociacion = json.dumps(historial, ensure_ascii=False)

            if tecnico and not turno.id_tecnico:
                turno.id_tecnico = tecnico.id_tecnico

            # REGLA: Si ambos aceptan (cliente y técnico), el agendamiento queda Confirmado
            cliente_acepto = bool(turno.es_demostracion or any(h.get("emisor") == "cliente" and h.get("tipo") == "aceptacion" for h in historial))
            if cliente_acepto:
                turno.estado = "Confirmado"
                try:
                    import threading
                    from app.shared.utils.email_service import EmailService

                    cli = turno.finca.cliente if (turno.finca and turno.finca.cliente) else None
                    cli_email = (cli.usuario.email if cli and cli.usuario else (cli.email if cli else None)) if cli else None
                    cli_nom = f"{cli.nombre} {cli.apellido_1 or ''}".strip() if cli else "Cliente"
                    finca_nom = turno.finca.nombre_finca if turno.finca else "Predio Registrado"
                    serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola"
                    tec_nom = f"{tecnico.nombre} {tecnico.apellido_1 or ''}".strip() if tecnico else "Piloto Técnico"

                    if cli_email and "@" in cli_email:
                        threading.Thread(
                            target=EmailService.send_booking_confirmed,
                            kwargs={
                                "to_email": cli_email.strip().lower(),
                                "nombre_cliente": cli_nom,
                                "id_turno": turno.id_turno,
                                "servicio": serv_nom,
                                "finca": finca_nom,
                                "fecha": str(turno.fecha_de_turno),
                                "hora": str(turno.hora_inicio_estimada or "08:00 AM"),
                                "tecnico_nombre": tec_nom,
                                "dron_modelo": turno.drone.modelo if turno.drone else "DJI AGRAS T40"
                            },
                            daemon=True
                        ).start()
                except Exception:
                    pass
            else:
                turno.estado = "Pendiente por confirmar"
        else:
            if not request.motivo_rechazo or len(request.motivo_rechazo.strip()) < 5:
                raise BadRequestException("Debe proporcionar un motivo de rechazo válido (mínimo 5 caracteres)")
            turno.estado = "Rechazado"
            turno.observaciones_servicio = f"{turno.observaciones_servicio or ''} | Rechazado por piloto: {request.motivo_rechazo}"
            # Liberar técnico y dron
            turno.id_tecnico = None
            turno.id_drone = None
            
        db.commit()
        db.refresh(turno)
        return turno

    @staticmethod
    def checkin(db: Session, turno_id: int, request: schemas.CheckinRequest, current_user: UsuarioModel) -> AgendaModel:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == turno_id).first()
        if not turno:
            raise NotFoundException("Turno no encontrado")
            
        tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
        if current_user.rol != "administrador":
            if not tecnico:
                raise ForbiddenException("No tienes un perfil técnico asignado")
            if turno.id_tecnico and turno.id_tecnico != tecnico.id_tecnico:
                raise ForbiddenException("No eres el técnico asignado a este turno")
            if not turno.id_tecnico:
                turno.id_tecnico = tecnico.id_tecnico
            
        if turno.estado != "Confirmado":
            raise ConflictException(f"No se puede hacer check-in en un turno con estado '{turno.estado}'. Debe estar 'Confirmado'.")
            
        # Registrar hora de llegada real (hora actual del servidor)
        turno.hora_inicio_real = datetime.now().time()
        turno.estado = "En Proceso"
        
        # Si se envían coordenadas de check-in, se asocia en observaciones para control de GPS
        if request.latitud_checkin and request.longitud_checkin:
            turno.observaciones_servicio = f"{turno.observaciones_servicio or ''} | GPS Check-in: ({request.latitud_checkin}, {request.longitud_checkin})"
            
        db.commit()
        db.refresh(turno)
        return turno

    @staticmethod
    def checkout(db: Session, turno_id: int, request: schemas.CheckoutRequest, current_user: UsuarioModel) -> ReporteVueloModel:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == turno_id).first()
        if not turno:
            raise NotFoundException("Turno no encontrado")
            
        tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
        if current_user.rol != "administrador":
            if not tecnico:
                raise ForbiddenException("No tienes un perfil técnico asignado")
            if turno.id_tecnico and turno.id_tecnico != tecnico.id_tecnico:
                raise ForbiddenException("No eres el técnico asignado a este turno")
            if not turno.id_tecnico:
                turno.id_tecnico = tecnico.id_tecnico
            
        if turno.estado not in ["En Proceso", "Confirmado", "Pendiente", "Hecho", "Completado", "Finalizado"]:
            raise ConflictException(f"El turno está '{turno.estado}' y no se puede realizar el checkout")
            
        hora_fin_real = datetime.now().time()
                    
        # Actualizar turno
        turno.hora_fin_real = hora_fin_real
        turno.estado = "Completado"
        if request.retraso_justificacion:
            turno.retraso_justificacion = request.retraso_justificacion
            
        # Si tiene un dron asociado, sumarle horas de vuelo estimadas
        if turno.drone:
            turno.drone.horas_vuelo = (turno.drone.horas_vuelo or 0) + 2 # suma 2 horas estimadas de vuelo
            
        # Crear o actualizar reporte de vuelo (Bitácora/RAC 100)
        reporte = db.query(ReporteVueloModel).filter_by(id_turno=turno_id).first()
        if reporte:
            reporte.insumos_litros_aplicados = request.insumos_litros_aplicados
            reporte.agua_litros = request.agua_litros
            reporte.baterias_utilizadas = request.baterias_utilizadas
            reporte.cumple_rac100 = request.cumple_rac100
            reporte.observaciones_campo = request.observaciones_campo
            reporte.recomendaciones_agronomicas = request.recomendaciones_agronomicas
            reporte.url_entregable_drive = request.url_entregable_drive
        else:
            reporte = ReporteVueloModel(
                id_turno=turno_id,
                insumos_litros_aplicados=request.insumos_litros_aplicados,
                agua_litros=request.agua_litros,
                baterias_utilizadas=request.baterias_utilizadas,
                cumple_rac100=request.cumple_rac100,
                observaciones_campo=request.observaciones_campo,
                recomendaciones_agronomicas=request.recomendaciones_agronomicas,
                url_entregable_drive=request.url_entregable_drive
            )
            db.add(reporte)

        if request.url_entregable_drive:
            entregable = db.query(EntregableModel).filter_by(id_turno=turno_id).first()
            if entregable:
                entregable.url_archivo = request.url_entregable_drive
            else:
                entregable = EntregableModel(
                    id_turno=turno_id,
                    tipo_archivo="Ortofoto / Drive",
                    url_archivo=request.url_entregable_drive,
                    nombre_archivo="Mapa y Entregables en Google Drive"
                )
                db.add(entregable)

        db.commit()
        db.refresh(reporte)
        
        # Crear notificación interna en plataforma para el cliente
        finca = turno.finca
        if finca and finca.cliente and finca.cliente.id_usuario:
            notif = NotificacionModel(
                id_usuario=finca.cliente.id_usuario,
                titulo="Vuelo Completado",
                mensaje=f"El piloto ha finalizado el servicio en la finca {finca.nombre_finca}. Se ha generado el informe técnico del vuelo.",
                leido=False
            )
            db.add(notif)
            db.commit()

        # Enviar correo de confirmación de servicio realizado con cronograma de entregables
        if finca and finca.cliente and finca.cliente.usuario and finca.cliente.usuario.email:
            try:
                from app.shared.utils.email_service import EmailService
                tec_nom = f"{tecnico.nombre} {tecnico.apellido_1 or ''}".strip() if tecnico else "Piloto Flymetrics Certificado"
                hora_str = hora_fin_real.strftime("%I:%M %p") if hasattr(hora_fin_real, 'strftime') else str(hora_fin_real)[:5]
                EmailService.send_service_completed(
                    to_email=finca.cliente.usuario.email,
                    nombre_cliente=finca.cliente.nombre,
                    id_turno=turno.id_turno,
                    servicio=turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola",
                    finca=finca.nombre_finca,
                    tecnico=tec_nom,
                    hora_finalizacion=hora_str,
                    fecha=turno.fecha_de_turno.strftime("%d/%m/%Y") if (turno.fecha_de_turno and hasattr(turno.fecha_de_turno, 'strftime')) else None,
                    url_informe=request.url_entregable_drive,
                    insumos=f"{request.insumos_litros_aplicados} L" if request.insumos_litros_aplicados else None,
                    agua=f"{request.agua_litros} L" if request.agua_litros else None
                )
                if request.url_entregable_drive:
                    EmailService.send_executive_report_ready(
                        to_email=finca.cliente.usuario.email,
                        nombre_cliente=finca.cliente.nombre,
                        id_turno=turno.id_turno,
                        servicio=turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola",
                        finca=finca.nombre_finca,
                        url_informe=request.url_entregable_drive,
                        tipo_informe="Bitácora de Vuelo / Informe Ejecutivo"
                    )
            except Exception as mail_err:
                print(f"[CHECKOUT EMAIL ERROR] {mail_err}")

        # Notificar a los administradores del sistema (Servicio Completado)
        try:
            from app.shared.utils.email_service import EmailService
            tec_nom = f"{tecnico.nombre} {tecnico.apellido_1 or ''}".strip() if tecnico else "Piloto Flymetrics Certificado"
            cli_nom = f"{finca.cliente.nombre} {finca.cliente.apellido_1 or ''}".strip() if (finca and finca.cliente) else "Cliente"
            finca_nom = finca.nombre_finca if finca else "Predio Registrado"
            serv_nom = turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola"
            hora_str = hora_fin_real.strftime("%I:%M %p") if hasattr(hora_fin_real, 'strftime') else str(hora_fin_real)[:5]
            fecha_str = turno.fecha_de_turno.strftime("%d/%m/%Y") if (turno.fecha_de_turno and hasattr(turno.fecha_de_turno, 'strftime')) else str(turno.fecha_de_turno or '')
            EmailService.send_admin_service_completed(
                id_turno=turno.id_turno,
                cliente_nombre=cli_nom,
                servicio=serv_nom,
                finca=finca_nom,
                tecnico_nombre=tec_nom,
                fecha=fecha_str,
                hora_fin=hora_str
            )
        except Exception as mail_err_adm:
            print(f"[CHECKOUT ADMIN EMAIL ERROR] {mail_err_adm}")
            
        return reporte

    @staticmethod
    def list_reportes(db: Session, current_user: UsuarioModel, id_turno: int = None, id_tecnico: int = None) -> list:
        query = db.query(ReporteVueloModel).join(AgendaModel)
        
        if current_user.rol == "tecnico":
            tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
            if not tecnico:
                return []
            query = query.filter(AgendaModel.id_tecnico == tecnico.id_tecnico)
        else:
            # administrador
            if id_tecnico:
                query = query.filter(AgendaModel.id_tecnico == id_tecnico)
                
        if id_turno:
            query = query.filter(ReporteVueloModel.id_turno == id_turno)
            
        return query.all()


# ==========================================
# 8. CASOS DE USO DE DRONES Y MANTENIMIENTO
# ==========================================
class FlotaUseCases:
    @staticmethod
    def list_drones(db: Session, estado: str = None) -> list:
        query = db.query(DroneModel)
        if estado:
            query = query.filter(DroneModel.estado == estado)
        return query.all()

    @staticmethod
    def create_drone(db: Session, request: schemas.DroneCreate) -> DroneModel:
        drone = DroneModel(
            modelo=request.modelo,
            tipo=request.tipo,
            estado=request.estado,
            numero_serie=request.numero_serie,
            ultima_revision=request.ultima_revision,
            id_tecnico_asignado=getattr(request, 'id_tecnico_asignado', None),
            horas_vuelo=0
        )
        db.add(drone)
        db.commit()
        db.refresh(drone)
        return drone

    @staticmethod
    def update_drone(db: Session, drone_id: int, request: schemas.DroneUpdate) -> DroneModel:
        drone = db.query(DroneModel).filter(DroneModel.id_drone == drone_id).first()
        if not drone:
            raise NotFoundException("Dron no encontrado")
            
        data = request.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(drone, key, value)
            
        db.commit()
        db.refresh(drone)
        return drone

    @staticmethod
    def registrar_mantenimiento(db: Session, drone_id: int, request: schemas.MantenimientoCreate) -> MantenimientoModel:
        drone = db.query(DroneModel).filter(DroneModel.id_drone == drone_id).first()
        if not drone:
            raise NotFoundException("Dron no encontrado")
            
        # Poner dron en mantenimiento
        drone.estado = "mantenimiento"
        
        mantenimiento = MantenimientoModel(
            id_drone=drone_id,
            tipo_mantenimiento=request.tipo_mantenimiento,
            descripcion_falla=request.descripcion_falla,
            fecha_ingreso=request.fecha_ingreso,
            fecha_salida=request.fecha_salida,
            costo_mantenimiento=request.costo_mantenimiento,
            responsable_tecnico=request.responsable_tecnico
        )
        db.add(mantenimiento)
        db.commit()
        db.refresh(mantenimiento)
        return mantenimiento

    @staticmethod
    def ver_historial_mantenimientos(db: Session, drone_id: int) -> list:
        # Verificar que el dron existe
        drone = db.query(DroneModel).filter(DroneModel.id_drone == drone_id).first()
        if not drone:
            raise NotFoundException("Dron no encontrado")
        return db.query(MantenimientoModel).filter(MantenimientoModel.id_drone == drone_id).all()


# ==========================================
# 9. CASOS DE USO DE ENTREGABLES
# ==========================================
class EntregableUseCases:
    @staticmethod
    def subir_entregable(db: Session, request: schemas.EntregableCreate) -> EntregableModel:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == request.id_turno).first()
        if not turno:
            raise NotFoundException("Turno no encontrado")
            
        # Check if an entregable for this turno exists to update it or create new
        entregable = db.query(EntregableModel).filter(
            EntregableModel.id_turno == request.id_turno,
            EntregableModel.tipo_archivo == request.tipo_archivo
        ).first()

        if not entregable:
            entregable = db.query(EntregableModel).filter(EntregableModel.id_turno == request.id_turno).first()

        if entregable:
            entregable.tipo_archivo = request.tipo_archivo
            entregable.url_archivo = request.url_archivo
            if getattr(request, 'nombre_archivo', None):
                entregable.nombre_archivo = request.nombre_archivo
        else:
            entregable = EntregableModel(
                id_turno=request.id_turno,
                tipo_archivo=request.tipo_archivo,
                url_archivo=request.url_archivo,
                nombre_archivo=getattr(request, 'nombre_archivo', None)
            )
            db.add(entregable)

        # Sync with ReporteVueloModel
        rep = db.query(ReporteVueloModel).filter(ReporteVueloModel.id_turno == request.id_turno).first()
        if rep:
            if request.url_archivo:
                rep.url_entregable_drive = request.url_archivo
            if getattr(request, 'notas', None):
                rep.recomendaciones_agronomicas = request.notas
        else:
            rep = ReporteVueloModel(
                id_turno=request.id_turno,
                insumos_litros_aplicados=15.0,
                agua_litros=100.0,
                baterias_utilizadas=4,
                cumple_rac100=1,
                url_entregable_drive=request.url_archivo,
                recomendaciones_agronomicas=getattr(request, 'notas', None) or "Información y entregables agronómicos procesados en la nube.",
                observaciones_campo="Operación completada con enlace de entregable."
            )
            db.add(rep)

        db.commit()
        db.refresh(entregable)
        
        # Enviar notificación y WhatsApp de entregables al cliente
        finca = turno.finca
        if finca and finca.cliente:
            cliente = finca.cliente
            if cliente.id_usuario:
                notif = NotificacionModel(
                    id_usuario=cliente.id_usuario,
                    titulo="Entregable de mapa disponible",
                    mensaje=f"Se ha subido el archivo '{request.tipo_archivo}' correspondiente al turno del {turno.fecha_de_turno} en la finca {finca.nombre_finca}.",
                    leido=False
                )
                db.add(notif)
                db.commit()
                
        return entregable

    @staticmethod
    def ver_mis_entregables(db: Session, current_user: UsuarioModel, id_turno: int = None) -> list:
        cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
        if not cliente:
            raise NotFoundException("Perfil de cliente no encontrado")
            
        query = db.query(EntregableModel).join(AgendaModel).join(FincaModel).filter(FincaModel.id_cliente == cliente.id_cliente)
        if id_turno:
            query = query.filter(EntregableModel.id_turno == id_turno)
            
        return query.all()

    @staticmethod
    def list_all_entregables(db: Session, id_turno: int = None) -> list:
        query = db.query(EntregableModel)
        if id_turno:
            query = query.filter(EntregableModel.id_turno == id_turno)
        return query.all()


# ==========================================
# 10. CASOS DE USO DE PAGOS
# ==========================================
class PagoUseCases:
    @staticmethod
    def registrar_pago(db: Session, request: schemas.PagoCreate) -> PagoModel:
        # Verificar turno
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == request.id_turno).first()
        if not turno:
            raise NotFoundException("Turno no encontrado")
            
        # Regla: Pago se registra para cualquier turno activo o completado
        est_lower = str(turno.estado or "").lower()
        if est_lower in ["cancelado"]:
            raise BadRequestException("No se puede registrar pago para un turno cancelado.")
            
        # Regla: Evitar doble pago
        existing_pago = db.query(PagoModel).filter(PagoModel.id_turno == request.id_turno).first()
        if existing_pago:
            raise ConflictException("Ya existe un pago registrado para este turno")
            
        pago = PagoModel(
            id_turno=request.id_turno,
            monto=request.monto,
            metodo_pago=request.metodo_pago,
            referencia_transaccion=request.referencia_transaccion
        )
        db.add(pago)
        db.commit()
        db.refresh(pago)
        return pago

    @staticmethod
    def ver_mis_pagos(db: Session, current_user: UsuarioModel, page: int = 1, limit: int = 10) -> list:
        cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
        if not cliente:
            raise NotFoundException("Perfil de cliente no encontrado")
            
        offset = (page - 1) * limit
        return db.query(PagoModel).join(AgendaModel).join(FincaModel).filter(
            FincaModel.id_cliente == cliente.id_cliente
        ).offset(offset).limit(limit).all()

    @staticmethod
    def list_all_pagos(db: Session, fecha_inicio: date = None, fecha_fin: date = None, metodo_pago: str = None) -> list:
        query = db.query(PagoModel)
        if fecha_inicio:
            query = query.filter(PagoModel.fecha_pago >= datetime.combine(fecha_inicio, time.min))
        if fecha_fin:
            query = query.filter(PagoModel.fecha_pago <= datetime.combine(fecha_fin, time.max))
        if metodo_pago:
            query = query.filter(PagoModel.metodo_pago == metodo_pago)
        return query.all()


# ==========================================
# 11. CASOS DE USO DE NOTIFICACIONES
# ==========================================
class NotificacionUseCases:
    @staticmethod
    def ver_notificaciones(db: Session, current_user: UsuarioModel, leido: bool = None) -> list:
        query = db.query(NotificacionModel).filter(NotificacionModel.id_usuario == current_user.id_usuarios)
        if leido is not None:
            query = query.filter(NotificacionModel.leido == leido)
        return query.order_by(NotificacionModel.fecha_envio.desc()).all()

    @staticmethod
    def marcar_leida(db: Session, notificacion_id: int, current_user: UsuarioModel) -> NotificacionModel:
        notif = db.query(NotificacionModel).filter(NotificacionModel.id_notificacion == notificacion_id).first()
        if not notif:
            raise NotFoundException("Notificación no encontrada")
            
        if notif.id_usuario != current_user.id_usuarios:
            raise ForbiddenException("La notificación no pertenece al usuario autenticado")
            
        notif.leido = True
        db.commit()
        db.refresh(notif)
        return notif

    @staticmethod
    def crear_notificacion(db: Session, request: schemas.NotificacionCreate) -> NotificacionModel:
        # Verificar usuario
        user = db.query(UsuarioModel).filter(UsuarioModel.id_usuarios == request.id_usuario).first()
        if not user:
            raise NotFoundException("Usuario no encontrado")
            
        notif = NotificacionModel(
            id_usuario=request.id_usuario,
            titulo=request.titulo,
            mensaje=request.mensaje,
            leido=False
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif


class PQRUseCases:
    @staticmethod
    def crear_pqr(db: Session, request: schemas.PQRCreate, current_user: UsuarioModel) -> PQRModel:
        content = request.mensaje or request.descripcion or ""
        pqr = PQRModel(
            id_usuario=current_user.id_usuarios,
            tipo=request.tipo,
            asunto=request.asunto,
            mensaje=content,
            estado="Abierto"
        )
        db.add(pqr)
        db.commit()
        db.refresh(pqr)
        return pqr

    @staticmethod
    def listar_pqrs(db: Session, current_user: UsuarioModel) -> list:
        if current_user.rol == "administrador":
            return db.query(PQRModel).all()
        return db.query(PQRModel).filter(PQRModel.id_usuario == current_user.id_usuarios).all()

    @staticmethod
    def obtener_pqr(db: Session, id_pqr: int, current_user: UsuarioModel) -> PQRModel:
        pqr = db.query(PQRModel).filter(PQRModel.id_pqr == id_pqr).first()
        if not pqr:
            raise NotFoundException("Ticket PQR no encontrado")
        if current_user.rol != "administrador" and pqr.id_usuario != current_user.id_usuarios:
            raise ForbiddenException("No tienes permiso para ver este ticket")
        return pqr

    @staticmethod
    def responder_pqr(db: Session, id_pqr: int, request: schemas.MensajePQRCreate, current_user: UsuarioModel) -> MensajePQRModel:
        pqr = db.query(PQRModel).filter(PQRModel.id_pqr == id_pqr).first()
        if not pqr:
            raise NotFoundException("Ticket PQR no encontrado")
        if current_user.rol != "administrador" and pqr.id_usuario != current_user.id_usuarios:
            raise ForbiddenException("No tienes permiso para responder a este ticket")
        
        id_emisor = current_user.id_usuarios
        if current_user.rol == "administrador":
            id_receptor = pqr.id_usuario
        else:
            admin = db.query(UsuarioModel).filter_by(rol="administrador").first()
            id_receptor = admin.id_usuarios if admin else 1

        msg = MensajePQRModel(
            id_pqr=id_pqr,
            id_usuario=id_emisor,
            id_emisor=id_emisor,
            id_receptor=id_receptor,
            mensaje=request.mensaje
        )
        pqr.estado = "En Proceso" if current_user.rol == "administrador" else "Abierto"
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def cerrar_pqr(db: Session, id_pqr: int, current_user: UsuarioModel) -> PQRModel:
        pqr = db.query(PQRModel).filter(PQRModel.id_pqr == id_pqr).first()
        if not pqr:
            raise NotFoundException("Ticket PQR no encontrado")
        if current_user.rol != "administrador":
            raise ForbiddenException("Solo los administradores pueden cerrar tickets")
        pqr.estado = "Cerrado"
        db.commit()
        db.refresh(pqr)
        return pqr

