from fastapi import APIRouter, Depends, status, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
from sqlalchemy.orm import Session
import json

from app.infrastructure.database.session import get_db
from app.infrastructure.database.models.models import PublicidadElementoModel, RedSocialModel, SystemConfigModel, UsuarioModel
from app.shared.responses.response import success_response
from app.presentation.api.dependencies.auth import RoleChecker, get_current_user
from app.presentation.api.routers.media import delete_physical_upload

router = APIRouter(prefix="/publicidad", tags=["Publicidad, Medios y Redes Sociales"])
admin_required = RoleChecker(["administrador", "Administrador", "admin", "Admin", "Staff", "staff"])

# ==========================================
# ESQUEMAS PYDANTIC
# ==========================================

class MediosGlobalesRequest(BaseModel):
    hero_video_url: Optional[str] = "/video/hero.mp4"
    mobile_poster_url: Optional[str] = "/img/servicio_precision.jpg"
    hero_slides: Optional[List[dict]] = None

class PublicidadElementoCreate(BaseModel):
    seccion: Optional[str] = "dashboard_cliente"
    titulo: str
    subtitulo: Optional[str] = ""
    tipo_medio: str = "imagen"  # 'imagen', 'video'
    url_medio: str
    badge: Optional[str] = None
    texto_boton: Optional[str] = None
    url_accion: Optional[str] = None
    orden: Optional[int] = 0
    activo: Optional[bool] = True

class PublicidadElementoUpdate(BaseModel):
    seccion: Optional[str] = None
    titulo: Optional[str] = None
    subtitulo: Optional[str] = None
    tipo_medio: Optional[str] = None
    url_medio: Optional[str] = None
    badge: Optional[str] = None
    texto_boton: Optional[str] = None
    url_accion: Optional[str] = None
    orden: Optional[int] = None
    activo: Optional[bool] = None

class RedSocialCreate(BaseModel):
    red: str  # 'whatsapp', 'instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', etc.
    nombre_visible: str
    url: str
    icono: Optional[str] = "fa-globe"
    orden: Optional[int] = 0
    activo: Optional[bool] = True

class RedSocialUpdate(BaseModel):
    red: Optional[str] = None
    nombre_visible: Optional[str] = None
    url: Optional[str] = None
    icono: Optional[str] = None
    orden: Optional[int] = None
    activo: Optional[bool] = None


# ==========================================
# 1. MEDIOS GLOBALES (HERO VIDEO, PÓSTER MÓVIL Y CARRUSEL HERO)
# ==========================================

@router.get("/medios-globales", status_code=status.HTTP_200_OK)
def get_medios_globales(db: Session = Depends(get_db)):
    """Obtiene las URLs del video principal, imagen y diapositivas de carrusel persistidas en la BD."""
    config_record = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "medios_globales").first()
    default_hero = "/video/hero.mp4"
    default_poster = "/img/servicio_precision.jpg"
    default_slides = [
        {
            "tipo": "video",
            "url": default_hero,
            "titulo": "FLYMETRICS",
            "subtitulo": "Agricultura y Ganadería de Precisión con Tecnología Aérea Avanzada en Colombia"
        },
        {
            "tipo": "imagen",
            "url": default_poster,
            "titulo": "Fumigación y Aspersión Aérea",
            "subtitulo": "Ahorro de hasta 90% de agua y protección milimétrica de cultivos"
        },
        {
            "tipo": "video",
            "url": "/video/field_drone.mp4",
            "titulo": "Monitoreo y Diagnóstico Multiespectral",
            "subtitulo": "Diagnóstico temprano con cámaras multiespectrales RTK"
        }
    ]

    result = {
        "hero_video_url": default_hero,
        "mobile_poster_url": default_poster,
        "hero_slides": default_slides
    }
    if config_record and config_record.valor:
        try:
            data = json.loads(config_record.valor)
            hero_v = (data.get("hero_video_url") or "").strip() or default_hero
            poster_v = (data.get("mobile_poster_url") or "").strip() or default_poster
            raw_slides = data.get("hero_slides")
            if not isinstance(raw_slides, list) or len(raw_slides) == 0:
                raw_slides = [
                    {"tipo": "video", "url": hero_v, "titulo": "FLYMETRICS", "subtitulo": "Agricultura y Ganadería de Precisión con Tecnología Aérea Avanzada en Colombia"},
                    {"tipo": "imagen", "url": poster_v, "titulo": "Fumigación y Aspersión Aérea", "subtitulo": "Ahorro de hasta 90% de agua y protección milimétrica de cultivos"},
                    {"tipo": "video", "url": "/video/field_drone.mp4", "titulo": "Monitoreo y Diagnóstico Multiespectral", "subtitulo": "Diagnóstico temprano con cámaras multiespectrales RTK"}
                ]
            result = {
                "hero_video_url": hero_v,
                "mobile_poster_url": poster_v,
                "hero_slides": raw_slides
            }
        except Exception:
            pass
    resp = success_response(message="Medios globales obtenidos exitosamente", data=result)
    try:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["CDN-Cache-Control"] = "no-store"
    except Exception:
        pass
    return resp


@router.post("/medios-globales", status_code=status.HTTP_200_OK)
def update_medios_globales(
    req: MediosGlobalesRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Actualiza la configuración de medios globales (video hero, imagen y diapositivas de carrusel)."""
    hero = (req.hero_video_url or "").strip()
    poster = (req.mobile_poster_url or "").strip()
    slides = req.hero_slides if req.hero_slides is not None else []

    # Normalizar rutas relativas asegurando slash inicial
    if hero and not hero.startswith("http") and not hero.startswith("/"):
        hero = "/" + hero
    if poster and not poster.startswith("http") and not poster.startswith("/"):
        poster = "/" + poster

    new_hero = hero or "/video/hero.mp4"
    new_poster = poster or "/img/servicio_precision.jpg"

    payload = {
        "hero_video_url": new_hero,
        "mobile_poster_url": new_poster,
        "hero_slides": slides
    }
    config_record = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "medios_globales").first()
    if not config_record:
        config_record = SystemConfigModel(clave="medios_globales", valor=json.dumps(payload))
        db.add(config_record)
    else:
        config_record.valor = json.dumps(payload)
    db.commit()
    db.refresh(config_record)
    return success_response(message="Medios globales actualizados exitosamente", data=payload)


# ==========================================
# 2. COLLAGE DASHBOARD CLIENTE
# ==========================================

DEFAULT_COLLAGE = [
    {
        "seccion": "dashboard_cliente",
        "titulo": "Aspersión Aérea Ultra-Fina & Nutrición Foliar",
        "subtitulo": "Flota certificada con boquillas de micro-gota atomizada. Cero compactación del terreno y máxima cobertura en cultivos de arroz, maíz, palma y caña.",
        "tipo_medio": "imagen",
        "url_medio": "/img/servicio_aspersion.jpg",
        "badge": "Servicio Estrella",
        "texto_boton": "Programar Aspersión",
        "url_accion": "#agendar",
        "orden": 1,
        "activo": True
    },
    {
        "seccion": "dashboard_cliente",
        "titulo": "Mapeo Multiespectral & Diagnóstico NDVI",
        "subtitulo": "Detección temprana de estrés hídrico, malezas y deficiencias nutricionales antes de que sean visibles a simple vista.",
        "tipo_medio": "imagen",
        "url_medio": "/img/servicio_multiespectral.jpg",
        "badge": "NDVI & NDRE",
        "texto_boton": "Ver Informes de Salud",
        "url_accion": "#documentos",
        "orden": 2,
        "activo": True
    },
    {
        "seccion": "dashboard_cliente",
        "titulo": "Zonificación Digital de Cultivos",
        "subtitulo": "Dosificación milimétrica por zonas para reducir costos de fertilización y agroquímicos en tu predio.",
        "tipo_medio": "imagen",
        "url_medio": "/img/servicio_precision.jpg",
        "badge": "Precisión Integral",
        "texto_boton": "Solicitar Diagnóstico",
        "url_accion": "#whatsapp",
        "orden": 3,
        "activo": True
    },
    {
        "seccion": "dashboard_cliente",
        "titulo": "Curvas de Nivel & Drenajes 3D",
        "subtitulo": "Mapeo de elevación centimétrico para diseño de canales de riego y control de escorrentías en épocas de lluvia.",
        "tipo_medio": "imagen",
        "url_medio": "/img/servicio_topografia_3d.jpg",
        "badge": "Topografía RTK",
        "texto_boton": "Consultar Modelado",
        "url_accion": "#whatsapp",
        "orden": 4,
        "activo": True
    },
    {
        "seccion": "dashboard_cliente",
        "titulo": "Conteo Aéreo & Ganadería de Precisión",
        "subtitulo": "Inventario de ganado térmico y evaluación de biomasa forrajera en potreros extensivos.",
        "tipo_medio": "imagen",
        "url_medio": "/img/servicio_ganaderia.jpg",
        "badge": "Ganadería Inteligente",
        "texto_boton": "Saber Más",
        "url_accion": "#whatsapp",
        "orden": 5,
        "activo": True
    }
]

def _normalize_url(u: str) -> str:
    if not u:
        return ""
    u = u.strip()
    if u and not u.startswith("http") and not u.startswith("/") and not u.startswith("../"):
        return "/" + u
    return u

def _seed_collage_if_empty(db: Session):
    count = db.query(PublicidadElementoModel).count()
    if count == 0:
        for item in DEFAULT_COLLAGE:
            db.add(PublicidadElementoModel(**item))
        db.commit()

@router.get("/collage", status_code=status.HTTP_200_OK)
def get_collage_cliente(db: Session = Depends(get_db)):
    """Obtiene los elementos activos del collage publicitario para el dashboard de cliente."""
    _seed_collage_if_empty(db)
    items = db.query(PublicidadElementoModel).filter(
        PublicidadElementoModel.seccion == "dashboard_cliente",
        PublicidadElementoModel.activo == True
    ).order_by(PublicidadElementoModel.orden.asc(), PublicidadElementoModel.id_publicidad.asc()).all()

    data = [
        {
            "id_publicidad": it.id_publicidad,
            "seccion": it.seccion,
            "titulo": it.titulo,
            "subtitulo": it.subtitulo,
            "tipo_medio": it.tipo_medio,
            "url_medio": _normalize_url(it.url_medio),
            "badge": it.badge,
            "texto_boton": it.texto_boton,
            "url_accion": it.url_accion,
            "orden": it.orden,
            "activo": it.activo
        }
        for it in items
    ]
    resp = success_response(message="Collage obtenido exitosamente", data=data)
    try:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
    except Exception:
        pass
    return resp


@router.get("/admin/collage", status_code=status.HTTP_200_OK)
def get_admin_collage(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Admin: Obtiene todos los elementos del collage (activos e inactivos)."""
    _seed_collage_if_empty(db)
    items = db.query(PublicidadElementoModel).order_by(
        PublicidadElementoModel.orden.asc(),
        PublicidadElementoModel.id_publicidad.asc()
    ).all()

    data = [
        {
            "id_publicidad": it.id_publicidad,
            "seccion": it.seccion,
            "titulo": it.titulo,
            "subtitulo": it.subtitulo,
            "tipo_medio": it.tipo_medio,
            "url_medio": _normalize_url(it.url_medio),
            "badge": it.badge,
            "texto_boton": it.texto_boton,
            "url_accion": it.url_accion,
            "orden": it.orden,
            "activo": it.activo
        }
        for it in items
    ]
    resp = success_response(message="Listado de collage para administración", data=data)
    try:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
    except Exception:
        pass
    return resp


@router.post("/admin/collage", status_code=status.HTTP_201_CREATED)
def create_collage_item(
    item: PublicidadElementoCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Admin: Agrega un nuevo elemento al collage."""
    nuevo = PublicidadElementoModel(
        seccion=item.seccion or "dashboard_cliente",
        titulo=item.titulo.strip(),
        subtitulo=item.subtitulo.strip() if item.subtitulo else "",
        tipo_medio=item.tipo_medio.lower() if item.tipo_medio else "imagen",
        url_medio=_normalize_url(item.url_medio),
        badge=item.badge.strip() if item.badge else None,
        texto_boton=item.texto_boton.strip() if item.texto_boton else None,
        url_accion=item.url_accion.strip() if item.url_accion else None,
        orden=item.orden or 0,
        activo=item.activo if item.activo is not None else True
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return success_response(message="Elemento de collage creado exitosamente", data={"id_publicidad": nuevo.id_publicidad})


@router.put("/admin/collage/{id_publicidad}", status_code=status.HTTP_200_OK)
def update_collage_item(
    id_publicidad: int,
    item: PublicidadElementoUpdate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Admin: Modifica un elemento del collage."""
    elem = db.query(PublicidadElementoModel).filter(PublicidadElementoModel.id_publicidad == id_publicidad).first()
    if not elem:
        raise HTTPException(status_code=404, detail="Elemento no encontrado")
    
    if item.titulo is not None: elem.titulo = item.titulo.strip()
    if item.subtitulo is not None: elem.subtitulo = item.subtitulo.strip()
    if item.tipo_medio is not None: elem.tipo_medio = item.tipo_medio.lower()
    if item.url_medio is not None:
        elem.url_medio = _normalize_url(item.url_medio)
    if item.badge is not None: elem.badge = item.badge.strip() if item.badge else None
    if item.texto_boton is not None: elem.texto_boton = item.texto_boton.strip() if item.texto_boton else None
    if item.url_accion is not None: elem.url_accion = item.url_accion.strip() if item.url_accion else None
    if item.orden is not None: elem.orden = item.orden
    if item.activo is not None: elem.activo = item.activo
    if item.seccion is not None: elem.seccion = item.seccion

    db.commit()
    db.refresh(elem)
    return success_response(message="Elemento de collage actualizado", data={"id_publicidad": elem.id_publicidad})


@router.delete("/admin/collage/{id_publicidad}", status_code=status.HTTP_200_OK)
def delete_collage_item(
    id_publicidad: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Admin: Elimina un elemento del collage y limpia el archivo local si fue subido."""
    elem = db.query(PublicidadElementoModel).filter(PublicidadElementoModel.id_publicidad == id_publicidad).first()
    if not elem:
        raise HTTPException(status_code=404, detail="Elemento no encontrado")
    
    # Si el archivo está en /uploads/, eliminarlo físicamente del disco de inmediato
    if elem.url_medio:
        delete_physical_upload(elem.url_medio)

    db.delete(elem)
    db.commit()
    return success_response(message="Elemento de collage eliminado exitosamente")


# ==========================================
# 3. REDES SOCIALES
# ==========================================

DEFAULT_REDES = [
    {
        "red": "whatsapp",
        "nombre_visible": "WhatsApp Oficial",
        "url": "https://wa.me/573143764972",
        "icono": "fa-brands fa-whatsapp",
        "orden": 1,
        "activo": True
    },
    {
        "red": "instagram",
        "nombre_visible": "Instagram",
        "url": "https://instagram.com/flymetrics_col",
        "icono": "fa-brands fa-instagram",
        "orden": 2,
        "activo": True
    },
    {
        "red": "facebook",
        "nombre_visible": "Facebook",
        "url": "https://facebook.com/flymetricscolombia",
        "icono": "fa-brands fa-facebook-f",
        "orden": 3,
        "activo": True
    },
    {
        "red": "tiktok",
        "nombre_visible": "TikTok",
        "url": "https://tiktok.com/@flymetrics",
        "icono": "fa-brands fa-tiktok",
        "orden": 4,
        "activo": True
    },
    {
        "red": "youtube",
        "nombre_visible": "YouTube",
        "url": "https://youtube.com/@flymetrics",
        "icono": "fa-brands fa-youtube",
        "orden": 5,
        "activo": True
    },
    {
        "red": "linkedin",
        "nombre_visible": "LinkedIn",
        "url": "https://linkedin.com/company/flymetrics",
        "icono": "fa-brands fa-linkedin-in",
        "orden": 6,
        "activo": True
    }
]

def _normalize_fa_icon(icono: str, red: str = "") -> str:
    if not icono:
        icono = ""
    icono = icono.strip()
    if icono.startswith("fa-brands ") or icono.startswith("fa-solid ") or icono.startswith("fab ") or icono.startswith("fas "):
        return icono
    clean = icono.replace("fa-", "").strip()
    brand_keywords = ["instagram", "facebook", "tiktok", "youtube", "linkedin", "whatsapp", "twitter", "x-twitter", "github", "telegram"]
    check_key = (red or clean).lower()
    if any(b in check_key for b in brand_keywords):
        if clean == "facebook": clean = "facebook-f"
        if clean == "linkedin": clean = "linkedin-in"
        return f"fa-brands fa-{clean or check_key}"
    return f"fa-solid fa-{clean or 'share-nodes'}"

def _seed_redes_if_empty(db: Session):
    count = db.query(RedSocialModel).count()
    if count == 0:
        for r in DEFAULT_REDES:
            db.add(RedSocialModel(**r))
        db.commit()

@router.get("/redes-sociales", status_code=status.HTTP_200_OK)
def get_redes_sociales_publico(db: Session = Depends(get_db)):
    """Público: Obtiene las redes sociales activas de Flymetrics."""
    _seed_redes_if_empty(db)
    items = db.query(RedSocialModel).filter(RedSocialModel.activo == True).order_by(
        RedSocialModel.orden.asc(),
        RedSocialModel.id_red.asc()
    ).all()

    data = [
        {
            "id_red": it.id_red,
            "red": it.red,
            "nombre_visible": it.nombre_visible,
            "url": it.url,
            "icono": _normalize_fa_icon(it.icono, it.red),
            "orden": it.orden,
            "activo": it.activo
        }
        for it in items
    ]
    return success_response(message="Redes sociales obtenidas", data=data)


@router.get("/admin/redes-sociales", status_code=status.HTTP_200_OK)
def get_admin_redes_sociales(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Admin: Obtiene todas las redes sociales registradas."""
    _seed_redes_if_empty(db)
    items = db.query(RedSocialModel).order_by(
        RedSocialModel.orden.asc(),
        RedSocialModel.id_red.asc()
    ).all()

    data = [
        {
            "id_red": it.id_red,
            "red": it.red,
            "nombre_visible": it.nombre_visible,
            "url": it.url,
            "icono": _normalize_fa_icon(it.icono, it.red),
            "orden": it.orden,
            "activo": it.activo
        }
        for it in items
    ]
    return success_response(message="Listado de redes sociales para administración", data=data)


@router.post("/admin/redes-sociales", status_code=status.HTTP_201_CREATED)
def create_red_social(
    item: RedSocialCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Admin: Agrega una nueva red social."""
    icono = _normalize_fa_icon(item.icono or "", item.red)

    nueva = RedSocialModel(
        red=item.red.strip(),
        nombre_visible=item.nombre_visible.strip(),
        url=item.url.strip(),
        icono=icono,
        orden=item.orden or 0,
        activo=item.activo if item.activo is not None else True
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return success_response(message="Red social registrada exitosamente", data={"id_red": nueva.id_red})


@router.put("/admin/redes-sociales/{id_red}", status_code=status.HTTP_200_OK)
def update_red_social(
    id_red: int,
    item: RedSocialUpdate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Admin: Modifica una red social existente."""
    elem = db.query(RedSocialModel).filter(RedSocialModel.id_red == id_red).first()
    if not elem:
        raise HTTPException(status_code=404, detail="Red social no encontrada")
    
    if item.red is not None: elem.red = item.red.strip()
    if item.nombre_visible is not None: elem.nombre_visible = item.nombre_visible.strip()
    if item.url is not None: elem.url = item.url.strip()
    if item.icono is not None: elem.icono = item.icono.strip()
    if item.orden is not None: elem.orden = item.orden
    if item.activo is not None: elem.activo = item.activo

    db.commit()
    db.refresh(elem)
    return success_response(message="Red social actualizada exitosamente", data={"id_red": elem.id_red})


@router.delete("/admin/redes-sociales/{id_red}", status_code=status.HTTP_200_OK)
def delete_red_social(
    id_red: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """Admin: Elimina una red social."""
    elem = db.query(RedSocialModel).filter(RedSocialModel.id_red == id_red).first()
    if not elem:
        raise HTTPException(status_code=404, detail="Red social no encontrada")
    
    db.delete(elem)
    db.commit()
    return success_response(message="Red social eliminada exitosamente")
