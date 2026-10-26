import requests

BASE = "http://127.0.0.1:3000"
print("=============================================================")
print("      FLYMETRICS - AUDITORIA DE SEGURIDAD EN TIEMPO REAL     ")
print("=============================================================")

# 1. SQL Injection Test
sqli_payloads = ["' OR '1'='1", "admin' --", "' UNION SELECT null, null --"]
for p in sqli_payloads:
    res = requests.post(f"{BASE}/api/v1/auth/login", json={"email": p, "password": "password123"})
    status = "BLOQUEADO" if res.status_code in [400, 401, 422] else "ALERTA"
    print(f"[SQLi] Payload: {p[:18]:<20} -> Status: {res.status_code} [{status}]")

# 2. XSS Injection Test
xss_payload = "<script>alert('XSS')</script>"
res = requests.post(f"{BASE}/api/v1/auth/login", json={"email": f"{xss_payload}@test.com", "password": "test"})
status = "BLOQUEADO" if res.status_code in [400, 422, 401] else "ALERTA"
print(f"[XSS]  Payload script tag      -> Status: {res.status_code} [{status}]")

# 3. Path Traversal Test
res = requests.get(f"{BASE}/../../etc/passwd")
status = "SEGURO" if res.status_code in [400, 404] else "ALERTA"
print(f"[PATH] /../../etc/passwd       -> Status: {res.status_code} [{status}]")

# 4. Auth & Role Escalation Protection
unauth_endpoints = [
    ("PATCH", "/api/v1/tecnico/agenda/3/checkin"),
    ("PATCH", "/api/v1/tecnico/agenda/3/checkout"),
    ("POST",  "/api/v1/tecnico/subir-informe-ejecutivo"),
    ("GET",   "/api/v1/admin/usuarios")
]

for method, ep in unauth_endpoints:
    if method == "PATCH":
        res = requests.patch(f"{BASE}{ep}")
    elif method == "POST":
        res = requests.post(f"{BASE}{ep}", json={})
    else:
        res = requests.get(f"{BASE}{ep}")
    status = "PROTEGIDO (401/403)" if res.status_code in [401, 403] else f"ALERTA ({res.status_code})"
    print(f"[AUTH] Sin Token {method} {ep:<38} -> {res.status_code} [{status}]")

# 5. Security Headers Inspection
res = requests.get(f"{BASE}/")
print("\n--- CABECERAS DE SEGURIDAD (HTTP HEADERS) ---")
for h in ["Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy"]:
    val = res.headers.get(h, "NO PRESENTE")
    print(f"  * {h}: {val[:55]}...")

print("\n[OK] Simulación de ataques y auditoría finalizada satisfactoriamente.")
