import re
from typing import Tuple, Optional
from decimal import Decimal

# Coordenadas centroides de municipios y regiones colombianas comunes
MUNICIPIOS_CENTROIDES = {
    "yopal": (5.337750, -72.395870),
    "casanare": (5.337750, -72.395870),
    "neiva": (2.925406, -75.259660),
    "huila": (2.925406, -75.259660),
    "villavicencio": (4.142000, -73.626600),
    "meta": (4.142000, -73.626600),
    "fusagasuga": (4.341800, -74.364400),
    "fusagasugá": (4.341800, -74.364400),
    "bogota": (4.711000, -74.072100),
    "bogotá": (4.711000, -74.072100),
    "cundinamarca": (4.711000, -74.072100),
    "montelibano": (7.979000, -75.417800),
    "montelíbano": (7.979000, -75.417800),
    "cordoba": (8.750000, -75.880000),
    "córdoba": (8.750000, -75.880000),
    "barranquilla": (10.968500, -74.781300),
    "atlantico": (10.968500, -74.781300),
    "atlántico": (10.968500, -74.781300),
    "cali": (3.451600, -76.532000),
    "medellin": (6.244200, -75.581200),
    "medellín": (6.244200, -75.581200),
    "bucaramanga": (7.119300, -73.122700),
    "ibague": (4.438900, -75.232200),
    "ibagué": (4.438900, -75.232200),
    "pereira": (4.813300, -75.696100),
    "tamara": (5.833300, -72.166700),
    "támara": (5.833300, -72.166700),
    "aguazul": (5.172800, -72.548100),
    "tauramena": (5.016700, -72.750000),
    "montería": (8.750000, -75.880000),
    "monteria": (8.750000, -75.880000)
}

def parse_and_normalize_maps(raw_val: Optional[str], municipio_fallback: Optional[str] = None) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """
    Normaliza enlaces y coordenadas de Google Maps de forma robusta.
    Retorna (clean_url, latitud, longitud).
    1. Si val contiene coordenadas directas (ej. '2.946644, -75.254211', '4.1420,-73.6266', '@2.946644,-75.254211', 'q=2.946644,-75.254211'):
       extrae lat y lng, y genera 'https://www.google.com/maps?q=lat,lng'.
    2. Si val contiene un link de Maps (ej. 'https://maps.app.goo.gl/...', 'https://goo.gl/maps/...', 'https://www.google.com/maps...'):
       extrae y limpia el enlace URL directamente.
    3. Si val es una URL genérica (http/https): retorna la URL limpia.
    4. Si val está vacío o no es geográfico pero se conoce el municipio, asigna las coordenadas centroidales del municipio.
    """
    if not raw_val or str(raw_val).strip() == "":
        if municipio_fallback:
            m_key = str(municipio_fallback).strip().lower()
            if m_key in MUNICIPIOS_CENTROIDES:
                lat, lng = MUNICIPIOS_CENTROIDES[m_key]
                return f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}", lat, lng
        return None, None, None

    s = str(raw_val).strip().rstrip('])>,.;:\'\"')
    s_lower = s.lower()
    if s_lower in ['none', 'null', 'undefined', 'n/a', 'colombia', 'sin registrar', 'finca', '']:
        if municipio_fallback:
            m_key = str(municipio_fallback).strip().lower()
            if m_key in MUNICIPIOS_CENTROIDES:
                lat, lng = MUNICIPIOS_CENTROIDES[m_key]
                return f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}", lat, lng
        return None, None, None

    # 1. Buscar coordenadas decimales en el string (ej: 2.946644, -75.254211 o q=2.946644,-75.254211)
    coord_match = re.search(r'([-+]?\d{1,3}\.\d+)[,\s]+([-+]?\d{1,3}\.\d+)', s)
    if coord_match:
        try:
            lat = float(coord_match.group(1))
            lng = float(coord_match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                norm_url = f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}"
                return norm_url, lat, lng
        except Exception:
            pass

    # 2. Si es una URL de Google Maps o link web
    if any(domain in s for domain in ["maps.app.goo.gl", "goo.gl/maps", "google.com/maps", "maps.google.com", "google.com", "maps"]):
        m_url = re.search(r'https?://[^\s\n\r"\'<>\]\)]+', s)
        clean_url = m_url.group(0).strip().rstrip('])>,.;:\'\"') if m_url else s
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = "https://" + clean_url
        return clean_url, None, None

    # 3. Si empieza con http o https
    if s.startswith("http://") or s.startswith("https://"):
        return s, None, None

    # 4. Fallback por nombre de municipio presente en el texto
    for m_name, (lat, lng) in MUNICIPIOS_CENTROIDES.items():
        if m_name in s_lower:
            return f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}", lat, lng

    if municipio_fallback:
        m_key = str(municipio_fallback).strip().lower()
        if m_key in MUNICIPIOS_CENTROIDES:
            lat, lng = MUNICIPIOS_CENTROIDES[m_key]
            return f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}", lat, lng

    return s, None, None
