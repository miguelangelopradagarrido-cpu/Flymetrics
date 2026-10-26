# Flymetrics Command Center OS — API REST & Web Platform

Plataforma web y API REST empresarial de **Flymetrics S.A.S.**, diseñada bajo **Arquitectura Hexagonal (Ports & Adapters)** e implementada con **FastAPI**, **SQLAlchemy 2.0**, **Pydantic v2**, **MySQL**, y **Vanilla Javascript / CSS Moderno**.

El sistema gestiona la agenda de vuelos de drones agrícolas, bitácoras RAC-100 de pilotos, entregables en la nube (SLA 24-48h), generación de informes técnicos en PDF con recomendaciones agronómicas, atención oficial por WhatsApp y la **Torre de Control Admin-Técnico**.

---

## 🏛️ Arquitectura del Proyecto

El proyecto está estructurado estrictamente en **dos directorios principales** de nivel Senior:

```
flymetrics/
├── backend/                       # API REST, Lógica de Negocio y Base de Datos (Hexagonal)
│   ├── app/
│   │   ├── domain/                # Capa de Dominio (Entities, Ports, Exceptions)
│   │   ├── application/           # Casos de Uso y DTOs (Pydantic schemas)
│   │   ├── infrastructure/        # Adaptadores (Database SQLAlchemy, Security, External APIs)
│   │   ├── presentation/          # Adaptadores Primarios (API Routers FastAPI, Middleware)
│   │   └── shared/                # Utilidades comunes y respuestas HTTP
│   ├── scripts/                   # Utilidades CLI (Creación de administradores, seeders)
│   ├── migrations/                # Migraciones de base de datos Alembic
│   ├── requirements.txt           # Dependencias backend
│   ├── .env                       # Variables de entorno
│   └── main.py                    # Punto de entrada de la aplicación FastAPI
│
├── frontend/                      # Aplicación Web y Paneles de Usuario
│   ├── css/                       # Estilos modulares y temas
│   ├── js/                        # Controladores e interacción con API
│   ├── img/                       # Assets visuales y logotipos
│   ├── admin.html                 # Torre de Control Administrador
│   ├── cliente.html               # Portal del Cliente
│   ├── tecnico.html               # Portal del Técnico
│   ├── agendar.html               # Portal de Agendamiento de Vuelo
│   ├── staff.html                 # Acceso y Login Staff
│   └── index.html                 # Landing Page Principal
│
└── README.md                      # Documentación del sistema
```

---

## 🛠️ Requisitos e Instalación Local

### 1. Instalación de Dependencias
Asegúrese de tener Python 3.10+ instalado:

```bash
pip install -r backend/requirements.txt
```

### 2. Configuración del Archivo `.env`
El archivo `backend/.env` contiene las variables de conexión a la base de datos `flymetrics_db` y secretos JWT.

---

## 👑 Creación de Usuarios Administradores por CLI

Para crear un nuevo usuario con rol de **administrador** directamente en la base de datos:

```bash
# Método interactivo seguro
python backend/scripts/create_admin.py

# Método con argumentos directos
python backend/scripts/admin/create_admin_cli.py nuevo_admin@flymetrics.co MiContraseña123!
```

---

## 🚀 Cómo Iniciar el Servidor Local

Ejecute el servidor web backend:

```bash
cd backend
python main.py
```

El servidor iniciará en `http://localhost:3000`.

### 🌐 Accesos a Paneles e Interfaces:
* **Panel Administrador (Torre Control)**: [http://localhost:3000/admin.html](http://localhost:3000/admin.html)
* **Panel del Cliente**: [http://localhost:3000/cliente.html](http://localhost:3000/cliente.html)
* **Portal del Técnico**: [http://localhost:3000/tecnico.html](http://localhost:3000/tecnico.html)
* **Documentación Swagger UI**: [http://localhost:3000/docs](http://localhost:3000/docs)

---

## 📋 Módulos y Flujo Operativo de la Plataforma

```
[1. Cliente: Agenda Servicio] ➔ [2. Admin-Técnico: Asigna Piloto + Dron] ➔ [3. Técnico: Check-in y Operación]
                                                                                     │
[6. Soporte WA & Auditoría] ◄── [5. Cliente: Abre Link Drive & PDF] ◄── [4. Técnico: Checkout + Link Drive]
```

### 1️⃣ Agendamiento y Cotización Directa (`/agenda`)
- El cliente registra su predio/finca y solicita el servicio deseado.
- El turno se crea en estado `Pendiente`.

### 2️⃣ Torre de Control & Monitoreo Admin-Técnico (`/admin.html`)
- Monitoreo individual de pilotos en tiempo real.
- Matriz de Ocupación Dron + Piloto anti-choque de horarios.
- Edición total de bitácoras, datos RAC-100, justificaciones y enlaces de Google Drive.
- Recálculo de rutas y reagendamiento en 1 clic.

### 3️⃣ Checkout Técnico & Bitácora RAC-100 (`/tecnico.html`)
- Registro de llegada ("Check-in") y cierre ("Checkout").
- Formulario con hectáreas, litros de insumo, agua, baterías, observaciones, **Recomendaciones Agronómicas** y el **Enlace de Google Drive / Nube**.

### 4️⃣ Entregables en Google Drive & Recomendaciones en PDF (`/entregables`)
- **Google Drive**: Evita la saturación del servidor alojando los mapas pesados en la nube.
- **Informe PDF Oficial**: Descarga directa del reporte técnico certificado que incluye la telemetría del vuelo, insumos y recomendaciones agronómicas firmadas.
- **Insignia SLA**: Indicador de tiempo estimado de entrega (24h - 48h).

### 5️⃣ Atención Oficial WhatsApp (`/cliente.html`)
- Canal de soporte directo a WhatsApp (`https://wa.me/573001234567`) para atención inmediata sin bucles de tickets lerdos.
