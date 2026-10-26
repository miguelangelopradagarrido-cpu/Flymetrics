import subprocess
import sys
import os
import re
from pathlib import Path

base_dir = Path(__file__).resolve().parent
cloudflared_path = base_dir / "cloudflared.exe"
url_file = base_dir / "active_tunnel_url.txt"

print("=" * 65)
print("     FLYMETRICS - TUNEL CLOUDFLARE PUBLICO (100% GRATUITO)")
print("=" * 65)
print("\n[+] Iniciando túnel seguro HTTPS con Cloudflare...")
print("[+] Conectando a http://localhost:3000 sin contraseñas...\n")

if not cloudflared_path.exists():
    print(f"Error: No se encontró {cloudflared_path}")
    sys.exit(1)

url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

try:
    proc = subprocess.Popen(
        [str(cloudflared_path), "tunnel", "--url", "http://localhost:3000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )

    detected = False
    for line in iter(proc.stdout.readline, ""):
        print(line, end="")
        if not detected:
            m = url_regex.search(line)
            if m:
                found_url = m.group(0)
                detected = True
                url_file.write_text(found_url, encoding="utf-8")
                # Copiar automaticamente al portapapeles de Windows para evitar tener que seleccionarlo
                try:
                    subprocess.run("clip", input=found_url.strip().encode("utf-8"), check=False, shell=True)
                    copiado_txt = " (¡COPIADO AUTOMATICAMENTE AL PORTAPAPELES!)"
                except Exception:
                    copiado_txt = ""

                print("\n" + "=" * 65)
                print(f" [OK] ENLACE ACTIVO DEL TUNEL{copiado_txt}:")
                print(f"      >>> {found_url} <<<")
                print(f"      Inicio de sesion: {found_url}/index.html?auth=login")
                print(f"      (Guardado tambien en: backend/scripts/tunnels/active_tunnel_url.txt)")
                print("=" * 65 + "\n")
    proc.stdout.close()
    proc.wait()
except KeyboardInterrupt:
    print("\n[!] Túnel detenido por el usuario.")
    if url_file.exists():
        try:
            url_file.unlink()
        except Exception:
            pass
