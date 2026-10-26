import sys
import requests
import io

BASE_URL = "http://127.0.0.1:3000"

def test_publicidad_medios():
    print("--- 1. INICIANDO SESION COMO ADMIN ---")
    login_res = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": "admin@flymetrics.co", "contraseña": "Admin123456!"}
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(" Admin logueado exitosamente")

    print("\n--- 2. GET MEDIOS GLOBALES ---")
    mg_res = requests.get(f"{BASE_URL}/api/v1/publicidad/medios-globales")
    assert mg_res.status_code == 200, f"Error get medios: {mg_res.text}"
    mg_data = mg_res.json()["data"]
    print(" Medios globales actuales:", mg_data)
    cache_ctrl = mg_res.headers.get("Cache-Control", "")
    assert "no-cache" in cache_ctrl or "no-store" in cache_ctrl, f"Expected no-cache header, got: {cache_ctrl}"
    print(" Cache-Control en medios globales correcto:", cache_ctrl)

    print("\n--- 3. SUBIR ARCHIVO MULTIMEDIA DE PRUEBA (POST /api/v1/media/upload) ---")
    dummy_img_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    files = {"file": ("test_banner_promo.png", io.BytesIO(dummy_img_content), "image/png")}
    data = {"tipo": "imagen", "modulo": "publicidad"}
    upload_res = requests.post(f"{BASE_URL}/api/v1/media/upload", headers=headers, files=files, data=data)
    assert upload_res.status_code in [200, 201], f"Upload failed: {upload_res.text}"
    up_data = upload_res.json()["data"]
    uploaded_url = up_data["url"]
    uploaded_filename = up_data["filename"]
    print(f" Imagen subida exitosamente: {uploaded_url}")
    assert uploaded_url.startswith("/uploads/publicidad/images/"), f"Unexpected url format: {uploaded_url}"

    print("\n--- 4. VERIFICAR QUE LA IMAGEN SUBIDA SE SIRVE SIN CACHE AGRESIVO (Cache-Control: no-cache) ---")
    static_res = requests.get(f"{BASE_URL}{uploaded_url}")
    assert static_res.status_code == 200, f"Failed to get uploaded static file: {static_res.status_code}"
    static_cc = static_res.headers.get("Cache-Control", "")
    print(f" Header Cache-Control para {uploaded_url}: {static_cc}")
    assert "no-cache" in static_cc, f"Expected no-cache for uploads, got: {static_cc}"

    print("\n--- 5. ACTUALIZAR MEDIOS GLOBALES CON LA NUEVA IMAGEN ---")
    update_mg_res = requests.post(
        f"{BASE_URL}/api/v1/publicidad/medios-globales",
        headers=headers,
        json={"hero_video_url": "/video/hero.mp4", "mobile_poster_url": uploaded_url}
    )
    assert update_mg_res.status_code == 200, f"Failed updating medios globales: {update_mg_res.text}"
    print(" Medios globales guardados en BD exitosamente")

    mg_check = requests.get(f"{BASE_URL}/api/v1/publicidad/medios-globales?t=123456").json()["data"]
    assert mg_check["mobile_poster_url"] == uploaded_url, f"Expected {uploaded_url}, got {mg_check['mobile_poster_url']}"
    print(" Confirmado: GET /medios-globales retorna inmediatamente la imagen guardada")

    print("\n--- 6. VERIFICAR COLLAGE PUBLICITARIO ---")
    col_res = requests.get(f"{BASE_URL}/api/v1/publicidad/collage")
    assert col_res.status_code == 200
    col_items = col_res.json()["data"]
    print(f" Total items en collage: {len(col_items)}")
    for item in col_items:
        assert item["url_medio"].startswith("/") or item["url_medio"].startswith("http"), f"Invalid url_medio: {item['url_medio']}"
    print(" Todas las URLs del collage inician correctamente con / o http")

    print("\n--- 7. CREAR NUEVO ELEMENTO EN EL COLLAGE ---")
    nuevo_payload = {
        "seccion": "dashboard_cliente",
        "titulo": "Prueba Automatizada Publicidad",
        "subtitulo": "Monitoreo especial de cultivos con dron multiespectral",
        "tipo_medio": "imagen",
        "url_medio": uploaded_url,
        "badge": "Test Activo",
        "texto_boton": "Conoce Más",
        "url_accion": "#contacto",
        "orden": 99,
        "activo": True
    }
    create_res = requests.post(f"{BASE_URL}/api/v1/publicidad/admin/collage", headers=headers, json=nuevo_payload)
    assert create_res.status_code in [200, 201], f"Failed creating collage item: {create_res.text}"
    new_id = create_res.json()["data"]["id_publicidad"]
    print(f" Elemento de collage creado con ID: {new_id}")

    print("\n--- 8. ACTUALIZAR ELEMENTO EN EL COLLAGE ---")
    update_item_payload = {
        "titulo": "Prueba Publicidad Actualizada",
        "url_medio": uploaded_url
    }
    up_item_res = requests.put(f"{BASE_URL}/api/v1/publicidad/admin/collage/{new_id}", headers=headers, json=update_item_payload)
    assert up_item_res.status_code == 200, f"Failed updating collage item: {up_item_res.text}"
    print(f" Elemento #{new_id} actualizado exitosamente")

    print("\n--- 9. ELIMINAR ELEMENTO DE COLLAGE DE PRUEBA ---")
    del_res = requests.delete(f"{BASE_URL}/api/v1/publicidad/admin/collage/{new_id}", headers=headers)
    assert del_res.status_code == 200, f"Failed deleting collage item: {del_res.text}"
    print(f" Elemento #{new_id} eliminado exitosamente")

    print("\n--- 10. LIMPIAR MEDIOS GLOBALES Y ARCHIVO DE PRUEBA ---")
    requests.post(
        f"{BASE_URL}/api/v1/publicidad/medios-globales",
        headers=headers,
        json={"hero_video_url": "/video/hero.mp4", "mobile_poster_url": "/img/servicio_precision.jpg"}
    )
    del_media_res = requests.delete(f"{BASE_URL}/api/v1/media/{uploaded_filename}", headers=headers)
    print(f" Archivo de prueba físico limpiado: {del_media_res.status_code}")

    print("\n=======================================================")
    print(" PRUEBAS DE PUBLICIDAD Y MEDIOS: 100% EXITOSAS")
    print("=======================================================")

if __name__ == "__main__":
    test_publicidad_medios()
