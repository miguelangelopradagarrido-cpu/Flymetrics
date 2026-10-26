import os
import json
import logging
from datetime import datetime, date, time, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger("uvicorn")

class MicrosoftCalendarService:
    """
    Servicio de integración con el ecosistema de Microsoft (Outlook / Hotmail / Office 365 / Microsoft Graph).
    Permite:
    1. Generar eventos estructurados iCalendar (.ics) RFC 5545 compatibles con Microsoft Outlook.
    2. Enviar invitaciones automáticas con actualización (REQUEST/CANCEL) directamente al buzón Microsoft del técnico.
    3. Soporte para Microsoft Graph API REST (/me/events o /users/{id}/events) vía OAuth2 si están configurados
       MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET y MICROSOFT_TENANT_ID.
    """

    @staticmethod
    def is_graph_api_configured() -> bool:
        client_id = os.getenv("MICROSOFT_CLIENT_ID", "")
        client_secret = os.getenv("MICROSOFT_CLIENT_SECRET", "")
        tenant_id = os.getenv("MICROSOFT_TENANT_ID", "")
        return bool(client_id and client_secret and tenant_id)

    @staticmethod
    def generate_ics_content(
        uid: str,
        summary: str,
        description: str,
        location: str,
        start_dt: datetime,
        end_dt: datetime,
        organizer_email: str = "operaciones@flymetrics.com.co",
        organizer_name: str = "Flymetrics Operaciones",
        attendee_email: Optional[str] = None,
        attendee_name: Optional[str] = None,
        method: str = "REQUEST",
        sequence: int = 0
    ) -> str:
        """
        Genera la estructura estándar RFC 5545 iCalendar que Microsoft Outlook,
        Hotmail y Teams reconocen para agregar el evento directamente en un clic o de forma automática.
        """
        fmt = "%Y%m%dT%H%M%SZ"
        dtstamp = datetime.utcnow().strftime(fmt)
        dtstart = start_dt.strftime(fmt)
        dtend = end_dt.strftime(fmt)

        # Sanitizar saltos de línea para descripción iCal
        clean_desc = description.replace("\r\n", "\\n").replace("\n", "\\n").replace(",", "\\,")

        attendee_line = ""
        if attendee_email:
            att_name = attendee_name or attendee_email
            attendee_line = f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN={att_name}:mailto:{attendee_email}\n"

        ics = (
            "BEGIN:VCALENDAR\n"
            "PRODID:-//Flymetrics S.A.S.//Operaciones Dron v1.0//ES\n"
            "VERSION:2.0\n"
            "CALSCALE:GREGORIAN\n"
            f"METHOD:{method}\n"
            "BEGIN:VEVENT\n"
            f"UID:{uid}@flymetrics.co\n"
            f"DTSTAMP:{dtstamp}\n"
            f"DTSTART:{dtstart}\n"
            f"DTEND:{dtend}\n"
            f"SEQUENCE:{sequence}\n"
            "STATUS:CONFIRMED\n"
            f"SUMMARY:{summary}\n"
            f"LOCATION:{location}\n"
            f"DESCRIPTION:{clean_desc}\n"
            f"ORGANIZER;CN={organizer_name}:mailto:{organizer_email}\n"
            f"{attendee_line}"
            "CLASS:PUBLIC\n"
            "TRANSP:OPAQUE\n"
            "BEGIN:VALARM\n"
            "TRIGGER:-PT2H\n"
            "ACTION:DISPLAY\n"
            "DESCRIPTION:Recordatorio de Vuelo Operativo Flymetrics (2 Horas Antes)\n"
            "END:VALARM\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        return ics

    @classmethod
    def sync_technician_calendar(
        cls,
        tecnico_email: str,
        tecnico_nombre: str,
        id_turno: int,
        servicio: str,
        finca: str,
        municipio: str,
        departamento: str,
        fecha_str: str,
        hora_str: str,
        cliente_nombre: str,
        cliente_tel: Optional[str] = None,
        hectareas: Optional[float] = None,
        cultivo: Optional[str] = None,
        maps_url: Optional[str] = None,
        observaciones: Optional[str] = None,
        tarifa: Optional[float] = None,
        dron: Optional[str] = None,
        cliente_email: Optional[str] = None,
        is_reschedule: bool = False
    ) -> Dict[str, Any]:
        """
        Crea o actualiza el evento en el calendario de Microsoft del técnico:
        1. Formatea la información puntual y separada (con link de ubicación GPS y precio).
        2. Genera el payload iCalendar (.ics).
        3. Si Graph API está disponible, sincroniza via REST. Si no, anexa la invitación al correo técnico.
        """
        tarifa_str = "Cotización Estándar"
        if tarifa is not None:
            try:
                val_flt = float(tarifa)
                if val_flt == 0.0:
                    tarifa_str = "$0 COP (Demostración Gratuita Sin Costo)"
                else:
                    tarifa_str = f"${val_flt:,.0f} COP"
            except Exception:
                tarifa_str = f"${tarifa}"
        try:
            # Parsear fecha y hora
            parts_f = [int(p) for p in fecha_str.strip()[:10].split("-")]
            parts_h = [int(p) for p in (hora_str or "08:00").strip()[:5].split(":")]
            start_dt = datetime(parts_f[0], parts_f[1], parts_f[2], parts_h[0], parts_h[1])
            ha_dur = min(4.0, max(1.0, round(float(hectareas or 10.0) / 5.0, 1)))
            end_dt = start_dt + timedelta(hours=ha_dur)
        except Exception:
            start_dt = datetime.now() + timedelta(days=1)
            end_dt = start_dt + timedelta(hours=2)

        # Campos puntuales y claros
        summary = f"Misión de Vuelo #{id_turno} — {servicio} ({finca})"
        location = f"{finca}, {municipio}, {departamento}"
        maps_link = maps_url or f"https://www.google.com/maps/search/?api=1&query={municipio}+{departamento}"

        drone_str = dron or "DJI AGRAS T40 / Dron Agrícola de Alta Capacidad"
        dur_mins = int(ha_dur * 60)

        # Descripción estructurada y limpia según indicaciones
        description_lines = [
            f"==================================================",
            f"   MISIÓN OPERATIVA FLYMETRICS — RADICADO #{id_turno}",
            f"==================================================",
            f"• Servicio / Misión: {servicio}",
            f"• Estado: {'REAGENDADO' if is_reschedule else 'PROGRAMADO / CONFIRMADO'}",
            "",
            "DATOS DEL CLIENTE:",
            f"• Nombre del Cliente: {cliente_nombre}",
            f"• Teléfono de Contacto: {cliente_tel or 'No registrado'}",
            f"• Correo Electrónico: {cliente_email or 'No registrado'}",
            "",
            "DATOS DEL PREDIO Y LOCALIZACIÓN:",
            f"• Finca / Predio: {finca}",
            f"• Número de Teléfono del Encargado de la Finca: {cliente_tel or 'Mismo número del cliente'}",
            f"• Municipio y Departamento: {municipio}, {departamento}",
            f"• Ubicación GPS (Ruta Google Maps): {maps_link}",
            f"• Área a Intervenir: {hectareas or 'N/A'} Hectáreas",
            f"• Cultivo: {cultivo or 'No reportado'}",
            "",
            "DETALLES COMERCIALES:",
            f"• Tarifa / Valor Facturado: {tarifa_str}",
            "",
            "RECOMENDACIÓN DEL CLIENTE / OBSERVACIONES:",
            f"• {observaciones or 'Sin recomendaciones especiales reportadas por el cliente.'}",
            "",
            f"• Piloto Asignado: {tecnico_nombre} ({tecnico_email})"
        ]

        description = "\n".join(description_lines)
        uid = f"flymetrics_turno_{id_turno}"
        sequence = 1 if is_reschedule else 0

        ics_payload = cls.generate_ics_content(
            uid=uid,
            summary=summary,
            description=description,
            location=location,
            start_dt=start_dt,
            end_dt=end_dt,
            attendee_email=tecnico_email,
            attendee_name=tecnico_nombre,
            method="REQUEST",
            sequence=sequence
        )

        logger.info(f"[MICROSOFT CALENDAR SYNC] Evento #{id_turno} generado para el técnico {tecnico_email}")

        res = {
            "success": True,
            "uid": uid,
            "ics_content": ics_payload,
            "summary": summary,
            "description": description,
            "location": location,
            "maps_link": maps_link,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "method": "REQUEST"
        }

        if cls.is_graph_api_configured():
            cls._graph_api_sync_event(tecnico_email=tecnico_email, event_data=res)

        return res

    @classmethod
    def cancel_technician_calendar(
        cls,
        tecnico_email: str,
        tecnico_nombre: str,
        id_turno: int,
        servicio: str,
        finca: str,
        municipio: Optional[str] = None,
        departamento: Optional[str] = None,
        fecha_str: Optional[str] = None,
        hora_str: Optional[str] = None,
        motivo: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera el payload iCalendar RFC 5545 con METHOD: CANCEL y STATUS: CANCELLED.
        Al enviarlo por correo o sincronizarlo, Microsoft Outlook, Hotmail y Teams
        eliminan o tachan automáticamente el evento de la agenda del técnico.
        """
        try:
            parts_f = [int(p) for p in (fecha_str or "2026-01-01").strip()[:10].split("-")]
            parts_h = [int(p) for p in (hora_str or "08:00").strip()[:5].split(":")]
            start_dt = datetime(parts_f[0], parts_f[1], parts_f[2], parts_h[0], parts_h[1])
            end_dt = start_dt + timedelta(hours=2)
        except Exception:
            start_dt = datetime.now()
            end_dt = start_dt + timedelta(hours=2)

        summary = f"[CANCELADO] Misión de Vuelo #{id_turno} — {servicio} ({finca})"
        location = f"{finca}, {municipio or ''}, {departamento or ''}".strip(", ")
        description = (
            f"CANCELACIÓN DE MISIÓN #{id_turno}\n"
            f"--------------------------------------------------\n"
            f"• Servicio: {servicio}\n"
            f"• Predio: {finca}\n"
            f"• Motivo: {motivo or 'Servicio cancelado desde administración'}\n"
            f"• Estado: CANCELADO / LIBERADO DE AGENDA"
        )
        uid = f"flymetrics_turno_{id_turno}"

        ics_payload = cls.generate_ics_content(
            uid=uid,
            summary=summary,
            description=description,
            location=location,
            start_dt=start_dt,
            end_dt=end_dt,
            attendee_email=tecnico_email,
            attendee_name=tecnico_nombre,
            method="CANCEL",
            sequence=2
        )

        # Si Microsoft Graph API está configurado en producción, sincronizar cancelación directamente
        if cls.is_graph_api_configured():
            cls._graph_api_delete_event(tecnico_email=tecnico_email, uid=uid)

        logger.info(f"[MICROSOFT CALENDAR CANCEL] Cancelación generada para el técnico {tecnico_email} en turno #{id_turno}")
        return {
            "success": True,
            "uid": uid,
            "ics_content": ics_payload,
            "method": "CANCEL"
        }

    @classmethod
    def _graph_api_sync_event(cls, tecnico_email: str, event_data: dict) -> bool:
        """
        Sincroniza directamente con Microsoft Graph API (/v1.0/users/{user-email}/events)
        cuando las credenciales Azure Entra ID están presentes en .env.
        """
        try:
            import urllib.request
            import urllib.parse

            client_id = os.getenv("MICROSOFT_CLIENT_ID", "")
            client_secret = os.getenv("MICROSOFT_CLIENT_SECRET", "")
            tenant_id = os.getenv("MICROSOFT_TENANT_ID", "")
            if not (client_id and client_secret and tenant_id):
                return False

            # 1. Obtener Token OAuth2 de Microsoft
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            token_data = urllib.parse.urlencode({
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            }).encode("utf-8")

            req = urllib.request.Request(token_url, data=token_data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                token_resp = json.loads(resp.read().decode("utf-8"))
                access_token = token_resp.get("access_token")

            if not access_token:
                return False

            # 2. Enviar evento al calendario del técnico vía Graph API (Crear o Actualizar si ya existe)
            graph_url = f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(tecnico_email)}/events"
            event_body = {
                "subject": event_data.get("summary"),
                "body": {
                    "contentType": "Text",
                    "content": event_data.get("description", "")
                },
                "start": {
                    "dateTime": event_data.get("start"),
                    "timeZone": "SA Pacific Standard Time"
                },
                "end": {
                    "dateTime": event_data.get("end"),
                    "timeZone": "SA Pacific Standard Time"
                },
                "location": {
                    "displayName": event_data.get("location")
                }
            }

            # Si es reprogramación o ya existe, buscar si ya hay un evento con ese transactionId
            uid = event_data.get("uid")
            existing_event_id = None
            try:
                search_url = f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(tecnico_email)}/events?$filter=transactionId eq '{uid}'"
                s_req = urllib.request.Request(search_url, headers={"Authorization": f"Bearer {access_token}"})
                with urllib.request.urlopen(s_req, timeout=5) as s_resp:
                    s_data = json.loads(s_resp.read().decode())
                    if s_data.get("value") and len(s_data["value"]) > 0:
                        existing_event_id = s_data["value"][0]["id"]
            except Exception:
                pass

            if existing_event_id:
                # Actualizar el evento existente (PATCH)
                update_url = f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(tecnico_email)}/events/{existing_event_id}"
                graph_req = urllib.request.Request(
                    update_url,
                    data=json.dumps(event_body).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    method="PATCH"
                )
            else:
                event_body["transactionId"] = uid
                graph_req = urllib.request.Request(
                    graph_url,
                    data=json.dumps(event_body).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )

            with urllib.request.urlopen(graph_req, timeout=10) as g_resp:
                if g_resp.status in (200, 201):
                    action_str = "actualizado" if existing_event_id else "cargado"
                    logger.info(f"[GRAPH API SYNC SUCCESS] Evento #{uid} {action_str} en calendario de {tecnico_email}")
                    return True
        except urllib.error.HTTPError as he:
            # Si Microsoft devuelve ErrorDuplicateTransactionId, actualizar directamente
            try:
                err_data = json.loads(he.read().decode())
                exist_id = err_data.get("@event.existingEventId")
                if exist_id and access_token:
                    patch_url = f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(tecnico_email)}/events/{exist_id}"
                    p_req = urllib.request.Request(
                        patch_url,
                        data=json.dumps(event_body).encode("utf-8"),
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        },
                        method="PATCH"
                    )
                    with urllib.request.urlopen(p_req, timeout=10) as p_resp:
                        if p_resp.status in (200, 201):
                            logger.info(f"[GRAPH API SYNC SUCCESS] Evento #{event_data.get('uid')} actualizado en {tecnico_email}")
                            return True
            except Exception:
                pass
            logger.warning(f"[GRAPH API SYNC WARNING] Graph API error ({he.code}). Utilizando transporte iCalendar nativo.")
        except Exception as e:
            logger.warning(f"[GRAPH API SYNC WARNING] Graph API omitido ({e}). Utilizando transporte iCalendar nativo.")
        return False

    @classmethod
    def _graph_api_delete_event(cls, tecnico_email: str, uid: str) -> bool:
        """Elimina o cancela un evento por TransactionId en Microsoft Graph API."""
        try:
            import urllib.request
            import urllib.parse
            client_id = os.getenv("MICROSOFT_CLIENT_ID", "")
            client_secret = os.getenv("MICROSOFT_CLIENT_SECRET", "")
            tenant_id = os.getenv("MICROSOFT_TENANT_ID", "")
            if not (client_id and client_secret and tenant_id):
                return False

            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            token_data = urllib.parse.urlencode({
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            }).encode("utf-8")
            req = urllib.request.Request(token_url, data=token_data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                access_token = json.loads(resp.read().decode()).get("access_token")

            if not access_token:
                return False

            search_url = f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(tecnico_email)}/events?$filter=transactionId eq '{uid}'"
            s_req = urllib.request.Request(search_url, headers={"Authorization": f"Bearer {access_token}"})
            with urllib.request.urlopen(s_req, timeout=5) as s_resp:
                s_data = json.loads(s_resp.read().decode())
                if s_data.get("value") and len(s_data["value"]) > 0:
                    for ev in s_data["value"]:
                        del_url = f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(tecnico_email)}/events/{ev['id']}"
                        d_req = urllib.request.Request(del_url, headers={"Authorization": f"Bearer {access_token}"}, method="DELETE")
                        urllib.request.urlopen(d_req, timeout=5)
                    logger.info(f"[GRAPH API CANCEL SUCCESS] Evento {uid} eliminado de calendario de {tecnico_email}")
                    return True
        except Exception as e:
            logger.warning(f"[GRAPH API CANCEL WARNING] {e}")
        return False
