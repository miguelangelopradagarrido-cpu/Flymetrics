from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator, model_validator
from typing import Optional, List, Any, Union
from datetime import date, time, datetime, timedelta
from decimal import Decimal
from app.infrastructure.database.models.models import MetodoPagoEnum, TipoTurnoEnum

# ==========================================
# MÓDULO 1 — AUTENTICACIÓN & USUARIOS
# ==========================================

class UsuarioCreate(BaseModel):
    email: EmailStr
    contraseña: str = Field(..., min_length=6, description="Contraseña de mínimo 6 caracteres")
    rol: Optional[str] = Field("cliente", description="cliente, tecnico o administrador")
    nombre: Optional[str] = Field(None, max_length=150, description="Nombre completo para el perfil")
    apellido_1: Optional[str] = Field(None, max_length=150, description="Primer apellido")
    apellido_2: Optional[str] = Field(None, max_length=150, description="Segundo apellido")
    telefono: Optional[str] = Field(None, max_length=20, description="Número de teléfono")

    @model_validator(mode="before")
    @classmethod
    def check_password_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "password" in data and "contraseña" not in data:
                data["contraseña"] = data.pop("password")
        return data

class UsuarioLogin(BaseModel):
    email: EmailStr
    contraseña: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def check_login_password_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            pwd = data.get("password") or data.get("contraseña") or data.get("contrasena")
            if not pwd:
                for k in list(data.keys()):
                    if "pass" in k.lower() or "contra" in k.lower():
                        pwd = data[k]
                        break
            if pwd:
                data["contraseña"] = str(pwd)
        return data

    model_config = ConfigDict(populate_by_name=True)

class GoogleLoginRequest(BaseModel):
    token: str

class UsuarioResponse(BaseModel):
    id_usuarios: int
    email: EmailStr
    rol: str
    fecha_de_creacion: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UsuarioUpdateRol(BaseModel):
    rol: str = Field(..., description="cliente, tecnico o administrador")

class UsuarioResetPassword(BaseModel):
    nueva_contrasena: str = Field(..., min_length=6)

    @model_validator(mode="before")
    @classmethod
    def check_reset_password_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "nueva_contraseña" in data and "nueva_contrasena" not in data:
                data["nueva_contrasena"] = data.pop("nueva_contraseña")
            elif "password" in data and "nueva_contrasena" not in data:
                data["nueva_contrasena"] = data.pop("password")
        return data

class TokenResponse(BaseModel):
    token: str
    rol: str
    id_usuarios: int
    email: str


# ==========================================
# MÓDULO 2 — CLIENTES
# ==========================================

class ClienteAdminCreate(BaseModel):
    nombre: str = Field(..., max_length=150, description="Nombre completo del cliente")
    telefono: Optional[str] = Field(None, max_length=20, description="Número de WhatsApp o teléfono")
    email: Optional[str] = Field(None, description="Correo electrónico opcional")
    contraseña: Optional[str] = Field(None, description="Contraseña opcional")
    nombre_finca: Optional[str] = Field(None, max_length=100)
    departamento: Optional[str] = Field(None, max_length=50)
    ubicacion_municipio: Optional[str] = Field(None, max_length=50)
    hectareas: Optional[float] = Field(None)

class ClienteCreate(BaseModel):
    id_usuario: Optional[int] = None
    nombre: str = Field(..., max_length=150)
    apellido_1: Optional[str] = Field("", max_length=150)
    apellido_2: Optional[str] = Field("", max_length=150)
    telefono: Optional[str] = Field(None)

class ClienteVerifyRequest(BaseModel):
    numero_documento: str = Field(..., min_length=7, max_length=20)
    ciudad_expedicion: str = Field(..., min_length=3, max_length=50)
    fecha_expedicion: str = Field(..., min_length=5, max_length=30)

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=150)
    apellido_1: Optional[str] = Field(None, max_length=150)
    apellido_2: Optional[str] = Field(None, max_length=150)
    telefono: Optional[str] = Field(None, max_length=20)
    numero_documento: Optional[str] = Field(None, max_length=20)
    cedula: Optional[str] = Field(None, max_length=20)
    fecha_expedicion: Optional[str] = None
    ciudad_expedicion: Optional[str] = None
    datos_cuenta: Optional[str] = None
    verificado: Optional[bool] = None
    link_alegra: Optional[str] = None
    link_sharepoint: Optional[str] = None
    transfer_password: Optional[str] = Field(None, description="Contraseña requerida si el NIT/Cédula ya pertenecía a otra cuenta para transferirlo")

class ClienteResponse(BaseModel):
    id_cliente: int
    id_usuario: Optional[int]
    email: Optional[str] = None
    nombre: str
    apellido_1: Optional[str] = ""
    apellido_2: Optional[str] = ""
    telefono: Optional[str]
    numero_documento: Optional[str]
    ciudad_expedicion: Optional[str]
    fecha_expedicion: Optional[str]
    fecha_nacimiento: Optional[str] = None
    verificado: bool
    link_alegra: Optional[str] = None
    link_sharepoint: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class ClienteAlegraRequest(BaseModel):
    link_alegra: Optional[str] = Field(None, description="Enlace directo a factura o portal de Alegra")

class ClienteSharePointRequest(BaseModel):
    link_sharepoint: Optional[str] = Field(None, description="Enlace directo a carpeta de SharePoint / informes ejecutivos")


class SolicitudCodigoRequest(BaseModel):
    email: str = Field(..., max_length=100)

class VerificacionCodigoRequest(BaseModel):
    email: str = Field(..., max_length=100)
    codigo: str = Field(..., min_length=4, max_length=10)

class CompletarVerificacionClienteRequest(BaseModel):
    numero_documento: Optional[str] = Field(None, max_length=20)
    cedula: Optional[str] = Field(None, max_length=20)
    nombre: str = Field(..., min_length=2, max_length=150)
    apellido_1: Optional[str] = Field("", max_length=150)
    tipo_documento: Optional[str] = Field("CC", max_length=20)
    fecha_nacimiento: Optional[str] = Field(None, max_length=30)
    fecha_expedicion: Optional[str] = Field(None, max_length=30)
    telefono: Optional[str] = Field(None, max_length=20)
    datos_cuenta: Optional[str] = Field(None, max_length=255)
    verificado: Optional[bool] = Field(True)
    transfer_password: Optional[str] = Field(None, description="Contraseña requerida si el NIT/Cédula pertenecía a otra cuenta para transferirlo")
    transfer_email: Optional[str] = Field(None, description="Correo opcional de la cuenta anterior para autenticar transferencia")



# ==========================================
# MÓDULO 3 — TÉCNICOS
# ==========================================

class TecnicoCreate(BaseModel):
    id_usuario: int
    nombre: str = Field(..., max_length=150)
    apellido_1: Optional[str] = Field("", max_length=150)
    apellido_2: Optional[str] = Field("", max_length=150)
    certificacion: Optional[str] = Field(None, max_length=50)
    telefono: Optional[str] = Field(None, max_length=20)

class TecnicoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=150)
    apellido_1: Optional[str] = Field(None, max_length=150)
    apellido_2: Optional[str] = Field(None, max_length=150)
    certificacion: Optional[str] = Field(None, max_length=50)
    estado: Optional[str] = Field(None, description="disponible, ocupado, mantenimiento")
    telefono: Optional[str] = Field(None, max_length=20)
    servicios_capacitados: Optional[str] = Field(None, max_length=255)

class TecnicoResponse(BaseModel):
    id_tecnico: int
    id_usuario: Optional[int]
    nombre: str
    apellido_1: Optional[str] = ""
    apellido_2: Optional[str] = ""
    certificacion: Optional[str]
    estado: str
    telefono: Optional[str]
    servicios_capacitados: str
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# MÓDULO 4 — FINCAS
# ==========================================

class FincaCreate(BaseModel):
    id_cliente: Optional[int] = None
    nombre_finca: str = Field(..., max_length=100)
    ubicacion_municipio: Optional[str] = Field(None, max_length=100)
    departamento: Optional[str] = Field(None, max_length=100)
    hectareas: Optional[Decimal] = Field(Decimal("1.0"), ge=0, description="Hectáreas del predio")
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    responsable_campo: Optional[str] = Field(None, max_length=150)
    telefono_admin: Optional[str] = Field(None, max_length=50)
    maps_url: Optional[str] = Field(None, max_length=500)

    @field_validator('latitud', 'longitud', mode='before')
    @classmethod
    def empty_gps_to_none(cls, v):
        if v == '' or v is None or str(v).strip().lower() in ['null', 'none', 'undefined', '0', '0.0']:
            return None
        try:
            return Decimal(str(v).strip())
        except Exception:
            return None

    @field_validator('hectareas', mode='before')
    @classmethod
    def parse_hectareas(cls, v):
        if v == '' or v is None:
            return Decimal("1.0")
        try:
            val = Decimal(str(v).strip())
            return val if val > 0 else Decimal("1.0")
        except Exception:
            return Decimal("1.0")


class FincaUpdate(BaseModel):
    nombre_finca: Optional[str] = Field(None, max_length=100)
    ubicacion_municipio: Optional[str] = Field(None, max_length=100)
    departamento: Optional[str] = Field(None, max_length=100)
    hectareas: Optional[Decimal] = None
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    responsable_campo: Optional[str] = Field(None, max_length=150)
    telefono_admin: Optional[str] = Field(None, max_length=50)
    maps_url: Optional[str] = Field(None, max_length=500)

    @field_validator('hectareas', mode='before')
    @classmethod
    def parse_hectareas(cls, v):
        if v == '' or v is None:
            return None
        try:
            clean_s = str(v).strip().replace(',', '.')
            val = Decimal(clean_s)
            return val if val > 0 else Decimal("0.1")
        except Exception:
            return None

    @field_validator('latitud', 'longitud', mode='before')
    @classmethod
    def empty_gps_to_none(cls, v):
        if v == '' or v is None or str(v).strip().lower() in ['null', 'none', 'undefined']:
            return None
        try:
            return Decimal(str(v).strip().replace(',', '.'))
        except Exception:
            return None

class FincaResponse(BaseModel):
    id_finca: int
    id_cliente: int
    nombre_finca: str
    ubicacion_municipio: Optional[str] = None
    departamento: Optional[str] = None
    hectareas: Optional[Decimal] = None
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    responsable_campo: Optional[str] = None
    telefono_admin: Optional[str] = None
    maps_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# MÓDULO 5 — SERVICIOS & COTIZACIONES
# ==========================================

class ServicioCreate(BaseModel):
    nombre_servicio: str = Field(..., max_length=100)
    descripcion: Optional[str] = None
    precio_base_m2: Optional[Decimal] = Field(Decimal("0.0"), ge=0)
    activo: Optional[bool] = True
    imagen_url: Optional[str] = Field(None, max_length=500)
    video_url: Optional[str] = Field(None, max_length=500)
    icono: Optional[str] = Field(None, max_length=255)
    sistema: Optional[str] = Field(None, max_length=255)
    eficiencia: Optional[str] = Field(None, max_length=255)
    capacidad: Optional[str] = Field(None, max_length=255)
    precision_metrica: Optional[str] = Field(None, max_length=255)

class ServicioUpdate(BaseModel):
    nombre_servicio: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    precio_base_m2: Optional[Decimal] = Field(None, ge=0)
    activo: Optional[bool] = None
    imagen_url: Optional[str] = Field(None, max_length=500)
    video_url: Optional[str] = Field(None, max_length=500)
    icono: Optional[str] = Field(None, max_length=255)
    sistema: Optional[str] = Field(None, max_length=255)
    eficiencia: Optional[str] = Field(None, max_length=255)
    capacidad: Optional[str] = Field(None, max_length=255)
    precision_metrica: Optional[str] = Field(None, max_length=255)

class ServicioResponse(BaseModel):
    id_servicio: int
    nombre_servicio: str
    descripcion: Optional[str] = None
    precio_base_m2: Decimal
    activo: Optional[bool] = True
    imagen_url: Optional[str] = None
    video_url: Optional[str] = None
    icono: Optional[str] = None
    sistema: Optional[str] = None
    eficiencia: Optional[str] = None
    capacidad: Optional[str] = None
    precision_metrica: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class CotizacionRequest(BaseModel):
    id_servicio: Optional[int] = None
    id_finca: Optional[int] = None

class CotizacionResponse(BaseModel):
    id_servicio: int
    id_finca: int
    nombre_servicio: str
    nombre_finca: str
    hectareas: Decimal
    precio_base: Decimal
    costo_logistico: Decimal
    precio_total: Decimal
    distancia_km: float
    duracion_estimada_horas: float


# ==========================================
# MÓDULO 6 — AGENDAMIENTO / TURNOS
# ==========================================

class AgendaCreate(BaseModel):
    id_finca: Optional[int] = None
    id_servicio: Optional[int] = None
    fecha_de_turno: Optional[date] = None
    hora_inicio_estimada: Optional[time] = time(8, 0)
    tipo_turno: Optional[Any] = TipoTurnoEnum.Fumigacion
    id_tecnico: Optional[int] = None
    tecnicos_adicionales: Optional[str] = None
    tecnicos_ids: Optional[List[int]] = None
    cel: Optional[str] = Field(None, max_length=50)
    observaciones_servicio: Optional[str] = None
    tarifa: Optional[Decimal] = None
    maps_url: Optional[str] = None
    cultivo: Optional[str] = None
    servicios_nombres: Optional[Any] = None
    hectareas: Optional[Decimal] = None

    @field_validator('id_finca', 'id_servicio', 'id_tecnico', mode='before')
    @classmethod
    def coerce_id(cls, v):
        if v == '' or v is None or str(v).strip().lower() in ['null', 'undefined']:
            return None
        try:
            return int(v)
        except Exception:
            return None

    @field_validator('fecha_de_turno', mode='before')
    @classmethod
    def parse_fecha(cls, v):
        if not v or v == '' or str(v).strip().lower() in ['null', 'undefined']:
            return date.today()
        if isinstance(v, str):
            try:
                return datetime.strptime(v.split('T')[0], '%Y-%m-%d').date()
            except Exception:
                return date.today()
        return v

    @field_validator('hora_inicio_estimada', mode='before')
    @classmethod
    def parse_hora(cls, v):
        if not v or v == '' or str(v).strip().lower() in ['null', 'undefined']:
            return time(8, 0)
        if isinstance(v, str):
            try:
                parts = v.split(':')
                return time(int(parts[0]), int(parts[1]))
            except Exception:
                return time(8, 0)
        return v

class ReservaRapidaCreate(BaseModel):
    nombre_completo: str = Field(..., min_length=2, max_length=150)
    cedula: str = Field(..., min_length=3, max_length=50)
    telefono: str = Field(..., min_length=5, max_length=20)
    email: Optional[str] = Field(None, max_length=150)
    nombre_finca: str = Field(..., min_length=2, max_length=150)
    departamento: str = Field(..., min_length=2, max_length=100)
    municipio: str = Field(..., min_length=2, max_length=100)
    vereda_corregimiento: str = Field(..., min_length=2, max_length=150)
    direccion_ubicacion: Optional[str] = Field(None, max_length=255)
    hectareas: float = Field(..., gt=0)
    tipo_cultivo: str = Field(..., min_length=2, max_length=100)
    servicio_solicitado: Optional[str] = Field("Fumigación Agrícola", max_length=100)
    id_servicio: Optional[int] = Field(None)
    fecha_deseada: date
    observaciones: Optional[str] = None
    maps_link: Optional[str] = None
    maps_url: Optional[str] = None
    es_demo_gratis: Optional[bool] = Field(False, description="Indica si la solicitud es una demostración gratuita")
    es_demostracion: Optional[bool] = Field(False, description="Alias para demostración gratuita")

class AgendaAsignarRequest(BaseModel):
    id_tecnico: Optional[int] = None
    tecnicos_ids: Optional[List[int]] = None
    tecnicos_adicionales: Optional[str] = None
    id_drone: Optional[int] = None

class AgendaDecisionRequest(BaseModel):
    decision: bool
    motivo_rechazo: Optional[str] = None

class CheckinRequest(BaseModel):
    latitud_checkin: Optional[Decimal] = None
    longitud_checkin: Optional[Decimal] = None

class CheckoutRequest(BaseModel):
    insumos_litros_aplicados: Decimal = Field(..., ge=0)
    agua_litros: Decimal = Field(..., ge=0)
    baterias_utilizadas: int = Field(..., ge=0)
    cumple_rac100: int = Field(..., ge=0, le=1, description="1 = Sí, 0 = No")
    observaciones_campo: Optional[str] = None
    recomendaciones_agronomicas: Optional[str] = None
    url_entregable_drive: Optional[str] = None
    retraso_justificacion: Optional[str] = None

class SubirBitacoraRequest(BaseModel):
    id_turno: int
    sharepoint_url: Optional[str] = Field(None, description="Enlace al archivo o carpeta de SharePoint")

class SubirInformeRequest(BaseModel):
    id_turno: int
    sharepoint_url: Optional[str] = Field(None, description="Enlace al informe técnico ejecutivo en SharePoint")

class AgendaForceEstadoRequest(BaseModel):
    estado: str = Field(..., description="Pendiente, Confirmado, En Proceso, Hecho, Cancelado")
    motivo_admin: Optional[str] = None
    tarifa: Optional[float] = Field(None, ge=0, description="Precio autorizado para confirmar el turno")
    id_admin_responsable: Optional[int] = Field(None, description="ID del administrador responsable para este cambio o reenvío")

class AgendaReenvioAceptacionRequest(BaseModel):
    id_admin_responsable: Optional[int] = Field(None, description="ID del administrador que reenvía la solicitud de aceptación pendiente")
    nota_admin: Optional[str] = Field(None, description="Nota opcional que se agregará como contexto del reenvío")

class AgendaCotizarRequest(BaseModel):
    tarifa: Decimal = Field(..., gt=0, description="Precio total propuesto para el servicio")
    id_tecnico: int = Field(..., description="ID del técnico obligatorio a asignar")
    tecnicos_adicionales: Optional[str] = None
    mensaje_admin: Optional[str] = Field(None, max_length=500, description="Mensaje o propuesta para el cliente")

class AgendaResponderPropuestaRequest(BaseModel):
    accion: str = Field(..., description="'aceptar' o 'modificar'")
    sugerencia: Optional[str] = Field(None, max_length=500, description="Observaciones o contrapropuesta del cliente (máx 500 caracteres)")

class AgendaResponse(BaseModel):
    id_turno: int
    id_finca: Optional[int] = None
    id_servicio: int
    id_drone: Optional[int] = None
    id_tecnico: Optional[int] = None
    tecnicos_adicionales: Optional[str] = None
    fecha_de_turno: Optional[Union[date, str]] = None
    hora_inicio_estimada: Optional[Union[time, timedelta, str]] = None
    hora_fin_estimada: Optional[Union[time, timedelta, str]] = None
    tipo_turno: Optional[str] = "Fumigación"
    estado: Optional[str] = "Pendiente"
    tarifa: Optional[Decimal] = None
    costo_logistico: Optional[Decimal] = Decimal("0.00")
    cel: Optional[str] = None
    observaciones_servicio: Optional[str] = None
    hora_inicio_real: Optional[Union[time, timedelta, str]] = None
    hora_fin_real: Optional[Union[time, timedelta, str]] = None
    retraso_justificacion: Optional[str] = None
    motivo_reagendamiento: Optional[str] = None
    es_demostracion: Optional[bool] = False
    sugerencia_cliente: Optional[str] = None
    token_confirmacion: Optional[str] = None
    historial_negociacion: Optional[str] = None

    @field_validator('hora_inicio_estimada', 'hora_fin_estimada', 'hora_inicio_real', 'hora_fin_real', mode='before')
    @classmethod
    def serialize_hora(cls, v: Any):
        if v is None:
            return None
        if isinstance(v, timedelta):
            total_seconds = int(v.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
        if isinstance(v, time):
            return v.strftime('%H:%M:%S')
        return str(v)

    model_config = ConfigDict(from_attributes=True)

class ReporteVueloResponse(BaseModel):
    id_reporte: int
    id_turno: int
    insumos_litros_aplicados: Decimal
    agua_litros: Decimal
    baterias_utilizadas: int
    cumple_rac100: int
    observaciones_campo: Optional[str]
    recomendaciones_agronomicas: Optional[str] = None
    url_entregable_drive: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# MÓDULO 8 — DRONES & MANTENIMIENTOS
# ==========================================

class DroneCreate(BaseModel):
    modelo: str = Field(..., max_length=50)
    tipo: str = Field(..., max_length=50, description="aspersion, fotogrametria")
    estado: str = Field("disponible", max_length=30)
    numero_serie: Optional[str] = Field(None, max_length=100)
    ultima_revision: Optional[str] = Field(None, max_length=50)
    id_tecnico_asignado: Optional[int] = Field(None, description="ID del técnico/piloto asignado")

class DroneUpdate(BaseModel):
    modelo: Optional[str] = Field(None, max_length=50)
    tipo: Optional[str] = Field(None, max_length=50)
    estado: Optional[str] = Field(None, max_length=30)
    numero_serie: Optional[str] = Field(None, max_length=100)
    ultima_revision: Optional[str] = Field(None, max_length=50)
    horas_vuelo: Optional[int] = Field(None, ge=0)
    id_tecnico_asignado: Optional[int] = Field(None)

class MantenimientoCreate(BaseModel):
    tipo_mantenimiento: str = Field(..., max_length=50)  # 'Preventivo', 'Correctivo'
    descripcion_falla: str
    fecha_ingreso: datetime = Field(default_factory=datetime.utcnow)
    fecha_salida: Optional[datetime] = None
    costo_mantenimiento: Optional[Decimal] = Decimal("0.00")
    responsable_tecnico: Optional[str] = Field(None, max_length=100)

class DroneResponse(BaseModel):
    id_drone: int
    modelo: str
    tipo: Optional[str]
    estado: Optional[str]
    numero_serie: Optional[str]
    ultima_revision: Optional[str]
    horas_vuelo: Optional[int]
    id_tecnico_asignado: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class MantenimientoResponse(BaseModel):
    id_mantenimiento: int
    id_drone: int
    tipo_mantenimiento: str
    descripcion_falla: str
    fecha_ingreso: datetime
    fecha_salida: Optional[datetime]
    costo_mantenimiento: Optional[Decimal]
    responsable_tecnico: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# MÓDULO 9 — ENTREGABLES
# ==========================================

class EntregableCreate(BaseModel):
    id_turno: int
    tipo_archivo: str = Field(..., max_length=50)  # 'ortofoto', 'ndvi', 'reporte_pdf'
    url_archivo: str = Field(..., max_length=255)
    nombre_archivo: Optional[str] = Field(None, max_length=150)
    notas: Optional[str] = None

class EntregableResponse(BaseModel):
    id_entregable: int
    id_turno: int
    tipo_archivo: str
    url_archivo: str
    fecha_subida: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# MÓDULO 10 — PAGOS
# ==========================================

class PagoCreate(BaseModel):
    id_turno: int
    monto: Decimal = Field(..., gt=0)
    metodo_pago: MetodoPagoEnum = MetodoPagoEnum.Pendiente
    referencia_transaccion: Optional[str] = Field(None, max_length=100)

class PagoResponse(BaseModel):
    id_pago: int
    id_turno: int
    monto: Decimal
    fecha_pago: datetime
    metodo_pago: MetodoPagoEnum
    referencia_transaccion: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# MÓDULO 11 — NOTIFICACIONES
# ==========================================

class NotificacionCreate(BaseModel):
    id_usuario: int
    titulo: str = Field(..., max_length=100)
    mensaje: str

class NotificacionResponse(BaseModel):
    id_notificacion: int
    id_usuario: int
    titulo: str
    mensaje: str
    leido: bool
    fecha_envio: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# MÓDULO 12 — QUEJAS, RECLAMOS Y SOPORTE (PQRs)
# ==========================================

class PQRCreate(BaseModel):
    tipo: str = Field(..., max_length=50)  # 'Petición', 'Queja', 'Reclamo', 'Soporte'
    asunto: str = Field(..., max_length=150)
    mensaje: Optional[str] = None
    descripcion: Optional[str] = None

class MensajePQRCreate(BaseModel):
    mensaje: str

class MensajePQRResponse(BaseModel):
    id_mensaje_pqr: int
    id_pqr: int
    id_usuario: int
    id_emisor: Optional[int] = None
    id_receptor: Optional[int] = None
    mensaje: str
    contenido: Optional[str] = None
    fecha_envio: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PQRResponse(BaseModel):
    id_pqr: int
    id_usuario: int
    tipo: str
    asunto: str
    mensaje: Optional[str] = ""
    estado: str
    fecha_creacion: datetime
    mensajes: List[MensajePQRResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# MÓDULO 13 — SOLICITUDES Y PERMISOS DE TÉCNICOS
# ==========================================

class SolicitudTecnicoCreate(BaseModel):
    id_turno: Optional[int] = None
    tipo_solicitud: str  # 'Cancelacion', 'Reprogramacion', 'Viaticos', 'Novedad_Equipo'
    titulo: str
    justificacion: str

class SolicitudTecnicoResponder(BaseModel):
    estado: str  # 'Aprobado', 'Rechazado'
    respuesta_admin: Optional[str] = None


