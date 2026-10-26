from fastapi import APIRouter, Depends, status, Query, File, UploadFile, Form
import os, uuid
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.application.dto import schemas
from app.application.use_cases.use_cases import EntregableUseCases
from app.presentation.api.dependencies.auth import RoleChecker, get_current_user
from app.infrastructure.database.models.models import UsuarioModel, EntregableModel, AgendaModel
from app.shared.responses.response import success_response
from app.shared.exceptions.exceptions import BadRequestException

router = APIRouter(prefix="/entregables", tags=["Buzón de Entregables"])

cliente_required = RoleChecker(["cliente"])
admin_required = RoleChecker(["administrador"])
admin_or_tech = RoleChecker(["administrador", "tecnico"])

ALLOWED_ENTREGABLE_EXTENSIONS = {
    ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz",
    ".tif", ".tiff", ".kml", ".kmz", ".geojson",
    ".jpg", ".jpeg", ".png", ".webp",
    ".csv", ".xlsx", ".xls"
}
MAX_ENTREGABLE_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def subir_archivo_entregable(
    id_turno: int = Form(...),
    tipo_archivo: str = Form("Ortofoto"),
    notas: str = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """Permite al técnico o administrador subir un archivo físico de entregable con validación estricta y streaming sin saturar RAM."""
    if not file.filename:
        raise BadRequestException("Debe seleccionar un archivo válido.")

    safe_filename = os.path.basename(file.filename or "")
    ext = os.path.splitext(safe_filename)[1].lower()
    if ext not in ALLOWED_ENTREGABLE_EXTENSIONS:
        raise BadRequestException(
            f"Extensión '{ext}' no permitida. Solo se admiten archivos técnicos de entregables "
            f"({', '.join(sorted(ALLOWED_ENTREGABLE_EXTENSIONS))})."
        )

    base_frontend = "frontend"
    if not os.path.isdir(base_frontend):
        base_frontend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    uploads_dir = os.path.join(base_frontend, "uploads", "entregables")
    os.makedirs(uploads_dir, exist_ok=True)
    
    unique_name = f"entregable_{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(uploads_dir, unique_name)
    
    total_size = 0
    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_ENTREGABLE_FILE_SIZE:
                    f.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise BadRequestException("El archivo supera el límite máximo permitido de 100 MB.")
                f.write(chunk)
    except BadRequestException:
        raise
    except Exception as stream_err:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise BadRequestException(f"Error al guardar el archivo en el servidor: {str(stream_err)}")
        
    relative_url = f"/uploads/entregables/{unique_name}"
    
    req = schemas.EntregableCreate(
        id_turno=id_turno,
        tipo_archivo=tipo_archivo,
        url_archivo=relative_url,
        nombre_archivo=file.filename,
        notas=notas
    )
    entregable = EntregableUseCases.subir_entregable(db, req)
    data = schemas.EntregableResponse.model_validate(entregable).model_dump()

    try:
        from app.shared.utils.email_service import EmailService
        turno = entregable.turno or db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
        if turno and turno.finca and turno.finca.cliente:
            c = turno.finca.cliente
            dest = c.usuario.email if c.usuario else None
            if dest:
                EmailService.send_executive_report_ready(
                    to_email=dest,
                    nombre_cliente=f"{c.nombre} {c.apellido_1 or ''}".strip(),
                    id_turno=turno.id_turno,
                    servicio=turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola",
                    finca=turno.finca.nombre_finca,
                    url_informe=entregable.url_archivo,
                    tipo_informe=entregable.tipo_archivo or "Informe Técnico Ejecutivo"
                )
    except Exception as mail_err:
        print(f"[ENTREGABLE EMAIL ERROR] {mail_err}")

    return success_response(message="Archivo de entregable subido exitosamente", data=data, status_code=201)

@router.post("", status_code=status.HTTP_201_CREATED)
def subir_entregable(
    request: schemas.EntregableCreate,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """El administrador sube la URL del mapa procesado (Ortofoto, NDVI) y lo vincula al turno. Envía alerta WhatsApp y Email."""
    entregable = EntregableUseCases.subir_entregable(db, request)
    data = schemas.EntregableResponse.model_validate(entregable).model_dump()

    try:
        from app.shared.utils.email_service import EmailService
        turno = entregable.turno or db.query(AgendaModel).filter(AgendaModel.id_turno == request.id_turno).first()
        if turno and turno.finca and turno.finca.cliente:
            c = turno.finca.cliente
            dest = c.usuario.email if c.usuario else None
            if dest:
                EmailService.send_executive_report_ready(
                    to_email=dest,
                    nombre_cliente=f"{c.nombre} {c.apellido_1 or ''}".strip(),
                    id_turno=turno.id_turno,
                    servicio=turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola",
                    finca=turno.finca.nombre_finca,
                    url_informe=entregable.url_archivo,
                    tipo_informe=entregable.tipo_archivo or "Informe Técnico Ejecutivo"
                )
    except Exception as mail_err:
        print(f"[ENTREGABLE EMAIL ERROR] {mail_err}")

    return success_response(message="Entregable registrado exitosamente y notificación enviada al cliente", data=data, status_code=201)

@router.get("/mis-archivos")
def get_mis_entregables(
    id_turno: int = Query(None, description="Filtrar por un turno específico"),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(cliente_required)
):
    """El cliente consulta su buzón privado de mapas y entregables."""
    from app.shared.exceptions.exceptions import NotFoundException
    try:
        entregables = EntregableUseCases.ver_mis_entregables(db, current_user, id_turno)
    except NotFoundException:
        entregables = []
    except Exception as exc:
        import logging
        logging.getLogger("flymetrics").error(f"Error al obtener entregables del cliente: {exc}")
        entregables = []

    from app.infrastructure.database.models.models import ClienteModel, FincaModel, AgendaModel, ReporteVueloModel
    cliente = db.query(ClienteModel).filter(ClienteModel.id_usuario == current_user.id_usuarios).first()
    
    data = []
    for e in entregables:
        item = schemas.EntregableResponse.model_validate(e).model_dump()
        if e.turno:
            item["fecha_turno"] = str(e.turno.fecha_de_turno)
            if e.turno.finca:
                item["nombre_finca"] = e.turno.finca.nombre_finca
                if e.turno.finca.cliente:
                    item["cliente_nombre"] = f"{e.turno.finca.cliente.nombre} {e.turno.finca.cliente.apellido_1 or ''}".strip()
        data.append(item)

    # Añadir entregables de Google Drive registrados en Reportes de Vuelo
    if cliente:
        rep_query = db.query(ReporteVueloModel).join(AgendaModel).join(FincaModel).filter(
            FincaModel.id_cliente == cliente.id_cliente,
            ReporteVueloModel.url_entregable_drive.isnot(None),
            ReporteVueloModel.url_entregable_drive != ""
        )
        if id_turno:
            rep_query = rep_query.filter(ReporteVueloModel.id_turno == id_turno)
        
        reps = rep_query.all()
        for r in reps:
            # Evitar duplicar si ya existe en data con la misma URL
            if not any(d.get("url_archivo") == r.url_entregable_drive for d in data):
                f_nom = r.turno.finca.nombre_finca if (r.turno and r.turno.finca) else "Predio Agrícola"
                f_fec = str(r.turno.fecha_de_turno) if (r.turno and r.turno.fecha_de_turno) else str(r.created_at)[:10]
                data.append({
                    "id_entregable": r.id_reporte * 10000,
                    "id_turno": r.id_turno,
                    "tipo_archivo": "Carpeta Google Drive (Mapas / Ortofotos)",
                    "url_archivo": r.url_entregable_drive,
                    "nombre_archivo": f"Entrega_Drive_Turno_{r.id_turno}.url",
                    "fecha_subida": r.created_at.isoformat() if r.created_at else None,
                    "fecha_turno": f_fec,
                    "nombre_finca": f_nom,
                    "cliente_nombre": f"{cliente.nombre} {cliente.apellido_1 or ''}".strip(),
                    "descripcion": "Enlace directo en la nube a mapas ortomosaicos, índices NDVI y telemetría completa."
                })

    return success_response(message="Buzón de entregables obtenido exitosamente", data=data)

cliente_or_admin_or_tech = RoleChecker(["cliente", "administrador", "tecnico"])

@router.get("")
def list_todos_entregables(
    id_turno: int = Query(None),
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(cliente_or_admin_or_tech)
):
    """Vista de entregables subidos al sistema. Admin ve todos, técnico ve los de sus vuelos y cliente ve los suyos."""
    if current_user.rol == "cliente":
        return get_mis_entregables(id_turno=id_turno, db=db, current_user=current_user)

    from app.infrastructure.database.models.models import TecnicoModel
    if current_user.rol == "tecnico":
        tecnico = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
        if tecnico:
            query = db.query(EntregableModel).join(AgendaModel).filter(AgendaModel.id_tecnico == tecnico.id_tecnico)
            if id_turno:
                query = query.filter(EntregableModel.id_turno == id_turno)
            entregables = query.all()
        else:
            entregables = []
    else:
        entregables = EntregableUseCases.list_all_entregables(db, id_turno)

    data = []
    for e in entregables:
        item = schemas.EntregableResponse.model_validate(e).model_dump()
        if e.turno:
            item["fecha_turno"] = str(e.turno.fecha_de_turno)
            if e.turno.finca:
                item["nombre_finca"] = e.turno.finca.nombre_finca
                if e.turno.finca.cliente:
                    item["cliente_nombre"] = f"{e.turno.finca.cliente.nombre} {e.turno.finca.cliente.apellido_1 or ''}".strip()
        data.append(item)
    return success_response(message="Historial de entregables obtenido", data=data)

from fastapi.responses import Response, FileResponse
import os

@router.get("/{id_entregable}/descargar")
def descargar_entregable(
    id_entregable: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Fuerza la descarga directa del archivo entregable en formato oficial PDF verificando permisos del usuario."""
    from app.infrastructure.database.models.models import EntregableModel, ReporteVueloModel
    from app.shared.exceptions.exceptions import NotFoundException, ForbiddenException
    import mimetypes

    entregable = db.query(EntregableModel).filter(EntregableModel.id_entregable == id_entregable).first()
    if not entregable:
        raise NotFoundException("Archivo entregable no encontrado")

    # Validación de propiedad (IDOR)
    if current_user.rol == "cliente":
        if not (entregable.turno and entregable.turno.finca and entregable.turno.finca.cliente and entregable.turno.finca.cliente.id_usuario == current_user.id_usuarios):
            raise ForbiddenException("No tienes permiso para descargar este archivo entregable")
    elif current_user.rol == "tecnico":
        tec_id = current_user.tecnico.id_tecnico if current_user.tecnico else None
        if entregable.turno and entregable.turno.id_tecnico != tec_id and (not entregable.turno.tecnicos_adicionales or str(tec_id) not in entregable.turno.tecnicos_adicionales):
            raise ForbiddenException("No tienes permiso para descargar este archivo entregable")

    filename = f"Entregable_Flymetrics_{id_entregable}.pdf"

    recom_text = "Se sugiere revision de suelo a los 5 dias y reingreso seguro al lote en 24h."
    insumos_text = "Insumos: 15.0L | Agua: 120.0L | Baterias: 4 | Estado: Operacion Exitosa"
    finca_text = "Predio: Finca Registrada Flymetrics"

    if entregable:
        raw_name = entregable.nombre_archivo or f"entregable_{entregable.tipo_archivo}_{id_entregable}"
        # Siempre garantizar extension .pdf en el nombre de descarga
        base_name = os.path.splitext(raw_name)[0]
        filename = base_name + ".pdf"

        clean_url = (entregable.url_archivo or "").lstrip("/")
        path1 = os.path.normpath(clean_url)
        path2 = os.path.normpath(os.path.join("frontend", clean_url))

        target_path = None
        if os.path.exists(path1):
            target_path = path1
        elif os.path.exists(path2):
            target_path = path2

        if target_path:
            # Detectar si el archivo es realmente un PDF por magic bytes
            # Esto evita que mimetypes lo clasifique como text/plain por extension erronea
            detected_mime = "application/pdf"
            try:
                with open(target_path, "rb") as f_check:
                    header = f_check.read(8)
                if header.startswith(b"%PDF"):
                    detected_mime = "application/pdf"
                else:
                    guessed, _ = mimetypes.guess_type(target_path)
                    if guessed and guessed not in ("text/plain", "application/octet-stream"):
                        detected_mime = guessed
                    # Si es text/plain pero el contenido puede ser PDF, forzar PDF
                    else:
                        detected_mime = "application/pdf"
            except Exception:
                pass

            return FileResponse(
                path=target_path,
                filename=filename,
                media_type=detected_mime,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Content-Type-Options": "nosniff"
                }
            )

        if entregable.turno:
            if entregable.turno.finca:
                finca_text = f"Predio: {entregable.turno.finca.nombre_finca}"
            if entregable.turno.reporte_vuelo:
                rep = entregable.turno.reporte_vuelo
                insumos_text = f"Insumos: {rep.insumos_litros_aplicados}L | Agua: {rep.agua_litros}L | Baterias: {rep.baterias_utilizadas}"
                if rep.recomendaciones_agronomicas:
                    recom_text = rep.recomendaciones_agronomicas[:90]

    # Documento PDF Oficial Autogenerado formateado
    pdf_str = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Count 1 /Kids [3 0 R] >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 450 >>
stream
BT
/F1 18 Tf
50 720 Td
(FLYMETRICS OS - CONTROL AEREO Y AGRO) Tj
/F1 14 Tf
0 -40 Td
(INFORME TECNICO Y RECOMENDACIONES DE VUELO) Tj
/F1 11 Tf
0 -30 Td
(ID Entregable: #{id_entregable} | {finca_text}) Tj
0 -20 Td
(Servicio: Fotogrametria y Aspersion Aerea Especializada) Tj
0 -25 Td
(TELEMETRIA: {insumos_text}) Tj
0 -25 Td
(RECOMENDACIONES AGRONOMICAS DEL PILOTO TECNICO:) Tj
0 -20 Td
({recom_text}) Tj
0 -40 Td
(Este reporte certifica la finalizacion del servicio y procesamiento) Tj
0 -20 Td
(exitoso de mapas multiespectrales en la nube de Flymetrics.) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000233 00000 n 
0000000302 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
815
%%EOF"""

    pdf_bytes = pdf_str.encode('latin1')
    pdf_filename = f"Informe_Recomendaciones_Flymetrics_{id_entregable}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{pdf_filename}"',
            "X-Content-Type-Options": "nosniff"
        }
    )

@router.get("/{id_turno}/descargar-docx")
def descargar_reporte_docx(
    id_turno: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Genera y descarga el documento oficial Word (.docx) del vuelo para el turno indicado verificando permisos."""
    from app.infrastructure.database.models.models import AgendaModel, ReporteVueloModel
    from app.shared.utils.docx_bitacora_service import generate_bitacora_docx
    from app.shared.exceptions.exceptions import NotFoundException, ForbiddenException

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        raise NotFoundException(f"Turno #{id_turno} no encontrado")

    # Validación de propiedad (IDOR)
    if current_user.rol == "cliente":
        if not (turno.finca and turno.finca.cliente and turno.finca.cliente.id_usuario == current_user.id_usuarios):
            raise ForbiddenException("No tienes permiso para descargar este reporte")
    elif current_user.rol == "tecnico":
        tec_id = current_user.tecnico.id_tecnico if current_user.tecnico else None
        if turno.id_tecnico != tec_id and (not turno.tecnicos_adicionales or str(tec_id) not in turno.tecnicos_adicionales):
            raise ForbiddenException("No tienes permiso para descargar este reporte")

    reporte = db.query(ReporteVueloModel).filter(ReporteVueloModel.id_turno == id_turno).first()

    data = {
        "id_turno": turno.id_turno,
        "fecha": str(turno.fecha_de_turno or "2026-01-01"),
        "hora_inicio": str(turno.hora_inicio_real or turno.hora_inicio_estimada or "08:00")[:5],
        "hora_fin": str(turno.hora_fin_real or turno.hora_fin_estimada or "10:30")[:5],
        "finca": turno.finca.nombre_finca if turno.finca else "Predio Agrícola",
        "municipio": turno.finca.ubicacion_municipio if turno.finca else "Yopal",
        "departamento": turno.finca.departamento if turno.finca else "Casanare",
        "hectareas": str(turno.finca.hectareas or 10.0) if turno.finca else "10.0",
        "coordenadas": f"{turno.finca.latitud or '5.337'}, {turno.finca.longitud or '-72.395'}" if turno.finca else "5.337, -72.395",
        "cliente": f"{turno.finca.cliente.nombre} {turno.finca.cliente.apellido_1 or ''}".strip() if (turno.finca and turno.finca.cliente) else "Cliente Flymetrics",
        "cliente_nit": turno.finca.cliente.numero_documento if (turno.finca and turno.finca.cliente) else "N/A",
        "cliente_telefono": turno.finca.cliente.telefono if (turno.finca and turno.finca.cliente) else "N/A",
        "piloto": f"{turno.tecnico.nombre} {turno.tecnico.apellido_1 or ''}".strip() if turno.tecnico else "Piloto Certificado",
        "piloto_cert": getattr(turno.tecnico, "certificacion", "RPAS-A-102030") if turno.tecnico else "RPAS-A-102030",
        "drone": f"{turno.drone.modelo} ({turno.drone.numero_serie or 'SN-DJI-T40'})" if turno.drone else "DJI Agras T40",
        "servicio": turno.servicio.nombre_servicio if turno.servicio else "Fumigación de Precisión",
        "insumos_litros": str(reporte.insumos_litros_aplicados or 15.0) if reporte else "15.0",
        "agua_litros": str(reporte.agua_litros or 120.0) if reporte else "120.0",
        "baterias": str(reporte.baterias_utilizadas or 4) if reporte else "4",
        "observaciones": reporte.observaciones_campo if reporte else "Operación ejecutada bajo parámetros RAC-100.",
        "recomendaciones": reporte.recomendaciones_agronomicas if reporte else "Monitorear cobertura foliar a las 48 horas.",
        "sharepoint_url": reporte.url_entregable_drive if reporte else (turno.finca.cliente.link_sharepoint if (turno.finca and turno.finca.cliente) else None)
    }

    docx_buffer = generate_bitacora_docx(data)
    filename = f"Informe_Vuelo_Turno_{id_turno}.docx"

    return Response(
        content=docx_buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff"
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# INFORMES DE VUELO Y ENTREGABLES EJECUTIVOS (ANTERIORMENTE BITÁCORA)
# ──────────────────────────────────────────────────────────────────────────────
from pydantic import BaseModel
from typing import Optional

class SubirInformeEjecutivoRequest(BaseModel):
    id_turno: int
    sharepoint_url: str

class UpdateReporteVueloRequest(BaseModel):
    insumos_litros_aplicados: Optional[float] = 0.0
    agua_litros: Optional[float] = 0.0
    baterias_utilizadas: Optional[int] = 1
    cumple_rac100: Optional[int] = 1
    url_entregable_drive: Optional[str] = None
    recomendaciones_agronomicas: Optional[str] = None
    observaciones_campo: Optional[str] = None
    motivo_retraso: Optional[str] = None

informes_router = APIRouter(prefix="", tags=["Reportes de Vuelo e Informes"])

@informes_router.get("/reportes-vuelo")
def list_reportes_vuelo(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Consulta la lista de reportes de vuelo técnicos y telemetría operativa."""
    from app.infrastructure.database.models.models import ReporteVueloModel, AgendaModel, FincaModel, ClienteModel, TecnicoModel
    query = db.query(ReporteVueloModel).join(AgendaModel)

    if current_user.rol == "cliente":
        query = query.join(FincaModel, AgendaModel.id_finca == FincaModel.id_finca)\
                     .join(ClienteModel, FincaModel.id_cliente == ClienteModel.id_cliente)\
                     .filter(ClienteModel.id_usuario == current_user.id_usuarios)
    elif current_user.rol == "tecnico":
        tec = db.query(TecnicoModel).filter(TecnicoModel.id_usuario == current_user.id_usuarios).first()
        if tec:
            query = query.filter(
                (AgendaModel.id_tecnico == tec.id_tecnico) |
                (AgendaModel.tecnicos_adicionales.like(f"%{tec.id_tecnico}%"))
            )
        else:
            return success_response(message="Reportes de vuelo obtenidos", data=[])

    reportes = query.all()
    data = []
    for r in reportes:
        t = r.turno
        f = t.finca if t else None
        c = f.cliente if f else None
        tec = t.tecnico if t else None
        s = t.servicio if t else None

        data.append({
            "id": r.id_reporte,
            "id_reporte": r.id_reporte,
            "id_turno": r.id_turno,
            "insumos_litros_aplicados": float(r.insumos_litros_aplicados or 0.0),
            "agua_litros": float(r.agua_litros or 0.0),
            "baterias_utilizadas": int(r.baterias_utilizadas or 1),
            "cumple_rac100": int(r.cumple_rac100 if r.cumple_rac100 is not None else 1),
            "observaciones_campo": r.observaciones_campo or "Operación ejecutada bajo parámetros técnicos.",
            "recomendaciones_agronomicas": r.recomendaciones_agronomicas or "",
            "url_entregable_drive": r.url_entregable_drive or "",
            "fecha": str(t.fecha_de_turno) if (t and t.fecha_de_turno) else "",
            "cliente": f"{c.nombre} {c.apellido_1 or ''}".strip() if c else "Cliente Flymetrics",
            "finca": f.nombre_finca if f else "Predio Agrícola",
            "tecnico": f"{tec.nombre} {tec.apellido_1 or ''}".strip() if tec else "Piloto Técnico",
            "servicio": s.nombre_servicio if s else "Vuelo Agrícola",
            "duracion_min": 45,
            "area_ha": float(f.hectareas or 10.0) if (f and f.hectareas) else 10.0
        })

    return success_response(message="Reportes de vuelo obtenidos", data=data)

@informes_router.get("/reportes-vuelo/{id_turno}")
def get_reporte_vuelo_por_turno(
    id_turno: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Obtiene el reporte de vuelo específico para un turno operativo."""
    from app.infrastructure.database.models.models import ReporteVueloModel, AgendaModel
    reporte = db.query(ReporteVueloModel).filter(ReporteVueloModel.id_turno == id_turno).first()
    if not reporte:
        turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
        if not turno:
            from app.shared.exceptions.exceptions import NotFoundException
            raise NotFoundException(f"Turno #{id_turno} no encontrado")
        return success_response(message="Detalle de reporte de vuelo", data={
            "id_reporte": 0,
            "id_turno": id_turno,
            "insumos_litros_aplicados": 0.0,
            "agua_litros": 0.0,
            "baterias_utilizadas": 1,
            "cumple_rac100": 1,
            "observaciones_campo": turno.observaciones_servicio or "",
            "recomendaciones_agronomicas": "",
            "url_entregable_drive": ""
        })

    return success_response(message="Detalle de reporte de vuelo", data={
        "id_reporte": reporte.id_reporte,
        "id_turno": reporte.id_turno,
        "insumos_litros_aplicados": float(reporte.insumos_litros_aplicados or 0.0),
        "agua_litros": float(reporte.agua_litros or 0.0),
        "baterias_utilizadas": int(reporte.baterias_utilizadas or 1),
        "cumple_rac100": int(reporte.cumple_rac100 if reporte.cumple_rac100 is not None else 1),
        "observaciones_campo": reporte.observaciones_campo or "",
        "recomendaciones_agronomicas": reporte.recomendaciones_agronomicas or "",
        "url_entregable_drive": reporte.url_entregable_drive or ""
    })

@informes_router.put("/reportes-vuelo/{id_turno}")
def update_reporte_vuelo(
    id_turno: int,
    req: UpdateReporteVueloRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """Actualiza telemetría y recomendaciones agronómicas de un reporte de vuelo."""
    from app.infrastructure.database.models.models import ReporteVueloModel, AgendaModel, EntregableModel
    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == id_turno).first()
    if not turno:
        from app.shared.exceptions.exceptions import NotFoundException
        raise NotFoundException(f"Turno #{id_turno} no encontrado")

    reporte = db.query(ReporteVueloModel).filter(ReporteVueloModel.id_turno == id_turno).first()
    if not reporte:
        reporte = ReporteVueloModel(
            id_turno=id_turno,
            insumos_litros_aplicados=req.insumos_litros_aplicados or 0.0,
            agua_litros=req.agua_litros or 0.0,
            baterias_utilizadas=req.baterias_utilizadas or 1,
            cumple_rac100=req.cumple_rac100 if req.cumple_rac100 is not None else 1,
            observaciones_campo=req.observaciones_campo or "",
            recomendaciones_agronomicas=req.recomendaciones_agronomicas or "",
            url_entregable_drive=req.url_entregable_drive or ""
        )
        db.add(reporte)
    else:
        if req.insumos_litros_aplicados is not None:
            reporte.insumos_litros_aplicados = req.insumos_litros_aplicados
        if req.agua_litros is not None:
            reporte.agua_litros = req.agua_litros
        if req.baterias_utilizadas is not None:
            reporte.baterias_utilizadas = req.baterias_utilizadas
        if req.cumple_rac100 is not None:
            reporte.cumple_rac100 = req.cumple_rac100
        if req.observaciones_campo is not None:
            reporte.observaciones_campo = req.observaciones_campo
        if req.recomendaciones_agronomicas is not None:
            reporte.recomendaciones_agronomicas = req.recomendaciones_agronomicas
        if req.url_entregable_drive is not None:
            reporte.url_entregable_drive = req.url_entregable_drive

    if req.motivo_retraso:
        turno.retraso_justificacion = req.motivo_retraso

    if req.url_entregable_drive:
        # Registrar entregable si no existe ya
        existente = db.query(EntregableModel).filter(
            EntregableModel.id_turno == id_turno,
            EntregableModel.url_archivo == req.url_entregable_drive
        ).first()
        if not existente:
            ent = EntregableModel(
                id_turno=id_turno,
                tipo_archivo="Carpeta Google Drive (Mapas / Ortofotos)",
                url_archivo=req.url_entregable_drive,
                nombre_archivo=f"Entrega_Drive_Turno_{id_turno}.url"
            )
            db.add(ent)

    db.commit()
    db.refresh(reporte)

    return success_response(
        message="Reporte de vuelo actualizado exitosamente",
        data={"id_reporte": reporte.id_reporte, "id_turno": reporte.id_turno}
    )

@informes_router.post("/tecnico/subir-informe-ejecutivo")
@informes_router.post("/tecnico/subir-bitacora")
def subir_informe_ejecutivo_tecnico(
    req: SubirInformeEjecutivoRequest,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(admin_or_tech)
):
    """Vincula el enlace de SharePoint / Drive del informe ejecutivo y finaliza el servicio marcando el turno como Completado."""
    from app.infrastructure.database.models.models import AgendaModel, ReporteVueloModel, EntregableModel
    from app.shared.exceptions.exceptions import NotFoundException
    from app.shared.utils.email_service import EmailService

    turno = db.query(AgendaModel).filter(AgendaModel.id_turno == req.id_turno).first()
    if not turno:
        raise NotFoundException(f"Turno #{req.id_turno} no encontrado")

    est_lower = str(turno.estado or "").lower()
    if not (est_lower.startswith("complet") or est_lower.startswith("hecho") or est_lower.startswith("finaliz")):
        from app.shared.exceptions.exceptions import ConflictException
        raise ConflictException(
            f"El vuelo #{req.id_turno} se encuentra en estado '{turno.estado}'. "
            "Para finalizar el servicio con el informe en SharePoint, primero debes registrar la bitácora técnica y completar el servicio."
        )

    from datetime import datetime
    # Marcar turno formalmente como Finalizado
    turno.estado = "Finalizado"
    if not turno.hora_fin_real:
        turno.hora_fin_real = datetime.now().time()

    # Actualizar o crear ReporteVueloModel
    reporte = db.query(ReporteVueloModel).filter(ReporteVueloModel.id_turno == req.id_turno).first()
    if not reporte:
        reporte = ReporteVueloModel(
            id_turno=req.id_turno,
            insumos_litros_aplicados=0.0,
            agua_litros=0.0,
            baterias_utilizadas=1,
            cumple_rac100=1,
            observaciones_campo="Servicio finalizado con informe ejecutivo SharePoint.",
            url_entregable_drive=req.sharepoint_url
        )
        db.add(reporte)
    else:
        reporte.url_entregable_drive = req.sharepoint_url

    # Registrar o actualizar entregable oficial
    entregable = db.query(EntregableModel).filter(
        EntregableModel.id_turno == req.id_turno,
        EntregableModel.tipo_archivo == "Informe Ejecutivo (SharePoint / Nube)"
    ).first()
    if entregable:
        entregable.url_archivo = req.sharepoint_url
        entregable.nombre_archivo = f"Informe_Ejecutivo_Turno_{req.id_turno}.url"
    else:
        entregable = EntregableModel(
            id_turno=req.id_turno,
            tipo_archivo="Informe Ejecutivo (SharePoint / Nube)",
            url_archivo=req.sharepoint_url,
            nombre_archivo=f"Informe_Ejecutivo_Turno_{req.id_turno}.url"
        )
        db.add(entregable)

    # Sincronizar automáticamente el enlace raíz de SharePoint del cliente si aún no está asignado o para mantenerlo actualizado
    if turno.finca and turno.finca.cliente:
        if not turno.finca.cliente.link_sharepoint or turno.finca.cliente.link_sharepoint.strip() == "":
            turno.finca.cliente.link_sharepoint = req.sharepoint_url

    db.commit()

    # Enviar notificación por correo de forma asíncrona y segura
    try:
        if turno.finca and turno.finca.cliente:
            c = turno.finca.cliente
            dest = c.usuario.email if c.usuario else None
            if dest:
                import threading
                def _send_mail():
                    try:
                        EmailService.send_executive_report_ready(
                            to_email=dest,
                            nombre_cliente=f"{c.nombre} {c.apellido_1 or ''}".strip(),
                            id_turno=turno.id_turno,
                            servicio=turno.servicio.nombre_servicio if turno.servicio else "Vuelo Agrícola Especializado",
                            finca=turno.finca.nombre_finca,
                            url_informe=req.sharepoint_url,
                            tipo_informe="Informe Técnico Ejecutivo (SharePoint)"
                        )
                    except Exception as mail_err:
                        print(f"[SUBIR INFORME EMAIL ERROR] {mail_err}")
                threading.Thread(target=_send_mail, daemon=True).start()
    except Exception as mail_err:
        print(f"[SUBIR INFORME EMAIL THREAD ERROR] {mail_err}")

    return success_response(
        message="Informe ejecutivo guardado y servicio marcado como Finalizado exitosamente",
        data={
            "id_turno": req.id_turno,
            "estado": "Finalizado",
            "sharepoint_url": req.sharepoint_url
        }
    )

@informes_router.get("/bitacora/{id_turno}/descargar-docx")
def alias_descargar_reporte_docx(
    id_turno: int,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(get_current_user)
):
    """Alias retrocompatible para descargar el informe Word de vuelo."""
    return descargar_reporte_docx(id_turno=id_turno, db=db, current_user=current_user)

