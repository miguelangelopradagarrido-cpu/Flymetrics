import os
import sys
import subprocess
import venv
from pathlib import Path

def print_step(msg):
    print(f"\n[+] {msg}")

def main():
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent.parent
    project_root = backend_dir.parent
    venv_dir = project_root / ".venv"
    
    print_step("Paso 1: Configurando Entorno Virtual...")
    if not venv_dir.exists():
        venv.create(venv_dir, with_pip=True)
        print("    Entorno virtual creado en .venv/")
    else:
        print("    El entorno virtual ya existe.")
    
    # Determinar el ejecutable de python dentro del venv
    if os.name == 'nt':
        python_exe = venv_dir / "Scripts" / "python.exe"
    else:
        python_exe = venv_dir / "bin" / "python"

    # En caso de que no haya pip preinstalado, intentamos usar ensurepip
    if not (venv_dir / "Scripts" / "pip.exe").exists() and not (venv_dir / "bin" / "pip").exists():
        subprocess.run([str(python_exe), "-m", "ensurepip", "--upgrade"], check=True)

    print_step("Paso 2: Instalando Dependencias...")
    subprocess.run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(python_exe), "-m", "pip", "install", "-r", str(backend_dir / "requirements.txt")], check=True)
    subprocess.run([str(python_exe), "-m", "pip", "install", "python-dotenv"], check=True)
    
    # Crear script temporal para inicializar BD
    db_init_script = backend_dir / "init_db_temp.py"
    db_init_code = f"""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv(r"{backend_dir / '.env'}")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "miguepro")
DB_NAME = os.getenv("DB_NAME", "flymetrics_db")

print(f"Conectando a MySQL en {{DB_HOST}}:{{DB_PORT}} como {{DB_USER}}...")
try:
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {{DB_NAME}} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Base de datos '{{DB_NAME}}' verificada/creada exitosamente.")
except Exception as e:
    print(f"Error al conectar/crear BD: {{e}}")
    exit(1)
"""
    db_init_script.write_text(db_init_code, encoding="utf-8")
    
    print_step("Paso 3: Verificando/Creando Base de Datos en MySQL...")
    try:
        subprocess.run([str(python_exe), str(db_init_script)], check=True)
    finally:
        if db_init_script.exists():
            db_init_script.unlink()
            
    print_step("Paso 4: Ejecutando Migraciones (Alembic)...")
    subprocess.run([str(python_exe), "-m", "alembic", "upgrade", "head"], cwd=str(backend_dir), check=True)

    print_step("Paso 5: Poblando Datos Iniciales del Sistema...")
    seed_script = script_dir / "seed_database.py"
    if seed_script.exists():
        subprocess.run([str(python_exe), str(seed_script)], cwd=str(backend_dir), check=True)
    
    print_step("¡Proceso Finalizado con Éxito!")
    print("Ya puedes ejecutar el servidor usando: python run_server.py (o doble clic en ejecutar_servidor.bat)")

if __name__ == "__main__":
    main()
