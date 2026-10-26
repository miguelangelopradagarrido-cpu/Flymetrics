import bleach

class Sanitizer:
    """
    Clase utilitaria para limpiar inputs de texto y evitar ataques XSS almacenados.
    """
    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Limpia un texto de cualquier etiqueta HTML o script malicioso.
        Debe usarse antes de guardar datos en la base de datos (por ejemplo, descripciones de PQRs).
        """
        if not text:
            return text
        
        # Bleach elimina cualquier etiqueta HTML (tags=[] significa ninguna etiqueta permitida)
        # strip=True elimina las etiquetas en vez de escaparlas.
        return bleach.clean(text, tags=[], attributes={}, strip=True)
