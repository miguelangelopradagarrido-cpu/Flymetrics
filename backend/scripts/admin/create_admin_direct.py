import os
import sys
import getpass
from pathlib import Path

# Directorio base del backend
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

# Inyectar librerías del entorno virtual
site_packages = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if site_packages.exists():
    sys.path.insert(0, str(site_packages))
else:
    for sp in (PROJECT_ROOT / ".venv").glob("**/site-packages"):
        sys.path.insert(0, str(sp))

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models.models import UsuarioModel
from app.infrastructure.security.jwt_handler import hash_password

def crear_admin():
    print("=" * 65)
    print(" [SISTEMA] CREADOR DE ADMINISTRADOR - FLYMETRICS OS")
    print("=" * 65)
    
    try:
        email = input("\n[>] Ingrese el correo del administrador: ").strip()
    except EOFError:
        return
        
    if not email or "@" not in email:
        print("[!] Error: Correo electronico invalido.")
        return

    try:
        password = getpass.getpass("[>] Ingrese la contrasena: ").strip()
    except Exception:
        password = input("[>] Ingrese la contrasena: ").strip()
        
    if not password or len(password) < 6:
        print("[!] Error: La contrasena debe tener al menos 6 caracteres.")
        return

    try:
        password_confirm = getpass.getpass("[>] Confirme la contrasena: ").strip()
    except Exception:
        password_confirm = input("[>] Confirme la contrasena: ").strip()
        
    if password != password_confirm:
        print("[!] Error: Las contrasenas no coinciden.")
        return

    db = SessionLocal()
    try:
        # Verificar si el usuario ya existe
        usuario_existente = db.query(UsuarioModel).filter(UsuarioModel.email == email).first()
        
        if usuario_existente:
            print(f"\n[!] El usuario con correo '{email}' ya existe (Rol actual: {usuario_existente.rol}).")
            opcion = input("Desea actualizar su contrasena y asignarle rol de 'administrador'? (s/n): ").strip().lower()
            if opcion == 's':
                usuario_existente.rol = "administrador"
                usuario_existente.contraseña = hash_password(password)
                db.commit()
                print(f"\n[OK] Administrador '{email}' actualizado exitosamente!")
            else:
                print("\nOperacion cancelada.")
                return
        else:
            # Crear nuevo administrador
            nuevo_admin = UsuarioModel(
                email=email,
                contraseña=hash_password(password),
                rol="administrador"
            )
            db.add(nuevo_admin)
            db.commit()
            print(f"\n[OK] Administrador '{email}' creado exitosamente en la base de datos!")

        print("\n" + "=" * 65)
        print("Datos listos para iniciar sesion en:")
        print("   - Portal Staff: http://localhost:3000/staff.html")
        print("=" * 65)

    except Exception as e:
        db.rollback()
        print(f"\n[!] Error al guardar en la base de datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    crear_admin()

