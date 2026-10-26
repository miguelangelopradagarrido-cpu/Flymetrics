"""
Script de re-autorización y renovación automática de Google Refresh Token para Flymetrics.
Uso:
    .venv\\Scripts\\python.exe backend/scripts/autorizar_google_email.py
"""
import sys
import os
import urllib.parse
import requests

# Ajustar path al backend
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
env_path = os.path.join(backend_dir, ".env")
load_dotenv(env_path)

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "24492089807-h4obre5cdd4u3id96unpd6jiumrbfusl.apps.googleusercontent.com")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # Flujo de copia y pega de código en terminal

def main():
    print("=" * 65)
    print(" 🔑 FLYMETRICS — RENOVADOR DE CREDENCIALES GMAIL OAUTH2")
    print("=" * 65)
    print(f"\n[1] Client ID configurado: {CLIENT_ID}")
    
    scopes = "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/userinfo.email"
    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": scopes,
        "access_type": "offline",
        "prompt": "consent"
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(auth_params)}"
    
    print("\n[2] Abre el siguiente enlace en tu navegador para autorizar la cuenta de Gmail:")
    print("-" * 65)
    print(auth_url)
    print("-" * 65)
    
    print("\n[3] Inicia sesión con la cuenta de Gmail autorizada (ej: Jonathancastro202009@gmail.com).")
    print("    Copia el código que Google te entregue en pantalla y pégalo a continuación:")
    
    code = input("\n👉 Pega aquí el código de autorización: ").strip()
    if not code:
        print("❌ No ingresaste ningún código. Operación cancelada.")
        return

    print("\n[4] Canjeando código por un nuevo Refresh Token...")
    token_url = "https://oauth2.googleapis.com/token"
    token_payload = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    
    try:
        resp = requests.post(token_url, data=token_payload, timeout=15)
        data = resp.json()
        
        if resp.status_code != 200:
            print(f"❌ Error de Google ({resp.status_code}):", data.get("error_description", data))
            return
            
        new_refresh_token = data.get("refresh_token")
        if not new_refresh_token:
            print("⚠️ Google no retornó un refresh_token nuevo. Verifica haber usado 'prompt=consent'.")
            print("Respuesta recibida:", data)
            return
            
        print(f"🎉 ¡Éxito! Nuevo Refresh Token obtenido:")
        print(f"    {new_refresh_token}")
        
        # Actualizar backend/.env
        with open(env_path, "r", encoding="utf-8") as f:
            env_content = f.read()
            
        import re
        if "GOOGLE_REFRESH_TOKEN=" in env_content:
            env_content = re.sub(r'GOOGLE_REFRESH_TOKEN=[^\n]*', f'GOOGLE_REFRESH_TOKEN={new_refresh_token}', env_content)
        else:
            env_content += f"\nGOOGLE_REFRESH_TOKEN={new_refresh_token}\n"
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
            
        print(f"\n✔ Archivo '{env_path}' actualizado automáticamente.")
        print("¡El sistema ya está listo para despachar correos reales por Gmail API!")
        
    except Exception as e:
        print(f"❌ Error al canjear token: {e}")

if __name__ == "__main__":
    main()
