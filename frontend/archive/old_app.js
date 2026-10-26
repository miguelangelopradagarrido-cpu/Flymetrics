// ═══════════════════════════════════════════════════════════
// FlyMetrics — app.js  |  2025
// Single-page · Login-required agenda · Cedula verify
// Distance calc from Bogotá · Google OAuth
// ═══════════════════════════════════════════════════════════
'use strict';
const API = (window.location.protocol === 'file:' || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:3000'
  : window.location.origin;

// Google OAuth Client ID (replace with your real Client ID from console.cloud.google.com)
const GOOGLE_CLIENT_ID = '1044490043488-n2l2jjvnpq2mn8km4ag62r4t4af10vb6.apps.googleusercontent.com';

let _token = null, _user = null, _verified = false;
let _step = 1, _freq = 1, _selSvc = '', _toastT;
let _distKm = 0, _distSurcharge = 0;

/* ────────────────────────────────────────────────────────────
   CITY COORDINATES (relative to Bogotá as HQ)
   ──────────────────────────────────────────────────────────── */
const CITIES = {
  bogota:        { lat:4.7110, lng:-74.0721, label:'Bogotá D.C.' },
  medellin:      { lat:6.2442, lng:-75.5812, label:'Medellín' },
  cali:          { lat:3.4516, lng:-76.5320, label:'Cali' },
  barranquilla:  { lat:10.9639,lng:-74.7964, label:'Barranquilla' },
  bucaramanga:   { lat:7.1198, lng:-73.1227, label:'Bucaramanga' },
  cartagena:     { lat:10.3997,lng:-75.5144, label:'Cartagena' },
  cucuta:        { lat:7.8939, lng:-72.5078, label:'Cúcuta' },
  pereira:       { lat:4.8133, lng:-75.6961, label:'Pereira' },
  manizales:     { lat:5.0703, lng:-75.5138, label:'Manizales' },
  armenia:       { lat:4.5339, lng:-75.6811, label:'Armenia' },
  ibague:        { lat:4.4389, lng:-75.2322, label:'Ibagué' },
  villavicencio: { lat:4.1420, lng:-73.6266, label:'Villavicencio' },
  yopal:         { lat:5.3378, lng:-72.3959, label:'Yopal' },
  neiva:         { lat:2.9273, lng:-75.2819, label:'Neiva' },
  pasto:         { lat:1.2136, lng:-77.2811, label:'Pasto' },
  monteria:      { lat:8.7479, lng:-75.8814, label:'Montería' },
  valledupar:    { lat:10.4772,lng:-73.2500, label:'Valledupar' },
  sincelejo:     { lat:9.3048, lng:-75.3970, label:'Sincelejo' },
  santa_marta:   { lat:11.2408,lng:-74.1990, label:'Santa Marta' },
  popayan:       { lat:2.4419, lng:-76.6060, label:'Popayán' },
  tunja:         { lat:5.5353, lng:-73.3675, label:'Tunja' },
  florencia:     { lat:1.6144, lng:-75.6062, label:'Florencia' },
};
const BOGOTA = { lat:4.7110, lng:-74.0721 };

/* ────────────────────────────────────────────────────────────
   INIT
   ──────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initCursor();
  initCanvas();
  initReveal();
  initCounters();
  initSidebarActive();
  initMap();
  checkSession();
  setMinDate();
  initGoogleSignIn();
});

/* ────────────────────────────────────────────────────────────
   CURSOR
   ──────────────────────────────────────────────────────────── */
function initCursor() {
  const cur = document.getElementById('cursor');
  const dot = document.getElementById('cursor-dot');
  if (!cur || !dot) return;
  if (window.matchMedia('(pointer: coarse)').matches) return;

  let mx = -200, my = -200;
  document.addEventListener('mousemove', e => {
    mx = e.clientX; my = e.clientY;
    cur.style.left = mx + 'px';  cur.style.top = my + 'px';
    dot.style.left = mx + 'px';  dot.style.top = my + 'px';
  });
  document.querySelectorAll('a,button,.svc-card,.spk-btn,.extra-row,.check-row,.freq-btn,.google-btn').forEach(el => {
    el.addEventListener('mouseenter', () => cur.classList.add('big'));
    el.addEventListener('mouseleave', () => cur.classList.remove('big'));
  });
  document.addEventListener('mousedown', () => cur.classList.add('click'));
  document.addEventListener('mouseup',   () => cur.classList.remove('click'));
  document.addEventListener('mouseleave', () => { cur.style.opacity='0'; dot.style.opacity='0'; });
  document.addEventListener('mouseenter', () => { cur.style.opacity=''; dot.style.opacity=''; });
}

/* ────────────────────────────────────────────────────────────
   PARTICLE CANVAS
   ──────────────────────────────────────────────────────────── */
function initCanvas() {
  const canvas = document.getElementById('hero-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, pts = [];

  const resize = () => { W = canvas.width = canvas.offsetWidth; H = canvas.height = canvas.offsetHeight; };
  resize();
  window.addEventListener('resize', resize);

  const N = Math.min(70, Math.floor((window.innerWidth * window.innerHeight) / 14000));
  for (let i = 0; i < N; i++) pts.push({ x: Math.random()*W, y: Math.random()*H, vx:(Math.random()-.5)*.32, vy:(Math.random()-.5)*.32, r:Math.random()*1.2+.4 });

  const draw = () => {
    ctx.clearRect(0,0,W,H);
    for (let i=0;i<pts.length;i++) {
      for (let j=i+1;j<pts.length;j++) {
        const dx=pts[i].x-pts[j].x, dy=pts[i].y-pts[j].y, d=Math.hypot(dx,dy);
        if (d<120) { ctx.beginPath(); ctx.strokeStyle=`rgba(30,144,255,${.1*(1-d/120)})`; ctx.lineWidth=.5; ctx.moveTo(pts[i].x,pts[i].y); ctx.lineTo(pts[j].x,pts[j].y); ctx.stroke(); }
      }
      const p=pts[i];
      ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2); ctx.fillStyle='rgba(30,144,255,.4)'; ctx.fill();
      p.x+=p.vx; p.y+=p.vy;
      if(p.x<0||p.x>W) p.vx*=-1;
      if(p.y<0||p.y>H) p.vy*=-1;
    }
    requestAnimationFrame(draw);
  };
  draw();
}

/* ────────────────────────────────────────────────────────────
   SCROLL REVEAL
   ──────────────────────────────────────────────────────────── */
function initReveal() {
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const parent = e.target.parentElement;
      if (parent) {
        const sibs = [...parent.querySelectorAll('.fade-up')];
        const idx = sibs.indexOf(e.target);
        e.target.style.transitionDelay = (idx * 0.07) + 's';
      }
      e.target.classList.add('vis');
      obs.unobserve(e.target);
    });
  }, { threshold:0.1, rootMargin:'0px 0px -40px 0px' });
  document.querySelectorAll('.fade-up').forEach(el => obs.observe(el));
}

/* ────────────────────────────────────────────────────────────
   COUNTERS
   ──────────────────────────────────────────────────────────── */
function initCounters() {
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      e.target.querySelectorAll('[data-count]').forEach(el => {
        const target = +el.dataset.count;
        let cur = 0;
        const iv = setInterval(() => {
          cur += target/55;
          if (cur >= target) { el.textContent = target.toLocaleString('es-CO'); clearInterval(iv); }
          else el.textContent = Math.floor(cur).toLocaleString('es-CO');
        }, 18);
      });
      obs.unobserve(e.target);
    });
  }, { threshold:0.3 });
  document.querySelectorAll('.hero-stats,.cob-stats').forEach(el => obs.observe(el));
}

/* ────────────────────────────────────────────────────────────
   SIDEBAR ACTIVE STATE
   ──────────────────────────────────────────────────────────── */
function initSidebarActive() {
  const sections = document.querySelectorAll('section[id],footer[id]');
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      document.querySelectorAll('.sb-link,.btab').forEach(l => l.classList.remove('active'));
      const link = document.querySelector(`.sb-link[data-section="${e.target.id}"]`);
      const tab  = document.querySelector(`.btab[href="#${e.target.id}"]`);
      if (link) link.classList.add('active');
      if (tab)  tab.classList.add('active');
    });
  }, { threshold:0.35 });
  sections.forEach(s => obs.observe(s));
}

/* ────────────────────────────────────────────────────────────
   MOBILE MENU
   ──────────────────────────────────────────────────────────── */
function toggleMobileMenu() {
  const d=document.getElementById('mobile-drawer'), o=document.getElementById('mobile-overlay');
  const open=d.classList.toggle('open');
  o.style.display=open?'block':'none';
  document.body.style.overflow=open?'hidden':'';
}
function closeMobileMenu() {
  document.getElementById('mobile-drawer')?.classList.remove('open');
  const o=document.getElementById('mobile-overlay');
  if(o) o.style.display='none';
  document.body.style.overflow='';
}

/* ────────────────────────────────────────────────────────────
   AGENDA ACCESS — LOGIN + CEDULA REQUIRED
   ──────────────────────────────────────────────────────────── */
function checkAgendaAccess(e) {
  if (e) e.preventDefault();
  if (!_token) {
    window.location.href = 'agenda.html';
    return;
  }
  window.location.href = 'cliente/index.html';
}

/* ────────────────────────────────────────────────────────────
   SERVICES
   ──────────────────────────────────────────────────────────── */
const SERVICES_DETAIL = {
  fumigacion: {
    icon: "🌾",
    title: "Fumigación Agrícola",
    desc: "Aplicación aérea de precisión para agroquímicos y fertilizantes líquidos. Máxima eficiencia y uniformidad de cobertura.",
    specs: [
      { label: "Equipos", value: "DJI Agras T40 / DJI Agras T30" },
      { label: "Capacidad de Tanque", value: "40 Litros / 30 Litros" },
      { label: "Rendimiento Operativo", value: "Hasta 20.3 Hectáreas por Hora" },
      { label: "Precisión de Vuelo", value: "Centimétrica RTK Integrada" },
      { label: "Sistema de Aspersión", value: "Boquillas de atomización centrífuga magnética" },
      { label: "Ancho de Franja", value: "Hasta 11 Metros" },
      { label: "Ahorro Hídrico", value: "Hasta 90% en comparación con métodos terrestres" }
    ]
  },
  ndvi: {
    icon: "🌿",
    title: "Monitoreo NDVI",
    desc: "Mapas multiespectrales de vigor vegetativo para identificar anomalías de salud del cultivo antes de que sean visibles.",
    specs: [
      { label: "Equipos", value: "DJI Mavic 3 Multispectral / P4M" },
      { label: "Bandas Espectrales", value: "Verde, Rojo, Red Edge (Red Edge), Infrarrojo Cercano (NIR), RGB" },
      { label: "Resolución Espacial", value: "GSD de hasta 2 cm por píxel" },
      { label: "Formatos de Salida", value: "GeoTIFF, KML/KMZ, PDF de Diagnóstico" },
      { label: "Precisión de Posición", value: "RTK Integrada de alta precisión" },
      { label: "Casos de Uso", value: "Detección de plagas, estrés hídrico y deficiencia nutricional" }
    ]
  },
  herbicidas: {
    icon: "🌱",
    title: "Aspersión de Herbicidas",
    desc: "Tratamiento y control focalizado de malezas con microdosificación inteligente para evitar contaminación cruzada.",
    specs: [
      { label: "Equipos", value: "DJI Agras T30 / DJI Agras T10" },
      { label: "Estrategia", value: "Aplicación selectiva basada en mapas multiespectrales previos" },
      { label: "Ahorro de Producto", value: "Hasta 70% de reducción en el volumen de herbicida" },
      { label: "Deriva Química", value: "Minimizada por control de gota y altura automática" },
      { label: "Tasa Variable", value: "Dosificación adaptativa según la densidad de la maleza" }
    ]
  },
  fotogrametria: {
    icon: "🗺️",
    title: "Fotogrametría 3D",
    desc: "Mapeo topográfico de alta resolución para planificación de fincas, curvas de nivel y modelación de escorrentías.",
    specs: [
      { label: "Equipos", value: "DJI Phantom 4 RTK / DJI Mavic 3 Enterprise" },
      { label: "Precisión Absoluta", value: "Horizontal y Vertical menor a 5 cm" },
      { label: "Resolución de Ortofoto", value: "GSD de 2 cm por píxel a 100m de altura" },
      { label: "Entregables Clave", value: "Ortomosaico, Modelos Digitales de Elevación (DEM/DSM), Nubes de Puntos" },
      { label: "Formatos", value: "TIFF, LAS, SHP, DXF (para AutoCAD)" },
      { label: "Procesamiento", value: "Software Pix4Dmapper de última generación" }
    ]
  },
  asesoria: {
    icon: "⚖️",
    title: "Asesoría Técnica RAC100",
    desc: "Consultoría experta en cumplimiento de normatividades de la Aeronáutica Civil (Aerocivil) para drones en Colombia.",
    specs: [
      { label: "Marco Regulador", value: "Resolución Aerocivil RAC 100" },
      { label: "Servicios", value: "Elaboración de manuales de operación, registros RPAS y gestión de licencias de piloto" },
      { label: "Certificación", value: "Acompañamiento en el proceso completo para operación comercial certificada" },
      { label: "Soporte Operacional", value: "Asesoramiento en análisis de riesgo (SORA) y planes de vuelo seguros" }
    ]
  },
  censo: {
    icon: "📊",
    title: "Censo de Cultivos",
    desc: "Conteo individualizado de plantas y árboles mediante Inteligencia Artificial y Visión por Computadora.",
    specs: [
      { label: "Tecnología", value: "Algoritmos propietarios de Deep Learning / Computer Vision" },
      { label: "Precisión Mínima", value: "Mayor al 97% en condiciones óptimas de visibilidad" },
      { label: "Parámetros", value: "Conteo neto de plantas, mapas de densidad y detección de fallas de siembra" },
      { label: "Exportable", value: "Reporte tabular e integración directa con Sistemas de Información Geográfica (GIS)" },
      { label: "Cultivos Aptos", value: "Palma de aceite, banano, café, forestales, aguacate, cítricos" }
    ]
  }
};

function goToServicio(slug) {
  const data = SERVICES_DETAIL[slug];
  if (!data) return;
  
  const iconEl = document.getElementById('svc-detail-icon');
  const titleEl = document.getElementById('svc-detail-title');
  const descEl = document.getElementById('svc-detail-desc');
  const specsList = document.getElementById('svc-detail-specs');
  
  if (iconEl) iconEl.textContent = data.icon;
  if (titleEl) titleEl.textContent = data.title;
  if (descEl) descEl.textContent = data.desc;
  
  if (specsList) {
    specsList.innerHTML = data.specs.map(spec => `
      <li style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--b); font-size: 0.82rem;">
        <span class="mono" style="color: var(--t3);">${spec.label}</span>
        <b style="color: var(--t1); text-align: right; margin-left: 10px; font-weight: 500;">${spec.value}</b>
      </li>
    `).join('');
  }
  
  openModal('modal-servicio');
}

/* ────────────────────────────────────────────────────────────
   COTIZADOR + DISTANCE CALCULATOR
   ──────────────────────────────────────────────────────────── */
const SVC_DATA = {
  fumigacion:    { label:'Fumigación Agrícola',      ppm2:18 },
  ndvi:          { label:'Monitoreo NDVI',            ppm2:28 },
  herbicidas:    { label:'Aspersión de Herbicidas',   ppm2:22 },
  fotogrametria: { label:'Fotogrametría 3D',          ppm2:35 },
  asesoria:      { label:'Asesoría RAC100',           flat:350000 },
  censo:         { label:'Censo de Cultivos',         ppm2:25 },
};

function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371, d2r = Math.PI/180;
  const dLat=(lat2-lat1)*d2r, dLng=(lng2-lng1)*d2r;
  const a=Math.sin(dLat/2)**2 + Math.cos(lat1*d2r)*Math.cos(lat2*d2r)*Math.sin(dLng/2)**2;
  return Math.round(R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a)));
}

function calcDistancia() {
  const cityKey = document.getElementById('cot-ciudad')?.value;
  const panel   = document.getElementById('dist-panel');
  if (!cityKey || cityKey === 'bogota') {
    if (panel) panel.style.display='none';
    _distKm=0; _distSurcharge=0;
    calcular(); return;
  }
  const city = CITIES[cityKey];
  if (!city || !panel) return;

  const km = haversine(BOGOTA.lat, BOGOTA.lng, city.lat, city.lng);
  _distKm = km;

  // Surcharge logic: >50km = $2500/km, >300km = $4000/km
  let surcharge = 0;
  if (km > 300) surcharge = Math.round(km * 4000);
  else if (km > 50) surcharge = Math.round(km * 2500);
  _distSurcharge = surcharge;

  const hours = Math.ceil(km / 80); // avg 80km/h
  document.getElementById('dist-km').textContent   = `${km.toLocaleString('es-CO')} km`;
  document.getElementById('dist-time').textContent  = hours <= 1 ? 'Menos de 1 hora' : `~${hours} horas en carretera`;
  document.getElementById('dist-surcharge').textContent = surcharge === 0
    ? 'Sin recargo (zona central)'
    : `+$${surcharge.toLocaleString('es-CO')} COP`;
  panel.style.display = 'flex';
  calcular();
}

function syncHa(v)   { document.getElementById('cot-ha').value=v; calcular(); }
function syncRange(v){ document.getElementById('cot-range').value=Math.min(v,500); calcular(); }
function setFreq(btn,val) {
  document.querySelectorAll('.freq-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); _freq=val; calcular();
}
function calcular() {
  const svcKey=document.getElementById('cot-svc')?.value;
  const ha=parseFloat(document.getElementById('cot-ha')?.value)||0;
  const prEl=document.getElementById('cot-total');
  const brkEl=document.getElementById('cot-breakdown');
  if (!prEl||!brkEl) return;
  if (!svcKey||ha<=0) { prEl.textContent='0'; brkEl.innerHTML='<div class="cot-row"><span>Selecciona servicio, hectáreas y ciudad</span></div>'; return; }

  const svc=SVC_DATA[svcKey];
  let base=svc.flat?svc.flat:svc.ppm2*ha*10000;
  let extras=0;
  if (document.getElementById('ex-reporte')?.checked) extras+=120000;
  if (document.getElementById('ex-ndvi')?.checked)    extras+=200000;
  if (document.getElementById('ex-urgente')?.checked) base*=1.3;

  const subtotal=(base+extras)*_freq;
  const total=subtotal+_distSurcharge;
  const dur=svc.flat?'—':(Math.ceil(ha/5*10)/10)+'h';

  prEl.textContent=Math.round(total).toLocaleString('es-CO');
  brkEl.innerHTML=`
    <div class="cot-row"><span>Servicio</span><b style="color:var(--t)">${svc.label}</b></div>
    <div class="cot-row"><span>Área</span><b style="color:var(--t)">${ha} ha</b></div>
    ${!svc.flat?`<div class="cot-row"><span>Precio base</span><b style="color:var(--t)">$${svc.ppm2}/m²</b></div>`:''}
    <div class="cot-row"><span>Duración est.</span><b style="color:var(--t)">${dur}</b></div>
    <div class="cot-row"><span>Frecuencia</span><b style="color:var(--t)">×${_freq}</b></div>
    ${extras>0?`<div class="cot-row"><span>Extras</span><b style="color:var(--a)">+$${extras.toLocaleString('es-CO')}</b></div>`:''}
    ${_distSurcharge>0?`<div class="cot-row"><span>Desplazamiento (${_distKm}km)</span><b style="color:var(--w)">+$${_distSurcharge.toLocaleString('es-CO')}</b></div>`:''}
  `;
}

/* ────────────────────────────────────────────────────────────
   MAP (LEAFLET) — expanded Colombia zones
   ──────────────────────────────────────────────────────────── */
function initMap() {
  const el=document.getElementById('mapa');
  if (!el||typeof L==='undefined') return;
  const map=L.map('mapa',{scrollWheelZoom:false,zoomControl:true}).setView([5.5,-74.0],5);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:'© CARTO',maxZoom:18}).addTo(map);

  // HQ Bogotá marker
  const hqIcon=L.divIcon({html:`<div style="width:14px;height:14px;background:#FFB800;border-radius:50%;box-shadow:0 0 16px #FFB800;border:2px solid #fff"></div>`,iconSize:[14,14],className:''});
  L.marker([4.7110,-74.0721],{icon:hqIcon}).addTo(map).bindPopup(`<b style="color:#FFB800">🏢 Sede Principal</b><br><small>Bogotá D.C., Colombia</small>`);

  const zonas=[
    // ACTIVE ZONES
    {lat:5.35, lng:-72.40,n:'Casanare',       a:true},
    {lat:4.15, lng:-73.64,n:'Meta',            a:true},
    {lat:6.25, lng:-75.56,n:'Antioquia',       a:true},
    {lat:10.39,lng:-75.51,n:'Bolívar',         a:true},
    {lat:3.87, lng:-76.05,n:'Valle del Cauca', a:true},
    {lat:5.07, lng:-75.52,n:'Caldas',          a:true},
    {lat:4.81, lng:-75.69,n:'Risaralda',       a:true},
    {lat:5.54, lng:-73.36,n:'Boyacá',          a:true},
    {lat:7.12, lng:-73.12,n:'Santander',       a:true},
    {lat:3.53, lng:-75.70,n:'Tolima',          a:true},
    {lat:4.70, lng:-74.07,n:'Cundinamarca',    a:true},
    {lat:4.81, lng:-75.69,n:'Quindío',         a:true},
    {lat:7.88, lng:-76.66,n:'Chocó (norte)',   a:true},
    {lat:9.30, lng:-75.40,n:'Sucre',           a:true},
    {lat:8.75, lng:-74.88,n:'Córdoba',         a:true},
    // COMING SOON
    {lat:1.21, lng:-77.28,n:'Nariño',          a:false},
    {lat:2.44, lng:-76.61,n:'Cauca',           a:false},
    {lat:10.47,lng:-73.25,n:'Cesar',           a:false},
    {lat:1.63, lng:-75.61,n:'Huila',           a:false},
    {lat:10.97,lng:-74.80,n:'Atlántico',       a:false},
    {lat:11.24,lng:-74.20,n:'Magdalena',       a:false},
    {lat:10.08,lng:-72.36,n:'Guajira',         a:false},
    {lat:6.50, lng:-72.70,n:'Norte de Santander',a:false},
    {lat:4.53, lng:-75.67,n:'Quindío',         a:false},
    {lat:5.85, lng:-76.64,n:'Chocó',           a:false},
  ];

  zonas.forEach(z => {
    const c=z.a?'#00FF88':'#1E90FF';
    const icon=L.divIcon({html:`<div style="width:9px;height:9px;background:${c};border-radius:50%;box-shadow:0 0 9px ${c};opacity:${z.a?1:.5}"></div>`,iconSize:[9,9],className:''});
    L.marker([z.lat,z.lng],{icon}).addTo(map)
      .bindPopup(`<div style="background:#0c0c0c;border:1px solid rgba(255,255,255,.1);padding:10px;color:#fff;font-family:'Space Grotesk',sans-serif;font-size:.83rem;min-width:120px"><b style="color:${c}">${z.n}</b><br><small style="color:#666">${z.a?'✓ Zona activa':'Próximamente'}</small></div>`,{className:'dark-popup'});
    L.circle([z.lat,z.lng],{color:c,fillColor:c,fillOpacity:.05,radius:60000,weight:.5,opacity:z.a?.35:.15}).addTo(map);
  });

  // Draw lines from Bogotá to active zones
  zonas.filter(z=>z.a).forEach(z=>{
    L.polyline([[4.7110,-74.0721],[z.lat,z.lng]],{color:'rgba(30,144,255,0.12)',weight:1,dashArray:'4,8'}).addTo(map);
  });
}

/* ────────────────────────────────────────────────────────────
   STEPPER — AGENDA FORM
   ──────────────────────────────────────────────────────────── */
function setMinDate() {
  const el=document.getElementById('ag-fecha');
  if (el) el.min=new Date().toISOString().split('T')[0];
}
function goStep(n) {
  document.getElementById('sp-'+_step)?.classList.remove('active');
  _step=n;
  document.getElementById('sp-'+_step)?.classList.add('active');
  for (let i=1;i<=4;i++) {
    document.getElementById('si-'+i)?.classList.toggle('done',i<_step);
    document.getElementById('si-'+i)?.classList.toggle('active',i===_step);
    document.getElementById('sl-'+i)?.classList.toggle('done',i<_step);
  }
  document.getElementById('agenda')?.scrollIntoView({behavior:'smooth',block:'start'});
}
function nextStep(from) { if (validateStep(from)) { if(from===3) buildConfirm(); goStep(from+1); } }
function validateStep(n) {
  const req={1:['ag-nombre','ag-email','ag-pass'],2:['ag-finca','ag-hectareas','ag-depto'],3:[]};
  let ok=true;
  (req[n]||[]).forEach(id=>{ const el=document.getElementById(id); if(el&&!el.value.trim()){el.style.borderColor='var(--e)';ok=false;}else if(el) el.style.borderColor=''; });
  if (n===3&&!_selSvc){showToast('⚠ Selecciona un servicio');ok=false;}
  if (n===3&&!document.getElementById('ag-fecha')?.value){showToast('⚠ Selecciona una fecha');ok=false;}
  if (n===3&&!document.getElementById('ag-terms')?.checked){showToast('⚠ Acepta los términos');ok=false;}
  if (!ok&&!['fumigacion','ndvi','herbicidas'].includes(_selSvc)) showToast('⚠ Completa los campos requeridos');
  return ok;
}
function pickSvc(btn) { document.querySelectorAll('.spk-btn').forEach(b=>b.classList.remove('sel')); btn.classList.add('sel'); _selSvc=btn.dataset.svc; }
function captureGPS() {
  const btn=document.getElementById('btn-gps'), disp=document.getElementById('gps-display');
  if (!navigator.geolocation){if(disp) disp.textContent='No disponible';return;}
  btn.textContent='Capturando...'; btn.disabled=true;
  navigator.geolocation.getCurrentPosition(pos=>{
    const lat=pos.coords.latitude.toFixed(6), lng=pos.coords.longitude.toFixed(6);
    document.getElementById('ag-lat').value=lat;
    document.getElementById('ag-lng').value=lng;
    if(disp){disp.textContent=`${lat}, ${lng}`;disp.style.color='var(--a)';}
    btn.textContent='✓ GPS capturado'; btn.disabled=false;
  },()=>{if(disp) disp.textContent='Error de GPS';btn.textContent='Reintentar';btn.disabled=false;});
}
function buildConfirm() {
  const rp=document.getElementById('cr-personal');
  const rf=document.getElementById('cr-finca');
  const rs=document.getElementById('cr-servicio');
  if(!rp) return;
  const svcLabel=SVC_DATA[_selSvc]?.label||_selSvc;
  rp.innerHTML=row('Nombre',document.getElementById('ag-nombre')?.value)+row('Email',document.getElementById('ag-email')?.value)+row('Teléfono','+57 '+document.getElementById('ag-tel')?.value);
  rf.innerHTML=row('Finca',document.getElementById('ag-finca')?.value)+row('Departamento',document.getElementById('ag-depto')?.value)+row('Hectáreas',document.getElementById('ag-hectareas')?.value+' Ha');
  rs.innerHTML=row('Servicio',svcLabel)+row('Fecha',document.getElementById('ag-fecha')?.value)+row('Hora',document.getElementById('ag-hora')?.value);
}
function row(k,v){return `<div class="cr-row"><span>${k}</span><b>${v||'—'}</b></div>`;}

async function submitAgenda() {
  const btn=document.getElementById('btn-submit'), txt=document.getElementById('submit-txt');
  txt.textContent='Enviando...'; btn.disabled=true;
  const email=document.getElementById('ag-email')?.value.trim();
  const pass=document.getElementById('ag-pass')?.value;
  const nombre=document.getElementById('ag-nombre')?.value.trim();
  const apellido=document.getElementById('ag-apellido')?.value.trim()||'';
  try {
    await fetch(`${API}/auth/register`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,contrasena:pass,rol:'cliente'})});
    const lRes=await fetch(`${API}/auth/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,contrasena:pass})});
    const lData=await lRes.json(); _token=lData.token;
    const headers={'Content-Type':'application/json','Authorization':`Bearer ${_token}`};
    const cRes=await fetch(`${API}/clientes`,{method:'POST',headers,body:JSON.stringify({id_usuario:lData.id_usuarios,nombre,apellido_1:apellido})});
    const cData=await cRes.json();
    const fRes=await fetch(`${API}/fincas`,{method:'POST',headers,body:JSON.stringify({id_cliente:cData.id_cliente,nombre_finca:document.getElementById('ag-finca')?.value,municipio:document.getElementById('ag-municipio')?.value,departamento:document.getElementById('ag-depto')?.value,hectareas:parseFloat(document.getElementById('ag-hectareas')?.value),tipo_cultivo:document.getElementById('ag-cultivo')?.value,latitud:document.getElementById('ag-lat')?.value,longitud:document.getElementById('ag-lng')?.value})});
    const fData=await fRes.json();
    const aRes=await fetch(`${API}/agenda`,{method:'POST',headers,body:JSON.stringify({id_cliente:cData.id_cliente,id_finca:fData.id_finca,id_servicio:1,nombre_servicio:_selSvc,fecha_solicitada:document.getElementById('ag-fecha')?.value,hora_preferida:document.getElementById('ag-hora')?.value,observaciones:document.getElementById('ag-obs')?.value,estado:'Pendiente'})});
    const aData=await aRes.json();
    showSuccess(aData.id_agenda||'FM-'+Date.now().toString(36).toUpperCase().slice(-6));
  } catch {
    showSuccess('FM-'+Date.now().toString(36).toUpperCase().slice(-6));
  } finally { txt.textContent='Enviar solicitud'; btn.disabled=false; }
}
function showSuccess(trackId) {
  document.getElementById('confirm-view').style.display='none';
  document.getElementById('success-view').style.display='block';
  document.getElementById('success-id').textContent='#'+trackId;
  document.getElementById('success-msg').textContent='Tu solicitud fue registrada. Nuestro equipo te contactará en menos de 2 horas hábiles.';
  document.getElementById('si-4')?.classList.add('done');
}
function resetAgenda() {
  _step=1; _selSvc='';
  document.getElementById('confirm-view').style.display='block';
  document.getElementById('success-view').style.display='none';
  document.querySelectorAll('.step-panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('sp-1')?.classList.add('active');
  for(let i=1;i<=4;i++){document.getElementById('si-'+i)?.classList.remove('active','done');document.getElementById('sl-'+i)?.classList.remove('done');}
  document.getElementById('si-1')?.classList.add('active');
}

/* ────────────────────────────────────────────────────────────
   CEDULA VERIFICATION
   ──────────────────────────────────────────────────────────── */
function openCedulaModal() {
  openModal('modal-cedula');
}
async function verificarCedula(e) {
  e.preventDefault();
  const cedula=document.getElementById('v-cedula')?.value.trim();
  const nombre=document.getElementById('v-nombre')?.value.trim();
  const apellido=document.getElementById('v-apellido')?.value.trim();
  const fecha=document.getElementById('v-fecha')?.value;
  const errEl=document.getElementById('v-err');
  const btn=document.getElementById('btn-verificar');
  const progress=document.getElementById('cedula-progress');
  const fill=document.getElementById('cedula-prog-fill');
  const txt=document.getElementById('cedula-prog-txt');

  if (!cedula||!nombre||!apellido||!fecha) {
    errEl.textContent='Completa todos los campos requeridos'; errEl.style.display='block'; return;
  }
  if (cedula.length<6) {
    errEl.textContent='Número de documento inválido'; errEl.style.display='block'; return;
  }
  errEl.style.display='none';
  btn.disabled=true; btn.textContent='Verificando...';
  progress.style.display='block';

  // Simulated verification steps
  const steps=[
    {p:20, msg:'Consultando base de datos RNEC...'},
    {p:45, msg:'Validando documento...'},
    {p:70, msg:'Verificando identidad...'},
    {p:90, msg:'Confirmando datos...'},
    {p:100,msg:'¡Verificación completada!'},
  ];
  for (const s of steps) {
    await delay(700);
    fill.style.width=s.p+'%';
    txt.textContent=s.msg;
  }
  await delay(600);

  // Mark as verified
  _verified=true;
  localStorage.setItem('fm_verified','1');
  localStorage.setItem('fm_cedula',cedula);
  closeModal('modal-cedula');
  showToast('✓ Identidad verificada — puedes agendar tu servicio');
  setTimeout(()=>document.getElementById('agenda')?.scrollIntoView({behavior:'smooth'}), 400);
}
function delay(ms){return new Promise(r=>setTimeout(r,ms));}

/* ── GOTO USER PANEL ──────────────────────────────────── */
function goToUserPanel() {
  if (!_token) {
    openLoginWithNote();
    return;
  }
  const userStr = localStorage.getItem('fm_user');
  if (userStr) {
    try {
      const u = JSON.parse(userStr);
      if (u.rol === 'tecnico') {
        window.location.href = 'tecnico.html';
        return;
      } else if (u.rol === 'administrador') {
        window.location.href = 'admin.html';
        return;
      }
    } catch(e) {}
  }
  window.location.href = 'cliente.html';
}

/* ── LOGIN / REGISTER ──────────────────────────────── */
function openLogin() {
  const n=document.getElementById('login-access-note');
  if(n) n.style.display='none';
  openModal('modal-login');
}
function openLoginWithNote() {
  openModal('modal-login');
  const n=document.getElementById('login-access-note');
  if(n) n.style.display='flex';
  setTimeout(()=>document.getElementById('l-email')?.focus(),200);
}
function closeLogin() { closeModal('modal-login'); }
function switchLoginTab(tab) {
  document.getElementById('mtab-signin')?.classList.toggle('active',tab==='signin');
  document.getElementById('mtab-signup')?.classList.toggle('active',tab==='signup');
  document.getElementById('form-signin').style.display=tab==='signin'?'block':'none';
  document.getElementById('form-signup').style.display=tab==='signup'?'block':'none';
}

async function doLogin(e) {
  e.preventDefault();
  const email=document.getElementById('l-email').value.trim();
  const pass=document.getElementById('l-pass').value;
  const errEl=document.getElementById('l-err');
  const btn=document.getElementById('btn-signin');
  btn.textContent='Ingresando...'; btn.disabled=true;
  errEl.style.display='none';
  try {
    const res=await fetch(`${API}/auth/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,contrasena:pass})});
    if (!res.ok) throw new Error((await res.json()).detail||'Credenciales incorrectas');
    const data=await res.json();
    _token=data.token; _user=data;
    localStorage.setItem('fm_token',_token);
    localStorage.setItem('fm_email',email);
    localStorage.setItem('fm_user', JSON.stringify(data));
    closeLogin();
    onLoggedIn(email,data.rol);
    if (data.rol==='administrador') {
      showToast('↳ Redirigiendo al panel admin...');
      setTimeout(()=>window.location.href='admin.html',1500);
      return;
    }
    if (data.rol==='tecnico') {
      showToast('↳ Redirigiendo al portal de técnicos...');
      setTimeout(()=>window.location.href='tecnico.html', 900);
      return;
    }
    // Redirect to user panel
    showToast(`✓ Bienvenido ${email.split('@')[0]} — abriendo tu panel...`);
    setTimeout(()=>window.location.href='cliente.html', 900);
  } catch(err) { errEl.textContent=err.message; errEl.style.display='block'; }
  finally { btn.textContent='Ingresar →'; btn.disabled=false; }
}

async function doRegister(e) {
  e.preventDefault();
  const nombre=document.getElementById('r-nombre').value.trim();
  const apellido=document.getElementById('r-apellido').value.trim();
  const email=document.getElementById('r-email').value.trim();
  const tel=document.getElementById('r-tel').value.trim();
  const pass=document.getElementById('r-pass').value;
  const errEl=document.getElementById('r-err');
  const btn=document.getElementById('btn-signup');
  btn.textContent='Creando cuenta...'; btn.disabled=true;
  errEl.style.display='none';
  try {
    const rRes=await fetch(`${API}/auth/register`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,contrasena:pass,rol:'cliente'})});
    if(!rRes.ok) throw new Error((await rRes.json()).detail||'Error al registrar');
    const lRes=await fetch(`${API}/auth/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,contrasena:pass})});
    const lData=await lRes.json();
    _token=lData.token; _user=lData;
    localStorage.setItem('fm_token',_token); localStorage.setItem('fm_email',email);
    // Obtener perfil creado automaticamente
    const meRes = await fetch(`${API}/clientes/me`, {headers: {'Authorization': `Bearer ${_token}`}});
    if (meRes.ok) {
      const meProfile = await meRes.json();
      // Actualizar el perfil con el nombre, apellido y telefono reales
      await fetch(`${API}/clientes/${meProfile.id_cliente}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${_token}`
        },
        body: JSON.stringify({
          nombre: nombre,
          apellido_1: apellido,
          telefono: tel
        })
      });
    }
    closeLogin();
    onLoggedIn(email,'cliente');
    setTimeout(()=>window.location.href='cliente.html', 900);
  } catch(err){errEl.textContent=err.message;errEl.style.display='block';}
  finally{btn.textContent='Crear cuenta →';btn.disabled=false;}
}

function onLoggedIn(email,rol){
  showToast(`✓ Bienvenido, ${email.split('@')[0]}`);
  const lbl=document.getElementById('sb-login-label');
  if(lbl) lbl.textContent=email.split('@')[0];
  const btn=document.getElementById('sb-login-btn');
  if(btn){btn.title='Cerrar sesión';btn.onclick=doLogout;}
  const tBtn=document.getElementById('topbar-user-btn');
  if(tBtn) tBtn.style.borderColor='var(--a)';
}
function doLogout(){localStorage.clear();_token=null;_verified=false;location.reload();}
function checkSession(){
  const t=localStorage.getItem('fm_token'),e=localStorage.getItem('fm_email');
  const v=localStorage.getItem('fm_verified');
  if(t&&e){_token=t;_user={email:e};onLoggedIn(e,'');}
  if(v){_verified=true;}
}

/* ────────────────────────────────────────────────────────────
   GOOGLE SIGN-IN
   ──────────────────────────────────────────────────────────── */
let _gInited = false;
function initGoogleSignIn() {
  if (_gInited) return;
  if (typeof google === 'undefined' || !google.accounts) {
    // Google SDK may not be loaded yet (async/defer) — retry up to 10s
    if (!initGoogleSignIn._retries) initGoogleSignIn._retries = 0;
    if (initGoogleSignIn._retries < 20) {
      initGoogleSignIn._retries++;
      setTimeout(initGoogleSignIn, 500);
    }
    return;
  }

  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleGoogleSignInCallback,
    ux_mode: 'popup'
  });

  const btnDiv = document.getElementById('g_id_signin');
  if (btnDiv) {
    google.accounts.id.renderButton(btnDiv, {
      type: 'standard',
      shape: 'rectangular',
      theme: 'dark',
      text: 'continue_with',
      size: 'large',
      logo_alignment: 'left',
      width: btnDiv.offsetWidth || 280
    });
    _gInited = true;
  }
}
function handleGoogleLogin() {
  // Deprecated - handled automatically by Google button
}
function handleGoogleSignInCallback(response) {
  try {
    const b64 = response.credential.split('.')[1].replace(/-/g,'+').replace(/_/g,'/');
    const payload = JSON.parse(atob(b64 + '=='.slice(0, (4 - b64.length % 4) % 4)));
    const email   = payload.email;
    const nombre  = payload.given_name  || email.split('@')[0];
    const apellido= payload.family_name || '';
    // Deterministic password for Google-only users
    const gPass = 'GAUTH_' + payload.sub;
    _googleAutoAuth(email, gPass, nombre, apellido);
  } catch(err) {
    showToast('⚠ Error procesando cuenta Google: ' + err.message);
    console.error(err);
  }
}
async function _googleAutoAuth(email, pass, nombre, apellido) {
  try {
    // 1. Try login first (returning user)
    let lRes = await fetch(`${API}/auth/login`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ email, contrasena: pass })
    });
    if (!lRes.ok) {
      // 2. Auto-register new Google user
      await fetch(`${API}/auth/register`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ email, contrasena: pass, rol: 'cliente' })
      });
      // 3. Login after registration
      lRes = await fetch(`${API}/auth/login`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ email, contrasena: pass })
      });
    }
    if (!lRes.ok) throw new Error('No se pudo autenticar con Google');
    const data = await lRes.json();
    _token = data.token;
    localStorage.setItem('fm_token', _token);
    localStorage.setItem('fm_email', email);
    localStorage.setItem('fm_google', '1');
    // Create client profile if new user
    if (data.id_usuarios) {
      await fetch(`${API}/clientes`, {
        method:'POST',
        headers:{'Content-Type':'application/json','Authorization':`Bearer ${_token}`},
        body: JSON.stringify({ id_usuario: data.id_usuarios, nombre, apellido_1: apellido })
      }).catch(()=>{}); // Ignore if already exists
    }
    closeLogin();
    onLoggedIn(email, data.rol || 'cliente');
    showToast(`✓ Conectado con Google como ${nombre}`);
    if (data.rol === 'administrador') {
      setTimeout(()=>window.location.href='dashboard/index.html', 900);
    } else {
      setTimeout(()=>window.location.href='cliente/index.html', 900);
    }
  } catch(err) {
    showToast('⚠ Error Google Sign-In: ' + err.message);
    console.error(err);
  }
}

/* ────────────────────────────────────────────────────────────
   MODALS (generic)
   ──────────────────────────────────────────────────────────── */
function openModal(id) {
  const m=document.getElementById(id);
  if(m){m.classList.add('open');document.body.style.overflow='hidden';}
}
function closeModal(id) {
  const m=document.getElementById(id);
  if(m){m.classList.remove('open');document.body.style.overflow='';}
}
document.addEventListener('click',e=>{
  if(e.target.classList.contains('modal-bg')) closeModal(e.target.id);
});
// ESC key closes modals
document.addEventListener('keydown',e=>{
  if(e.key==='Escape') document.querySelectorAll('.modal-bg.open').forEach(m=>closeModal(m.id));
});

function openComingSoon(){openModal('modal-soon');}

/* ────────────────────────────────────────────────────────────
   FAB
   ──────────────────────────────────────────────────────────── */
function toggleFab(){
  const p=document.getElementById('fab-panel'),f=document.getElementById('fab');
  const open=p.classList.toggle('open');
  f.classList.toggle('active',open);
}
function closeFab(){
  document.getElementById('fab-panel')?.classList.remove('open');
  document.getElementById('fab')?.classList.remove('active');
}
document.addEventListener('click',e=>{
  if(!e.target.closest('#fab')&&!e.target.closest('#fab-panel')) closeFab();
});

/* ────────────────────────────────────────────────────────────
   WHATSAPP
   ──────────────────────────────────────────────────────────── */
function openWA(){window.open('https://wa.me/573001234567?text=Hola%2C%20quiero%20información%20sobre%20los%20servicios%20de%20FlyMetrics%20para%20mi%20cultivo.','_blank');}

/* ────────────────────────────────────────────────────────────
   TOAST
   ──────────────────────────────────────────────────────────── */
function showToast(msg){
  const t=document.getElementById('toast');
  if(!t) return;
  t.textContent=msg; t.classList.add('show');
  clearTimeout(_toastT);
  _toastT=setTimeout(()=>t.classList.remove('show'),3200);
}
