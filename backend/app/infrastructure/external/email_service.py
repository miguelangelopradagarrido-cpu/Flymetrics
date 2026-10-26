import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, body_text: str) -> bool:
        """
        Envía un correo electrónico priorizando Gmail API REST (OAuth2) con fallback a SMTP o simulación.
        """
        try:
            from app.infrastructure.external.gmail_api_service import GmailApiService
            if GmailApiService.is_configured():
                res = GmailApiService.send_email(to_email=to_email, subject=subject, html_body=f"<p>{body_text}</p>", text_body=body_text)
                if res.get("success") and not res.get("mock"):
                    return True
        except Exception:
            pass

        import os
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        smtp_from = os.getenv("GMAIL_SENDER_EMAIL") or os.getenv("SMTP_FROM", smtp_user or "jonathan.d.castro.ortiz@gmail.com")
        
        # Si no hay SMTP ni Gmail OAuth2, simular de forma segura
        if not smtp_user or not smtp_password:
            from app.infrastructure.external.gmail_api_service import GmailApiService
            GmailApiService.send_email(to_email=to_email, subject=subject, html_body=f"<p>{body_text}</p>", text_body=body_text)
            return True
            
        try:
            # Crear el mensaje
            msg = MIMEMultipart()
            msg["From"] = smtp_from
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            
            # Conexión SMTP segura con TLS
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, to_email, msg.as_string())
            server.quit()
            
            print(f"[EMAIL SERVICE] Correo enviado exitosamente a {to_email}")
            return True
        except Exception as e:
            # En caso de error, logear el fallo y simular el envío para evitar caídas del sistema
            print(f"[EMAIL SERVICE ERROR] Falló el envío de correo real: {e}")
            print("\n[MOCK EMAIL SERVICE] --- CORREO DE RESPALDO EN LOGS ---")
            print(f"Para: {to_email}")
            print(f"Asunto: {subject}")
            print(f"Contenido:\n{body_text}")
            print("-------------------------------------------------------\n")
            return True
