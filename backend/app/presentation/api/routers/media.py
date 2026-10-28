
import os
import shutil
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.presentation.api.dependencies.auth import RoleChecker
from app.infrastructure.database.models.models import UsuarioModel
from app.shared.responses.response import success_response

router = APIRouter(prefix="/media", tags=["Multimedia & Galería"])

admin_or_tech = RoleChecker(["administrador", "tecnico", "admin", "Admin", "Staff", "staff"])
admin_required = RoleChecker(["administrador", "Administrador", "admin", "Admin", "Staff", "staff"])

_curr = Path(__file__).resolve()
PROJECT_ROOT = None
for p in [_curr] + list(_curr.parents):
    if (p / "frontend").is_dir() and (p / "backend").is_dir():
        PROJECT_ROOT = p
        break
if not PROJECT_ROOT:
    PROJECT_ROOT = _curr.parent.parent.parent.parent.parent

FRONTEND_DIR = PROJECT_ROOT / "frontend"
# Si se despliega únicamente el backend de forma aislada, almacenar en backend/uploads
if FRONTEND_DIR.is_dir():
    UPLOADS_DIR = FRONTEND_DIR / "uploads"
else:
    BACKEND_ROOT = _curr.parent.parent.parent.parent
    UPLOADS_DIR = BACKEND_ROOT / "uploads"

UPLOADS_IMG_DIR = UPLOADS_DIR / "images"
UPLOADS_VID_DIR = UPLOADS_DIR / "videos"

# Asegurar directorios sin fallar si el contenedor tiene carpetas de solo lectura
try:
    UPLOADS_IMG_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_VID_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif"}
ALLOWED_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".m4v"}

def _sanitize_filename(name: str) -> str:
    import re
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    return clean.strip('_') or "media_file"

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    tipo: Optional[str] = Form(None),
    modulo: Optional[str] = Form("general"),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """
    Sube directamente una imagen o video al servidor para usar en servicios de la página principal o galerías.
    Organiza por módulo: 'publicidad', 'servicios', 'collage', etc.
    """
    import re
    ext = Path(file.filename).suffix.lower()
    is_img = ext in ALLOWED_IMAGE_EXTS
    is_vid = ext in ALLOWED_VIDEO_EXTS

    if not is_img and not is_vid:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de archivo no soportado ({ext}). Formatos permitidos: JPG, PNG, WEBP, SVG, MP4, WEBM, MOV."
        )

    media_type = "video" if is_vid else "imagen"
    if tipo and tipo in ["video", "imagen"]:
        media_type = tipo

    clean_mod = re.sub(r'[^a-zA-Z0-9_-]', '_', modulo or "general").strip('_') or "general"
    mod_dir = UPLOADS_DIR / clean_mod / ("videos" if media_type == "video" else "images")
    mod_dir.mkdir(parents=True, exist_ok=True)

    dest_folder = mod_dir
    ts = int(time.time())
    safe_name = _sanitize_filename(Path(file.filename).stem)
    new_filename = f"{safe_name}_{ts}{ext}"
    dest_path = dest_folder / new_filename

    total_bytes = 0
    with open(dest_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            buffer.write(chunk)
            total_bytes += len(chunk)

    rel_url = f"/uploads/{clean_mod}/{'videos' if media_type == 'video' else 'images'}/{new_filename}"

    return success_response(
        message=f"{media_type.capitalize()} subido exitosamente en módulo {clean_mod}",
        data={
            "filename": new_filename,
            "url": rel_url,
            "tipo": media_type,
            "modulo": clean_mod,
            "size_bytes": total_bytes,
            "size_formatted": f"{total_bytes / (1024 * 1024):.1f} MB" if total_bytes >= 1024*1024 else f"{total_bytes / 1024:.0f} KB"
        },
        status_code=201
    )


@router.post("/upload-batch", status_code=status.HTTP_201_CREATED)
async def upload_media_batch(
    files: list[UploadFile] = File(...),
    modulo: Optional[str] = Form("collage"),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """
    Sube múltiples imágenes/videos de una sola vez organizados por módulo (ej: collage).
    Retorna la lista de URLs de todos los archivos subidos exitosamente.
    """
    import re
    results = []
    errors = []
    clean_mod = re.sub(r'[^a-zA-Z0-9_-]', '_', modulo or "collage").strip('_') or "collage"

    for file in files:
        ext = Path(file.filename).suffix.lower()
        is_img = ext in ALLOWED_IMAGE_EXTS
        is_vid = ext in ALLOWED_VIDEO_EXTS

        if not is_img and not is_vid:
            errors.append({"filename": file.filename, "error": f"Formato no soportado: {ext}"})
            continue

        media_type = "video" if is_vid else "imagen"
        mod_dir = UPLOADS_DIR / clean_mod / ("videos" if media_type == "video" else "images")
        mod_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)  # milisegundos para evitar colisiones
        safe_name = _sanitize_filename(Path(file.filename).stem)
        new_filename = f"{safe_name}_{ts}{ext}"
        dest_path = mod_dir / new_filename

        try:
            total_bytes = 0
            with open(dest_path, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):
                    buffer.write(chunk)
                    total_bytes += len(chunk)

            rel_url = f"/uploads/{clean_mod}/{'videos' if media_type == 'video' else 'images'}/{new_filename}"
            results.append({
                "filename": new_filename,
                "original_name": file.filename,
                "url": rel_url,
                "tipo": media_type,
                "modulo": clean_mod,
                "size_bytes": total_bytes,
                "size_formatted": f"{total_bytes / (1024 * 1024):.1f} MB" if total_bytes >= 1024*1024 else f"{total_bytes / 1024:.0f} KB"
            })
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    return success_response(
        message=f"{len(results)} archivo(s) subido(s) exitosamente" + (f", {len(errors)} con errores" if errors else ""),
        data={"uploaded": results, "errors": errors, "total_subidos": len(results), "total_errores": len(errors)},
        status_code=201
    )


def _get_deleted_media_set(db: Session) -> set:
    """Retorna el conjunto de archivos eliminados registrados en la base de datos."""
    try:
        from app.infrastructure.database.models.models import SystemConfigModel
        import json
        cfg = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "media_deleted_files").first()
        if cfg and cfg.valor:
            data = json.loads(cfg.valor)
            if isinstance(data, list):
                return set(data)
    except Exception:
        pass
    return set()


def _add_deleted_media(db: Session, identifier: str):
    """Registra un archivo en la lista negra de medios eliminados en base de datos."""
    if not identifier:
        return
    try:
        from app.infrastructure.database.models.models import SystemConfigModel
        import json
        cfg = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "media_deleted_files").first()
        items = []
        if cfg and cfg.valor:
            try:
                items = json.loads(cfg.valor)
                if not isinstance(items, list):
                    items = []
            except Exception:
                items = []
        if identifier not in items:
            items.append(identifier)
        if not cfg:
            cfg = SystemConfigModel(clave="media_deleted_files", valor=json.dumps(items))
            db.add(cfg)
        else:
            cfg.valor = json.dumps(items)
        db.commit()
    except Exception as e:
        print(f"Error registrando archivo eliminado en BD: {e}")


@router.get("")
def list_media(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """
    Lista todos los archivos multimedia disponibles (imágenes y videos).
    Solo los logotipos oficiales del sistema se marcan como protegidos.
    Filtra automáticamente cualquier archivo registrado como eliminado.
    """
    items = []
    seen_urls = set()
    deleted_set = _get_deleted_media_set(db)

    # 1. Escanear recursivamente uploads/
    if UPLOADS_DIR.exists():
        for f in UPLOADS_DIR.rglob("*"):
            if f.is_file():
                ext = f.suffix.lower()
                is_vid = ext in ALLOWED_VIDEO_EXTS
                is_img = ext in ALLOWED_IMAGE_EXTS
                if not (is_vid or is_img):
                    continue

                if f.name in deleted_set:
                    continue

                try:
                    rel_to_uploads = f.relative_to(UPLOADS_DIR).as_posix()
                    url = f"/uploads/{rel_to_uploads}"
                except Exception:
                    url = f"/uploads/{f.name}"

                if url in seen_urls or url in deleted_set:
                    continue
                seen_urls.add(url)
                sz = f.stat().st_size
                is_logo = "logo" in f.name.lower()
                items.append({
                    "name": f.name,
                    "url": url,
                    "tipo": "video" if is_vid else "imagen",
                    "size_bytes": sz,
                    "size_formatted": f"{sz / (1024 * 1024):.1f} MB" if sz >= 1024*1024 else f"{sz / 1024:.0f} KB",
                    "is_custom_upload": not is_logo,
                    "is_protected": is_logo,
                    "updated_at": int(f.stat().st_mtime)
                })

    # 2. Escanear imágenes y videos base
    for folder, m_type, prefix in [
        (FRONTEND_DIR / "img", "imagen", "/img/"),
        (FRONTEND_DIR / "video", "video", "/video/")
    ]:
        if folder.exists():
            for f in folder.iterdir():
                if f.is_file():
                    ext = f.suffix.lower()
                    if (m_type == "imagen" and ext in ALLOWED_IMAGE_EXTS) or (m_type == "video" and ext in ALLOWED_VIDEO_EXTS):
                        if f.name in deleted_set:
                            continue
                        url = f"{prefix}{f.name}"
                        if url not in seen_urls and url not in deleted_set:
                            seen_urls.add(url)
                            sz = f.stat().st_size
                            is_logo = "logo" in f.name.lower()
                            items.append({
                                "name": f.name,
                                "url": url,
                                "tipo": m_type,
                                "size_bytes": sz,
                                "size_formatted": f"{sz / (1024 * 1024):.1f} MB" if sz >= 1024*1024 else f"{sz / 1024:.0f} KB",
                                "is_custom_upload": not is_logo,
                                "is_protected": is_logo,
                                "updated_at": int(f.stat().st_mtime)
                            })

    # Ordenar por fecha de modificación descendente
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return success_response(message="Archivos multimedia obtenidos exitosamente", data=items)


def delete_physical_upload(url_or_path: str) -> bool:
    """
    Elimina físicamente del disco un archivo multimedia (uploads, servicios, collage o base).
    Solo rechaza si es un logo institucional del sistema.
    """
    if not url_or_path:
        return False
    clean_url = str(url_or_path).strip().split("?")[0]
    filename = Path(clean_url).name
    if not filename:
        return False

    if "logo" in filename.lower():
        return False

    try:
        if UPLOADS_DIR.exists():
            for target in UPLOADS_DIR.rglob(filename):
                if target.is_file():
                    target.unlink()
                    return True

        for root in [FRONTEND_DIR / "img", FRONTEND_DIR / "video"]:
            target = root / filename
            if target.is_file():
                target.unlink()
                return True
    except Exception as e:
        print(f"Error borrando archivo '{url_or_path}': {e}")
    return False


@router.get("/{filename:path}")
def get_media_file(
    filename: str,
    db: Session = Depends(get_db)
):
    """
    Sirve directamente cualquier archivo multimedia (video o imagen)
    buscando en uploads/, video/ o img/. Soporta streaming de video con Range headers.
    """
    safe_name = Path(filename).name
    deleted_set = _get_deleted_media_set(db)
    if safe_name in deleted_set or filename in deleted_set:
        raise HTTPException(status_code=404, detail=f"Archivo multimedia '{safe_name}' no encontrado en el servidor")

    # 1. Buscar en uploads/
    if UPLOADS_DIR.exists():
        direct_target = UPLOADS_DIR / filename
        if direct_target.is_file():
            return FileResponse(str(direct_target))
        for target in UPLOADS_DIR.rglob(safe_name):
            if target.is_file():
                return FileResponse(str(target))

    # 2. Buscar en video/ o img/
    candidate_roots = [
        FRONTEND_DIR / "video",
        FRONTEND_DIR / "img",
        PROJECT_ROOT / "frontend" / "video",
        PROJECT_ROOT / "frontend" / "img",
        _curr.parent.parent.parent.parent / "frontend" / "video",
        _curr.parent.parent.parent.parent / "frontend" / "img",
        _curr.parent.parent.parent.parent / "video",
        _curr.parent.parent.parent.parent / "img",
    ]
    for root in candidate_roots:
        if root.exists():
            direct_target = root / filename
            if direct_target.is_file():
                return FileResponse(str(direct_target))
            target = root / safe_name
            if target.is_file():
                return FileResponse(str(target))

    raise HTTPException(status_code=404, detail=f"Archivo multimedia '{safe_name}' no encontrado en el servidor")


@router.delete("/{filename:path}")
def delete_media(
    filename: str,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_required)
):
    """
    Elimina directamente un archivo multimedia del servidor.
    - Soporta entornos con filesystem de solo lectura ([Errno 30]) ocultando de inmediato el recurso en BD.
    - Elimina físicamente si el archivo tiene permisos de escritura.
    - Limpia automáticamente referencias activas en medios_globales o servicios para evitar pantallas rotas.
    - Protege logotipos institucionales oficiales.
    """
    safe_name = Path(filename).name
    if "logo" in safe_name.lower():
        raise HTTPException(status_code=403, detail="Los logotipos institucionales del sistema están protegidos y no pueden eliminarse")

    physical_deleted = False

    # 1. Intentar borrar físicamente en uploads
    if UPLOADS_DIR.exists():
        for target in UPLOADS_DIR.rglob(safe_name):
            if target.is_file():
                try:
                    target.unlink()
                    physical_deleted = True
                    break
                except OSError as e:
                    print(f"[MEDIA UNLINK WARN] No se pudo borrar {target} en disco ({e}). Se registrará como eliminado en BD.")

    # 2. Si no estaba en uploads, intentar buscar en img/ o video/
    if not physical_deleted:
        for root in [FRONTEND_DIR / "img", FRONTEND_DIR / "video"]:
            if root.exists():
                target = root / safe_name
                if target.is_file():
                    try:
                        target.unlink()
                        physical_deleted = True
                        break
                    except OSError as e:
                        print(f"[MEDIA UNLINK WARN] No se pudo borrar {target} en disco ({e}). Se registrará como eliminado en BD.")

    # 3. Registrar siempre en la base de datos como eliminado permanentemente
    _add_deleted_media(db, safe_name)
    _add_deleted_media(db, filename)

    # 4. Limpiar referencias activas en medios_globales o servicios
    try:
        from app.infrastructure.database.models.models import SystemConfigModel, ServicioModel
        import json

        # Limpiar en medios globales
        cfg_medios = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "medios_globales").first()
        if cfg_medios and cfg_medios.valor:
            m_data = json.loads(cfg_medios.valor)
            changed = False
            if safe_name in (m_data.get("hero_video_url") or ""):
                m_data["hero_video_url"] = "/video/hero.mp4"
                changed = True
            if safe_name in (m_data.get("mobile_poster_url") or ""):
                m_data["mobile_poster_url"] = "/img/servicio_precision.jpg"
                changed = True
            if changed:
                cfg_medios.valor = json.dumps(m_data)
                db.commit()

        # Limpiar en servicios
        servicios_afectados = db.query(ServicioModel).all()
        for s in servicios_afectados:
            s_changed = False
            if s.video_url and safe_name in s.video_url:
                s.video_url = None
                s_changed = True
            if s.imagen_url and safe_name in s.imagen_url:
                s.imagen_url = None
                s_changed = True
            if s_changed:
                db.add(s)
        db.commit()
    except Exception as ref_err:
        print(f"[MEDIA CLEANUP REFS WARN] {ref_err}")

    return success_response(message=f"Archivo '{safe_name}' eliminado exitosamente del servidor")

