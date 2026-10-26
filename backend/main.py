import os
import sys
from pathlib import Path
from fastapi import FastAPI, APIRouter, Depends
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.infrastructure.database.models.models import UsuarioModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn

# Configurar path base
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Asegurar que BASE_DIR esté en sys.path
sys.path.insert(0, str(BASE_DIR))

from app.infrastructure.config.settings import settings
from app.presentation.api.middleware.error_handler import setup_error_handlers
from app.shared.seguridad.rate_limiter import setup_rate_limiter
from app.shared.seguridad.security_headers import security_headers_middleware

# Importar routers de la arquitectura hexagonal
from app.presentation.api.routers import (
    auth, clientes, tecnicos, fincas, servicios, agenda, drones,
    entregables, pagos, notificaciones, webhook, usuarios, solicitudes, pqrs, contacto, media, publicidad
)

from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context manager moderno de ciclo de vida de FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Asegurar usuario administrador por defecto al iniciar / desplegar
    try:
        from app.infrastructure.database.session import SessionLocal
        from app.infrastructure.security.jwt_handler import hash_password
        
        default_admin_email = os.getenv("ADMIN_EMAIL", "admin@flymetrics.co").strip()
        default_admin_password = os.getenv("ADMIN_PASSWORD", "Admin123456!").strip()

        with SessionLocal() as db_session:
            admin_user = db_session.query(UsuarioModel).filter(UsuarioModel.email == default_admin_email).first()
            if not admin_user:
                admin_user = UsuarioModel(
                    email=default_admin_email,
                    contraseña=hash_password(default_admin_password),
                    rol="administrador"
                )
                db_session.add(admin_user)
                db_session.commit()
                print(f"[STARTUP] Usuario Administrador creado exitosamente: {default_admin_email}")
            else:
                # Si existe, garantizar que tenga el rol y contraseña correcta
                actualizado = False
                if admin_user.rol != "administrador":
                    admin_user.rol = "administrador"
                    actualizado = True
                if default_admin_password and not admin_user.contraseña:
                    admin_user.contraseña = hash_password(default_admin_password)
                    actualizado = True
                if actualizado:
                    db_session.commit()
                    print(f"[STARTUP] Usuario Administrador actualizado: {default_admin_email}")
    except Exception as e:
        print(f"[STARTUP] Aviso: No se pudo verificar el usuario admin inicial: {e}")

    # Listener en segundo plano para sincronizar bitácoras de Microsoft Forms por correo
    import threading, time
    from app.shared.utils.forms_email_sync import sync_bitacoras_from_email
    
    stop_event = threading.Event()
    def _poll_loop():
        time.sleep(3)
        while not stop_event.is_set():
            try:
                sync_bitacoras_from_email(mark_as_read=True)
            except Exception:
                pass
            stop_event.wait(20)
            
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
    yield
    stop_event.set()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API REST profesional para la gestión de flota de drones, agendas de vuelo y bitácoras de Flymetrics S.A.S.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Middleware de aceleración y control de caché HTTP para recursos estáticos
class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        # Uploads y archivos dinámicos (siempre validar para ver cambios de inmediato)
        if path.startswith("/uploads") or path.startswith("/pages/uploads"):
            if response.status_code == 200:
                response.headers["Cache-Control"] = "no-cache, must-revalidate"
        # Activos estáticos de diseño/librerías (CSS, JS, Fuentes fijas)
        elif any(path.startswith(prefix) for prefix in ["/js", "/css", "/img", "/video", "/pages/js", "/pages/css", "/pages/img", "/pages/video"]):
            if response.status_code == 200:
                response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
        elif path.endswith(".html") or path in ["/", "/admin", "/cliente", "/tecnico", "/agendar", "/bitacora", "/staff"]:
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        elif path.startswith("/api/"):
            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response

app.add_middleware(CacheControlMiddleware)

# Configurar compresión Gzip
app.add_middleware(GZipMiddleware, minimum_size=500)

# Middleware de headers de seguridad (CSP, HSTS, X-Frame-Options, etc.)
app.add_middleware(BaseHTTPMiddleware, dispatch=security_headers_middleware)

# Configurar CORS seguro según entorno y orígenes permitidos
allowed_origins_list = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
if getattr(settings, "ENVIRONMENT", "development") != "production":
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.trycloudflare\.com)(:\d+)?$",
        allow_origins=allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Registrar limitador de tasa (Rate Limiter)
setup_rate_limiter(app)

# Registrar manejadores de error globales
setup_error_handlers(app)

# Sub-router principal de la API con versión v1
api_router = APIRouter(prefix="/api/v1")

# Registrar routers modulares
api_router.include_router(auth.router)
api_router.include_router(clientes.router)
api_router.include_router(tecnicos.router)
api_router.include_router(tecnicos.tecnico_ops_router)
api_router.include_router(fincas.router)
api_router.include_router(servicios.router)
api_router.include_router(agenda.router)
api_router.include_router(agenda.admin_router)
api_router.include_router(webhook.webhook_forms_router)
api_router.include_router(drones.router)
api_router.include_router(entregables.router)
api_router.include_router(entregables.informes_router)
api_router.include_router(pagos.router)
api_router.include_router(notificaciones.router)
api_router.include_router(webhook.router)
api_router.include_router(usuarios.router)
api_router.include_router(solicitudes.router)
api_router.include_router(pqrs.router)
api_router.include_router(contacto.router)
api_router.include_router(media.router)
api_router.include_router(publicidad.router)

# Health check y estado del sistema
@api_router.get("/health", tags=["General"])
def read_root():
    return {
        "success": True,
        "message": f"Servicio activo de {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "environment": "development",
        "docs": "/docs"
    }

# Alias directo para Solicitudes 24h a nivel de /api/v1/solicitudes
@api_router.get("/solicitudes", tags=["Contacto Web & Cotizaciones 24H"])
def listar_solicitudes_alias(db: Session = Depends(get_db)):
    """Retorna el listado completo de solicitudes de cotización 24h con todos los campos detallados."""
    from app.presentation.api.routers.contacto import listar_solicitudes_contacto
    return listar_solicitudes_contacto(db=db)

# Alias directo para Zonas de Mayor Presencia / Demanda
@api_router.get("/zonas", tags=["Zonas de Mayor Demanda"])
def listar_zonas_alias(db: Session = Depends(get_db)):
    """Retorna las zonas de mayor demanda y presencia para el mapa y las interfaces."""
    from app.presentation.api.routers.contacto import get_public_zonas
    return get_public_zonas(db=db)

# Alias directo para Administrador: /admin/agendas (plural)
@api_router.get("/admin/agendas", include_in_schema=False)
@api_router.get("/admin/agendas/", include_in_schema=False)
def listar_agendas_admin_plural_alias(
    estado: str = None,
    id_tecnico: int = None,
    fecha: str = None,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(agenda.admin_required)
):
    return agenda.admin_list_agenda(estado=estado, id_tecnico=id_tecnico, fecha=fecha, db=db, current_user=current_user)


# Registrar el sub-router en la aplicación
app.include_router(api_router)

# Rutas públicas directas en la raíz para compatibilidad total con scripts y llamadas sin prefijo /api/v1
@app.get("/zonas", tags=["Zonas de Mayor Demanda (Root)"])
def listar_zonas_root(db: Session = Depends(get_db)):
    from app.presentation.api.routers.contacto import get_public_zonas
    return get_public_zonas(db=db)

@app.get("/contacto/config/sistema", tags=["Configuración Sistema (Root)"])
def get_config_sistema_root(db: Session = Depends(get_db)):
    from app.presentation.api.routers.contacto import get_public_system_config
    return get_public_system_config(db=db)




# Rutas transparentes para servir vistas HTML desde la carpeta pages/
@app.get("/", include_in_schema=False)
@app.get("/index", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
@app.get("/pages/index.html", include_in_schema=False)
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "pages" / "index.html"))

@app.get("/admin", include_in_schema=False)
@app.get("/admin.html", include_in_schema=False)
@app.get("/pages/admin.html", include_in_schema=False)
def serve_admin():
    return FileResponse(str(FRONTEND_DIR / "pages" / "admin.html"))

@app.get("/cliente", include_in_schema=False)
@app.get("/cliente.html", include_in_schema=False)
@app.get("/pages/cliente.html", include_in_schema=False)
def serve_cliente():
    return FileResponse(str(FRONTEND_DIR / "pages" / "cliente.html"))

@app.get("/tecnico", include_in_schema=False)
@app.get("/tecnico.html", include_in_schema=False)
@app.get("/pages/tecnico.html", include_in_schema=False)
def serve_tecnico():
    return FileResponse(str(FRONTEND_DIR / "pages" / "tecnico.html"))

@app.get("/agendar", include_in_schema=False)
@app.get("/agendar.html", include_in_schema=False)
@app.get("/pages/agendar.html", include_in_schema=False)
def serve_agendar():
    return FileResponse(str(FRONTEND_DIR / "pages" / "agendar.html"))

@app.get("/staff.html", include_in_schema=False)
@app.get("/pages/staff.html", include_in_schema=False)
def serve_staff():
    return FileResponse(str(FRONTEND_DIR / "pages" / "staff.html"))

# Favicon y Fallback
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    fav_path = FRONTEND_DIR / "img" / "logo.png"
    if not fav_path.exists():
        fav_path = FRONTEND_DIR / "assets" / "images" / "logo.png"
    if fav_path.exists():
        return FileResponse(str(fav_path))
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Flymetrics API"}

# Montar los archivos estáticos del frontend de forma robusta y a prueba de rutas relativas/absolutas
target_dir = FRONTEND_DIR if FRONTEND_DIR.exists() else (BASE_DIR / "frontend")
if target_dir.exists():
    if (target_dir / "js").exists():
        app.mount("/js", StaticFiles(directory=str(target_dir / "js")), name="js")
        app.mount("/pages/js", StaticFiles(directory=str(target_dir / "js")), name="pages_js")
    if (target_dir / "css").exists():
        app.mount("/css", StaticFiles(directory=str(target_dir / "css")), name="css")
        app.mount("/pages/css", StaticFiles(directory=str(target_dir / "css")), name="pages_css")
    if (target_dir / "img").exists():
        app.mount("/img", StaticFiles(directory=str(target_dir / "img")), name="img")
        app.mount("/pages/img", StaticFiles(directory=str(target_dir / "img")), name="pages_img")
    if (target_dir / "video").exists():
        app.mount("/video", StaticFiles(directory=str(target_dir / "video")), name="video")
        app.mount("/pages/video", StaticFiles(directory=str(target_dir / "video")), name="pages_video")
    # Uploads directos
    uploads_dir = target_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
    app.mount("/pages/uploads", StaticFiles(directory=str(uploads_dir)), name="pages_uploads")
    app.mount("/", StaticFiles(directory=str(target_dir), html=True), name="frontend")
else:
    # Backend desplegado de forma independiente: asegurar y servir /uploads localmente
    standalone_uploads = BASE_DIR / "uploads"
    standalone_uploads.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(standalone_uploads)), name="uploads")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
