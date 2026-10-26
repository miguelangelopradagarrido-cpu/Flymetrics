from fastapi import APIRouter, Depends, status, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
import re

from app.infrastructure.database.session import get_db
from app.infrastructure.database.models.models import UsuarioModel, ClienteModel, PQRModel, NotificacionModel
from app.infrastructure.security.jwt_handler import hash_password
from app.shared.responses.response import success_response
from app.presentation.api.dependencies.auth import RoleChecker, get_current_user

router = APIRouter(prefix="/contacto", tags=["Contacto Web (Público)"])
admin_required = RoleChecker(["administrador"])


class ContactoPublicoRequest(BaseModel):
    nombre: str
    telefono: str
    email: str
    tipo_documento: Optional[str] = "CC"
    numero_documento: Optional[str] = None
    cedula: Optional[str] = None
    tipo: Optional[str] = "Cotización de servicio"
    asunto: Optional[str] = None
    sector: Optional[str] = None
    hectareas: Optional[float] = None
    cultivo: Optional[str] = None
    ubicacion: Optional[str] = None
    mensaje: Optional[str] = ""


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/peticion", status_code=status.HTTP_201_CREATED)
def recibir_contacto_web(
    request: ContactoPublicoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Endpoint público (sin autenticación) para recibir solicitudes de cotización e información 24 horas
    desde la página de inicio. Guarda la solicitud en la base de datos (tabla_pqrs) y genera una notificación
    automática en la base de datos para todos los administradores del sistema.
    """
    # Intentar encontrar o crear usuario para el contacto
    usuario_sistema = db.query(UsuarioModel).filter(
        UsuarioModel.rol == "administrador"
    ).first()

    # Buscar si ya existe un usuario con ese email
    usuario_contacto = db.query(UsuarioModel).filter(
        UsuarioModel.email == request.email.strip().lower()
    ).first()

    doc_clean = (request.numero_documento or request.cedula or "").strip()
    tipo_doc_clean = (request.tipo_documento or "CC").strip().upper()

    # Si no existe, crear cuenta de cliente provisional con clave inexpugnable
    if not usuario_contacto:
        try:
            import secrets
            # Clave criptográficamente aleatoria e inexpugnable (no determinista)
            random_secret = secrets.token_urlsafe(32)
            usuario_contacto = UsuarioModel(
                email=request.email.strip().lower(),
                contraseña=hash_password(random_secret),
                rol="cliente"
            )
            db.add(usuario_contacto)
            db.flush()

            # Crear perfil de cliente básico con documento registrado
            nombre_partes = request.nombre.strip().split(" ", 1)
            cliente = ClienteModel(
                id_usuario=usuario_contacto.id_usuarios,
                nombre=nombre_partes[0],
                apellido_1=nombre_partes[1] if len(nombre_partes) > 1 else "Contacto",
                telefono=request.telefono.strip(),
                numero_documento=doc_clean or None,
                verificado=False
            )
            db.add(cliente)
            db.flush()
        except Exception:
            db.rollback()
            usuario_contacto = usuario_sistema
    elif doc_clean:
        # Si ya existía el usuario, asegurar que su perfil tenga el documento guardado si estaba vacío
        try:
            cli = db.query(ClienteModel).filter(ClienteModel.id_usuario == usuario_contacto.id_usuarios).first()
            if cli and not cli.numero_documento:
                cli.numero_documento = doc_clean
                db.flush()
        except Exception:
            pass

    # ID de usuario asociado para el ticket
    id_usuario_pqr = usuario_contacto.id_usuarios if usuario_contacto else (
        usuario_sistema.id_usuarios if usuario_sistema else 1
    )

    ha_str = f"{request.hectareas} ha" if request.hectareas else "No especificado"
    cultivo_str = request.cultivo if request.cultivo else (request.sector if request.sector else "No especificado")
    ubicacion_str = request.ubicacion if request.ubicacion else "No especificado"
    doc_display = f"{tipo_doc_clean}: {doc_clean}" if doc_clean else "No especificado"

    cuerpo_mensaje = (
        f"📋 SOLICITUD DE COTIZACIÓN 24 HORAS (DESDE LA PÁGINA WEB)\n\n"
        f"👤 Nombre: {request.nombre.strip()}\n"
        f"🪪 Documento / Identificación: {doc_display}\n"
        f"📱 Teléfono/WhatsApp: {request.telefono.strip()}\n"
        f"📧 Email: {request.email.strip()}\n"
        f"🌾 Hectáreas: {ha_str}\n"
        f"🌱 Cultivo: {cultivo_str}\n"
        f"📍 Ubicación/Municipio: {ubicacion_str}\n"
        f"🗂️ Servicio Requerido: {request.tipo}\n\n"
        f"💬 Mensaje / Consulta:\n{request.mensaje.strip() if request.mensaje else 'Sin mensaje adicional'}\n\n"
        f"---\n⏰ Recibido: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    pqr = PQRModel(
        id_usuario=id_usuario_pqr,
        tipo="Petición",
        asunto=f"[CONTACTO 24H] {request.tipo} — {request.nombre.strip()} ({ha_str})",
        mensaje=cuerpo_mensaje,
        estado="Abierto"
    )
    db.add(pqr)
    db.flush()

    # Notificar en la base de datos a todos los administradores
    admins = db.query(UsuarioModel).filter(UsuarioModel.rol == "administrador").all()
    for adm in admins:
        notif = NotificacionModel(
            id_usuario=adm.id_usuarios,
            titulo=f"📩 Nueva Cotización 24h: {request.nombre.strip()}",
            mensaje=f"Se ha recibido una nueva solicitud de {request.tipo} para {ha_str} de {cultivo_str}. Doc: {doc_display} | Tel: {request.telefono}",
            leido=False
        )
        db.add(notif)

    db.commit()
    db.refresh(pqr)

    # Despacho Asíncrono en BackgroundTasks para máxima fluidez de la interfaz web
    try:
        from app.shared.utils.email_service import EmailService
        background_tasks.add_task(
            EmailService.send_quote_confirmation,
            to_email=request.email.strip().lower(),
            nombre_cliente=request.nombre.strip(),
            id_pqr=pqr.id_pqr,
            servicio=request.tipo or "Servicios Aéreos Especializados",
            hectareas=float(request.hectareas or 0.0),
            cultivo=cultivo_str,
            ubicacion=ubicacion_str,
            mensaje=request.mensaje
        )
        background_tasks.add_task(
            EmailService.send_admin_new_quote,
            nombre=request.nombre.strip(),
            email=request.email.strip().lower(),
            telefono=request.telefono.strip(),
            documento=doc_display,
            servicio=request.tipo or "Servicios Aéreos Especializados",
            hectareas=ha_str,
            cultivo=cultivo_str,
            ubicacion=ubicacion_str,
            mensaje=request.mensaje or "Sin mensaje adicional",
            id_pqr=pqr.id_pqr
        )
    except Exception as mail_err:
        print(f"[CONTACTO EMAIL NOTIF ERROR] No se pudo encolar correo de cotización: {mail_err}")

    return success_response(
        message="¡Solicitud recibida! Un asesor de Flymetrics te contactará en menos de 24 horas.",
        data={
            "recibido": True,
            "id_ticket": pqr.id_pqr,
            "nombre": request.nombre,
            "tipo_documento": tipo_doc_clean,
            "numero_documento": doc_clean,
            "email": request.email,
            "telefono": request.telefono,
            "hectareas": request.hectareas
        },
        status_code=201
    )


@router.get("/solicitudes", status_code=status.HTTP_200_OK)
@router.get("/cotizaciones", status_code=status.HTTP_200_OK)
@router.get("", status_code=status.HTTP_200_OK)
def listar_solicitudes_contacto(
    db: Session = Depends(get_db)
):
    """
    Obtiene la lista de todas las solicitudes de contacto y cotización recibidas desde la landing page con todos sus campos completos.
    """
    solicitudes = db.query(PQRModel).filter(
        ~PQRModel.asunto.like("%[INFORMES SHAREPOINT]%"),
        ~PQRModel.asunto.like("%[FACTURACIÓN ALEGRA]%"),
        (
            (PQRModel.asunto.like("%[CONTACTO%")) | 
            (PQRModel.asunto.like("%Contacto%")) | 
            (PQRModel.asunto.like("%Cotización%")) |
            (PQRModel.mensaje.like("%SOLICITUD DE COTIZACIÓN%")) |
            (PQRModel.mensaje.like("%[CONTACTO%"))
        )
    ).order_by(PQRModel.fecha_creacion.desc()).all()

    if not solicitudes:
        solicitudes = db.query(PQRModel).filter(
            ~PQRModel.asunto.like("%[INFORMES SHAREPOINT]%"),
            ~PQRModel.asunto.like("%[FACTURACIÓN ALEGRA]%")
        ).order_by(PQRModel.fecha_creacion.desc()).limit(50).all()
    
    result = []
    for p in solicitudes:
        txt = p.mensaje or ""
        # Extraer campos mediante regex si existen
        nombre_match = re.search(r"Nombre:\s*([^\n]+)", txt)
        doc_match = re.search(r"(?:Documento\s*/\s*Identificación|Documento|Cédula|NIT|CC):\s*([^\n]+)", txt, re.IGNORECASE)
        tel_match = re.search(r"(?:Teléfono/WhatsApp|Teléfono|Celular|WhatsApp):\s*([^\n]+)", txt, re.IGNORECASE)
        email_match = re.search(r"Email:\s*([^\n]+)", txt, re.IGNORECASE)
        ha_match = re.search(r"Hectáreas:\s*([^\n]+)", txt, re.IGNORECASE)
        cultivo_match = re.search(r"Cultivo:\s*([^\n]+)", txt, re.IGNORECASE)
        ubicacion_match = re.search(r"(?:Ubicación/Municipio|Ubicación|Municipio):\s*([^\n]+)", txt, re.IGNORECASE)
        servicio_match = re.search(r"Servicio Requerido:\s*([^\n]+)", txt, re.IGNORECASE)
        msg_match = re.search(r"(?:Mensaje / Consulta|Mensaje|Consulta):\s*\n([^\n-]+)", txt, re.IGNORECASE)

        nombre = nombre_match.group(1).strip() if nombre_match else (p.usuario.cliente.nombre if (p.usuario and getattr(p.usuario, 'cliente', None)) else "Contacto Web")
        
        # Resolver documento de la solicitud o del cliente vinculado
        raw_doc = doc_match.group(1).strip() if doc_match else ""
        if not raw_doc and p.usuario and getattr(p.usuario, 'cliente', None) and p.usuario.cliente.numero_documento:
            raw_doc = f"CC: {p.usuario.cliente.numero_documento}"
        
        tipo_doc = "CC"
        num_doc = raw_doc
        if ":" in raw_doc:
            parts = raw_doc.split(":", 1)
            tipo_doc = parts[0].strip().upper()
            num_doc = parts[1].strip()
        elif " " in raw_doc:
            parts = raw_doc.split(" ", 1)
            if parts[0].upper() in ["CC", "NIT", "CE", "PASAPORTE", "TI"]:
                tipo_doc = parts[0].upper()
                num_doc = parts[1].strip()

        telefono = tel_match.group(1).strip() if tel_match else (p.usuario.cliente.telefono if (p.usuario and getattr(p.usuario, 'cliente', None)) else "")
        email = email_match.group(1).strip() if email_match else (p.usuario.email if p.usuario else "")
        hectareas = ha_match.group(1).strip() if ha_match else "—"
        cultivo = cultivo_match.group(1).strip() if cultivo_match else "—"
        ubicacion = ubicacion_match.group(1).strip() if ubicacion_match else "—"
        servicio = servicio_match.group(1).strip() if servicio_match else p.asunto
        mensaje_limpio = msg_match.group(1).strip() if msg_match else (txt.replace("📋 SOLICITUD DE COTIZACIÓN 24 HORAS (DESDE LA PÁGINA WEB)", "").strip() or txt)

        result.append({
            "id": p.id_pqr,
            "id_pqr": p.id_pqr,
            "asunto": p.asunto,
            "nombre": nombre,
            "tipo_documento": tipo_doc,
            "numero_documento": num_doc,
            "documento": f"{tipo_doc}: {num_doc}" if num_doc else "No especificado",
            "telefono": telefono,
            "email": email,
            "hectareas": hectareas,
            "cultivo": cultivo,
            "ubicacion": ubicacion,
            "servicio": servicio,
            "mensaje": mensaje_limpio,
            "mensaje_completo": txt,
            "estado": p.estado or "Abierto",
            "fecha": p.fecha_creacion.isoformat() if p.fecha_creacion else None,
            "respuesta": p.mensajes[0].mensaje if (p.mensajes and len(p.mensajes) > 0) else None
        })

    return success_response(message="Solicitudes de contacto obtenidas exitosamente", data=result)


@router.patch("/solicitudes/{id_pqr}/estado", status_code=status.HTTP_200_OK)
def cambiar_estado_solicitud(
    id_pqr: int,
    request: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    Permite al administrador cambiar el estado de una solicitud (Abierto, En Proceso, Atendido, Cerrado).
    """
    pqr = db.query(PQRModel).filter(PQRModel.id_pqr == id_pqr).first()
    if not pqr:
        from app.shared.exceptions.exceptions import NotFoundException
        raise NotFoundException("Solicitud no encontrada")
    
    nuevo_estado = request.get("estado", "Atendido")
    pqr.estado = nuevo_estado
    db.commit()
    db.refresh(pqr)
    return success_response(message=f"Estado de solicitud #{id_pqr} actualizado a '{nuevo_estado}'", data={"id_pqr": id_pqr, "estado": nuevo_estado})


@router.get("/solicitudes/{id_pqr}", status_code=status.HTTP_200_OK)
def detalle_solicitud_contacto(
    id_pqr: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    Obtiene el detalle de una solicitud de contacto específica.
    """
    pqr = db.query(PQRModel).filter(PQRModel.id_pqr == id_pqr).first()
    if not pqr:
        from app.shared.exceptions.exceptions import NotFoundException
        raise NotFoundException("Solicitud no encontrada")
    return success_response(message="Detalle de solicitud obtenido", data={"id_pqr": pqr.id_pqr, "asunto": pqr.asunto, "mensaje": pqr.mensaje, "estado": pqr.estado})


@router.delete("/solicitudes/{id_pqr}", status_code=status.HTTP_200_OK)
def eliminar_solicitud_contacto(
    id_pqr: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    Elimina permanentemente una solicitud de contacto por su id_pqr.
    """
    pqr = db.query(PQRModel).filter(PQRModel.id_pqr == id_pqr).first()
    if not pqr:
        from app.shared.exceptions.exceptions import NotFoundException
        raise NotFoundException("Solicitud no encontrada")
    
    db.delete(pqr)
    db.commit()
    return success_response(message=f"Solicitud de cotización #{id_pqr} eliminada permanentemente.", data={"id_pqr": id_pqr, "eliminado": True})



@router.get("/config/sistema", status_code=status.HTTP_200_OK)
def get_public_system_config(db: Session = Depends(get_db)):
    """
    Endpoint público para sincronización omnicanal de canales oficiales y plantillas de WhatsApp.
    """
    from app.infrastructure.database.models.models import SystemConfigModel
    import json
    config_record = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "perfil_corporativo").first()
    default_data = {
        "empresa": "Flymetrics S.A.S.",
        "nit": "902036414-3",
        "telefono": "+57 314 3764972",
        "whatsapp": "+57 314 3764972",
        "email": "comercial@flymetrics.com.co",
        "direccion": "Bogotá, Colombia",
        "wa_template_24h": "Hola {nombre}, te contactamos desde Flymetrics Colombia sobre tu solicitud de {servicio} ({hectareas} ha).",
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
    return success_response(message="Configuración corporativa obtenida exitosamente", data=data)


@router.get("/zonas", status_code=status.HTTP_200_OK)
def get_public_zonas(db: Session = Depends(get_db)):
    """
    Endpoint público para obtener las zonas de mayor demanda y presencia para el mapa interactivo.
    """
    from app.infrastructure.database.models.models import SystemConfigModel
    import json
    config_record = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "perfil_corporativo").first()
    default_zonas = [
        {"nombre": "Cundinamarca", "tag": "Base Central", "lat": 4.7110, "lng": -74.0721, "descripcion": "Sabana de Bogotá, Facatativá, Chía, Madrid — Flores, Papa y Hortalizas", "servicio": "Monitoreo Multiespectral, Cartografía y Aspersión", "demanda": "Base Central y Operaciones Sabana"},
        {"nombre": "Meta", "tag": "Operación Continua", "lat": 4.1420, "lng": -73.6266, "descripcion": "Villavicencio, Puerto López, Granada — Palma, Soya, Maíz y Ganadería", "servicio": "Fumigación de Palma, Soya, Maíz y Ganadería", "demanda": "Operación Continua Llanos"},
        {"nombre": "Huila", "tag": "Laderas y Valles", "lat": 2.9273, "lng": -75.2819, "descripcion": "Neiva, Campoalegre, Pitalito — Café de Especialidad, Arroz y Frutales", "servicio": "Aspersión en Café de Especialidad, Arroz y Frutales", "demanda": "Laderas y Valles Andinos"},
        {"nombre": "Tolima", "tag": "Planicies de Riego", "lat": 4.1420, "lng": -74.8880, "descripcion": "Espinal, Ibagué, Saldaña — Arroz, Maíz, Algodón y Pasturas", "servicio": "Fumigación y Fertilización de Arroz, Maíz y Pastos", "demanda": "Planicies de Riego"}
    ]
    if config_record and config_record.valor:
        try:
            val = json.loads(config_record.valor)
            if isinstance(val, dict) and "zonas_mayor_presencia" in val and isinstance(val["zonas_mayor_presencia"], list) and len(val["zonas_mayor_presencia"]) > 0:
                valid_zonas = []
                for z in val["zonas_mayor_presencia"]:
                    if not isinstance(z, dict):
                        continue
                    try:
                        lat_val = float(z.get("lat") if z.get("lat") is not None else z.get("latitud", 999))
                        lng_val = float(z.get("lng") if z.get("lng") is not None else z.get("longitud", 999))
                        if -90.0 <= lat_val <= 90.0 and -180.0 <= lng_val <= 180.0:
                            clean_z = dict(z)
                            clean_z["lat"] = lat_val
                            clean_z["lng"] = lng_val
                            valid_zonas.append(clean_z)
                    except (ValueError, TypeError):
                        continue
                if valid_zonas:
                    return success_response(message="Zonas obtenidas exitosamente", data=valid_zonas)
        except Exception:
            pass
    return success_response(message="Zonas obtenidas exitosamente", data=default_zonas)


@router.post("/solicitar-soporte-facturacion", status_code=status.HTTP_200_OK)
def solicitar_soporte_facturacion(
    request: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """
    Registra automáticamente una solicitud de soporte / enlace de facturación Alegra en la base de datos (tabla_pqrs y notificaciones).
    """
    cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
    nombre_cli = f"{cliente.nombre} {cliente.apellido_1 or ''}".strip() if cliente else current_user.email
    cedula_cli = cliente.numero_documento if (cliente and cliente.numero_documento) else "No registrada"
    tel_cli = cliente.telefono if (cliente and cliente.telefono) else "No registrado"

    pqr = PQRModel(
        id_usuario=current_user.id_usuarios,
        tipo="Petición",
        asunto=f"[FACTURACIÓN ALEGRA] Solicitud de factura / portal para {nombre_cli}",
        mensaje=(
            f"📋 SOLICITUD DE FACTURACIÓN ELECTRÓNICA & INTEGRACIÓN ALEGRA\n\n"
            f"👤 Cliente: {nombre_cli}\n"
            f"🆔 CC / NIT: {cedula_cli}\n"
            f"📱 Teléfono: {tel_cli}\n"
            f"📧 Email: {current_user.email}\n"
            f"💬 Detalle: El cliente solicita vinculación y acceso directo a su facturación electrónica en Alegra.\n\n"
            f"---\n⏰ Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        ),
        estado="Abierto"
    )
    db.add(pqr)

    # Notificar a administradores
    admins = db.query(UsuarioModel).filter(UsuarioModel.rol == "administrador").all()
    for adm in admins:
        notif = NotificacionModel(
            id_usuario=adm.id_usuarios,
            titulo=f"🧾 Solicitud Facturación Alegra: {nombre_cli}",
            mensaje=f"El cliente {nombre_cli} solicita vincular su cuenta o factura electrónica en Alegra.",
            leido=False
        )
        db.add(notif)

    db.commit()
    return success_response(message="Solicitud de facturación registrada exitosamente en la base de datos.", data={"id_pqr": pqr.id_pqr})


@router.post("/solicitar-soporte-sharepoint")
def solicitar_soporte_sharepoint(
    request: dict,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """
    Registra automáticamente una solicitud de vinculación de carpeta SharePoint / Informes Ejecutivos en la base de datos (tabla_pqrs y notificaciones).
    """
    cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
    nombre_cli = f"{cliente.nombre} {cliente.apellido_1 or ''}".strip() if cliente else current_user.email
    cedula_cli = cliente.numero_documento if (cliente and cliente.numero_documento) else "No registrada"
    tel_cli = cliente.telefono if (cliente and cliente.telefono) else "No registrado"

    pqr = PQRModel(
        id_usuario=current_user.id_usuarios,
        tipo="Petición",
        asunto=f"[INFORMES SHAREPOINT] Solicitud de vinculación para {nombre_cli}",
        mensaje=(
            f"📁 SOLICITUD DE VINCULACIÓN CARPETA SHAREPOINT (INFORMES EJECUTIVOS)\n\n"
            f"👤 Cliente: {nombre_cli}\n"
            f"🆔 CC / NIT: {cedula_cli}\n"
            f"📱 Teléfono: {tel_cli}\n"
            f"📧 Email: {current_user.email}\n"
            f"💬 Detalle: El cliente solicita la vinculación de su carpeta oficial de SharePoint para consultar sus informes ejecutivos y entregables.\n\n"
            f"---\n⏰ Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        ),
        estado="Abierto"
    )
    db.add(pqr)

    admins = db.query(UsuarioModel).filter(UsuarioModel.rol == "administrador").all()
    for adm in admins:
        notif = NotificacionModel(
            id_usuario=adm.id_usuarios,
            titulo=f"📁 Solicitud SharePoint: {nombre_cli}",
            mensaje=f"El cliente {nombre_cli} solicita vincular su carpeta de SharePoint para ver sus informes ejecutivos.",
            leido=False
        )
        db.add(notif)

    db.commit()
    return success_response(message="Solicitud de SharePoint registrada exitosamente en la base de datos.", data={"id_pqr": pqr.id_pqr})



