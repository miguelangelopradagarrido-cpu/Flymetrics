import sys
import os
import getpass

# Asegurar path de imports
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, BACKEND_DIR)

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models.models import UsuarioModel
from app.infrastructure.security.jwt_handler import hash_password

def create_admin(email: str = None, password: str = None):
    print("==================================================")
    print("   Flymetrics Command Center - Crear Administrador ")
    print("==================================================")
    
    # 1. Leer de argumentos de línea de comandos si se proporcionaron
    if len(sys.argv) >= 3 and not email:
        email = sys.argv[1].strip()
        password = sys.argv[2].strip()
    elif len(sys.argv) == 2 and not email:
        email = sys.argv[1].strip()

    # 2. Solicitar correo si no está definido
    if not email:
        try:
            email = input("Ingrese el correo electronico del administrador: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperacion cancelada por el usuario.")
            sys.exit(0)
    
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        print("[ERROR] Debe ingresar un correo electronico valido.")
        sys.exit(1)

    # 3. Solicitar contraseña si no está definida
    if not password:
        try:
            password = getpass.getpass("Ingrese la contrasena (minimo 6 caracteres): ")
            if len(password) < 6:
                print("[ERROR] La contrasena debe tener al menos 6 caracteres.")
                sys.exit(1)
                
            confirm_password = getpass.getpass("Confirme la contrasena: ")
            if password != confirm_password:
                print("[ERROR] Las contrasenas no coinciden.")
                sys.exit(1)
        except (KeyboardInterrupt, EOFError):
            print("\nOperacion cancelada por el usuario.")
            sys.exit(0)
    elif len(password) < 6:
        print("[ERROR] La contrasena debe tener al menos 6 caracteres.")
        sys.exit(1)
        
    db = SessionLocal()
    try:
        # Verificar si el correo ya existe
        existing = db.query(UsuarioModel).filter(UsuarioModel.email == email).first()
        if existing:
            print(f"[ERROR] El correo '{email}' ya se encuentra registrado con el rol '{existing.rol}'.")
            print("Si desea cambiar su rol a administrador o restablecer su contrasena, use el panel o ejecute una actualizacion.")
            sys.exit(1)
            
        # Hashear e insertar el administrador
        hashed_pwd = hash_password(password)
        admin = UsuarioModel(
            email=email,
            contraseña=hashed_pwd,
            rol="administrador"
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print("==================================================")
        print(f"[OK] Administrador '{email}' creado exitosamente.")
        print(f"ID Usuario: #{admin.id_usuarios} | Rol: {admin.rol}")
        print("Ya puede iniciar sesion en el portal: /staff.html o /index.html")
        print("==================================================")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error inesperado al insertar en la base de datos: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
