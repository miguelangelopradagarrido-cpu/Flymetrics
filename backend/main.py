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
# Auto-detectar frontend tanto si se ejecuta en la raiz del repo como dentro del contenedor /backend
if (BASE_DIR / "frontend").exists():
    FRONTEND_DIR = BASE_DIR / "frontend"
elif (PROJECT_ROOT / "frontend").exists():
    FRONTEND_DIR = PROJECT_ROOT / "frontend"
else:
    FRONTEND_DIR = BASE_DIR / "frontend"

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
    # Asegurar usuario administrador y técnico por defecto al iniciar / desplegar
    try:
        from app.infrastructure.database.session import SessionLocal
        from app.infrastructure.security.jwt_handler import hash_password
        from app.infrastructure.database.models.models import TecnicoModel
        
        default_admin_email = os.getenv("ADMIN_EMAIL", "admin@flymetrics.co").strip().lower()
        default_admin_password = os.getenv("ADMIN_PASSWORD", "FlymetricsAdmin2026*").strip()
        default_tec_email = os.getenv("TECNICO_EMAIL", "tecnico@flymetrics.co").strip().lower()
        default_tec_password = os.getenv("TECNICO_PASSWORD", "FlymetricsAdmin2026*").strip()

        with SessionLocal() as db_session:
            admin_user = db_session.query(UsuarioModel).filter(UsuarioModel.email == default_admin_email).first()
            if not admin_user:
                admin_user = UsuarioModel(
                    email=default_admin_email,
                    rol="administrador"
                )
                admin_user.password_hash = hash_password(default_admin_password)
                db_session.add(admin_user)
                db_session.commit()
                print(f"[STARTUP] Usuario Administrador creado exitosamente: {default_admin_email}")
            else:
                admin_user.rol = "administrador"
                admin_user.password_hash = hash_password(default_admin_password)
                db_session.commit()
                print(f"[STARTUP] Contraseña de Administrador actualizada a la oficial: {default_admin_email}")

            tec_user = db_session.query(UsuarioModel).filter(UsuarioModel.email == default_tec_email).first()
            if not tec_user:
                tec_user = UsuarioModel(
                    email=default_tec_email,
                    rol="tecnico"
                )
                tec_user.password_hash = hash_password(default_tec_password)
                db_session.add(tec_user)
                db_session.commit()
                print(f"[STARTUP] Usuario Técnico creado exitosamente: {default_tec_email}")
            else:
                tec_user.rol = "tecnico"
                tec_user.password_hash = hash_password(default_tec_password)
                db_session.commit()

            # Asegurar perfil técnico asociado
            tec_profile = db_session.query(TecnicoModel).filter(TecnicoModel.id_usuario == tec_user.id_usuarios).first()
            if not tec_profile:
                tec_profile = TecnicoModel(
                    id_usuario=tec_user.id_usuarios,
                    nombre="Carlos",
                    apellido_1="Mendoza",
                    especialidad="Piloto Dron Agrícola RTK",
                    telefono="3101234567",
                    estado="disponible"
                )
                db_session.add(tec_profile)
                db_session.commit()
                print(f"[STARTUP] Perfil de Técnico vinculado para {default_tec_email}")
    except Exception as e:
        print(f"[STARTUP] Aviso en inicialización de usuarios: {e}")

    # Tareas en segundo plano ligeras (sincronizacion de bitacoras bajo demanda o webhook)
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API REST profesional para la gestión de flota de drones, agendas de vuelo y bitácoras de Flymetrics S.A.S.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 1. CORS Middleware añadido PRIMERO para interceptar todas las peticiones (incluyendo preflight OPTIONS)
cors_regex = r"^https?://(localhost|127\.0\.0\.1|.*\.hostless\.site|.*\.hostless\.app|.*\.flymetrics\.com\.co|.*\.flymetrics\.co)(:\d+)?$"
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=cors_regex,
    allow_origins=[
        "https://flymetrics.com.co",
        "https://www.flymetrics.com.co",
        "https://flymetrics.co",
        "https://www.flymetrics.co",
        "https://flymetrics.hostless.site",
        "https://flymetrics-api.hostless.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
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


# Registrar limitador de tasa (Rate Limiter)
setup_rate_limiter(app)

# Registrar manejadores de error globales
setup_error_handlers(app)

# Lista completa de routers modulares de la arquitectura
all_modular_routers = [
    auth.router,
    clientes.router,
    tecnicos.router,
    tecnicos.tecnico_ops_router,
    fincas.router,
    servicios.router,
    agenda.router,
    agenda.admin_router,
    webhook.webhook_forms_router,
    drones.router,
    entregables.router,
    entregables.informes_router,
    pagos.router,
    notificaciones.router,
    webhook.router,
    usuarios.router,
    solicitudes.router,
    pqrs.router,
    contacto.router,
    media.router,
    publicidad.router,
]

# 1. Sub-router principal oficial con prefijo /api/v1
api_router = APIRouter(prefix="/api/v1")
for r in all_modular_routers:
    api_router.include_router(r)

# Health check y estado del sistema bajo /api/v1
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

# Registrar /api/v1 en FastAPI
app.include_router(api_router)

# 2. Sub-router espejo a nivel de raíz (prefix="") para compatibilidad total ante peticiones sin /api/v1
root_api_router = APIRouter(prefix="", include_in_schema=False)
for r in all_modular_routers:
    root_api_router.include_router(r)

# Alias root para /admin/agendas
@root_api_router.get("/admin/agendas", include_in_schema=False)
@root_api_router.get("/admin/agendas/", include_in_schema=False)
def listar_agendas_admin_plural_alias_root(
    estado: str = None,
    id_tecnico: int = None,
    fecha: str = None,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(agenda.admin_required)
):
    return agenda.admin_list_agenda(estado=estado, id_tecnico=id_tecnico, fecha=fecha, db=db, current_user=current_user)

app.include_router(root_api_router)

@app.get("/health", tags=["Salud"])
def health_check():
    """Estado de la API y de la conexion a la base de datos."""
    from sqlalchemy import text as _sql_text
    from app.infrastructure.database.session import engine as _engine
    db_status, detalle = "ok", None
    try:
        with _engine.connect() as conn:
            conn.execute(_sql_text("SELECT 1"))
    except Exception as e:
        db_status, detalle = "error", str(e)[:300]
    return {"api": "ok", "database": db_status, "detalle": detalle}




# Rutas transparentes para servir vistas HTML desde la carpeta pages/
def _safe_serve_page(filename: str):
    candidate_paths = [
        FRONTEND_DIR / "pages" / filename,
        FRONTEND_DIR / filename,
        BASE_DIR / "frontend" / "pages" / filename,
        BASE_DIR / "frontend" / filename,
    ]
    for p in candidate_paths:
        if p.exists():
            return FileResponse(str(p))
    return {
        "status": "online",
        "app": "Flymetrics API OS",
        "docs": "/docs",
        "health": "/health",
        "message": f"Endpoint standalone para {filename}. Frontend activo en https://www.flymetrics.com.co"
    }

@app.get("/", include_in_schema=False)
@app.get("/index", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
@app.get("/pages/index.html", include_in_schema=False)
def serve_index():
    return _safe_serve_page("index.html")

@app.get("/admin", include_in_schema=False)
@app.get("/admin.html", include_in_schema=False)
@app.get("/pages/admin.html", include_in_schema=False)
def serve_admin():
    return _safe_serve_page("admin.html")

@app.get("/cliente", include_in_schema=False)
@app.get("/cliente.html", include_in_schema=False)
@app.get("/pages/cliente.html", include_in_schema=False)
def serve_cliente():
    return _safe_serve_page("cliente.html")

@app.get("/tecnico", include_in_schema=False)
@app.get("/tecnico.html", include_in_schema=False)
@app.get("/pages/tecnico.html", include_in_schema=False)
def serve_tecnico():
    return _safe_serve_page("tecnico.html")

@app.get("/agendar", include_in_schema=False)
@app.get("/agendar.html", include_in_schema=False)
@app.get("/pages/agendar.html", include_in_schema=False)
def serve_agendar():
    return _safe_serve_page("agendar.html")

@app.get("/staff.html", include_in_schema=False)
@app.get("/pages/staff.html", include_in_schema=False)
def serve_staff():
    return _safe_serve_page("staff.html")

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
    # Uploads directos unificados con el módulo media
    from app.presentation.api.routers.media import UPLOADS_DIR
    try:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
    app.mount("/pages/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="pages_uploads")
    app.mount("/", StaticFiles(directory=str(target_dir), html=True), name="frontend")
else:
    # Backend desplegado de forma independiente: asegurar y servir /uploads localmente
    from app.presentation.api.routers.media import UPLOADS_DIR
    try:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)