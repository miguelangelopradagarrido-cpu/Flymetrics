import time
import threading
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import FastAPI

class InMemoryRateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Middleware de Rate Limiting autónomo y de alto rendimiento.
    Protege la API contra ataques de fuerza bruta y saturación sin requerir dependencias externas.
    """
    def __init__(self, app: FastAPI, max_requests_per_minute: int = 150, auth_max_requests: int = 25):
        super().__init__(app)
        self.max_requests = max_requests_per_minute
        self.auth_max_requests = auth_max_requests
        self.history = defaultdict(list)
        self.lock = threading.Lock()
        self.last_cleanup = time.time()

    def _cleanup_stale(self, now: float):
        """Elimina registros antiguos (> 60s) cada 5 minutos para evitar fugas de memoria."""
        if now - self.last_cleanup > 300:
            stale_keys = [ip for ip, timestamps in self.history.items() if not timestamps or (now - timestamps[-1] > 60)]
            for ip in stale_keys:
                self.history.pop(ip, None)
            self.last_cleanup = now

    async def dispatch(self, request: Request, call_next):
        # Extraer IP real del cliente considerando Load Balancers / Reverse Proxies (Nginx, Cloudflare)
        forwarded_for = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = (
                request.headers.get("cf-connecting-ip")
                or request.headers.get("CF-Connecting-IP")
                or (request.client.host if request.client else "127.0.0.1")
            )
        path = request.url.path
        
        # Omitir archivos estáticos y documentación para no degradar el frontend
        if not path.startswith("/api/"):
            return await call_next(request)

        # En localhost o desarrollo, permitir umbral amplio para pruebas y presentaciones fluidas
        is_local = client_ip in ("127.0.0.1", "::1", "localhost", "testclient")

        now = time.time()
        is_sensitive_auth = any(path.startswith(p) for p in [
            "/api/v1/auth/login",
            "/api/v1/auth/verificar",
            "/api/v1/auth/solicitar",
            "/api/v1/auth/enviar-codigo",
            "/api/v1/auth/restablecer-password",
            "/api/v1/agenda/lookup-cliente",
            "/api/v1/contacto"
        ])
        
        # Separar llaves de rate limit para que peticiones normales no consuman el límite de login
        history_key = f"{client_ip}:auth" if is_sensitive_auth else f"{client_ip}:general"
        limit = (self.auth_max_requests * 5 if is_local else self.auth_max_requests) if is_sensitive_auth else (self.max_requests * 5 if is_local else self.max_requests)

        with self.lock:
            self._cleanup_stale(now)
            timestamps = self.history[history_key]
            # Filtrar marcas de tiempo mayores a 60 segundos
            cutoff = now - 60.0
            valid_timestamps = [t for t in timestamps if t > cutoff]
            
            if len(valid_timestamps) >= limit:
                retry_after = int(60 - (now - valid_timestamps[0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "Demasiadas peticiones (Rate Limit Exceeded). Por favor intente más tarde.",
                        "retry_after_seconds": max(1, retry_after)
                    },
                    headers={"Retry-After": str(max(1, retry_after))}
                )
            
            valid_timestamps.append(now)
            self.history[history_key] = valid_timestamps

        return await call_next(request)

def setup_rate_limiter(app: FastAPI):
    """
    Registra el middleware de limitación de tasa en la aplicación FastAPI.
    """
    app.add_middleware(InMemoryRateLimiterMiddleware, max_requests_per_minute=300, auth_max_requests=60)


