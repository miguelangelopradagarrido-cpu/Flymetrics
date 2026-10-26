import logging

logger = logging.getLogger("whatsapp_service")

class WhatsAppService:
    """
    Servicio de WhatsApp.
    NOTIFICACIONES AUTOMÁTICAS DESHABILITADAS:
    Por directriz del sistema, todos los mensajes y confirmaciones automáticas
    se envían única y exclusivamente por correo electrónico.
    """
    AUTO_WHATSAPP_ENABLED = False

    @classmethod
    def send_template_message(cls, phone: str, template_name: str, parameters: list) -> bool:
        """Notificación automática por WhatsApp deshabilitada (Solo correo)."""
        logger.info(f"[WHATSAPP AUTOMATICO DESHABILITADO] Plantilla '{template_name}' omitida para {phone}. Notificaciones exclusivamente por correo.")
        return False

    @classmethod
    def send_text_message(cls, phone: str, text: str = "", message: str = "") -> bool:
        """Notificación automática por WhatsApp deshabilitada (Solo correo)."""
        logger.info(f"[WHATSAPP AUTOMATICO DESHABILITADO] Mensaje omitido para {phone}. Notificaciones exclusivamente por correo.")
        return False

