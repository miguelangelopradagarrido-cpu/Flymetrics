import os
from fastapi import Request

# Detectar entorno para ajustar headers
_IS_PROD = os.getenv("ENVIRONMENT", "development").lower() == "production"

async def security_headers_middleware(request: Request, call_next):
    """
    Middleware para inyectar headers de seguridad robustos en todas las respuestas.
    Previene Clickjacking, XSS, MIME-sniffing, etc.
    Soporta tÃºneles Cloudflare (*.trycloudflare.com) y ngrok para desarrollo/demo.
    """
    response = await call_next(request)
    
    # HSTS solo bajo HTTPS real (producciÃ³n); en dev evita problemas con http://
    if _IS_PROD:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"  # DENY rompe Google OAuth popup
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
    
    # Content Security Policy (CSP) diferenciado para APIs y Frontend
    if request.url.path.startswith("/api/"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none';"
        )
    else:
        # connect-src ampliado: localhost + cualquier tÃºnel Cloudflare/ngrok que sirva el frontend
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "  https://accounts.google.com https://apis.google.com "
            "  https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
            "  https://unpkg.com https://kit.fontawesome.com https://static.cloudflareinsights.com; "
            "style-src 'self' 'unsafe-inline' "
            "  https://fonts.googleapis.com https://accounts.google.com "
            "  https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
            "  https://unpkg.com; "
            "font-src 'self' data: "
            "  https://fonts.gstatic.com https://kit.fontawesome.com "
            "  https://use.fontawesome.com https://fa6.bootstrapcdn.com "
            "  https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob: https: "
            "  https://*.tile.openstreetmap.org https://*.basemaps.cartocdn.com "
            "  https://unpkg.com https://accounts.google.com; "
            "media-src 'self' blob: https:; "
            "frame-src 'self' https://accounts.google.com https://www.youtube.com https://youtube.com; "
            "connect-src 'self' "
            "  http://localhost:3000 http://127.0.0.1:3000 "
            "  https://*.trycloudflare.com https://*.ngrok.io "
            "  https://*.ngrok-free.app https://accounts.google.com "
            "  https://apis.google.com https://www.googleapis.com "
            "  https://*.tile.openstreetmap.org https://*.basemaps.cartocdn.com "
            "  https://unpkg.com; "
            "object-src 'none'; "
            "frame-ancestors 'self' https://accounts.google.com;"
        )
    
    # Ocultar la tecnologÃ­a del backend por seguridad
    response.headers["Server"] = "Flymetrics-Secure"
    if "x-powered-by" in response.headers:
        del response.headers["x-powered-by"]
        
    return response
