import os
import sys
import subprocess
from pathlib import Path

def main():
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    venv_dir = project_root / ".venv"
    
    if os.name == 'nt':
        python_exe = venv_dir / "Scripts" / "python.exe"
    else:
        python_exe = venv_dir / "bin" / "python"
        
    if not python_exe.exists():
        python_exe = sys.executable
        
    print("==================================================")
    print("  Iniciando Flymetrics Command Center OS (API)... ")
    print("  Host: http://localhost:3000                     ")
    print("  Docs: http://localhost:3000/docs                ")
    print("==================================================")
    
    main_py = backend_dir / "main.py"
    try:
        subprocess.run([str(python_exe), str(main_py)], cwd=str(backend_dir))
    except KeyboardInterrupt:
        print("\nServidor detenido por el usuario.")

if __name__ == "__main__":
    main()

