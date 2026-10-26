"""
Script de diagnóstico y prueba en vivo para el envío de correos con Gmail API OAuth2 en Flymetrics.
Uso:
    .venv\\Scripts\\python.exe probar_correo.py
"""
import sys
import os

# Asegurar importaciones del backend
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.dirname(current_dir) if os.path.basename(current_dir) == "scripts" else os.path.join(current_dir, "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from app.infrastructure.external.gmail_api_service import GmailApiService
from app.shared.utils.email_service import EmailService

def main():
    print("\n" + "=" * 65)
    print(" 🚀 FLYMETRICS — DIAGNÓSTICO Y PRUEBA DE ENVÍO DE CORREOS")
    print("=" * 65)

    creds = GmailApiService.get_credentials()
    print(f"\n[1] Verificación de credenciales en backend/.env:")
    print(f"    • GOOGLE_CLIENT_ID:      {'✔ Configurado' if creds['client_id'] else '❌ Faltante'}")
    print(f"    • GOOGLE_CLIENT_SECRET:  {'✔ Configurado' if creds['client_secret'] else '❌ Faltante'}")
    print(f"    • GOOGLE_REFRESH_TOKEN:  {'✔ Configurado' if creds['refresh_token'] else '❌ Faltante'}")
    print(f"    • Correo Remitente:      {creds['email']}")

    if not GmailApiService.is_configured():
        print("\n⚠️  ATENCIÓN:")
        print("    Faltan el GOOGLE_CLIENT_SECRET y/o GOOGLE_REFRESH_TOKEN en tu archivo 'backend/.env'.")
        print("    Ábrelo y colócalos:")
        print("    GOOGLE_CLIENT_SECRET=tu_secreto")
        print("    GOOGLE_REFRESH_TOKEN=tu_token")
        print("\n    (Si pruebas ahora, el sistema ejecutará en Modo Simulación segura).\n")

    print("\n[2] Comprobando conexión con los servidores de Google...")
    diag = GmailApiService.test_connection()
    if diag.get("connected"):
        print(f"    ✔ ¡CONECTADO CON ÉXITO A GOOGLE CLOUD!")
        print(f"    • Cuenta autorizada: {diag.get('email_cuenta')}")
        print(f"    • Mensajes en buzón: {diag.get('mensajes_totales', 'N/A')}")
    else:
        print(f"    ℹ️  Estado: {diag.get('detalles', diag.get('error', 'Sin conexión real aún'))}")

    print("\n[3] Enviar correo de prueba en vivo:")
    destinatario = input(f"    Ingresa el correo a donde quieres que llegue la prueba (ej: {creds['email']}): ").strip()
    if not destinatario or "@" not in destinatario:
        destinatario = creds['email']
        print(f"    Usando correo por defecto: {destinatario}")

    print(f"\n    Despachando correo de prueba a: {destinatario}...")
    
    # Enviamos utilizando la plantilla oficial de Flymetrics
    res = GmailApiService.send_email(
        to_email=destinatario,
        subject="🌾 Prueba de Envío Exitoso — Flymetrics Operaciones",
        html_body=f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
            <div style="background: #003049; color: #ffffff; padding: 24px; text-align: center;">
                <h1 style="margin: 0; font-size: 22px; letter-spacing: 1px;">FLYMETRICS</h1>
                <p style="margin: 4px 0 0 0; color: #e4c7a1; font-size: 13px; font-weight: bold;">SERVICIOS AÉREOS CON DRONES RPAS</p>
            </div>
            <div style="padding: 26px; background: #ffffff; color: #334155; line-height: 1.6;">
                <h2 style="color: #003049; margin-top: 0;">¡Conexión de Correo Exitosa!</h2>
                <p>Este correo confirma que el sistema de <strong>Flymetrics</strong> está configurado y funcionando para despachar notificaciones automáticamente mediante <strong>Gmail API y OAuth2</strong>.</p>
                <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 12px 16px; border-radius: 6px; margin: 18px 0;">
                    <strong style="color: #166534;">✔ Remitente:</strong> {creds['formatted']}<br>
                    <strong style="color: #166534;">✔ Destinatario:</strong> {destinatario}<br>
                    <strong style="color: #166534;">✔ Canal:</strong> Google Cloud Console OAuth 2.0
                </div>
                <p style="font-size: 13px; color: #64748b;">A partir de este momento, tus clientes recibirán confirmaciones de reservas, cotizaciones, cambios de fecha e informes de vuelo en tiempo real.</p>
            </div>
            <div style="background: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #edf2f7;">
                Flymetrics S.A.S. &bull; Operaciones de Campo &bull; Colombia
            </div>
        </div>
        """,
        text_body="Prueba de conexión exitosa desde Flymetrics con Gmail API OAuth2."
    )

    print("\n[4] Resultado:")
    if res.get("success"):
        if res.get("mock"):
            print("    ✔ SIMULACIÓN EXITOSA: El código funciona a la perfección.")
            print("    Para que llegue a la bandeja de entrada real de Gmail, recuerda completar tu CLIENT_SECRET y REFRESH_TOKEN en backend/.env.")
        else:
            print(f"    🎉 ¡CORREO ENVIADO A LA BANDEJA REAL!")
            print(f"    • ID del Mensaje en Google: {res.get('message_id')}")
            print(f"    • Revisa la bandeja de entrada (y spam si es primera vez) de: {destinatario}")
    else:
        print(f"    ❌ ERROR DE ENVÍO: {res.get('error')}")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
