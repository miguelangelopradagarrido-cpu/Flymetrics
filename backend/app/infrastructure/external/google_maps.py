import math
from typing import Dict, Any

class GoogleMapsService:
    # Coordenadas del Centro de Operaciones en Neiva, Huila
    NEIVA_LAT = 2.9273
    NEIVA_LON = -75.28189
    
    @classmethod
    def calculate_distance(cls, lat: float, lon: float) -> float:
        """Calcula la distancia en km usando la fórmula de Haversine."""
        # Convertir a radianes
        lat1, lon1 = math.radians(cls.NEIVA_LAT), math.radians(cls.NEIVA_LON)
        lat2, lon2 = math.radians(lat), math.radians(lon)
        
        # Diferencias
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Haversine
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radio de la tierra en km
        
        return round(c * r, 2)

    @classmethod
    def get_quote_data(cls, lat: float, lon: float) -> Dict[str, Any]:
        """Simula respuesta de Google Maps API y calcula costo logístico."""
        dist_km = cls.calculate_distance(lat, lon)
        
        # Velocidad promedio del vehículo en carreteras colombianas (ej: 40 km/h)
        duracion_estimada_horas = round(dist_km / 40.0, 2)
        if duracion_estimada_horas < 0.5:
            duracion_estimada_horas = 0.5
            
        # Costo logístico: gratis hasta 40km. Luego $2500 por km extra (ida y vuelta)
        costo_logistico = 0.0
        if dist_km > 40.0:
            distancia_adicional = dist_km - 40.0
            costo_logistico = round(distancia_adicional * 2500.0 * 2, 2) # Ida y vuelta
            
        return {
            "distancia_km": dist_km,
            "duracion_estimada_horas": duracion_estimada_horas,
            "costo_logistico": costo_logistico
        }
