document.addEventListener("DOMContentLoaded", () => {
    // 1. Inicializar Mapa (Leaflet)
    // Coordenadas centrales de Colombia, con estilo oscuro
    const map = L.map('map').setView([4.5709, -74.2973], 6);
    L.tileLayer('https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_46oy_1_6c24848b24580ff43b413ec3', {
        attribution: '&copy; OpenStreetMap contributors, &copy; CARTO'
    }).addTo(map);

    // Zonas de servicio con estilos de borde/relleno pulidos (blancos y plateados traslúcidos)
    L.circle([2.9273, -75.2818], { color: 'rgba(255, 255, 255, 0.4)', fillColor: '#ffffff', fillOpacity: 0.1, radius: 50000 }).addTo(map).bindPopup("Zona Sur (Huila)");
    L.circle([4.6097, -74.0817], { color: 'rgba(255, 255, 255, 0.4)', fillColor: '#ffffff', fillOpacity: 0.1, radius: 30000 }).addTo(map).bindPopup("Zona Centro (Cundinamarca)");

    // 2. Control del Scroll para el Navbar (Efecto Blurring)
    const navbar = document.getElementById('navbar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // 3. Efecto Mouse Spotlight en Tarjetas (Micro-iluminación Interactiva)
    const cards = document.querySelectorAll(".card");
    cards.forEach(card => {
        card.addEventListener("mousemove", e => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty("--x", `${x}px`);
            card.style.setProperty("--y", `${y}px`);
        });
    });

    // 4. Lógica de Expansión de Servicios (Drawer de Ficha Técnica)
    const serviceData = {
        fumigacion: {
            icon: "🌾",
            title: "Fumigación de Precisión",
            desc: "Optimiza la aplicación de insumos agrícolas reduciendo el desperdicio y protegiendo el ecosistema.",
            specs: {
                "Tecnología Empleada": "Sistema de Aspersión de Precisión",
                "Capacidad del Tanque": "40 Litros (Líquido) / 50 kg (Sólido)",
                "Rendimiento Promedio": "Hasta 21.3 Hectáreas por Hora",
                "Precisión de Vuelo": "Centimétrica RTK Integrada",
                "Ancho de Aspersión": "11 Metros",
                "Ahorro Estimado": "90% de Agua, 30% de Agroquímicos"
            }
        },
        ortofoto: {
            icon: "🗺️",
            title: "Ortofoto 2D / 3D",
            desc: "Mapas topográficos digitales de alta fidelidad para planificación agrícola, catastro e irrigación.",
            specs: {
                "Tecnología Empleada": "Sistema Multiespectral Aéreo",
                "Resolución Espacial (GSD)": "Menor a 1.5 cm por Píxel a 100m",
                "Entregables Estándar": "Ortomosaico, Curvas de Nivel, MDT y MDS",
                "Precisión Vertical / Horiz.": "Menor a 5 cm sin puntos de control terrestres",
                "Formatos de Salida": "TIFF, SHP, DXF, KMZ",
                "Tiempo de Entrega": "Menos de 24 Horas"
            }
        },
        ndvi: {
            icon: "🌿",
            title: "Análisis Multiespectral",
            desc: "Monitoreo avanzado de salud vegetal y vigor de cultivos para aplicación de tasa variable.",
            specs: {
                "Tecnología Empleada": "Sistema Multiespectral Aéreo",
                "Bandas del Sensor": "Verde, Rojo, Borde Rojo, Infrarrojo Cercano (NIR)",
                "Salud Foliar": "Reflectancia espectral y vigor vegetativo",
                "Beneficio Clave": "Detección de estrés hídrico y plagas de forma temprana",
                "Mapas de Prescripción": "Compatibles con maquinaria John Deere, Case, etc."
            }
        },
        inspeccion: {
            icon: "🔎",
            title: "Inspecciones Agrícolas de Cultivos",
            desc: "Monitoreo fitosanitario, diagnóstico térmico de riego y anomalías en cultivos agrícolas.",
            specs: {
                "Tecnología Empleada": "Dron con Cámara RGB 48MP y Sensor Térmico",
                "Sensor Térmico": "Microbolómetro radiométrico de alta precisión",
                "Sensibilidad Térmica": "Menor a 50 mK para detección de estrés",
                "Precisión": "Centimétrica RTK",
                "Cobertura": "Hasta 250 Hectáreas / jornada",
                "Casos de Uso": "Detección de plagas, fallas de riego, estrés calórico en cultivos"
            }
        }
    };

    const drawer = document.getElementById("serviceDrawer");
    const closeDrawer = document.getElementById("closeDrawer");
    const drawerIcon = document.getElementById("drawerIcon");
    const drawerTitle = document.getElementById("drawerTitle");
    const drawerDesc = document.getElementById("drawerDesc");
    const drawerSpecs = document.getElementById("drawerSpecs");
    const drawerAgendaBtn = document.getElementById("drawerAgendaBtn");

    cards.forEach(card => {
        card.addEventListener("click", () => {
            const serviceKey = card.getAttribute("data-service");
            const data = serviceData[serviceKey];
            if (data) {
                drawerIcon.textContent = data.icon;
                drawerTitle.textContent = data.title;
                drawerDesc.textContent = data.desc;
                
                drawerSpecs.innerHTML = "";
                for (const [key, value] of Object.entries(data.specs)) {
                    drawerSpecs.innerHTML += `
                        <li>
                            <span class="spec-label">${key}</span>
                            <span class="spec-value">${value}</span>
                        </li>
                    `;
                }
                drawer.classList.add("active");
            }
        });
    });

    closeDrawer.addEventListener("click", () => {
        drawer.classList.remove("active");
    });
    
    drawer.addEventListener("click", (e) => {
        if (e.target === drawer) drawer.classList.remove("active");
    });

    // 5. Lógica de Modales de Autenticación
    const modal = document.getElementById('authModal');
    const loginNavBtn = document.getElementById('loginNavBtn');
    const registerNavBtn = document.getElementById('registerNavBtn');
    const heroMapBtn = document.getElementById('heroMapBtn');
    const closeModal = document.getElementById('closeModal');

    const openAuthModal = () => {
        modal.classList.add('active');
    };

    if (loginNavBtn) loginNavBtn.addEventListener('click', openAuthModal);
    if (registerNavBtn) registerNavBtn.addEventListener('click', openAuthModal);
    if (drawerAgendaBtn) drawerAgendaBtn.addEventListener('click', () => {
        drawer.classList.remove('active');
        openAuthModal();
    });
    if (heroMapBtn) heroMapBtn.addEventListener('click', () => {
        document.getElementById('cobertura').scrollIntoView({ behavior: 'smooth' });
    });
    
    if (closeModal) {
        closeModal.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }

    window.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
    });

    // 6. Formulario de Inicio de Sesión
    const loginForm = document.getElementById('loginForm');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                const data = await API.login(emailInput.value, passwordInput.value);
                API.setToken(data.access_token);
                
                // Redirigir según el rol
                const user = await API.getMe(data.access_token);
                if (user.data.rol === 'administrador') window.location.href = 'admin.html';
                else if (user.data.rol === 'tecnico') window.location.href = 'tecnico.html';
                else window.location.href = 'cliente.html';

            } catch (error) {
                alert(error.message || 'Error al iniciar sesión');
            }
        });
    }
});
