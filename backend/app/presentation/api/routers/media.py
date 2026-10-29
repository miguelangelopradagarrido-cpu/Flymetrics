
import os
import shutil
import time
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import unquote
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.presentation.api.dependencies.auth import RoleChecker
from app.infrastructure.database.models.models import UsuarioModel, MediaUploadModel
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

def _get_writable_uploads_dir() -> Path:
    """
    Determina la carpeta de subida con permisos de escritura reales.
    Si la carpeta estándar del contenedor es de solo lectura ([Errno 30]),
    retrocede dinámicamente a /tmp/flymetrics_uploads para garantizar la subida.
    """
    candidates = [
        UPLOADS_DIR,
        (PROJECT_ROOT / "uploads") if PROJECT_ROOT else None,
        Path(tempfile.gettempdir()) / "flymetrics_uploads",
        Path("/tmp/flymetrics_uploads")
    ]
    for c in candidates:
        if not c:
            continue
        try:
            c.mkdir(parents=True, exist_ok=True)
            test_file = c / f".perm_check_{int(time.time()*1000)}"
            test_file.write_text("ok")
            test_file.unlink()
            return c
        except Exception:
            continue
    fallback = Path(tempfile.gettempdir())
    return fallback

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif"}
ALLOWED_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".m4v"}

def _get_fotovideofly_candidates() -> List[Path]:
    candidates = [
        Path("/app/fotovideofly/fotovideofly"),
        Path("/app/fotovideofly"),
        (PROJECT_ROOT / "fotovideofly" / "fotovideofly") if PROJECT_ROOT else None,
        (PROJECT_ROOT / "fotovideofly") if PROJECT_ROOT else None,
        (PROJECT_ROOT / "video" / "video") if PROJECT_ROOT else None,
        (FRONTEND_DIR / "fotovideofly") if FRONTEND_DIR else None,
        (UPLOADS_DIR / "fotovideofly") if UPLOADS_DIR else None,
        Path("fotovideofly/fotovideofly"),
        Path("fotovideofly"),
        Path("video/video"),
        Path("../fotovideofly/fotovideofly"),
        Path("../fotovideofly")
    ]
    res = []
    seen = set()
    for c in candidates:
        if c and c.exists() and c.is_dir():
            try:
                resolved = c.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    res.append(c)
            except Exception:
                res.append(c)
    return res

def get_fotovideofly_items() -> List[Dict[str, Any]]:
    """
    Escanea y devuelve todos los archivos multimedia de la carpeta fotovideofly
    directamente desde el disco, sin intermediación de base de datos para máxima velocidad (< 5 ms).
    """
    seen_names = set()
    items = []
    for c_dir in _get_fotovideofly_candidates():
        for f in c_dir.rglob("*"):
            if f.is_file() and f.name not in seen_names:
                ext = f.suffix.lower()
                is_vid = ext in ALLOWED_VIDEO_EXTS
                is_img = ext in ALLOWED_IMAGE_EXTS
                if not (is_vid or is_img):
                    continue
                seen_names.add(f.name)
                sz = f.stat().st_size
                name_clean = f.stem.replace("_", " ").replace("-", " ")
                if is_vid:
                    titulo = f"Operación Aérea en Campo: {name_clean}"
                    subtitulo = "Video de dron agrícola en vuelo, aspersión y telemetría RTK en tiempo real"
                    badge = "Video de Vuelo"
                else:
                    titulo = f"Operación en Campo: {name_clean}"
                    subtitulo = "Captura de alta resolución de cultivos y predios con tecnología Flymetrics"
                    badge = "Operación en Campo"

                items.append({
                    "id_publicidad": f"fv_{len(items)+1}",
                    "name": f.name,
                    "titulo": titulo,
                    "subtitulo": subtitulo,
                    "badge": badge,
                    "tipo": "video" if is_vid else "imagen",
                    "tipo_medio": "video" if is_vid else "imagen",
                    "url": f"/fotovideofly/{f.name}",
                    "url_medio": f"/fotovideofly/{f.name}",
                    "texto_boton": "Cotizar Operación",
                    "url_accion": "#agendar",
                    "size_bytes": sz,
                    "size_formatted": f"{sz / (1024 * 1024):.1f} MB" if sz >= 1024*1024 else f"{sz / 1024:.0f} KB",
                    "is_custom_upload": True,
                    "is_protected": False,
                    "is_fotovideofly": True,
                    "modulo": "fotovideofly",
                    "origin": "fotovideofly",
                    "activo": True,
                    "updated_at": int(f.stat().st_mtime)
                })
    items.sort(key=lambda x: (0 if x["tipo"] == "video" else 1, -x["updated_at"]))
    return items

def _sanitize_filename(name: str) -> str:
    import re
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    return clean.strip('_') or "media_file"

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    tipo: Optional[str] = Form(None),
    modulo: Optional[str] = Form("general"),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """
    Sube directamente una imagen o video al servidor para usar en servicios de la página principal o galerías.
    Organiza por módulo: 'publicidad', 'servicios', 'collage', etc.
    Guarda en disco escribible (/tmp o uploads) y en base de datos para persistencia total contra reinicios.
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
    writable_dir = _get_writable_uploads_dir()
    mod_dir = writable_dir / clean_mod / ("videos" if media_type == "video" else "images")
    try:
        mod_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        mod_dir = writable_dir

    ts = int(time.time())
    safe_name = _sanitize_filename(Path(file.filename).stem)
    new_filename = f"{safe_name}_{ts}{ext}"
    dest_path = mod_dir / new_filename

    # 1. Leer buffer completo en memoria
    file_bytes = await file.read()
    total_bytes = len(file_bytes)

    # 2. Intentar guardar en disco escribible (ej: /tmp/flymetrics_uploads o uploads)
    try:
        dest_path.write_bytes(file_bytes)
    except Exception as disk_err:
        print(f"[MEDIA DISK WRITE WARN] No se pudo escribir en disco ({disk_err}). Respaldando en base de datos...")

    rel_url = f"/uploads/{clean_mod}/{'videos' if media_type == 'video' else 'images'}/{new_filename}"

    # 3. Guardar en base de datos MySQL para persistencia total contra reinicios o entornos de solo lectura
    try:
        import base64
        b64_str = base64.b64encode(file_bytes).decode('ascii') if total_bytes <= 25 * 1024 * 1024 else None
        media_rec = db.query(MediaUploadModel).filter(MediaUploadModel.filename == new_filename).first()
        if not media_rec:
            media_rec = MediaUploadModel(
                filename=new_filename,
                rel_url=rel_url,
                modulo=clean_mod,
                tipo=media_type,
                content_type=file.content_type or ("video/mp4" if is_vid else "image/jpeg"),
                data=b64_str,
                size_bytes=total_bytes,
                activo=True
            )
            db.add(media_rec)
        else:
            if b64_str:
                media_rec.data = b64_str
            media_rec.size_bytes = total_bytes
            media_rec.activo = True
        db.commit()
    except Exception as db_err:
        db.rollback()
        print(f"[MEDIA DB BACKUP WARN] Error guardando respaldo en BD: {db_err}")

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
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """
    Sube múltiples imágenes/videos de una sola vez organizados por módulo (ej: collage).
    Retorna la lista de URLs de todos los archivos subidos exitosamente.
    """
    import re
    import base64
    results = []
    errors = []
    clean_mod = re.sub(r'[^a-zA-Z0-9_-]', '_', modulo or "collage").strip('_') or "collage"
    writable_dir = _get_writable_uploads_dir()

    for file in files:
        ext = Path(file.filename).suffix.lower()
        is_img = ext in ALLOWED_IMAGE_EXTS
        is_vid = ext in ALLOWED_VIDEO_EXTS

        if not is_img and not is_vid:
            errors.append({"filename": file.filename, "error": f"Formato no soportado: {ext}"})
            continue

        media_type = "video" if is_vid else "imagen"
        mod_dir = writable_dir / clean_mod / ("videos" if media_type == "video" else "images")
        try:
            mod_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            mod_dir = writable_dir

        ts = int(time.time() * 1000)
        safe_name = _sanitize_filename(Path(file.filename).stem)
        new_filename = f"{safe_name}_{ts}{ext}"
        dest_path = mod_dir / new_filename

        try:
            file_bytes = await file.read()
            total_bytes = len(file_bytes)

            try:
                dest_path.write_bytes(file_bytes)
            except Exception as disk_err:
                print(f"[MEDIA BATCH DISK WARN] {disk_err}")

            rel_url = f"/uploads/{clean_mod}/{'videos' if media_type == 'video' else 'images'}/{new_filename}"

            try:
                b64_str = base64.b64encode(file_bytes).decode('ascii') if total_bytes <= 25 * 1024 * 1024 else None
                media_rec = MediaUploadModel(
                    filename=new_filename,
                    rel_url=rel_url,
                    modulo=clean_mod,
                    tipo=media_type,
                    content_type=file.content_type or ("video/mp4" if is_vid else "image/jpeg"),
                    data=b64_str,
                    size_bytes=total_bytes,
                    activo=True
                )
                db.add(media_rec)
                db.commit()
            except Exception as db_e:
                db.rollback()
                print(f"[MEDIA BATCH DB WARN] {db_e}")

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
    Integra archivos de la base de datos MySQL (persistentes), carpetas de uploads y recursos base.
    Filtra automáticamente cualquier archivo registrado como eliminado.
    """
    items = []
    seen_urls = set()
    deleted_set = _get_deleted_media_set(db)

    # 1. Escanear registros en la base de datos (subidas dinámicas persistentes)
    try:
        db_items = db.query(MediaUploadModel).filter(MediaUploadModel.activo == True).all()
        for rec in db_items:
            if rec.filename in deleted_set or rec.rel_url in deleted_set:
                continue
            if rec.rel_url in seen_urls:
                continue
            seen_urls.add(rec.rel_url)
            sz = rec.size_bytes or 0
            items.append({
                "name": rec.filename,
                "url": rec.rel_url,
                "tipo": rec.tipo or "imagen",
                "size_bytes": sz,
                "size_formatted": f"{sz / (1024 * 1024):.1f} MB" if sz >= 1024*1024 else f"{sz / 1024:.0f} KB",
                "is_custom_upload": True,
                "is_protected": False,
                "updated_at": int(rec.created_at.timestamp()) if hasattr(rec, "created_at") and rec.created_at else int(time.time())
            })
    except Exception as db_e:
        print(f"[LIST MEDIA DB WARN] {db_e}")

    # 2. Escanear recursivamente carpetas de uploads en disco
    writable_dir = _get_writable_uploads_dir()
    for search_dir in [UPLOADS_DIR, writable_dir]:
        if search_dir and search_dir.exists():
            for f in search_dir.rglob("*"):
                if f.is_file():
                    ext = f.suffix.lower()
                    is_vid = ext in ALLOWED_VIDEO_EXTS
                    is_img = ext in ALLOWED_IMAGE_EXTS
                    if not (is_vid or is_img):
                        continue
                    if f.name in deleted_set:
                        continue
                    try:
                        rel_to_uploads = f.relative_to(search_dir).as_posix()
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

    # 3. Escanear imágenes y videos base
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

    # 4. Escanear carpeta 'fotovideofly' en disco
    for fv_item in get_fotovideofly_items():
        if fv_item["url"] not in seen_urls and fv_item["name"] not in deleted_set:
            seen_urls.add(fv_item["url"])
            items.append(fv_item)

    # Ordenar por fecha de modificación descendente
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return success_response(message="Archivos multimedia obtenidos exitosamente", data=items)


@router.get("/fotovideofly/list", status_code=status.HTTP_200_OK)
def list_fotovideofly_files():
    """Retorna directamente la lista de archivos de la carpeta fotovideofly (sin base de datos)."""
    items = get_fotovideofly_items()
    resp = success_response(message="Archivos de fotovideofly obtenidos exitosamente", data=items)
    try:
        resp.headers["Cache-Control"] = "public, max-age=300"
    except Exception:
        pass
    return resp


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
        writable_dir = _get_writable_uploads_dir()
        for check_dir in [UPLOADS_DIR, writable_dir]:
            if check_dir and check_dir.exists():
                for target in check_dir.rglob(filename):
                    if target.is_file():
                        try:
                            target.unlink()
                            return True
                        except OSError:
                            pass

        for root in [FRONTEND_DIR / "img", FRONTEND_DIR / "video"]:
            if root and root.exists():
                target = root / filename
                if target.is_file():
                    try:
                        target.unlink()
                        return True
                    except OSError:
                        pass
    except Exception as e:
        print(f"Error borrando archivo '{url_or_path}': {e}")
    return False


def _guess_media_type(filename_or_path: str) -> str:
    ext = Path(filename_or_path).suffix.lower()
    mapping = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".m4v": "video/mp4",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".gif": "image/gif",
    }
    return mapping.get(ext, "application/octet-stream")


@router.get("/{filename:path}")
def get_media_file(
    filename: str,
    db: Session = Depends(get_db)
):
    """
    Sirve directamente cualquier archivo multimedia (video o imagen)
    buscando en uploads/, video/ o img/, y restaurando de MySQL si es necesario.
    Soporta streaming de video con Range headers.
    """
    filename = unquote(filename)
    safe_name = Path(filename).name
    deleted_set = _get_deleted_media_set(db)
    if safe_name in deleted_set or filename in deleted_set:
        raise HTTPException(status_code=404, detail=f"Archivo multimedia '{safe_name}' no encontrado en el servidor")

    writable_dir = _get_writable_uploads_dir()

    # Normalizar ruta relativa eliminando prefijos redundantes
    clean_rel = filename.lstrip("/")
    if clean_rel.startswith("uploads/"):
        clean_rel = clean_rel[len("uploads/"):]
    elif clean_rel.startswith("pages/uploads/"):
        clean_rel = clean_rel[len("pages/uploads/"):]
    elif clean_rel.startswith("fotovideofly/"):
        clean_rel = clean_rel[len("fotovideofly/"):]
    elif clean_rel.startswith("pages/fotovideofly/"):
        clean_rel = clean_rel[len("pages/fotovideofly/"):]

    # 1. Buscar en carpetas fotovideofly en disco
    for fv_dir in _get_fotovideofly_candidates():
        direct_target = fv_dir / clean_rel
        if direct_target.is_file():
            return FileResponse(str(direct_target), media_type=_guess_media_type(direct_target), headers={"Cache-Control": "public, max-age=86400"})
        direct_raw = fv_dir / filename
        if direct_raw.is_file():
            return FileResponse(str(direct_raw), media_type=_guess_media_type(direct_raw), headers={"Cache-Control": "public, max-age=86400"})
        for target in fv_dir.rglob(safe_name):
            if target.is_file():
                return FileResponse(str(target), media_type=_guess_media_type(target), headers={"Cache-Control": "public, max-age=86400"})
        # Fallback insensitivo a mayúsculas/minúsculas para Linux
        safe_lower = safe_name.lower()
        unquoted_lower = unquote(safe_name).lower()
        for target in fv_dir.rglob("*"):
            if target.is_file() and target.name.lower() in [safe_lower, unquoted_lower]:
                return FileResponse(str(target), media_type=_guess_media_type(target), headers={"Cache-Control": "public, max-age=86400"})

    # 2. Buscar en directorios de uploads en disco
    candidate_dirs = [
        writable_dir,
        UPLOADS_DIR,
        Path(tempfile.gettempdir()) / "flymetrics_uploads",
        Path("/tmp/flymetrics_uploads"),
        (PROJECT_ROOT / "uploads") if PROJECT_ROOT else None,
        (PROJECT_ROOT / "frontend" / "uploads") if PROJECT_ROOT else None
    ]
    for c_dir in candidate_dirs:
        if c_dir and c_dir.exists():
            direct_target = c_dir / clean_rel
            if direct_target.is_file():
                return FileResponse(str(direct_target), media_type=_guess_media_type(direct_target), headers={"Cache-Control": "public, max-age=86400"})
            direct_raw = c_dir / filename
            if direct_raw.is_file():
                return FileResponse(str(direct_raw), media_type=_guess_media_type(direct_raw), headers={"Cache-Control": "public, max-age=86400"})
            for target in c_dir.rglob(safe_name):
                if target.is_file():
                    return FileResponse(str(target), media_type=_guess_media_type(target), headers={"Cache-Control": "public, max-age=86400"})

    # 3. Buscar en video/ o img/ base
    candidate_roots = [
        FRONTEND_DIR / "video",
        FRONTEND_DIR / "img",
        PROJECT_ROOT / "frontend" / "video" if PROJECT_ROOT else None,
        PROJECT_ROOT / "frontend" / "img" if PROJECT_ROOT else None,
        _curr.parent.parent.parent.parent / "frontend" / "video",
        _curr.parent.parent.parent.parent / "frontend" / "img",
        _curr.parent.parent.parent.parent / "video",
        _curr.parent.parent.parent.parent / "img",
    ]
    for root in candidate_roots:
        if root and root.exists():
            direct_target = root / clean_rel
            if direct_target.is_file():
                return FileResponse(str(direct_target), media_type=_guess_media_type(direct_target), headers={"Cache-Control": "public, max-age=86400"})
            target = root / safe_name
            if target.is_file():
                return FileResponse(str(target), media_type=_guess_media_type(target), headers={"Cache-Control": "public, max-age=86400"})

    # 3. Restaurar desde MySQL si no está en disco (ej: tras despliegue de contenedor efímero)
    try:
        import base64
        clean_url_match = f"/uploads/{clean_rel.lstrip('/')}"
        media_rec = db.query(MediaUploadModel).filter(
            (MediaUploadModel.filename == safe_name) | 
            (MediaUploadModel.filename == filename) |
            (MediaUploadModel.rel_url == clean_url_match) |
            (MediaUploadModel.rel_url == f"/{filename.lstrip('/')}")
        ).first()

        if media_rec and media_rec.data and media_rec.activo:
            cache_file = writable_dir / safe_name
            try:
                raw_bytes = base64.b64decode(media_rec.data)
                cache_file.write_bytes(raw_bytes)
                return FileResponse(str(cache_file), media_type=media_rec.content_type or _guess_media_type(cache_file))
            except Exception:
                from fastapi.responses import Response
                return Response(content=base64.b64decode(media_rec.data), media_type=media_rec.content_type or _guess_media_type(safe_name))
    except Exception as rec_err:
        print(f"[MEDIA RESTORE DB WARN] {rec_err}")

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
    if any(p in safe_name.lower() for p in ["logo", "hero.mp4", "field_drone.mp4", "servicio_precision.jpg"]):
        raise HTTPException(status_code=403, detail="Los recursos base del sistema están protegidos y no pueden eliminarse")

    physical_deleted = False
    writable_dir = _get_writable_uploads_dir()

    # 1. Intentar borrar físicamente en uploads
    for search_dir in [UPLOADS_DIR, writable_dir]:
        if search_dir and search_dir.exists():
            for target in search_dir.rglob(safe_name):
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
            if root and root.exists():
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

    # 4. Desactivar en tabla_archivos_media en BD
    try:
        db.query(MediaUploadModel).filter(
            (MediaUploadModel.filename == safe_name) | (MediaUploadModel.filename == filename)
        ).delete(synchronize_session=False)
        db.commit()
    except Exception as db_del_err:
        print(f"[MEDIA DB DELETE WARN] {db_del_err}")

    # 5. Limpiar referencias activas en medios_globales o servicios
    try:
        from app.infrastructure.database.models.models import SystemConfigModel, ServicioModel
        import json

        # Limpiar en medios globales
        cfg_medios = db.query(SystemConfigModel).filter(SystemConfigModel.clave == "medios_globales").first()
        if cfg_medios and cfg_medios.valor:
            m_data = json.loads(cfg_medios.valor)
            changed = False
            if safe_name in (m_data.get("hero_video_url") or "") or filename in (m_data.get("hero_video_url") or ""):
                m_data["hero_video_url"] = "/video/hero.mp4"
                changed = True
            if safe_name in (m_data.get("mobile_poster_url") or "") or filename in (m_data.get("mobile_poster_url") or ""):
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


