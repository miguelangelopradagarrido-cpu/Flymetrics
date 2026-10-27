# Flymetrics Frontend Architecture

Este directorio contiene la interfaz web de usuario de Flymetrics con una estructura limpia, funcional y sin carpetas vacías innecesarias.

## Estructura de Directorios

```
frontend/
├── index.html                 # Landing Page Principal
├── pages/                     # Páginas y Paneles de Usuario
│   ├── admin.html             # Torre de Control Administrador
│   ├── cliente.html           # Portal del Cliente
│   ├── tecnico.html           # Portal del Técnico
│   ├── agendar.html           # Portal de Agendamiento
│   ├── staff.html             # Login y Acceso Staff
│   └── bitacora_template.html # Plantilla de Bitácora
├── css/                       # Estilos CSS
│   ├── style.css              # Estilos base y globales
│   ├── admin.css              # Estilos del panel de control
│   └── fontawesome/           # Iconografía local
├── js/                        # Controladores y Lógica JavaScript
│   ├── main.js                # Inicializador
│   ├── app.js                 # Lógica interactiva
│   ├── admin.js               # Lógica del panel administrativo
│   └── api.js                 # Cliente API REST
├── img/                       # Logotipos y recursos gráficos
├── video/                     # Recursos multimedia
└── uploads/                   # Cargas estáticas
```
