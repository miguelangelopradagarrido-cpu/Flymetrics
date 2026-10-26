import sys
import os
from pathlib import Path

# Configurar path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models.models import (
    UsuarioModel, ClienteModel, TecnicoModel, ServicioModel,
    DroneModel, SystemConfigModel, RedSocialModel, PublicidadElementoModel
)
from app.infrastructure.security.jwt_handler import hash_password
import json

def seed():
    db = SessionLocal()
    print("==================================================")
    print("   Flymetrics OS - Inicializacion de Base de Datos")
    print("==================================================")
    
    try:
        # 1. Administrador
        admin_email = "admin@flymetrics.co"
        admin = db.query(UsuarioModel).filter(UsuarioModel.email == admin_email).first()
        if not admin:
            admin = UsuarioModel(
                email=admin_email,
                contraseña=hash_password("Admin123456!"),
                rol="administrador"
            )
            db.add(admin)
            print(f"[+] Usuario Administrador creado: {admin_email} / Admin123456!")
        else:
            admin.contraseña = hash_password("Admin123456!")
            admin.rol = "administrador"
            print(f"[~] Usuario Administrador sincronizado: {admin_email} / Admin123456!")
        db.flush()

        # 2. Tecnico Oficial
        tec_email = "tecnico@flymetrics.co"
        tec_user = db.query(UsuarioModel).filter(UsuarioModel.email == tec_email).first()
        if not tec_user:
            tec_user = UsuarioModel(
                email=tec_email,
                contraseña=hash_password("Tecnico123!"),
                rol="tecnico"
            )
            db.add(tec_user)
            db.flush()
            print(f"[+] Usuario Tecnico creado: {tec_email} / Tecnico123!")
        else:
            tec_user.contraseña = hash_password("Tecnico123!")
            print(f"[~] Usuario Tecnico actualizado: {tec_email} / Tecnico123!")
        
        tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == tec_user.id_usuarios).first()
        if not tecnico:
            tecnico = TecnicoModel(
                id_usuario=tec_user.id_usuarios,
                nombre="Juan Camilo Martínez",
                certificacion="RAC-100-DIR",
                estado="disponible",
                telefono="3115550101",
                servicios_capacitados="1,2,3,4"
            )
            db.add(tecnico)
            print("[+] Perfil de Técnico registrado: Juan Camilo Martínez (RAC-100-DIR)")

        # 3. Cliente Principal Miguel
        miguel_email = "miguelangelopradagarrido@gmail.com"
        miguel_user = db.query(UsuarioModel).filter(UsuarioModel.email == miguel_email).first()
        if miguel_user:
            cli_miguel = db.query(ClienteModel).filter(ClienteModel.id_usuario == miguel_user.id_usuarios).first()
            if not cli_miguel:
                cli_miguel = ClienteModel(
                    id_usuario=miguel_user.id_usuarios,
                    nombre="Miguel Ángel Prada Garrido",
                    telefono="3109998877",
                    numero_documento="1098765432",
                    ciudad_expedicion="Bogotá",
                    verificado=True
                )
                db.add(cli_miguel)
                print(f"[+] Perfil de Cliente vinculado para: {miguel_email}")

        # 4. Servicios Agroindustriales
        servicios_data = [
            {
                "nombre_servicio": "Aspersión y Fumigación Aérea de Precisión",
                "descripcion": "Aplicación ultralocalizada de agroquímicos y bioinsumos mediante drones agrícolas de alta capacidad. Cobertura uniforme, control de deriva y reducción del uso de químicos hasta en un 30% sin pisoteo del cultivo.",
                "precio_base_m2": 4.5000,
                "activo": True,
                "sistema": "Gotas ULV con micro-turbina centrífuga",
                "eficiencia": "Hasta 18 ha/hora",
                "capacidad": "Tanque de 40 Litros",
                "precision_metrica": "Margen RTK ±2 cm centimétrico",
                "icono": "drone"
            },
            {
                "nombre_servicio": "Monitoreo Multiespectral y Análisis NDVI",
                "descripcion": "Captura y procesamiento de imágenes multiespectrales de alta resolución para generar mapas de vigor vegetal (NDVI/NDRE), detección temprana de estrés hídrico, deficiencias nutricionales y focos de malezas.",
                "precio_base_m2": 3.5000,
                "activo": True,
                "sistema": "Cámaras multiespectrales 4 bandas + RGB",
                "eficiencia": "Hasta 200 ha/día",
                "capacidad": "Sensor CMOS de 20 MP",
                "precision_metrica": "Resolución terrestre GSD < 5 cm/px",
                "icono": "map"
            },
            {
                "nombre_servicio": "Topografía Agrícola y Fotogrametría 3D",
                "descripcion": "Levantamientos topográficos de precisión con modelos digitales de elevación (DEM), curvas de nivel georreferenciadas, cálculo de pendientes y planificación de canales de drenaje y riego.",
                "precio_base_m2": 5.0000,
                "activo": True,
                "sistema": "LIDAR & Fotogrametría RTK",
                "eficiencia": "Hasta 100 ha/día",
                "capacidad": "Modelado 3D en nubes de puntos",
                "precision_metrica": "Precisión vertical/horizontal < 3 cm",
                "icono": "layers"
            },
            {
                "nombre_servicio": "Demostración Gratuita",
                "descripcion": "Demostración técnica sin costo en el predio del productor para validar la tecnología de drones en su cultivo específico.",
                "precio_base_m2": 0.0000,
                "activo": True,
                "sistema": "Demostración guiada en predio",
                "eficiencia": "1 vuelo de prueba",
                "capacidad": "Piloto certificado RAC-100",
                "precision_metrica": "Asesoría personalizada",
                "icono": "star"
            }
        ]

        for s_data in servicios_data:
            existing_s = db.query(ServicioModel).filter(ServicioModel.nombre_servicio == s_data["nombre_servicio"]).first()
            if not existing_s:
                new_s = ServicioModel(**s_data)
                db.add(new_s)
                print(f"[+] Servicio registrado: {s_data['nombre_servicio']}")
            else:
                for k, v in s_data.items():
                    setattr(existing_s, k, v)

        # 5. Drones de Flota
        drones_data = [
            {
                "modelo": "DJI Agras T40",
                "estado": "disponible",
                "tipo": "Aspersión",
                "numero_serie": "T40-AG-2026-001",
                "horas_vuelo": 42,
                "ultima_revision": "2026-09-01"
            },
            {
                "modelo": "DJI Agras T25",
                "estado": "disponible",
                "tipo": "Aspersión",
                "numero_serie": "T25-AG-2026-002",
                "horas_vuelo": 18,
                "ultima_revision": "2026-09-15"
            },
            {
                "modelo": "DJI Mavic 3 Enterprise Multispectral",
                "estado": "disponible",
                "tipo": "Monitoreo",
                "numero_serie": "M3M-MO-2026-003",
                "horas_vuelo": 75,
                "ultima_revision": "2026-10-01"
            }
        ]

        for d_data in drones_data:
            existing_d = db.query(DroneModel).filter(DroneModel.numero_serie == d_data["numero_serie"]).first()
            if not existing_d:
                new_d = DroneModel(**d_data)
                db.add(new_d)
                print(f"[+] Dron registrado: {d_data['modelo']} ({d_data['numero_serie']})")

        # 6. Perfil Corporativo en Configuracion del Sistema
        perfil_corporativo = {
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

        conf = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "perfil_corporativo").first()
        if not conf:
            conf = SystemConfigModel(
                clave="perfil_corporativo",
                valor=json.dumps(perfil_corporativo, ensure_ascii=False)
            )
            db.add(conf)
            print("[+] Configuracion 'perfil_corporativo' creada.")
        else:
            conf.valor = json.dumps(perfil_corporativo, ensure_ascii=False)
            print("[~] Configuracion 'perfil_corporativo' actualizada.")

        # 7. Redes Sociales
        redes_data = [
            {"red": "whatsapp", "nombre_visible": "WhatsApp Oficial", "url": "https://wa.me/573143764972", "icono": "fa-brands fa-whatsapp", "orden": 1, "activo": True},
            {"red": "instagram", "nombre_visible": "Instagram", "url": "https://instagram.com/flymetrics.agro", "icono": "fa-brands fa-instagram", "orden": 2, "activo": True},
            {"red": "linkedin", "nombre_visible": "LinkedIn", "url": "https://linkedin.com/company/flymetrics", "icono": "fa-brands fa-linkedin", "orden": 3, "activo": True}
        ]
        for r_data in redes_data:
            existing_r = db.query(RedSocialModel).filter(RedSocialModel.red == r_data["red"]).first()
            if not existing_r:
                new_r = RedSocialModel(**r_data)
                db.add(new_r)
                print(f"[+] Red social registrada: {r_data['nombre_visible']}")

        db.commit()
        print("\n[OK] ¡Base de datos poblada exitosamente y lista para operar!")

    except Exception as e:
        db.rollback()
        print(f"\n[!] Error durante el seed de la base de datos: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed()
