import requests
import json
import sys

BASE_URL = "http://localhost:3000/api/v1"

def print_result(title, ok, detail=""):
    mark = "[PASS]" if ok else "[FAIL]"
    print(f"{mark} | {title} {detail}")

def test_system():
    s = requests.Session()
    print("==================================================")
    print("INICIANDO AUDITORIA INTEGRAL DE ROLES Y APIS")
    print("==================================================")

    # ----------------------------------------------------
    # 1. PRUEBAS ROL ADMINISTRADOR
    # ----------------------------------------------------
    print("\n--- [1] ROL ADMINISTRADOR ---")
    login_admin = s.post(f"{BASE_URL}/auth/login", json={
        "email": "admin@flymetrics.co",
        "contraseña": "Admin123456!"
    })
    if login_admin.status_code != 200:
        print_result("Login Administrador", False, f"Status: {login_admin.status_code}, Msg: {login_admin.text}")
        return False
    admin_token = login_admin.json().get("data", {}).get("token")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print_result("Login Administrador", True, f"(Token obtenido: {admin_token[:15]}...)")

    # Obtener configuración corporativa
    cfg_res = s.get(f"{BASE_URL}/admin/usuarios/config/sistema", headers=admin_headers)
    print_result("Admin - Obtener Configuracion Corporativa", cfg_res.status_code == 200, f"Status: {cfg_res.status_code}")

    # Listar usuarios
    users_res = s.get(f"{BASE_URL}/admin/usuarios", headers=admin_headers)
    print_result("Admin - Listar Usuarios", users_res.status_code == 200, f"Total usuarios: {len(users_res.json().get('data', [])) if users_res.status_code == 200 else 0}")

    # Listar agendas / turnos
    agendas_res = s.get(f"{BASE_URL}/admin/agendas", headers=admin_headers)
    print_result("Admin - Listar Agendas Generales", agendas_res.status_code == 200, f"Total agendas: {len(agendas_res.json().get('data', [])) if agendas_res.status_code == 200 else 0}")

    # Listar drones
    drones_res = s.get(f"{BASE_URL}/drones/", headers=admin_headers)
    print_result("Admin - Listar Drones Operativos", drones_res.status_code == 200, f"Total drones: {len(drones_res.json().get('data', [])) if drones_res.status_code == 200 else 0}")

    # Listar servicios
    servicios_res = s.get(f"{BASE_URL}/servicios/")
    print_result("Publico/Admin - Catalogo de Servicios", servicios_res.status_code == 200, f"Total servicios: {len(servicios_res.json().get('data', [])) if servicios_res.status_code == 200 else 0}")

    # ----------------------------------------------------
    # 2. PRUEBAS DEMO GRATIS / RESERVA RAPIDA
    # ----------------------------------------------------
    print("\n--- [2] PRUEBA FLUJO AGENDAMIENTO DEMO GRATIS ---")
    demo_payload = {
        "nombre_completo": "Carlos Agro Productor",
        "email": "carlos.productor@gmail.com",
        "telefono": "3149876543",
        "cedula": "1098765432",
        "nombre_finca": "Hacienda El Paraiso",
        "departamento": "Cundinamarca",
        "municipio": "Facatativa",
        "vereda_corregimiento": "Vereda Manablanca",
        "direccion_ubicacion": "Km 4 Via Facatativa - Alban",
        "tipo_cultivo": "Flores / Rosa",
        "hectareas": 15.5,
        "servicio_solicitado": "Demostracion Gratuita",
        "fecha_deseada": "2026-10-15",
        "es_demo_gratis": True,
        "observaciones": "Solicitud de demostracion gratuita para aspersion y monitoreo multiespectral."
    }
    demo_res = s.post(f"{BASE_URL}/agenda/reserva-rapida", json=demo_payload)
    is_demo_ok = demo_res.status_code in [200, 201]
    print_result("Reserva Rapida Demo Gratis", is_demo_ok, f"Status: {demo_res.status_code}, Codigo: {demo_res.json().get('data', {}).get('codigo_reserva', 'N/A') if is_demo_ok else demo_res.text}")

    # ----------------------------------------------------
    # 3. PRUEBAS ROL CLIENTE (LOGIN CON CREDENCIALES / ASIGNACION CLAVE)
    # ----------------------------------------------------
    print("\n--- [3] ROL CLIENTE ---")
    # Probar registro formal / asignacion de clave personalizada para el cliente que acaba de agendar
    reg_cliente = s.post(f"{BASE_URL}/auth/register", json={
        "nombre": "Carlos Agro",
        "apellido_1": "Productor",
        "email": "carlos.productor@gmail.com",
        "contraseña": "CarlosSegura2026!",
        "telefono": "3149876543"
    })
    print_result("Cliente - Asignacion / Registro de Contrasena", reg_cliente.status_code in [200, 201], f"Status: {reg_cliente.status_code}")

    # Login con la nueva clave asignada
    login_cli = s.post(f"{BASE_URL}/auth/login", json={
        "email": "carlos.productor@gmail.com",
        "contraseña": "CarlosSegura2026!"
    })
    cli_token = None
    if login_cli.status_code == 200:
        cli_token = login_cli.json().get("data", {}).get("token")
        print_result("Cliente - Login con Clave Personalizada", True, f"(Token: {cli_token[:15]}...)")
    else:
        print_result("Cliente - Login con Clave Personalizada", False, f"Status: {login_cli.status_code}")

    if cli_token:
        cli_headers = {"Authorization": f"Bearer {cli_token}"}
        # Obtener perfil
        me_res = s.get(f"{BASE_URL}/clientes/me", headers=cli_headers)
        print_result("Cliente - Obtener Perfil /me", me_res.status_code == 200, f"Nombre: {me_res.json().get('data', {}).get('nombre', '') if me_res.status_code == 200 else 'Error'}")

        # Actualizar perfil
        upd_res = s.put(f"{BASE_URL}/clientes/me", headers=cli_headers, json={
            "nombre": "Carlos Agro Productor",
            "telefono": "3149876543",
            "numero_documento": "1098765432"
        })
        print_result("Cliente - Actualizar Perfil", upd_res.status_code == 200, f"Status: {upd_res.status_code}")

        # Listar fincas
        fincas_res = s.get(f"{BASE_URL}/fincas/", headers=cli_headers)
        print_result("Cliente - Listar Fincas", fincas_res.status_code == 200, f"Total fincas: {len(fincas_res.json().get('data', [])) if fincas_res.status_code == 200 else 0}")

        # Registrar nueva finca
        new_finca = s.post(f"{BASE_URL}/fincas/", headers=cli_headers, json={
            "nombre_finca": "Finca La Esperanza",
            "ubicacion_municipio": "Madrid",
            "departamento": "Cundinamarca",
            "tipo_cultivo": "Papa",
            "tamano_hectareas": 8.0
        })
        print_result("Cliente - Registrar Nueva Finca", new_finca.status_code in [200, 201], f"Status: {new_finca.status_code}")

        # Listar agendas propias
        cli_agendas = s.get(f"{BASE_URL}/agenda/", headers=cli_headers)
        print_result("Cliente - Consultar Agendamientos Propios", cli_agendas.status_code == 200, f"Total turnos: {len(cli_agendas.json().get('data', [])) if cli_agendas.status_code == 200 else 0}")

    # ----------------------------------------------------
    # 4. PRUEBAS ROL TECNICO
    # ----------------------------------------------------
    print("\n--- [4] ROL TECNICO ---")
    login_tec = s.post(f"{BASE_URL}/auth/login", json={
        "email": "tecnico@flymetrics.co",
        "contraseña": "Tecnico123!"
    })
    if login_tec.status_code != 200:
        print_result("Login Tecnico", False, f"Status: {login_tec.status_code}, Msg: {login_tec.text}")
    else:
        tec_token = login_tec.json().get("data", {}).get("token")
        tec_headers = {"Authorization": f"Bearer {tec_token}"}
        print_result("Login Tecnico", True, f"(Token: {tec_token[:15]}...)")

        # Consultar turnos asignados
        mis_turnos = s.get(f"{BASE_URL}/tecnicos/mis-turnos", headers=tec_headers)
        print_result("Tecnico - Consultar Turnos Asignados", mis_turnos.status_code == 200, f"Status: {mis_turnos.status_code}, Total: {len(mis_turnos.json().get('data', [])) if mis_turnos.status_code == 200 else 0}")

        # Consultar checklist operacional
        ops = s.get(f"{BASE_URL}/tecnicos/operaciones", headers=tec_headers)
        print_result("Tecnico - Listar Operaciones de Vuelo", ops.status_code == 200, f"Status: {ops.status_code}")

    # ----------------------------------------------------
    # 5. PRUEBAS CONTACTO / SEGURIDAD
    # ----------------------------------------------------
    print("\n--- [5] CONTACTO Y SEGURIDAD ---")
    pqr_res = s.post(f"{BASE_URL}/contacto/peticion", json={
        "nombre": "Prueba Contacto",
        "email": "contacto.prueba@ejemplo.com",
        "telefono": "3001234567",
        "tipo": "peticion",
        "asunto": "Consulta Tecnica sobre Cobertura de Vuelos",
        "mensaje": "Mensaje de prueba para validar que el canal de PQRS y contacto guarde y responda sin fallas."
    })
    print_result("Contacto - Envio de PQRS / Mensaje", pqr_res.status_code in [200, 201], f"Status: {pqr_res.status_code}")

    print("\n==================================================")
    print("FIN DE AUDITORIA DE PRUEBAS")
    print("==================================================")

if __name__ == "__main__":
    test_system()
