"""
Domain Entities Module
Entidades puras del dominio de negocio (desacopladas de ORM y frameworks).
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, date, time

@dataclass
class Usuario:
    id_usuarios: Optional[int]
    rol: str
    email: str
    contraseña: str
    fecha_de_creacion: Optional[datetime] = None

@dataclass
class Cliente:
    id_cliente: Optional[int]
    id_usuario: Optional[int]
    nombre: str
    apellido_1: Optional[str] = ""
    apellido_2: Optional[str] = ""
    telefono: Optional[str] = None
    numero_documento: Optional[str] = None
    ciudad_expedicion: Optional[str] = None
    fecha_expedicion: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    codigo_verificacion: Optional[str] = None
    verificado: bool = False
    link_alegra: Optional[str] = None

@dataclass
class Tecnico:
    id_tecnico: Optional[int]
    id_usuario: Optional[int]
    nombre: str
    apellido_1: Optional[str] = ""
    apellido_2: Optional[str] = ""
    telefono: Optional[str] = None
    especialidad: Optional[str] = None
    licencia_vuelo: Optional[str] = None
    disponibilidad: bool = True
    latitud_actual: Optional[float] = None
    longitud_actual: Optional[float] = None
    ultima_actualizacion_ubicacion: Optional[datetime] = None

@dataclass
class Drone:
    id_drone: Optional[int]
    modelo: str
    matricula: str
    tipo_uso: Optional[str] = None
    estado_operativo: str = "Disponible"
    capacidad_bateria_mah: Optional[int] = None
    capacidad_tanque_litros: Optional[float] = None
    horas_vuelo_acumuladas: float = 0.0
    ultimo_mantenimiento: Optional[date] = None
    proximo_mantenimiento: Optional[date] = None
    observaciones: Optional[str] = None

@dataclass
class TurnoAgenda:
    id_turno: Optional[int]
    id_finca: int
    id_servicio: int
    id_tecnico: Optional[int]
    id_drone: Optional[int]
    fecha_de_turno: date
    hora_inicio_estimada: Optional[time]
    hora_fin_estimada: Optional[time]
    estado: str = "Pendiente"
    motivo_cancelacion: Optional[str] = None
    motivo_reagendamiento: Optional[str] = None
    observaciones_servicio: Optional[str] = None
    pago_validado: bool = False
    checkin_hora: Optional[datetime] = None
    checkout_hora: Optional[datetime] = None
