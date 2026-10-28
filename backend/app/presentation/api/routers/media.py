
import os
import shutil
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
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


@router.get("")
def list_media(current_user: UsuarioModel = Depends(admin_or_tech)):
    """
    Lista todos los archivos multimedia disponibles (imágenes y videos).
    Solo los logotipos oficiales del sistema se marcan como protegidos.
    """
    items = []
    seen_urls = set()

    # 1. Escanear recursivamente uploads/
    if UPLOADS_DIR.exists():
        for f in UPLOADS_DIR.rglob("*"):
            if f.is_file():
                ext = f.suffix.lower()
                rel_path = f.relative_to(FRONTEND_DIR).as_posix()
                url = f"/{rel_path}"
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                sz = f.stat().st_size
                is_vid = ext in ALLOWED_VIDEO_EXTS
                is_img = ext in ALLOWED_IMAGE_EXTS
                if is_vid or is_img:
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
                        url = f"{prefix}{f.name}"
                        if url not in seen_urls:
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

    # Proteger exclusivamente los logos
    if "logo" in filename.lower():
        return False

    try:
        # 1. Buscar en uploads/
        if UPLOADS_DIR.exists():
            for target in UPLOADS_DIR.rglob(filename):
                if target.is_file():
                    target.unlink()
                    return True

        # 2. Buscar en img/ o video/
        for root in [FRONTEND_DIR / "img", FRONTEND_DIR / "video"]:
            target = root / filename
            if target.is_file():
                target.unlink()
                return True
    except Exception as e:
        print(f"Error borrando archivo '{url_or_path}': {e}")
    return False

@router.delete("/{filename:path}")
def delete_media(filename: str, current_user: UsuarioModel = Depends(admin_required)):
    """
    Elimina directamente un archivo multimedia del servidor.
    Se permite eliminar cualquier archivo de servicios, publicidad, videos o imágenes,
    salvaguardando únicamente los logos oficiales de la marca.
    """
    safe_name = Path(filename).name
    if "logo" in safe_name.lower():
        raise HTTPException(status_code=403, detail="Los logotipos institucionales del sistema están protegidos y no pueden eliminarse")

    deleted = False

    # 1. Buscar en uploads
    if UPLOADS_DIR.exists():
        for target in UPLOADS_DIR.rglob(safe_name):
            if target.is_file():
                try:
                    target.unlink()
                    deleted = True
                    break
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"No se pudo eliminar: {str(e)}")

    # 2. Si no estaba en uploads, buscar en img/ o video/
    if not deleted:
        for root in [FRONTEND_DIR / "img", FRONTEND_DIR / "video"]:
            target = root / safe_name
            if target.is_file():
                try:
                    target.unlink()
                    deleted = True
                    break
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"No se pudo eliminar: {str(e)}")

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Archivo '{safe_name}' no encontrado en el servidor")

    return success_response(message=f"Archivo '{safe_name}' eliminado exitosamente del servidor")
