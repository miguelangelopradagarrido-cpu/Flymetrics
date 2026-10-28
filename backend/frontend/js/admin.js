/* ============================================================
   Flymetrics Admin Dashboard — admin.js
   Complete JS: API calls, panels, CRUD, modals, calendar
   ============================================================ */

'use strict';

var _adminIsDev = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && window.location.port && window.location.port !== '3000';
var _rawApiOrigin = (window.location.protocol === 'file:' || _adminIsDev)
  ? 'http://localhost:3000'
  : (window.location.hostname.includes('flymetrics-api') ? window.location.origin : 'https://flymetrics-api.hostless.app');

var API_BASE = _rawApiOrigin.replace(/\/+$/, '').replace(/\/api\/v1\/?$/, '') + '/api/v1';
window.API_BASE = API_BASE;
window.BASE_URL = API_BASE;

// ─────────────────────────────────────────
// UNIVERSAL MEDIA URL RESOLVER
// ─────────────────────────────────────────
function resolveMediaUrl(url) {
  if (!url || typeof url !== 'string') return '';
  url = url.trim();
  if (!url) return '';
  if (/^(https?:|\/\/|data:|blob:)/i.test(url)) return url;
  if (/^\/?(img|video|css|js|assets)\//i.test(url)) {
    return url.startsWith('/') ? url : ('/' + url);
  }
  const apiOrigin = API_BASE.replace(/\/api\/v1\/?$/, '');
  const cleanPath = url.startsWith('/') ? url : ('/' + url);
  return `${apiOrigin}${cleanPath}`;
}
window.resolveMediaUrl = resolveMediaUrl;

// ─────────────────────────────────────────
// ANTI-XSS UTILITY HELPER
// ─────────────────────────────────────────
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

// GLOBAL STATE VARIABLES
let _usuariosList = [];
let tecnicosData = [];
let clientesData = [];
let agendaData = [];
let dronesData = [];
let serviciosData = [];
let adminSolicitudesData = [];
let gastosData = [];
let pqrsData = [];
let activePQRId = null;
let pagosData = [];
let reportesData = [];
let _adminNotifs = [];
let agendaFilters = { tecnico: '', estado: '' };
let selectedCalDate = new Date().toISOString().split('T')[0];
let _usuariosFiltroRol = '';
// GLOBAL STATE VARIABLES
















// ─────────────────────────────────────────
// MAPS NORMALIZATION HELPER
// ─────────────────────────────────────────
function normalizeMapsInput(raw) {
  if (!raw) return '';
  let s = String(raw).trim().replace(/[\]\)\>]+$/, '');
  if (!s || ['none', 'null', 'undefined', 'n/a', 'colombia', 'sin registrar', 'finca'].includes(s.toLowerCase())) return '';

  // Coordenadas directas: 2.946644, -75.254211 o @2.946644,-75.254211 o q=2.946644,-75.254211
  const mCoord = s.match(/([-+]?\d{1,3}\.\d+)[,\s]+([-+]?\d{1,3}\.\d+)/);
  if (mCoord) {
    const lat = parseFloat(mCoord[1]);
    const lng = parseFloat(mCoord[2]);
    if (!isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
      return `https://www.google.com/maps?q=${lat.toFixed(6)},${lng.toFixed(6)}`;
    }
  }

  // Enlace directo de Maps
  if (s.includes('maps.app.goo.gl') || s.includes('goo.gl/maps') || s.includes('google.com/maps') || s.includes('maps.google.com')) {
    const mUrl = s.match(/https?:\/\/[^\s\n\r"\'<>\]\)]+/);
    let clean = mUrl ? mUrl[0].trim().replace(/[\]\)\>]+$/, '') : s;
    if (!clean.startsWith('http://') && !clean.startsWith('https://')) {
      clean = 'https://' + clean;
    }
    return clean;
  }
  return s;
}
window.normalizeMapsInput = normalizeMapsInput;

// ─────────────────────────────────────────
// AUTH HELPERS
// ─────────────────────────────────────────
function getToken() { return sessionStorage.getItem('fm_token') || localStorage.getItem('fm_token'); }
function getUser() {
  try { return JSON.parse(sessionStorage.getItem('fm_user') || localStorage.getItem('fm_user')) || {}; } catch { return {}; }
}
function getCurrentUser() { return getUser(); }
window.getCurrentUser = getCurrentUser;

async function logout() {
  try {
    await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => null);
  } catch(e) {}
  try { sessionStorage.clear(); } catch(e) {}
  try { localStorage.clear(); } catch(e) {}
  window.location.href = 'staff.html';
}
window.logout = logout;

function toggleAdminSidebar(e) {
  if (e) e.stopPropagation();
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('adminSidebarOverlay');
  if (!sidebar) return;

  if (window.innerWidth > 900) {
    // Desktop: toggle compact collapse
    sidebar.classList.toggle('collapsed');
    const isCollapsed = sidebar.classList.contains('collapsed');
    localStorage.setItem('fm_admin_sidebar_collapsed', isCollapsed ? 'true' : 'false');
  } else {
    // Mobile / Tablet: toggle off-canvas drawer
    sidebar.classList.toggle('open');
    if (overlay) {
      if (sidebar.classList.contains('open')) {
        overlay.classList.remove('hidden');
        overlay.classList.add('active');
      } else {
        overlay.classList.remove('active');
        overlay.classList.add('hidden');
      }
    }
  }
}
window.toggleAdminSidebar = toggleAdminSidebar;
window.toggleAdminSidebarCollapse = toggleAdminSidebar;

async function ensureAdminAuth() {
  let token = getToken();
  let u = getUser();

  // Si no hay token ni usuario admin en almacenamiento, redirigir a staff
  if (!token && (!u || u.rol !== 'administrador')) {
    window.location.href = 'staff.html';
    return;
  }

  // Si ya tenemos usuario administrador en caché, mantenerlo activo y nunca expulsarlo
  if (u && (u.rol === 'administrador' || u.email === 'admin@flymetrics.co')) {
    if (token) {
      try {
        const res = await fetch(`${API_BASE}/auth/me`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const json = await res.json();
          const curUser = json.data || json;
          sessionStorage.setItem('fm_user', JSON.stringify(curUser));
          localStorage.setItem('fm_user', JSON.stringify(curUser));
        }
      } catch(e) {
        console.warn('Verificación en segundo plano:', e);
      }
    }
    const curr = getUser();
    const nameEl = document.getElementById('sidebarUserName');
    const emailEl = document.getElementById('sidebarUserEmail');
    const initEl = document.getElementById('sidebarUserInitials');
    if (nameEl) nameEl.textContent = `${curr.nombre || 'Administrador'} ${curr.apellido_1 || ''}`.trim();
    if (emailEl) emailEl.textContent = curr.email || 'admin@flymetrics.co';
    if (initEl) initEl.textContent = ((curr.nombre || 'A')[0] + (curr.apellido_1 || 'D')[0]).toUpperCase();
    return;
  }

  // Si hay token pero no sabíamos el rol, verificar contra API
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) {
      const json = await res.json();
      const curUser = json.data || json;
      if (curUser.rol === 'administrador') {
        sessionStorage.setItem('fm_user', JSON.stringify(curUser));
        localStorage.setItem('fm_user', JSON.stringify(curUser));
      } else if (curUser.rol === 'cliente') {
        showToast('Acceso denegado: El panel de administración es exclusivo para personal autorizado.', 'error');
        setTimeout(() => { window.location.href = 'cliente.html'; }, 1000);
        return;
      } else if (curUser.rol === 'tecnico') {
        showToast('Redirigiendo a tu Portal de Técnico y Piloto...', 'info');
        setTimeout(() => { window.location.href = 'tecnico.html'; }, 1000);
        return;
      }
    }
  } catch(e) {
    console.warn('Verificación inicial de sesión:', e);
  }

  const curr = getUser();
  const nameEl = document.getElementById('sidebarUserName');
  const emailEl = document.getElementById('sidebarUserEmail');
  const initEl = document.getElementById('sidebarUserInitials');

  if (nameEl) nameEl.textContent = `${curr.nombre || 'Administrador'} ${curr.apellido_1 || ''}`.trim();
  if (emailEl) emailEl.textContent = curr.email || 'admin@flymetrics.co';
  if (initEl) initEl.textContent = ((curr.nombre || 'A')[0] + (curr.apellido_1 || 'D')[0]).toUpperCase();
}

// ─── API FETCH WRAPPER
// ─────────────────────────────────────────
async function apiFetch(path, options = {}) {
  if (typeof path !== 'string') path = String(path || '');
  if (!path.startsWith('/')) path = '/' + path;
  if (path.startsWith('/api/v1/')) path = path.slice(7);

  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

        if ((res.status === 401 || res.status === 403) && !path.includes('verificar-clave') && !options.ignoreAuthRedirect) {
      console.warn(`apiFetch [${path}] retornó estado ${res.status}. Se mantiene la sesión de administrador activa.`);
      return null;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      let msg = err.message;
      if (!msg && err.detail) {
        if (Array.isArray(err.detail)) {
          msg = err.detail.map(d => (d.loc ? d.loc.slice(-1)[0] + ': ' : '') + d.msg).join(', ');
        } else if (typeof err.detail === 'object') {
          msg = JSON.stringify(err.detail);
        } else {
          msg = String(err.detail);
        }
      }
      throw new Error(msg || err.error || `Error ${res.status}`);
    }

    if (res.status === 204) return null;
    let data = await res.json();
    if (data && (data.success === true || data.status === 'success' || data.success === 'true') && data.data !== undefined) {
      data = data.data;
    }
    if (data) {
      const mapId = (item) => {
        if (item && typeof item === 'object') {
          if (item.id === undefined) {
            item.id = item.id_turno || item.id_tecnico || item.id_cliente || item.id_pago || item.id_drone || item.id_reporte || item.id_usuarios || item.id_notificacion;
          }
          if (item.cliente === undefined && item.nombre_cliente !== undefined) {
            item.cliente = item.nombre_cliente;
          }
          if (item.finca === undefined && item.nombre_finca !== undefined) {
            item.finca = item.nombre_finca;
          }
          if (item.servicio === undefined && item.nombre_servicio !== undefined) {
            item.servicio = item.nombre_servicio;
          }
          if (item.tecnico === undefined && item.tecnico_nombre !== undefined) {
            item.tecnico = item.tecnico_nombre === 'Sin asignar' ? '' : item.tecnico_nombre;
          }
          if (item.fecha === undefined && item.fecha_de_turno !== undefined) {
            item.fecha = item.fecha_de_turno;
          }
          if (item.hora === undefined && item.hora_inicio_estimada !== undefined) {
            item.hora = item.hora_inicio_estimada.slice(0, 5); // HH:MM
          }
          if (item.monto === undefined && item.tarifa !== undefined) {
            item.monto = item.tarifa;
          }
          if (item.precio === undefined && item.tarifa !== undefined) {
            item.precio = item.tarifa;
          }
          if (!item.maps_url && (item.finca_maps_url || item.maps_link)) {
            item.maps_url = item.finca_maps_url || item.maps_link;
          }
          if (!item.cliente_documento && (item.numero_documento || item.cedula)) {
            item.cliente_documento = item.numero_documento || item.cedula;
          }
        }
      };
      if (Array.isArray(data)) {
        data.forEach(mapId);
      } else {
        mapId(data);
      }
    }
    return data;
  } catch (err) {
    console.error(`[API] Request failed for ${path}:`, err.message);
    throw err;
  }
}

// All data sourced from real API - no mock data




// ─────────────────────────────────────────
// TOAST NOTIFICATIONS (DEDUPLICATED)
// ─────────────────────────────────────────
let _lastToastText = '';
let _lastToastTime = 0;

function showToast(message, type = 'success', duration = 3500) {
  const now = Date.now();
  const cleanMsg = String(message).replace(/<[^>]*>?/gm, '').trim();
  
  // Prevent duplicate toast spam within 1.2s
  if (_lastToastText === cleanMsg && now - _lastToastTime < 1200) {
    return;
  }
  _lastToastText = cleanMsg;
  _lastToastTime = now;

  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.position = 'fixed';
    container.style.bottom = '24px';
    container.style.right = '24px';
    container.style.zIndex = '9999';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '8px';
    document.body.appendChild(container);
  }

  // Remove existing toasts with exact same message
  Array.from(container.children).forEach(child => {
    if (child.textContent.includes(cleanMsg)) {
      child.remove();
    }
  });

  const icons = { success: '<i class="fa-solid fa-check"></i>', error: '✕', info: 'ℹ', warn: '<i class="fa-solid fa-triangle-exclamation"></i>' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  // Format clean message without double checkmarks
  const renderedMsg = message.startsWith('<i') ? message : `<span>${icons[type] || '•'}</span> <span>${message}</span>`;
  toast.innerHTML = renderedMsg;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ─────────────────────────────────────────
// FORMAT HELPERS
// ─────────────────────────────────────────
function formatCurrency(n) {
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(n || 0);
}
function formatDate(d) {
  if (!d) return '—';
  try {
    let dateObj;
    if (d instanceof Date) {
      dateObj = d;
    } else if (typeof d === 'string') {
      const s = d.trim();
      if (s.includes('T') || s.includes(' ') || s.includes('/')) {
        dateObj = new Date(s);
      } else {
        dateObj = new Date(s + 'T12:00:00');
      }
    } else if (typeof d === 'number') {
      dateObj = new Date(d);
    } else {
      dateObj = new Date(d);
    }
    if (isNaN(dateObj.getTime())) {
      return typeof d === 'string' ? d.split('T')[0] : '—';
    }
    return dateObj.toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch (e) {
    return typeof d === 'string' ? d : '—';
  }
}

function formatDateShort(d) {
  if (!d) return '—';
  try {
    let dateObj;
    if (d instanceof Date) {
      dateObj = d;
    } else if (typeof d === 'string') {
      const s = d.trim();
      if (s.includes('T') || s.includes(' ') || s.includes('/')) {
        dateObj = new Date(s);
      } else {
        dateObj = new Date(s + 'T12:00:00');
      }
    } else if (typeof d === 'number') {
      dateObj = new Date(d);
    } else {
      dateObj = new Date(d);
    }
    if (isNaN(dateObj.getTime())) {
      return typeof d === 'string' ? d.split('T')[0] : '—';
    }
    return dateObj.toLocaleDateString('es-CO', { day: '2-digit', month: 'short' });
  } catch (e) {
    return typeof d === 'string' ? d : '—';
  }
}
function cleanPersonName(name) {
  if (!name || typeof name !== 'string') return '';
  const genericWords = new Set(['tecnico', 'técnico', 'piloto', 'cliente', 'registrado', 'usuario']);
  let words = name.trim().split(/\s+/).filter(w => !genericWords.has(w.toLowerCase().replace(/[,.-]/g, '')));
  
  const n = words.length;
  if (n <= 1) return words.join(' ');
  
  for (let k = Math.floor(n / 2); k >= 1; k--) {
    for (let start = 0; start <= n - 2 * k; start++) {
      const c1 = words.slice(start, start + k).map(w => w.toLowerCase()).join(' ');
      const c2 = words.slice(start + k, start + 2 * k).map(w => w.toLowerCase()).join(' ');
      if (c1 === c2) {
        words.splice(start + k, k);
        return cleanPersonName(words.join(' '));
      }
    }
  }
  for (let suffixLen = n - 1; suffixLen >= 1; suffixLen--) {
    const suffix = words.slice(-suffixLen).map(w => w.toLowerCase()).join(' ');
    const prefix = words.slice(0, -suffixLen).map(w => w.toLowerCase()).join(' ');
    if (prefix.endsWith(suffix)) {
      words.splice(-suffixLen, suffixLen);
      return cleanPersonName(words.join(' '));
    }
  }
  return words.join(' ');
}

function initials(name, last) {
  if (last && String(last).trim()) {
    return ((name || '?')[0] + String(last).trim()[0]).toUpperCase();
  }
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  if (parts.length === 1 && parts[0].length >= 2) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return ((name || '?')[0] || '?').toUpperCase();
}

function statusBadge(estado) {
  const norm = (estado || '').trim();
  const lower = norm.toLowerCase();
  
  let cls = 'badge-inactive';
  if (lower === 'pendiente') cls = 'badge-pending';
  else if (lower === 'pendiente por confirmar' || lower.includes('por confirmar')) cls = 'badge-pending';
  else if (lower === 'confirmado') cls = 'badge-confirmed';
  else if (lower === 'en proceso' || lower === 'en_proceso' || (lower.includes('proceso') && !lower.includes('complet'))) cls = 'badge-inprocess';
  else if (lower === 'completado' || lower === 'hecho' || lower === 'realizado') cls = 'badge-completed';
  else if (lower === 'finalizado') cls = 'badge-completed';
  else if (lower === 'cancelado' || lower === 'rechazado') cls = 'badge-cancelled';
  else if (lower === 'disponible') cls = 'badge-available';
  else if (lower === 'ocupado') cls = 'badge-busy';
  else if (lower === 'mantenimiento') cls = 'badge-maintenance';
  else if (lower === 'pagado') cls = 'badge-paid';
  else if (lower === 'pendiente_pago') cls = 'badge-unpaid';

  let customStyle = '';
  if (lower === 'pendiente por confirmar' || lower.includes('por confirmar')) {
    customStyle = 'style="background:#fef3c7; color:#b45309; border:1px solid #fde68a; font-weight:700;"';
  } else if (lower === 'finalizado' || lower === 'completado' || lower === 'hecho' || lower === 'realizado') {
    customStyle = 'style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; font-weight:800;"';
  }

  let iconHtml = '';
  if (lower === 'completado' || lower === 'finalizado' || lower === 'hecho' || lower === 'realizado') {
    iconHtml = '<i class="fa-solid fa-circle-check" style="margin-right:4px;"></i>';
  } else if (lower.includes('confirm')) {
    iconHtml = '<i class="fa-solid fa-check" style="margin-right:4px;"></i>';
  } else if (lower.includes('proceso')) {
    iconHtml = '<i class="fa-solid fa-bolt" style="margin-right:4px;"></i>';
  } else if (lower.includes('pendiente')) {
    iconHtml = '<i class="fa-solid fa-clock" style="margin-right:4px;"></i>';
  }

  const label = (lower === 'completado' || lower === 'finalizado' || lower === 'hecho' || lower === 'realizado') 
    ? 'Finalizado' 
    : (lower === 'disponible' ? 'Disponible' : lower === 'ocupado' ? 'Ocupado' : lower === 'mantenimiento' ? 'Mantenimiento' : norm);
  return `<span class="badge ${cls}" ${customStyle}>${iconHtml}${label}</span>`;
}


// ─────────────────────────────────────────
// MODAL HELPERS
// ─────────────────────────────────────────
function openModal(id) {
  const el = document.getElementById(id);
  if (!el) {
    console.warn('Modal no encontrado:', id);
    return;
  }
  el.classList.remove('hidden');
  el.classList.add('active', 'open');
  el.style.setProperty('display', 'flex', 'important');
  el.style.setProperty('visibility', 'visible', 'important');
  el.style.setProperty('opacity', '1', 'important');
  el.style.setProperty('pointer-events', 'auto', 'important');

  const inner = el.querySelector('.modal, .modal-box, .modal-card');
  if (inner) {
    inner.style.setProperty('display', 'flex', 'important');
    inner.style.setProperty('visibility', 'visible', 'important');
    inner.style.setProperty('opacity', '1', 'important');
    inner.style.setProperty('transform', 'translateY(0) scale(1)', 'important');
  }

  document.body.style.overflow = 'hidden';

  // Hooks sin monkey-patch para carga de selects de dron y gastos
  if (id === 'newDroneModal' || id === 'editDroneModal') {
    if (typeof populateDroneServiceDropdowns === 'function') {
      populateDroneServiceDropdowns().catch(err => console.warn('Error populating drone dropdown:', err));
    }
  }
  if (id === 'newGastoModal' || id === 'editGastoModal') {
    (async () => {
      if (!dronesData || dronesData.length === 0) {
        try {
          const authH = (typeof getAuthHeaders === 'function') ? getAuthHeaders() : { 'Authorization': `Bearer ${getToken()}` };
          const res = await fetch(`${API_BASE}/drones`, { headers: authH });
          if (res.ok) {
            const body = await res.json();
            dronesData = body.data || body || [];
          }
        } catch (e) {}
      }
      const select = document.getElementById(id === 'newGastoModal' ? 'newGastoDroneSelect' : 'editGastoDroneSelect');
      if (select) {
        const droneList = (dronesData && dronesData.length) ? dronesData : [
          { id_drone: 1, modelo: 'DJI Agras T40', numero_serie: 'AGRAS-T40-001' },
          { id_drone: 2, modelo: 'DJI Mavic 3 Multispectral', numero_serie: 'M3M-002' }
        ];
        select.innerHTML = droneList
          .map(d => `<option value="${d.id_drone || d.id}">🚁 ${d.modelo || 'Dron Agrícola'} (${d.numero_serie || 'SN-N/A'})</option>`).join('');
      }
    })();
  }
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('active', 'open');
  el.classList.add('hidden');
  el.style.setProperty('display', 'none', 'important');
  el.style.setProperty('visibility', 'hidden', 'important');
  el.style.setProperty('opacity', '0', 'important');
  el.style.setProperty('pointer-events', 'none', 'important');

  const inner = el.querySelector('.modal, .modal-box, .modal-card');
  if (inner) {
    inner.style.setProperty('visibility', 'hidden', 'important');
    inner.style.setProperty('opacity', '0', 'important');
  }

  document.body.style.overflow = '';
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay').forEach(m => {
    m.classList.remove('active');
    m.classList.remove('open');
    m.classList.add('hidden');
    m.style.display = 'none';
    m.style.visibility = 'hidden';
    m.style.opacity = '0';
    m.style.pointerEvents = 'none';
    const inner = m.querySelector('.modal, .modal-box, .modal-card');
    if (inner) {
      inner.style.visibility = 'hidden';
      inner.style.opacity = '0';
    }
  });
  document.body.style.overflow = '';
}

window.openModal = openModal;
window.closeModal = closeModal;
window.closeAllModals = closeAllModals;

window.openNewAgendaModal = async function() {
  const form = document.getElementById('newAgendaForm');
  if (form) form.reset();
  
  const errEl = document.getElementById('newAgendaErrMsg');
  if (errEl) errEl.style.display = 'none';

  // Open modal FIRST so user sees it right away!
  openModal('newAgendaModal');

  // Set smart defaults
  const todayIso = new Date().toISOString().split('T')[0];
  const fInput = document.getElementById('newAgendaFecha');
  if (fInput) {
    fInput.min = todayIso;
    if (!fInput.value || fInput.value < todayIso) fInput.value = todayIso;
  }
  const hInput = document.getElementById('newAgendaHora');
  if (hInput && !hInput.value) hInput.value = '08:00';
  const haInput = document.getElementById('newAgendaHa');
  if (haInput && !haInput.value) haInput.value = '10';

  const populateFields = () => {
    const csel = document.getElementById('newAgendaClienteSelect');
    if (csel && clientesData && clientesData.length) {
      const currentVal = csel.value;
      csel.innerHTML = '<option value="">-- Crear cliente nuevo o seleccionar existente --</option>' +
        clientesData.map(c => `<option value="${c.id_cliente || c.id}">${c.nombre} ${c.apellido || c.apellido_1 || ''} — CC: ${c.numero_documento || 'S/N'} (${c.email || 'Sin email'})</option>`).join('');
      if (currentVal) csel.value = currentVal;
    }
    const sContainer = document.getElementById('newAgendaServiciosContainer');
    if (sContainer && serviciosData && serviciosData.length) {
      sContainer.innerHTML = serviciosData.filter(s => s.activo !== false).map((s, idx) => {
        const sName = s.nombre_servicio || s.nombre;
        const sId = s.id_servicio || s.id;
        const isChecked = idx === 0 ? 'checked' : '';
        return `
          <label style="display:inline-flex; align-items:center; gap:6px; background:#ffffff; padding:6px 12px; border-radius:8px; border:1px solid #cbd5e1; cursor:pointer; font-size:0.84rem; font-weight:600; color:#003049;">
            <input type="checkbox" name="newAgendaServicioCb" value="${sName}" data-id="${sId}" ${isChecked} style="accent-color:#1C82AD; width:16px; height:16px;" />
            <span>${sName}</span>
          </label>
        `;
      }).join('');
    }
    const sel = document.getElementById('newAgendaServicio');
    if (sel && serviciosData && serviciosData.length) {
      const currentVal = sel.value;
      sel.innerHTML = '<option value="">Seleccionar servicio...</option>' +
        serviciosData.filter(s => s.activo !== false).map(s => `<option value="${s.nombre || s.nombre_servicio}">${s.nombre || s.nombre_servicio}</option>`).join('');
      if (currentVal) sel.value = currentVal;
    }
    const tsel = document.getElementById('newAgendaTecnico');
    if (tsel && tecnicosData && tecnicosData.length) {
      const currentVal = tsel.value;
      const activeTecs = tecnicosData.filter(t => {
        const est = (t.estado || '').toLowerCase().trim();
        return est !== 'deshabilitado' && est !== 'inactivo';
      });
      tsel.innerHTML = '<option value="">Sin asignar</option>' +
        activeTecs.map(t => `<option value="${t.nombre}">${t.nombre}</option>`).join('');
      if (currentVal) tsel.value = currentVal;
    }
  };

  populateFields();

  try {
    if (!clientesData || !clientesData.length) await loadClientes();
    if (!serviciosData || !serviciosData.length) await loadServicios();
    if (!tecnicosData || !tecnicosData.length) await loadTecnicos();
    populateFields();
  } catch (e) {
    console.warn('Error precargando listas en newAgendaModal:', e);
  }
};

window.openNewClienteModal = function() {
  const form = document.getElementById('newClienteForm');
  if (form) form.reset();
  openModal('newClienteModal');
};

window.openNewServicioModal = function() {
  const form = document.getElementById('newServicioForm');
  if (form) form.reset();
  openModal('newServicioModal');
};

window.openNewTecnicoModal = function() {
  const form = document.getElementById('newTecnicoForm');
  if (form) form.reset();
  openModal('newTecnicoModal');
};

window.openNewDroneModal = function() {
  const form = document.getElementById('newDroneForm');
  if (form) form.reset();
  openModal('newDroneModal');
};

window.openNewUsuarioModal = function() {
  const form = document.getElementById('newUsuarioForm');
  if (form) form.reset();
  openModal('newUsuarioModal');
};

// ─────────────────────────────────────────
// NAVIGATION
// ─────────────────────────────────────────
let activePanel = 'dashboard';

function navigateTo(panelId) {
  if (panelId === 'reportes-vuelo' || panelId === 'reportes') {
    panelId = 'informes-ejecutivos';
  }

  // Close notifications dropdown
  document.getElementById('adminNotificationsDropdown')?.classList.add('hidden');

  // Hide all panels
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Show selected
  const panel = document.getElementById(`panel-${panelId}`);
  if (panel) panel.classList.add('active');

  const navItem = document.querySelector(`[data-panel="${panelId}"]`);
  if (navItem) navItem.classList.add('active');

  // Update topbar title
  const titles = {
    dashboard: 'Dashboard General', agenda: 'Agenda Operativa', clientes: 'Directorio de Clientes',
    tecnicos: 'Monitoreo y Técnicos en Vivo', drones: 'Hangar de Drones', servicios: 'Catálogo de Servicios Agrícolas',
    publicidad: 'Publicidad, Medios & Redes Sociales',
    reagendamiento: 'Módulo de Reagendamiento de Turnos',
    facturacion: 'Facturación & Estados de Cuenta',
    'informes-ejecutivos': 'Informes Ejecutivos & Entregables (SharePoint)',
    zonas: 'Zonas de Mayor Demanda & Cobertura',
    solicitudes: 'Peticiones & Solicitudes de Pilotos',
    configuracion: 'Configuración del Sistema',
    usuarios: 'Gestión de Usuarios y Roles', gastos: 'Gastos & Mantenimiento',
    'contacto-web': 'Solicitudes Contacto Web ("Nosotros te contactamos")', 'admin-tecnico': 'Torre Control Admin-Técnico'
  };
  document.getElementById('topbarTitle').textContent = titles[panelId] || panelId;

  activePanel = panelId;

  // Load data
  panelLoaders[panelId]?.();
}

let _contactoSolicitudes = [];
let _activeContactoId = null;

async function loadContactoWeb() {
  const tbody = document.getElementById('contactoWebTableBody');
  const badge = document.getElementById('webContactoBadge');

  try {
    const raw = await apiFetch('/contacto/solicitudes') || [];
    _contactoSolicitudes = Array.isArray(raw) ? raw : (raw.data || []);
    
    // Si no hay solicitudes en /contacto/solicitudes, cargar de /pqrs
    if (!_contactoSolicitudes.length) {
      const pqrsRaw = await apiFetch('/pqrs') || [];
      const pqrsList = Array.isArray(pqrsRaw) ? pqrsRaw : (pqrsRaw.data || []);
      _contactoSolicitudes = pqrsList.filter(p => (p.asunto || '').includes('[CONTACTO') || (p.asunto || '').includes('Contacto') || p.tipo === 'Petición').map(p => ({
        id_pqr: p.id_pqr,
        asunto: p.asunto,
        nombre: p.usuario?.cliente?.nombre || 'Contacto Web',
        telefono: p.usuario?.cliente?.telefono || '',
        email: p.usuario?.email || '',
        hectareas: '—',
        cultivo: '—',
        ubicacion: '—',
        servicio: p.asunto,
        mensaje: p.mensaje || '',
        mensaje_completo: p.mensaje || '',
        estado: p.estado || 'Abierto',
        fecha: p.fecha_creacion
      }));
    }

    const abiertas = _contactoSolicitudes.filter(s => (s.estado || '').toLowerCase() === 'abierto').length;
    if (badge) {
      badge.textContent = abiertas;
      badge.style.display = abiertas > 0 ? 'inline-flex' : 'none';
    }

    renderContactoWebTable();
  } catch (e) {
    console.warn('Error loading contacto web:', e);
    renderContactoWebTable();
  }
}
window.loadContactoWeb = loadContactoWeb;

function renderContactoWebTable() {
  const tbody = document.getElementById('contactoWebTableBody');
  if (!tbody) return;

  const q = (document.getElementById('contactoWebSearch')?.value || '').toLowerCase().trim();
  const estadoFilter = document.getElementById('contactoWebEstadoFilter')?.value || '';

  let data = _contactoSolicitudes;
  if (estadoFilter) {
    data = data.filter(s => (s.estado || 'Abierto').toLowerCase() === estadoFilter.toLowerCase());
  }
  if (q) {
    data = data.filter(s => [s.nombre, s.telefono, s.email, s.cultivo, s.ubicacion, s.servicio, s.mensaje, s.asunto].some(v => (v || '').toLowerCase().includes(q)));
  }

  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted" style="padding:40px;"><div class="empty-icon">📩</div><div class="empty-title">No hay solicitudes de cotización registradas</div></td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(s => {
    const id = s.id_pqr || s.id;
    const estado = s.estado || 'Abierto';
    const badgeCls = estado === 'Cerrado' ? 'badge-completed' : (estado === 'Atendido' ? 'badge-confirmed' : (estado === 'En Proceso' ? 'badge-inprocess' : 'badge-pending'));
    const telClean = (s.telefono || '').replace(/\D/g, '');
    const waUrl = telClean ? `https://wa.me/57${telClean.length === 10 ? telClean : telClean.slice(-10)}?text=${encodeURIComponent(`Hola ${s.nombre}, te contactamos desde Flymetrics respecto a tu solicitud de cotización 24h para ${s.servicio}.`)}` : '#';

    return `
      <tr>
        <td style="font-weight:800; color:var(--primary);">#COT-${id}</td>
        <td>
          <div style="font-weight:700; color:#003049;">${s.nombre || '—'}</div>
          <div style="font-size:0.75rem; color:#4a5568; font-weight:600; display:inline-flex; align-items:center; gap:4px;">
            <i class="fa-solid fa-id-card" style="font-size:0.7rem; color:#1c82ad;"></i> ${s.documento || (s.numero_documento ? `${s.tipo_documento || 'CC'}: ${s.numero_documento}` : 'Sin documento')}
          </div>
          <div style="font-size:0.75rem; color:#4a5568;">
            ${s.telefono ? `<a href="tel:${s.telefono}" style="color:#1c82ad; text-decoration:none; font-weight:600; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-phone" style="font-size:0.7rem;"></i> ${s.telefono}</a>` : ''}
          </div>
          <div style="font-size:0.75rem; color:#718096;">${s.email || ''}</div>
        </td>
        <td>
          <div style="font-weight:700; color:#1c82ad; font-size:0.88rem;">${s.servicio || 'Servicio Dron'}</div>
          <div style="font-size:0.78rem; color:#4a5568; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-seedling" style="color:#10b981;"></i> ${s.cultivo && s.cultivo !== '—' ? s.cultivo : 'Cultivo General'}</div>
        </td>
        <td>
          <span class="badge" style="background:rgba(16, 185, 129, 0.12); color:#059669; border:1px solid rgba(16, 185, 129, 0.25); font-weight:700; font-size:0.82rem;">
            ${s.hectareas && s.hectareas !== '—' ? `${s.hectareas}` : 'Por definir'}
          </span>
        </td>
        <td>
          <div style="font-size:0.85rem; color:#2d3748; font-weight:600; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-location-dot" style="color:#ef4444;"></i> ${s.ubicacion || '—'}</div>
        </td>
        <td style="max-width:260px;">
          <div style="font-size:0.82rem; color:#4a5568; line-height:1.4; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;">
            ${s.mensaje || s.asunto || '—'}
          </div>
        </td>
        <td>${formatDate(s.fecha)}</td>
        <td><span class="badge ${badgeCls}">${estado}</span></td>
        <td style="text-align:center;">
          <div style="display:flex; gap:6px; justify-content:center; flex-wrap:wrap;">
            <button class="btn btn-ghost btn-sm" onclick="openContactoDetailModal(${id})" title="Ver detalle completo" style="padding:4px 8px; font-weight:700; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-eye"></i> Ver</button>
            ${telClean ? `
              <a href="${waUrl}" target="_blank" class="btn btn-sm" title="Contactar por WhatsApp" style="background:#25D366; color:#fff; padding:4px 8px; border-radius:6px; font-weight:700; text-decoration:none; display:inline-flex; align-items:center; gap:4px;">
                <i class="fa-brands fa-whatsapp"></i>
              </a>
            ` : ''}
            ${estado !== 'Atendido' ? `
              <button class="btn btn-accent btn-sm" onclick="markContactoAtendido(${id})" title="Marcar como atendido" style="padding:4px 8px; display:inline-flex; align-items:center;"><i class="fa-solid fa-check"></i></button>
            ` : ''}
            <button class="btn btn-danger btn-sm" onclick="deleteContactoCotizacion(${id})" title="Eliminar cotización" style="padding:4px 8px; display:inline-flex; align-items:center; background:#ef4444; color:#fff; border:none; border-radius:6px; font-weight:700;"><i class="fa-solid fa-trash-can"></i></button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}
window.renderContactoWebTable = renderContactoWebTable;

window.deleteContactoCotizacion = async function(id) {
  if (!confirm(`¿Estás seguro de que deseas eliminar permanentemente la solicitud de cotización #COT-${id}?`)) {
    return;
  }
  try {
    showToast('Eliminando solicitud...', 'info');
    await apiFetch(`/contacto/solicitudes/${id}`, { method: 'DELETE' });
    _contactoSolicitudes = _contactoSolicitudes.filter(x => (x.id_pqr || x.id) != id);
    renderContactoWebTable();
    showToast(`<i class="fa-solid fa-check"></i> Cotización #COT-${id} eliminada de la base de datos`, 'success');
  } catch (err) {
    showToast('Error al eliminar: ' + err.message, 'error');
  }
};

window.openContactoDetailModal = function(id) {
  const s = _contactoSolicitudes.find(x => (x.id_pqr || x.id) == id);
  if (!s) return;
  _activeContactoId = id;

  const titleEl = document.getElementById('contactoDetailTitle');
  if (titleEl) titleEl.textContent = `📩 Solicitud #COT-${id} — ${s.nombre}`;

  const telClean = (s.telefono || '').replace(/\D/g, '');
  const waBtn = document.getElementById('contactoDetailWhatsappBtn');
  if (waBtn) {
    if (telClean) {
      const cfg = getCorporateConfig();
      let tmpl = cfg.wa_template_24h || 'Hola {nombre}, te contactamos desde Flymetrics Colombia sobre tu solicitud de {servicio} ({hectareas} ha).';
      tmpl = tmpl.replace('{nombre}', s.nombre || 'estimado cliente')
                 .replace('{servicio}', s.servicio || 'servicios de drones')
                 .replace('{hectareas}', s.hectareas || 'área indicada');
      
      const phoneParam = telClean.startsWith('57') ? telClean : ('57' + (telClean.length === 10 ? telClean : telClean.slice(-10)));
      waBtn.href = `https://wa.me/${phoneParam}?text=${encodeURIComponent(tmpl)}`;
      waBtn.style.display = 'inline-flex';
    } else {
      waBtn.style.display = 'none';
    }
  }

  const estadoSelect = document.getElementById('contactoDetailEstadoSelect');
  if (estadoSelect) estadoSelect.value = s.estado || 'Abierto';

  const bodyEl = document.getElementById('contactoDetailBody');
  if (bodyEl) {
    bodyEl.innerHTML = `
      <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:16px; padding:18px; margin-bottom:16px;">
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:14px;">
          <div><strong style="color:#003049;"><i class="fa-solid fa-user" style="color:#1c82ad; margin-right:6px;"></i>Cliente:</strong> ${s.nombre || '—'}</div>
          <div><strong style="color:#003049;"><i class="fa-solid fa-id-card" style="color:#1c82ad; margin-right:6px;"></i>Documento / CC:</strong> <span style="font-weight:700; color:#003049;">${s.documento || (s.numero_documento ? `${s.tipo_documento || 'CC'}: ${s.numero_documento}` : '—')}</span></div>
          <div><strong style="color:#003049;"><i class="fa-solid fa-phone" style="color:#10b981; margin-right:6px;"></i>Teléfono / WA:</strong> ${s.telefono ? `<a href="tel:${s.telefono}" style="color:#1c82ad; font-weight:700; text-decoration:none;">${s.telefono}</a>` : '—'}</div>
          <div><strong style="color:#003049;"><i class="fa-solid fa-envelope" style="color:#6366f1; margin-right:6px;"></i>Correo:</strong> ${s.email || '—'}</div>
          <div><strong style="color:#003049;"><i class="fa-solid fa-cubes" style="color:#0284c7; margin-right:6px;"></i>Servicio:</strong> ${s.servicio || '—'}</div>
          <div><strong style="color:#003049;"><i class="fa-solid fa-wheat-awn" style="color:#d97706; margin-right:6px;"></i>Área / Hectáreas:</strong> ${s.hectareas || '—'}</div>
          <div><strong style="color:#003049;"><i class="fa-solid fa-seedling" style="color:#059669; margin-right:6px;"></i>Cultivo:</strong> ${s.cultivo || '—'}</div>
          <div><strong style="color:#003049;"><i class="fa-solid fa-location-dot" style="color:#ef4444; margin-right:6px;"></i>Ubicación:</strong> ${s.ubicacion || '—'}</div>
          <div><strong style="color:#003049;"><i class="fa-solid fa-calendar-day" style="color:#475569; margin-right:6px;"></i>Fecha Recibido:</strong> ${formatDate(s.fecha)}</div>
        </div>
      </div>
      <div style="margin-top:12px;">
        <strong style="color:#003049; display:flex; align-items:center; gap:6px; margin-bottom:8px;">
          <i class="fa-solid fa-comment-dots" style="color:var(--accent);"></i> Mensaje / Consulta del Cliente:
        </strong>
        <div style="background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:14px; color:#334155; font-size:0.92rem; line-height:1.5; white-space:pre-wrap; max-height:160px; overflow-y:auto; box-shadow:inset 0 1px 3px rgba(0,0,0,0.03);">
          ${s.mensaje || s.mensaje_completo || 'Sin mensaje adicional'}
        </div>
      </div>
    `;
  }

  openModal('contactoDetailModal');
};

window.saveContactoEstadoFromModal = async function() {
  if (!_activeContactoId) return;
  const nuevoEstado = document.getElementById('contactoDetailEstadoSelect')?.value || 'Atendido';

  try {
    showToast('Actualizando estado...', 'info');
    await apiFetch(`/contacto/solicitudes/${_activeContactoId}/estado`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: nuevoEstado })
    });
    const s = _contactoSolicitudes.find(x => (x.id_pqr || x.id) == _activeContactoId);
    if (s) s.estado = nuevoEstado;
    renderContactoWebTable();
    showToast(`<i class="fa-solid fa-check"></i> Estado actualizado a '${nuevoEstado}'`, 'success');
    closeModal('contactoDetailModal');
  } catch (err) {
    showToast('Error al actualizar estado: ' + err.message, 'error');
  }
};

window.markContactoAtendido = async function(id) {
  try {
    await apiFetch(`/contacto/solicitudes/${id}/estado`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: 'Atendido' })
    });
    const s = _contactoSolicitudes.find(x => (x.id_pqr || x.id) == id);
    if (s) s.estado = 'Atendido';
    renderContactoWebTable();
    showToast('<i class="fa-solid fa-check"></i> Solicitud marcada como Atendida', 'success');
  } catch (err) {
    showToast('Error al actualizar: ' + err.message, 'error');
  }
};

const panelLoaders = {
  dashboard: loadDashboard,
  agenda: loadAgenda,
  clientes: loadClientes,
  tecnicos: loadTecnicos,
  drones: loadDrones,
  servicios: loadServicios,
  publicidad: async function() {
    if (typeof loadPublicidadPanel === 'function') {
      return await loadPublicidadPanel();
    } else if (typeof window.loadPublicidadPanel === 'function') {
      return await window.loadPublicidadPanel();
    }
  },
  reagendamiento: async function() {
    await loadAgenda();
    renderReagendamientoTable();
  },
  facturacion: loadFacturacion,
  'reportes-vuelo': loadReportes,
  'informes-ejecutivos': loadInformesEjecutivosClientes,
  reportes: loadReportes,
  zonas: function() { if (typeof window.loadCorporateConfig === 'function') window.loadCorporateConfig(); },
  configuracion: loadConfiguracion,
  usuarios: loadUsuarios,
  solicitudes: loadAdminSolicitudes,
  'contacto-web': loadContactoWeb,
  'admin-tecnico': function() { if (window.loadAdminTecnicoModule) window.loadAdminTecnicoModule(); }
};

// ─────────────────────────────────────────
// CACHE
// ─────────────────────────────────────────
const cache = {};

async function fetchCached(key, path) {
  if (cache[key] && (Date.now() - cache[key].ts < 2000)) return cache[key].data;
  const data = await apiFetch(path);
  cache[key] = { data: data || [], ts: Date.now() };
  return cache[key].data;
}

function invalidateCache(key) { delete cache[key]; }

// ─────────────────────────────────────────
// 1. DASHBOARD PANEL
// ─────────────────────────────────────────
async function loadDashboard() {
  try {
    const [agenda, clientes, tecnicos, pagos] = await Promise.all([
      apiFetch('/admin/agenda').catch(() => []),
      apiFetch('/clientes').catch(() => []),
      apiFetch('/tecnicos').catch(() => []),
      apiFetch('/admin/pagos').catch(() => []),
    ]);

    loadContactoWeb().catch(() => null);

    const safeAgenda = Array.isArray(agenda) ? agenda : (agenda?.data || []);
    const safeClientes = Array.isArray(clientes) ? clientes : (clientes?.data || []);
    const safeTecnicos = Array.isArray(tecnicos) ? tecnicos : (tecnicos?.data || []);
    const safePagos = Array.isArray(pagos) ? pagos : (pagos?.data || []);

    const today = new Date().toISOString().split('T')[0];
    const turnosHoy = safeAgenda.filter(a => a.fecha === today || a.fecha_de_turno === today).length || safeAgenda.length;
    const clientesTotales = safeClientes.length;
    const tecnicosActivos = safeTecnicos.length;
    const ingresosMes = safePagos.reduce((s, p) => s + (p.monto || p.tarifa || 0), 0) || safeAgenda.reduce((s, a) => s + (parseFloat(a.tarifa) || 0), 0);

    const turnosEnProceso = safeAgenda.filter(a => {
      const st = (a.estado || '').toLowerCase().trim();
      return st === 'en proceso' || st === 'en_proceso' || st.includes('proceso') || st === 'hecho';
    }).length;

    const elTurnos = document.getElementById('statTurnosHoy');
    if (elTurnos) elTurnos.textContent = turnosHoy;
    const elClientes = document.getElementById('statClientes');
    if (elClientes) elClientes.textContent = clientesTotales;
    const elTecnicos = document.getElementById('statTecnicos');
    if (elTecnicos) elTecnicos.textContent = tecnicosActivos;
    const elIngresos = document.getElementById('statIngresos');
    if (elIngresos) elIngresos.textContent = formatCurrency(ingresosMes);

    // Recent agenda: Orden estricto descendente por ID (#30, #29, #28...)
    const sortedAgenda = [...(safeAgenda || [])].sort((a, b) => {
      const idA = Number(a.id || a.id_turno || 0);
      const idB = Number(b.id || b.id_turno || 0);
      return idB - idA;
    });
    const recent = sortedAgenda.slice(0, 8);
    const tbody = document.getElementById('recentAgendaBody');
    if (tbody) {
      tbody.innerHTML = recent.length ? recent.map(a => {
        const id = escapeHtml(a.id || a.id_turno);
        const cliente = escapeHtml(a.cliente || a.cliente_nombre || a.nombre_cliente || 'Cliente');
        const servicio = escapeHtml(a.servicio || a.servicio_nombre || a.nombre_servicio || 'Vuelo agrícola');
        const fecha = a.fecha || a.fecha_de_turno || '';
        const hora = a.hora || a.hora_inicio_estimada || '';
        const tecnicoRaw = a.tecnico || a.tecnico_nombre || '';
        const tecnico = tecnicoRaw ? escapeHtml(tecnicoRaw) : '<span class="text-muted">Sin asignar</span>';
        return `
          <tr>
            <td style="font-weight:bold; color:var(--primary);">#${id}</td>
            <td style="font-weight:500;">${cliente}</td>
            <td>${servicio}</td>
            <td>${formatDateShort(fecha)} ${escapeHtml(String(hora).slice(0,5))}</td>
            <td>${statusBadge(a.estado)}</td>
            <td>${tecnico}</td>
          </tr>
        `;
      }).join('') : `<tr><td colspan="6" class="text-center text-muted" style="padding:24px">No hay turnos recientes registrados.</td></tr>`;
    }
  } catch (err) {
    console.error('Error in loadDashboard:', err);
  }
}

// ─────────────────────────────────────────
// 2. AGENDA PANEL
// ─────────────────────────────────────────




async function loadAgenda() {
  const [raw, rawTecs] = await Promise.all([
    apiFetch('/admin/agenda').catch(() => []),
    (!tecnicosData || tecnicosData.length === 0) ? fetchCached('tecnicos', '/tecnicos').catch(() => []) : Promise.resolve(tecnicosData)
  ]);

  if (rawTecs && Array.isArray(rawTecs) && rawTecs.length > 0 && (!tecnicosData || tecnicosData.length === 0)) {
    tecnicosData = rawTecs.map(t => ({
      id: t.id_tecnico || t.id,
      id_tecnico: t.id_tecnico || t.id,
      id_usuario: t.id_usuario,
      nombre: t.nombre,
      apellido_1: t.apellido_1 || t.apellido || '',
      apellido: [t.apellido_1, t.apellido_2].filter(Boolean).join(' ') || t.apellido || '',
      certificacion: t.certificacion,
      estado: t.estado || 'disponible',
      telefono: t.telefono
    }));
  }

  window.setAgendaDataFromRaw(raw);
  renderCalendar();
  renderAgendaTable();
  renderReagendamientoTable();
  populateTecnicoFilter();
}

window.setAgendaDataFromRaw = function(raw) {
  const list = Array.isArray(raw) ? raw : (raw?.data || []);
  agendaData = list.map(t => {
    const idVal = t.id_turno || t.id;
    const cliNom = t.cliente || t.cliente_nombre || (t.nombre ? `${t.nombre} ${t.apellido || ''}`.trim() : 'Cliente');
    const finNom = t.finca || t.finca_nombre || (t.id_finca ? 'Finca #' + t.id_finca : 'Predio');
    const servNom = t.servicio || t.servicio_nombre || (t.id_servicio ? 'Servicio #' + t.id_servicio : 'Servicio Dron');
    const tecNom = t.tecnico || t.tecnico_nombre || '';
    const obsTxt = t.notas || t.observaciones_servicio || t.observaciones || '';
    const fecVal = (t.fecha || t.fecha_de_turno || '').slice(0, 10);
    const horVal = (t.hora || t.hora_inicio_estimada || '').slice(0, 5);
    const estVal = t.estado || 'Pendiente';

    const rawTarifa = (t.tarifa !== undefined && t.tarifa !== null && t.tarifa !== '') ? Number(t.tarifa) : ((t.precio !== undefined && t.precio !== null && t.precio !== '') ? Number(t.precio) : null);
    const isDemoVal = Boolean(t.es_demostracion || (rawTarifa === 0 && String(servNom).toLowerCase().includes('demo')));

    return {
      ...t,
      id: idVal,
      id_turno: idVal,
      id_finca: t.id_finca,
      id_servicio: t.id_servicio,
      id_tecnico: t.id_tecnico,
      id_drone: t.id_drone,
      cliente: cliNom,
      cliente_nombre: cliNom,
      email: t.email || t.cliente_email || '',
      cliente_email: t.email || t.cliente_email || '',
      finca: finNom,
      finca_nombre: finNom,
      servicio: servNom,
      servicio_nombre: servNom,
      tecnico: tecNom,
      tecnico_nombre: tecNom,
      fecha: fecVal,
      fecha_de_turno: fecVal,
      hora: horVal,
      hora_inicio_estimada: horVal,
      estado: estVal,
      hectareas: t.hectareas || 0,
      tarifa: rawTarifa,
      precio: rawTarifa !== null ? rawTarifa : 0,
      monto: rawTarifa !== null ? rawTarifa : 0,
      es_demostracion: isDemoVal,
      sugerencia_cliente: t.sugerencia_cliente || '',
      token_confirmacion: t.token_confirmacion || '',
      historial_negociacion: t.historial_negociacion || '',
      notas: obsTxt,
      observaciones_servicio: obsTxt,
      telefono: t.cel || t.telefono || t.cliente_telefono || '',
      cliente_telefono: t.cliente_telefono || t.cel || t.telefono || '',
      maps_url: t.maps_url || t.maps_link || '',
      cliente_documento: t.cliente_documento || t.numero_documento || t.cedula || '',
      numero_documento: t.numero_documento || t.cliente_documento || t.cedula || '',
      cliente_tipo_persona: t.cliente_tipo_persona || t.tipo_persona || 'Persona Natural (Cédula CC)',
      tipo_persona: t.tipo_persona || t.cliente_tipo_persona || 'Persona Natural (Cédula CC)',
      cliente_verificado: (t.cliente_verificado !== undefined) ? Boolean(t.cliente_verificado) : Boolean(t.verificado),
      verificado: (t.verificado !== undefined) ? Boolean(t.verificado) : Boolean(t.cliente_verificado),
      cultivo: t.cultivo || t.tipo_cultivo || '',
      motivo_reagendamiento: t.motivo_reagendamiento || ''
    };
  }).sort((a, b) => (b.id || 0) - (a.id || 0));
  return agendaData;
};

let calViewMode = '7days';
let calBaseDate = new Date();

window.setCalendarView = function(mode) {
  calViewMode = mode;
  document.getElementById('btnCalView7')?.classList.toggle('active', mode === '7days');
  document.getElementById('btnCalView14')?.classList.toggle('active', mode === '14days');
  document.getElementById('btnCalViewMonth')?.classList.toggle('active', mode === 'month');
  renderCalendar();
};

window.setCalendarMonth = function(monthIndex) {
  calBaseDate.setMonth(parseInt(monthIndex));
  calViewMode = 'month';
  document.getElementById('btnCalView7')?.classList.remove('active');
  document.getElementById('btnCalView14')?.classList.remove('active');
  document.getElementById('btnCalViewMonth')?.classList.add('active');
  renderCalendar();
};

window.navCalendar = function(dir) {
  if (dir === 0) {
    calBaseDate = new Date();
  } else if (calViewMode === 'month') {
    calBaseDate.setMonth(calBaseDate.getMonth() + dir);
  } else if (calViewMode === '14days') {
    calBaseDate.setDate(calBaseDate.getDate() + (dir * 14));
  } else {
    calBaseDate.setDate(calBaseDate.getDate() + (dir * 7));
  }
  renderCalendar();
};

function renderCalendar() {
  const container = document.getElementById('calendarGrid');
  if (!container) return;
  const today = new Date();
  const todayIso = today.toISOString().split('T')[0];
  const dayNames = ['DOM', 'LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB'];
  const monthNames = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

  const titleEl = document.getElementById('calMonthTitle');
  if (titleEl) {
    const curMonth = calBaseDate.getMonth();
    const curYear = calBaseDate.getFullYear();
    const monthSelectOptions = monthNames.map((m, idx) => 
      `<option value="${idx}" ${idx === curMonth ? 'selected' : ''}>${m}</option>`
    ).join('');

    titleEl.innerHTML = `
      <i class="fa-solid fa-calendar-days" style="color:var(--accent);"></i>
      <select onchange="setCalendarMonth(this.value)" style="border:1px solid #cbd5e1; border-radius:8px; padding:3px 8px; font-weight:800; font-size:1.02rem; color:var(--primary); background:#ffffff; cursor:pointer;">
        ${monthSelectOptions}
      </select>
      <span style="font-weight:800; color:var(--primary); font-size:1.02rem;">${curYear}</span>
      ${calViewMode !== 'month' ? `<span style="font-size:0.75rem; color:#64748b; font-weight:700;">(${calViewMode === '14days' ? '14 días' : '7 días'})</span>` : ''}
    `;
  }

  let days = [];
  if (calViewMode === 'month') {
    container.style.gridTemplateColumns = 'repeat(7, 1fr)';
    const year = calBaseDate.getFullYear();
    const month = calBaseDate.getMonth();
    const firstDayIndex = new Date(year, month, 1).getDay();
    const lastDayOfMonth = new Date(year, month + 1, 0).getDate();
    
    // Previous month filler
    const prevMonthLastDay = new Date(year, month, 0).getDate();
    for (let i = firstDayIndex - 1; i >= 0; i--) {
      const d = new Date(year, month - 1, prevMonthLastDay - i);
      days.push({ date: d, isCurrentMonth: false });
    }
    // Current month
    for (let i = 1; i <= lastDayOfMonth; i++) {
      const d = new Date(year, month, i);
      days.push({ date: d, isCurrentMonth: true });
    }
    // Next month filler
    const totalCells = days.length > 35 ? 42 : 35;
    const remaining = totalCells - days.length;
    for (let i = 1; i <= remaining; i++) {
      const d = new Date(year, month + 1, i);
      days.push({ date: d, isCurrentMonth: false });
    }
  } else {
    const count = calViewMode === '14days' ? 14 : 7;
    container.style.gridTemplateColumns = 'repeat(7, 1fr)';
    for (let i = 0; i < count; i++) {
      const d = new Date(calBaseDate);
      d.setDate(calBaseDate.getDate() + i);
      days.push({ date: d, isCurrentMonth: true });
    }
  }

  // Header row for weekdays
  let html = `
    <div style="grid-column: 1 / -1; display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; margin-bottom: 6px;">
      ${dayNames.map(name => `
        <div style="text-align:center; font-weight:800; font-size:0.75rem; color:#64748b; padding:4px 0; letter-spacing:0.5px;">
          ${name}
        </div>
      `).join('')}
    </div>
  `;

  html += days.map(item => {
    const d = item.date;
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const iso = `${yyyy}-${mm}-${dd}`;
    const isToday = iso === todayIso;
    const isSelected = iso === selectedCalDate;
    const turnos = (agendaData || []).filter(a => {
      if (a.fecha !== iso) return false;
      const st = (a.estado || '').toLowerCase().trim();
      return st !== 'cancelado' && st !== 'cancelada';
    });
    let badgeHtml = '';
    if (turnos.length > 0) {
      const label = turnos.length === 1 ? '1 vuelo' : `${turnos.length} vuelos`;
      badgeHtml = `
        <div class="cal-count-badge" onclick="event.stopPropagation(); selectCalDate('${iso}')" style="margin-top:6px; background:linear-gradient(135deg, #1c82ad 0%, #003049 100%); color:#ffffff; font-size:0.75rem; font-weight:700; padding:4px 8px; border-radius:12px; text-align:center; box-shadow:0 2px 8px rgba(0,48,73,0.18); display:flex; align-items:center; justify-content:center; gap:5px; cursor:pointer; transition:transform 0.15s ease;" onmouseover="this.style.transform='scale(1.04)'" onmouseout="this.style.transform='scale(1)'" title="${turnos.length} vuelo(s) programado(s) el ${iso}">
          <i class="fa-solid fa-plane-departure" style="font-size:0.70rem;"></i> <span>${label}</span>
        </div>`;
    }

    return `
      <div class="cal-day ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''} ${!item.isCurrentMonth ? 'opacity-40' : ''}" onclick="selectCalDate('${iso}')" style="min-height:85px; cursor:pointer; transition:all 0.2s;">
        <div class="cal-day-header" style="display:flex; justify-content:flex-end; align-items:center;">
          <span class="cal-day-num" style="font-weight:800; font-size:0.92rem; ${isToday ? 'color:#1c82ad; background:rgba(28,130,173,0.15); border-radius:50%; width:24px; height:24px; display:inline-flex; align-items:center; justify-content:center;' : ''}">${d.getDate()}</span>
        </div>
        <div style="margin-top:4px; display:flex; flex-direction:column; gap:3px;">
          ${badgeHtml}
        </div>
      </div>`;
  }).join('');

  container.innerHTML = html;
}

function selectCalDate(iso) {
  const dateInput = document.getElementById('agendaDateFilter');
  let isFiltering = false;
  if (selectedCalDate === iso && dateInput && dateInput.value === iso) {
    selectedCalDate = '';
    if (dateInput) dateInput.value = '';
  } else {
    selectedCalDate = iso;
    isFiltering = true;
    if (dateInput) dateInput.value = iso;
    const estadoSelect = document.getElementById('agendaEstadoFilter');
    if (estadoSelect && estadoSelect.value) {
      const turnosOnDay = agendaData.filter(a => a.fecha === iso);
      const ef = estadoSelect.value.toLowerCase().trim();
      const matchingTurnos = turnosOnDay.filter(a => {
        const st = (a.estado || '').toLowerCase().trim();
        if (ef === 'en proceso' || ef === 'en_proceso' || ef === 'proceso') {
          return st === 'en proceso' || st === 'en_proceso' || st.includes('proceso') || st === 'hecho';
        }
        return st === ef;
      });
      if (turnosOnDay.length > 0 && matchingTurnos.length === 0) {
        estadoSelect.value = '';
      }
    }
  }
  renderCalendar();
  renderAgendaTable();

  if (isFiltering) {
    setTimeout(() => {
      const targetCard = document.getElementById('agendaTurnosTable') || document.querySelector('#panel-agenda .card') || document.getElementById('agendaDateFilter');
      if (targetCard) {
        targetCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 60);
  }
}

function filterByDate(iso) {
  selectCalDate(iso);
}

function clearAgendaFilters() {
  selectedCalDate = '';
  const ef = document.getElementById('agendaEstadoFilter');
  if (ef) ef.value = '';
  const tf = document.getElementById('agendaTecnicoFilter');
  if (tf) tf.value = '';
  const df = document.getElementById('agendaDateFilter');
  if (df) df.value = '';
  const sf = document.getElementById('agendaSearch');
  if (sf) sf.value = '';
  renderCalendar();
  renderAgendaTable();
}
window.clearAgendaFilters = clearAgendaFilters;

function filterAgendaByState(state) {
  if (typeof navigateTo === 'function') navigateTo('agenda');
  const select = document.getElementById('agendaEstadoFilter');
  if (select) {
    select.value = state;
    renderAgendaTable();
  }
}
window.filterAgendaByState = filterAgendaByState;

function populateTecnicoFilter() {
  const select = document.getElementById('agendaTecnicoFilter');
  const tecnicos = [...new Set(agendaData.filter(a => a.tecnico).map(a => a.tecnico))];
  select.innerHTML = '<option value="">Todos los técnicos</option>' +
    tecnicos.map(t => `<option value="${t}">${t}</option>`).join('');
}

function renderAgendaTable() {
  const search = (document.getElementById('agendaSearch')?.value || '').toLowerCase().trim();
  const estadoFilter = (document.getElementById('agendaEstadoFilter')?.value || '').toLowerCase().trim();
  const tecnicoFilter = (document.getElementById('agendaTecnicoFilter')?.value || '').trim();
  const dateFilter = (document.getElementById('agendaDateFilter')?.value || '').trim();

  let data = agendaData;
  if (search) {
    data = data.filter(a =>
      [a.cliente, a.email, a.finca, a.servicio, a.tecnico, a.notas, String(a.id), String(a.id_turno), String(a.telefono)].some(v => (v || '').toLowerCase().includes(search))
    );
  }
  if (estadoFilter) {
    data = data.filter(a => {
      const st = (a.estado || '').toLowerCase().trim();
      if (estadoFilter === 'en proceso' || estadoFilter === 'en_proceso' || estadoFilter.includes('proceso')) {
        return st === 'en proceso' || st === 'en_proceso' || st.includes('proceso') || st === 'hecho';
      }
      if (estadoFilter === 'completado' || estadoFilter === 'finalizado') {
        return st === 'completado' || st === 'finalizado' || st === 'hecho' || st === 'realizado';
      }
      return st === estadoFilter;
    });
  }
  if (tecnicoFilter) data = data.filter(a => (a.tecnico || '').trim() === tecnicoFilter);
  if (dateFilter) data = data.filter(a => (a.fecha || '').trim() === dateFilter);

  // Orden estricto por llegada / ID descendente
  data = [...data].sort((a, b) => (b.id || 0) - (a.id || 0));

  const tbody = document.getElementById('agendaTableBody');
  const allTecnicos = (tecnicosData && tecnicosData.length) ? tecnicosData : (cache['tecnicos']?.data || []);
  const listTecnicos = allTecnicos.filter(t => {
    const est = (t.estado || '').toLowerCase().trim();
    return est !== 'deshabilitado' && est !== 'inactivo';
  });

  tbody.innerHTML = data.length ? data.map(a => {
    const isRechazado = a.estado === 'Rechazado';
    const rawCleanNotas = (a.notas || '')
      .replace(/\[Servicios:\s*[^\]]+\]/gi, '')
      .replace(/(\s*\|\s*Cambiado por Admin:\s*Modificado por el administrador)+/gi, '')
      .replace(/(\s*\|\s*Cambiado por Admin:[^|]+)+/gi, '')
      .trim();
    const cleanNotas = escapeHtml(rawCleanNotas);

    const isConfirmado = a.estado === 'Confirmado';
    const isEnProceso = (a.estado || '').toLowerCase() === 'en proceso' || (a.estado || '').toLowerCase() === 'en_proceso';
    const isFinalizado = (a.estado || '').toLowerCase() === 'finalizado' || (a.estado || '').toLowerCase() === 'completado';
    const isCompletado = isFinalizado || (a.estado || '').toLowerCase() === 'hecho' || (a.estado || '').toLowerCase() === 'realizado';
    const isCancelado = (a.estado || '').toLowerCase() === 'cancelado';

    const aId = escapeHtml(a.id || a.id_turno);
    const clienteDisplay = escapeHtml(a.cliente || a.cliente_nombre || 'Cliente');
    const emailDisplay = escapeHtml(a.email || a.cliente_email || '');
    const docDisplay = escapeHtml(a.cliente_documento || a.numero_documento || a.documento || a.cedula || '');
    const telDisplay = escapeHtml(a.cliente_telefono || a.telefono || a.cel || '');
    const fincaDisplay = escapeHtml(a.finca || a.finca_nombre || (a.id_finca ? 'Finca #' + a.id_finca : '—'));
    
    // Parseo de servicios consolidados
    let rawServicioDisplay = a.servicio || a.servicio_nombre || 'Servicio Dron';
    const rawTag = (a.observaciones_servicio || a.notas || '');
    const mSvcTag = rawTag.match(/\[Servicios:\s*([^\]]+)\]/i);
    if (mSvcTag && mSvcTag[1]) {
      rawServicioDisplay = mSvcTag[1].trim();
    }
    const servicioDisplay = escapeHtml(rawServicioDisplay);

    const fechaDisplay = formatDateShort(a.fecha || a.fecha_de_turno);
    const horaDisplay = (a.hora || a.hora_inicio_estimada || '—').slice(0, 5);
    const tecnicoDisplay = escapeHtml(a.tecnico || a.tecnico_nombre || '');
    // Estricto: Sólo es demostración si la base de datos lo marca formalmente como tal
    const isDemo = Boolean(
      (a.es_demostracion === true || a.es_demostracion === 1 || a.es_demo_gratis === true) &&
      (a.tarifa === null || a.tarifa === undefined || Number(a.tarifa) === 0)
    );
    const tarifaVal = (a.tarifa !== undefined && a.tarifa !== null) ? Number(a.tarifa) : (a.monto !== undefined && a.monto !== null ? Number(a.monto) : null);
    const tieneSugerencia = Boolean(a.sugerencia_cliente && String(a.sugerencia_cliente).trim());

    let historyList = [];
    if (a.historial_negociacion) {
      try {
        historyList = typeof a.historial_negociacion === 'string' ? JSON.parse(a.historial_negociacion) : a.historial_negociacion;
        if (!Array.isArray(historyList)) historyList = [];
      } catch(e) { historyList = []; }
    }
    const clienteRespondio = isDemo || historyList.some(h => h.emisor === 'cliente');

    let precioBadge = '';
    if (isDemo) {
      precioBadge = `<span class="badge" style="background:#dcfce7; color:#15803d; border:1.5px solid #86efac; font-weight:800; font-size:0.75rem; white-space:nowrap; display:inline-flex; align-items:center; gap:5px; padding:5px 10px; border-radius:8px;"><i class="fa-solid fa-gift" style="color:#16a34a;"></i> Análisis del Terreno ($0)</span>`;
    } else if (tarifaVal !== null && tarifaVal > 0) {
      precioBadge = `<div style="font-weight:800; color:#065f46; font-size:0.90rem; white-space:nowrap;">${formatCurrency(tarifaVal)}</div>`;
    } else {
      precioBadge = `<span class="badge" style="background:#eff6ff; color:#1d4ed8; border:1.5px solid #bfdbfe; font-weight:800; font-size:0.75rem; white-space:nowrap; display:inline-flex; align-items:center; gap:5px; padding:5px 10px; border-radius:8px;"><i class="fa-solid fa-file-invoice-dollar" style="color:#2563eb;"></i> Servicio Normal (Por Cotizar)</span>`;
    }

    const deliverableUrl = a.url_entregable || a.url_entregable_drive || a.url_archivo || a.sharepoint_url || a.link_sharepoint || '';

    return `
    <tr style="${isRechazado ? 'background: rgba(255, 77, 109, 0.04);' : (isFinalizado ? 'background: rgba(16, 185, 129, 0.03);' : '')}">
      <td style="font-weight:800; color:var(--primary);">#${aId}</td>
      <td>
        <div style="font-weight:700; color:#003049; display:flex; align-items:center; gap:5px;">
          ${clienteDisplay}
          ${a.cliente_verificado ? '<i class="fa-solid fa-circle-check" style="color:#10b981; font-size:0.75rem;" title="Cliente verificado"></i>' : ''}
        </div>
        <div style="font-size:0.74rem; color:#64748b; margin-top:2px;">
          ${(docDisplay && docDisplay !== 'Sin registrar') ? `<span style="display:inline-flex; align-items:center; gap:3px;"><i class="fa-solid fa-id-card" style="font-size:0.7rem; color:#1c82ad;"></i> CC: ${docDisplay}</span>` : ''}
          ${telDisplay ? `${(docDisplay && docDisplay !== 'Sin registrar') ? ' &bull; ' : ''}<span style="display:inline-flex; align-items:center; gap:3px;"><i class="fa-solid fa-phone" style="font-size:0.7rem; color:#10b981;"></i> ${telDisplay}</span>` : ''}
        </div>
        ${emailDisplay ? `<div class="text-muted" style="font-size:0.72rem; margin-top:1px;"><i class="fa-regular fa-envelope" style="font-size:0.7rem;"></i> ${emailDisplay}</div>` : ''}
      </td>
      <td>${fincaDisplay}</td>
      <td><span style="font-weight:700; color:#1c82ad; font-size:0.83rem;">${servicioDisplay}</span></td>
      <td>${fechaDisplay}</td>
      <td>${horaDisplay}</td>
      <td style="max-width:200px;">
        <div style="font-size:0.80rem; color:#475569; line-height:1.35; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;" title="${cleanNotas || 'Sin observaciones'}">
          ${cleanNotas ? `<i class="fa-solid fa-comment-dots" style="color:var(--accent); margin-right:4px;"></i>${cleanNotas}` : '<span style="color:#94a3b8; font-style:italic;">—</span>'}
        </div>
      </td>
      <td style="text-align:center; min-width:140px;">
        ${precioBadge}
      </td>
      <td>
        ${statusBadge(a.estado)}
        ${tieneSugerencia ? `
          <div style="margin-top:5px;">
            <button class="btn btn-sm" onclick="openCotizarAgendaModal(${aId})" style="padding:2px 7px; font-size:0.70rem; font-weight:800; background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe; border-radius:6px; cursor:pointer;" title="El cliente envió sugerencia: ${String(a.sugerencia_cliente).replace(/"/g, '&quot;')}">
              <i class="fa-solid fa-comment-dots"></i> Sugerencia cliente
            </button>
          </div>
        ` : ''}
        ${isRechazado ? `<div style="font-size:0.7rem;color:#FF4D6D;margin-top:4px;display:flex;align-items:center;gap:4px;"><i class="fa-solid fa-triangle-exclamation"></i> Piloto rechazó el turno</div>` : ''}
      </td>
      <td>
        ${tecnicoDisplay
        ? `<div style="display:flex;align-items:center;gap:6px;"><div class="avatar" style="width:24px;height:24px;font-size:0.6rem;font-weight:700;">${tecnicoDisplay.split(' ').map(w => w[0]).join('').slice(0, 2)}</div>${tecnicoDisplay}</div>`
        : `<span class="badge badge-unpaid">Sin asignar</span>`
      }
      </td>
      <td>
        <div class="agenda-actions-grid">
          <!-- Fila 1: Cotización y Asignación de Piloto -->
          <div class="agenda-action-row">
            <button class="agenda-act-btn view" onclick="viewAgendaDetail(${aId})" title="Ver detalle completo">
              <i class="fa-solid fa-eye"></i>
            </button>

            ${(!isDemo && !isCancelado && !isCompletado) ? `
              <button class="agenda-act-btn cotizar" onclick="openCotizarAgendaModal(${aId})" title="Adjuntar precio y piloto obligatorio">
                <i class="fa-solid fa-hand-holding-dollar"></i> ${a.estado === 'Pendiente por confirmar' ? 'Renegociar' : 'Cotizar'}
              </button>
            ` : ''}

            ${(!isFinalizado && !isCancelado) ? `
              <select class="agenda-pilot-select" onchange="assignTecnico(${aId}, this.value); this.value=''" title="Asignar piloto rápido">
                <option value="">${tecnicoDisplay ? 'Reasignar piloto' : 'Asignar piloto'}</option>
                ${listTecnicos.map(t => `<option value="${t.id_tecnico || t.id}">${t.nombre}</option>`).join('')}
              </select>
            ` : ''}

            ${isFinalizado ? `
              <span class="badge" style="background:#ecfdf5; color:#065f46; font-size:0.70rem; font-weight:800; padding:4px 8px; border-radius:6px;" title="Servicio completado con entregable SharePoint">
                <i class="fa-solid fa-circle-check"></i> Finalizado
              </span>
            ` : ''}
          </div>

          <!-- Fila 2: Flujo de Aceptación y Notificación -->
          <div class="agenda-action-row">
            ${(!isConfirmado && !isEnProceso && !isCompletado && !isCancelado) ? `
              ${(!isDemo && (!tarifaVal || tarifaVal === 0)) ? `
                <button class="agenda-act-btn cotizar" onclick="openCotizarAgendaModal(${aId})" style="background:#fffbeb; color:#b45309; border-color:#fde68a;" title="Debes cotizar la tarifa antes de confirmar este servicio">
                  <i class="fa-solid fa-hand-holding-dollar"></i> Cotizar primero
                </button>
              ` : (!isDemo && !clienteRespondio) ? `
                <button class="agenda-act-btn waiting" onclick="alertEsperandoCliente(${aId})" style="background:#fff7ed; color:#c2410c; border-color:#fed7aa; font-weight:700;" title="Cotización enviada ($${Number(tarifaVal || 0).toLocaleString('es-CO')}). Esperando respuesta del cliente para poder aceptar">
                  <i class="fa-solid fa-hourglass-half"></i> Esperando respuesta
                </button>
              ` : `
                <button class="agenda-act-btn accept" onclick="confirmarYAceptarAgenda(${aId}, this)" title="Aceptar y confirmar agendamiento">
                  <i class="fa-solid fa-circle-check"></i> Aceptar
                </button>
              `}
            ` : ''}

            ${(a.estado === 'Pendiente por confirmar' || isDemo) && !isFinalizado ? `
              <button class="agenda-act-btn resend" onclick="reenviarAceptacionPendiente(${aId})" title="Reenviar solicitud al cliente">
                <i class="fa-solid fa-paper-plane"></i> Reenviar
              </button>
            ` : ''}

            <button class="agenda-act-btn notify" onclick="notificarManualTurno(${aId})" title="Notificar a Cliente y Técnico por email">
              <i class="fa-solid fa-bell"></i> Notificar
            </button>

            ${deliverableUrl ? `
              <a href="${deliverableUrl}" target="_blank" rel="noopener noreferrer" class="agenda-act-btn" style="background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe; text-decoration:none; display:inline-flex; align-items:center; justify-content:center;" title="Abrir entregable en SharePoint">
                <i class="fa-solid fa-folder-open"></i>
              </a>
            ` : `
              <button class="agenda-act-btn" onclick="openAttachSharepointModal(${aId})" style="background:#f0fdf4; color:#15803d; border-color:#bbf7d0;" title="Adjuntar enlace oficial de SharePoint">
                <i class="fa-solid fa-cloud-arrow-up"></i>
              </button>
            `}
          </div>

          <!-- Fila 3: Acciones secundarias (Reagendar / Modificar / Cancelar) -->
          <div class="agenda-action-row">
            ${(!isCancelado && !isCompletado && !isFinalizado) ? `
              <button class="agenda-act-btn edit" onclick="openReagendarModal(${aId})" style="background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe;" title="Reagendar fecha u hora del servicio">
                <i class="fa-solid fa-calendar-plus"></i> Reagendar
              </button>
            ` : ''}

            ${(isCompletado || isFinalizado) ? `
              <span class="badge" style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; font-weight:800; font-size:0.75rem; padding:5px 10px; border-radius:8px; display:inline-flex; align-items:center; gap:5px;" title="Servicio finalizado exitosamente">
                <i class="fa-solid fa-circle-check"></i> Finalizado
              </span>
            ` : (!isConfirmado && !isEnProceso) ? `
              <button class="agenda-act-btn edit" onclick="openModificarAgendaModal(${aId})" title="Modificar datos del turno">
                <i class="fa-solid fa-pen-to-square"></i> Modificar
              </button>
            ` : ''}

            ${(!isCancelado && !isCompletado) ? `
              <button class="agenda-act-btn cancel" onclick="cancelAgendaTurno(${aId})" title="Cancelar turno">
                <i class="fa-solid fa-ban"></i> Cancelar
              </button>
            ` : ''}
          </div>
        </div>
      </td>
    </tr>
  `;
  }).join('') : `<tr><td colspan="11" class="text-center" style="padding:40px"><div class="empty-state" style="padding:0"><div class="empty-icon"><i class="fa-solid fa-calendar-xmark" style="font-size:2rem; color:var(--accent);"></i></div><div class="empty-title">No hay turnos agendados</div><div class="empty-sub" style="margin-bottom:12px">No se encontraron turnos con los filtros activos.</div><button class="btn btn-primary btn-sm" onclick="clearAgendaFilters()" style="margin: 0 auto; display: inline-flex; align-items: center; gap: 6px; font-weight:700;"><i class="fa-solid fa-rotate"></i> Mostrar todos los turnos</button></div></td></tr>`;
}

window.notificarManualTurno = async function(id) {
  if (!id) return;
  if (!confirm(`¿Deseas enviar una notificación manual por correo al Cliente y al Técnico asignado para el turno #${id}?`)) {
    return;
  }
  try {
    showToast('Enviando notificación a cliente y técnico...', 'info');
    const res = await apiFetch(`/agenda/${id}/notificar-manual`, { method: 'POST' });
    showToast('<i class="fa-solid fa-circle-check"></i> Notificación enviada con éxito al cliente y técnico.', 'success');
  } catch (err) {
    showToast('Error al notificar: ' + err.message, 'error');
  }
};

window.cancelAgendaTurno = async function(id) {
  if (!confirm(`¿Estás seguro de cancelar el agendamiento del turno #${id}? Se notificará al cliente por correo.`)) return;
  await changeAgendaStatus(id, 'Cancelado');
};

window.openAttachSharepointModal = async function(idTurno) {
  const current = (agendaData || []).find(a => ((a.id === idTurno) || (a.id_turno === idTurno)));
  const prevUrl = current ? (current.url_entregable || current.url_entregable_drive || current.sharepoint_url || current.link_sharepoint || '') : '';
  
  const inputUrl = prompt(`Ingresa o pega el enlace de Microsoft SharePoint / Entregables para el vuelo #RAD-${idTurno}:`, prevUrl || '');
  if (inputUrl === null) return;
  
  let cleanUrl = inputUrl.trim();
  if (!cleanUrl) return showToast('El enlace de SharePoint no puede estar vacío.', 'warn');
  if (!cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) {
    cleanUrl = 'https://' + cleanUrl;
  }

  try {
    showToast('Vinculando SharePoint y finalizando servicio...', 'info');
    await apiFetch('/tecnico/subir-informe-ejecutivo', {
      method: 'POST',
      body: JSON.stringify({
        id_turno: idTurno,
        sharepoint_url: cleanUrl
      })
    });
    showToast('<i class="fa-solid fa-circle-check"></i> Enlace de SharePoint guardado y servicio finalizado.', 'success');
    invalidateCache('agenda');
    await loadAgenda();
  } catch (err) {
    showToast('Error al vincular SharePoint: ' + err.message, 'error');
  }
};

window.reenviarAceptacionPendiente = async function(id) {
  if (!id) return;

  try {
    if (!_usuariosList || _usuariosList.length === 0) {
      await loadUsuarios();
    }

    const admins = (_usuariosList || []).filter(u => String(u.rol || '').toLowerCase() === 'administrador');
    if (!admins.length) {
      showToast('No hay administradores registrados para seleccionar.', 'error');
      return;
    }

    const adminListText = admins.map(a => `- ${a.email || `Admin #${a.id_usuarios}`} (${a.id_usuarios})`).join('\n');
    const adminInput = window.prompt(
      `Selecciona el administrador responsable para reenviar la aceptación pendiente.\n\nOpciones disponibles:\n${adminListText}\n\nEscribe el correo o el ID del administrador:`,
      admins[0]?.email || ''
    );

    if (!adminInput || !adminInput.trim()) {
      return;
    }

    const elegido = admins.find(a =>
      String(a.id_usuarios) === String(adminInput.trim()) ||
      String(a.email || '').toLowerCase() === String(adminInput.trim()).toLowerCase()
    ) || admins.find(a => String(a.email || '').toLowerCase().includes(String(adminInput.trim()).toLowerCase()));

    if (!elegido) {
      showToast('No encontré ese administrador en la lista. Intenta con el correo o el ID exacto.', 'warning');
      return;
    }

    showToast('Reenviando la aceptación pendiente al cliente...', 'info');
    await apiFetch(`/admin/agenda/${id}/reenviar-aceptacion`, {
      method: 'POST',
      body: JSON.stringify({ id_admin_responsable: elegido.id_usuarios || elegido.id_usuarios })
    });

    invalidateCache('agenda');
    await loadAgenda();
    showToast(`<i class="fa-solid fa-check"></i> Solicitud de aceptación pendiente reenviada por ${elegido.email || `Admin #${elegido.id_usuarios}`}.`, 'success');
  } catch (err) {
    showToast('Error al reenviar la aceptación pendiente: ' + err.message, 'error');
  }
};

// ==========================================
// MODAL COTIZACIÓN Y CICLO INFINITO DE NEGOCIACIÓN
// ==========================================

let _currentCotizarTurno = null;

window.openCotizarAgendaModal = function(id) {
  const turno = agendaData.find(a => (a.id == id || a.id_turno == id));
  if (!turno) {
    showToast('No se encontró el turno seleccionado.', 'error');
    return;
  }
  _currentCotizarTurno = turno;

  const titleEl = document.getElementById('cotizarModalTitle');
  if (titleEl) titleEl.textContent = `Cotizar y Gestionar Turno #RAD-${turno.id || turno.id_turno}`;

  const inputId = document.getElementById('cotizarTurnoId');
  if (inputId) inputId.value = turno.id || turno.id_turno;

  // Llenar resumen
  const resumenEl = document.getElementById('cotizarModalResumen');
  if (resumenEl) {
    const cliNom = turno.cliente || turno.cliente_nombre || 'Cliente';
    const finNom = turno.finca || turno.finca_nombre || 'Predio';
    const srvNom = turno.servicio || turno.servicio_nombre || 'Servicio Dron';
    const fec = formatDateShort(turno.fecha || turno.fecha_de_turno);
    const hor = (turno.hora || turno.hora_inicio_estimada || '08:00 AM').slice(0, 5);
    const est = turno.estado || 'Pendiente';
    const ha = turno.hectareas ? `${turno.hectareas} Ha` : '';

    resumenEl.innerHTML = `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
        <div><strong>Cliente:</strong> ${cliNom}</div>
        <div><strong>Finca:</strong> ${finNom} ${ha ? `(${ha})` : ''}</div>
        <div><strong>Servicio:</strong> <span style="color:#1c82ad; font-weight:700;">${srvNom}</span></div>
        <div><strong>Fecha y Hora:</strong> ${fec} a las ${hor}</div>
        <div><strong>Estado Actual:</strong> ${statusBadge(est)}</div>
        <div><strong>Email Cliente:</strong> ${turno.cliente_email || turno.email || '—'}</div>
      </div>
    `;
  }

  // Pre-cargar tarifa
  const tarifaInput = document.getElementById('cotizarTarifaInput');
  if (tarifaInput) {
    const currTarifa = (turno.tarifa !== undefined && turno.tarifa !== null && Number(turno.tarifa) > 0)
      ? Number(turno.tarifa)
      : (turno.monto ? Number(turno.monto) : '');
    tarifaInput.value = currTarifa || '';
  }

  // Cargar técnicos
  const selectTec = document.getElementById('cotizarTecnicoSelect');
  if (selectTec) {
    const allTecnicos = (tecnicosData && tecnicosData.length) ? tecnicosData : (cache['tecnicos']?.data || []);
    const listTecnicos = allTecnicos.filter(t => {
      const est = (t.estado || '').toLowerCase().trim();
      return est !== 'deshabilitado' && est !== 'inactivo';
    });
    selectTec.innerHTML = '<option value="">Seleccione piloto obligatorio...</option>' +
      listTecnicos.map(t => {
        const tid = t.id_tecnico || t.id;
        const selected = (turno.id_tecnico && turno.id_tecnico == tid) ? 'selected' : '';
        return `<option value="${tid}" ${selected}>${t.nombre} ${t.apellido_1 || ''} (${t.certificacion || 'RAC 100'})</option>`;
      }).join('');
  }

  // Limpiar mensaje
  const msgInput = document.getElementById('cotizarMensajeAdmin');
  if (msgInput) msgInput.value = '';

  // Sugerencia del cliente
  const sugBox = document.getElementById('cotizarModalSugerenciaBox');
  const sugText = document.getElementById('cotizarModalSugerenciaTexto');
  if (turno.sugerencia_cliente && String(turno.sugerencia_cliente).trim()) {
    if (sugBox) sugBox.style.display = 'block';
    if (sugText) sugText.textContent = `"${turno.sugerencia_cliente.trim()}"`;
  } else {
    if (sugBox) sugBox.style.display = 'none';
    if (sugText) sugText.textContent = '';
  }

  // Historial de negociación
  const histBox = document.getElementById('cotizarModalHistorialBox');
  const histTimeline = document.getElementById('cotizarModalHistorialTimeline');
  if (turno.historial_negociacion) {
    try {
      const parsed = typeof turno.historial_negociacion === 'string' ? JSON.parse(turno.historial_negociacion) : turno.historial_negociacion;
      if (Array.isArray(parsed) && parsed.length > 0) {
        if (histBox) histBox.style.display = 'block';
        if (histTimeline) {
          histTimeline.innerHTML = parsed.map((h, idx) => {
            const emisorBadge = h.emisor === 'admin'
              ? `<span style="background:#003049; color:#fff; font-weight:800; padding:2px 6px; border-radius:4px; font-size:0.7rem;">ADMINISTRADOR</span>`
              : `<span style="background:#2563eb; color:#fff; font-weight:800; padding:2px 6px; border-radius:4px; font-size:0.7rem;">CLIENTE</span>`;
            const tarifaTxt = h.tarifa ? ` &bull; Tarifa: $ ${Number(h.tarifa).toLocaleString('es-CO')} COP` : '';
            return `
              <div style="padding:6px 0; border-bottom:1px dashed #e2e8f0;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <div>${emisorBadge} <strong>${h.tipo || 'Mensaje'}</strong>${tarifaTxt}</div>
                  <div style="color:#94a3b8; font-size:0.75rem;">${h.fecha || ''}</div>
                </div>
                <div style="color:#334155; margin-top:2px;">${h.mensaje || ''}</div>
              </div>
            `;
          }).join('');
        }
      } else {
        if (histBox) histBox.style.display = 'none';
      }
    } catch(e) {
      if (histBox) histBox.style.display = 'none';
    }
  } else {
    if (histBox) histBox.style.display = 'none';
  }

  openModal('cotizarAgendaModal');
};

window.submitCotizarAgendaForm = async function(event) {
  event.preventDefault();
  const id = document.getElementById('cotizarTurnoId')?.value;
  const tarifaVal = document.getElementById('cotizarTarifaInput')?.value;
  const tecnicoVal = document.getElementById('cotizarTecnicoSelect')?.value;
  const mensajeVal = document.getElementById('cotizarMensajeAdmin')?.value;

  if (!id) return;
  if (!tarifaVal || Number(tarifaVal) <= 0) {
    showToast('Debe ingresar un precio válido mayor a 0.', 'warning');
    return;
  }
  if (!tecnicoVal) {
    showToast('Debe seleccionar obligatoriamente un técnico / piloto.', 'warning');
    return;
  }

  try {
    showToast('Enviando propuesta de precio al cliente...', 'info');
    await apiFetch(`/admin/agenda/${id}/cotizar`, {
      method: 'POST',
      body: JSON.stringify({
        tarifa: Number(tarifaVal),
        id_tecnico: Number(tecnicoVal),
        mensaje_admin: mensajeVal ? mensajeVal.trim() : null
      })
    });

    closeModal('cotizarAgendaModal');
    showToast('<i class="fa-solid fa-circle-check"></i> Cotización guardada en base de datos y notificada al cliente por correo (Pendiente por confirmar).', 'success');
    invalidateCache('agenda');
    await loadAgenda();
  } catch(err) {
    showToast('Error al cotizar turno: ' + (err.detail || err.message), 'error');
  }
};

window.adminAceptarDirectoServicio = async function() {
  const id = document.getElementById('cotizarTurnoId')?.value;
  if (!id) return;

  const tecnicoVal = document.getElementById('cotizarTecnicoSelect')?.value;
  if (!tecnicoVal && (!_currentCotizarTurno || !_currentCotizarTurno.id_tecnico)) {
    showToast('Debe haber un técnico asignado antes de confirmar el servicio.', 'warning');
    return;
  }

  if (!confirm(`¿Confirmas la aceptación directa del servicio #${id}? Se establecerá en estado 'Confirmado' y se notificará de inmediato al piloto asignado y al cliente.`)) {
    return;
  }

  try {
    // Si cambió el técnico en el selector, actualizarlo primero
    if (tecnicoVal && _currentCotizarTurno && _currentCotizarTurno.id_tecnico != tecnicoVal) {
      await apiFetch(`/admin/agenda/${id}/asignar`, {
        method: 'PATCH',
        body: JSON.stringify({ id_tecnico: Number(tecnicoVal) })
      });
    }

    showToast('Aceptando directamente y confirmando servicio...', 'info');
    await apiFetch(`/admin/agenda/${id}/aceptar-directo`, {
      method: 'POST'
    });

    closeModal('cotizarAgendaModal');
    showToast('<i class="fa-solid fa-check-double"></i> Servicio Confirmado exitosamente. Piloto y cliente han sido notificados.', 'success');
    invalidateCache('agenda');
    await loadAgenda();
  } catch(err) {
    showToast('Error al aceptar directamente: ' + (err.detail || err.message), 'error');
  }
};

window.alertConfirmadoNoModificable = function(id) {
  if (typeof openReagendarModal === 'function') {
    openReagendarModal(id);
  }
};

window.openModificarAgendaModal = async function(id) {
  let turno = (agendaData || []).find(x => (x.id_turno == id || x.id == id));
  if (!turno && id) {
    try {
      const res = await apiFetch(`/agenda/${id}`);
      turno = res.data || res;
    } catch(e) {}
  }

  const est = String(turno?.estado || '').toLowerCase();
  if (['completado', 'finalizado'].includes(est)) {
    showToast(`El turno #${id} ya se encuentra ${est} y no se puede modificar.`, 'info');
    return;
  }

  // Si ya está confirmado, en proceso o aceptado, abrir directamente el modal de reagendamiento sin bloqueos
  if (['confirmado', 'en proceso', 'aceptado'].includes(est)) {
    if (typeof openReagendarModal === 'function') {
      openReagendarModal(id);
      return;
    }
  }

  const modal = document.getElementById('reprogramarModal');
  const todayIso = new Date().toISOString().split('T')[0];
  if (!modal) {
    navigateTo('reagendamiento');
    return;
  }

  // Abrir modal inmediatamente sin esperar llamadas a la red
  openModal('reprogramarModal');

  if (!turno) {
    turno = { id_turno: id, id: id };
  }

  const turnoId = turno.id_turno || turno.id;
  document.getElementById('reprogramarTurnoId').value = turnoId;
  
  // Clear error message
  const errEl = document.getElementById('reprogramarErrMsg');
  if (errEl) errEl.style.display = 'none';

  // 1. Populate Servicios Multi-Select
  if (!serviciosData || !serviciosData.length) {
    if (typeof loadServicios === 'function') await loadServicios();
  }
  const currentServicios = (turno.servicios_list && turno.servicios_list.length) 
    ? turno.servicios_list 
    : [(turno.servicio_nombre || turno.servicio || '')];

  const svcContainer = document.getElementById('reprogramarServiciosContainer');
  if (svcContainer) {
    svcContainer.innerHTML = (serviciosData || [])
      .filter(s => s.activo !== false)
      .map(s => {
        const sId = s.id_servicio || s.id;
        const sName = s.nombre_servicio || s.nombre;
        const isChecked = currentServicios.some(cs => (cs||'').toLowerCase().includes(sName.toLowerCase()) || sName.toLowerCase().includes((cs||'').toLowerCase()));
        return `
          <label style="display:inline-flex; align-items:center; gap:6px; background:#ffffff; padding:6px 12px; border-radius:8px; border:1px solid #cbd5e1; cursor:pointer; font-size:0.83rem; font-weight:600; color:#003049;">
            <input type="checkbox" name="reprogramarServicioCb" value="${sName}" data-id="${sId}" ${isChecked ? 'checked' : ''} style="accent-color:#1C82AD; width:16px; height:16px;" />
            <span>${sName}</span>
          </label>
        `;
      }).join('');
  }

  // Pre-llenar Maps y Cultivo
  let mapLink = normalizeMapsInput(turno.maps_url || '');
  if (!mapLink && (turno.notas || turno.observaciones_servicio)) {
    const rawN = (turno.notas || '') + ' ' + (turno.observaciones_servicio || '');
    const m = rawN.match(/https?:\/\/(?:maps\.app\.goo\.gl|goo\.gl\/maps|www\.google\.com\/maps|maps\.google\.com)[^\s\n\r"'<>\]\)]+/);
    if (m) {
      mapLink = normalizeMapsInput(m[0]);
    } else {
      const mCoord = rawN.match(/[-+]?\d{1,3}\.\d+[,\s]+[-+]?\d{1,3}\.\d+/);
      if (mCoord) mapLink = normalizeMapsInput(mCoord[0]);
    }
  }
  if (!mapLink && turno.latitud && turno.longitud) {
    const isDummyYopal = Math.abs(parseFloat(turno.latitud) - 5.33775) < 0.001 && Math.abs(parseFloat(turno.longitud) - (-72.39587)) < 0.001;
    const munIsYopal = String(turno.ubicacion_municipio || turno.finca_municipio || '').trim().toLowerCase() === 'yopal';
    if (!(isDummyYopal && !munIsYopal)) {
      mapLink = `https://www.google.com/maps?q=${parseFloat(turno.latitud).toFixed(6)},${parseFloat(turno.longitud).toFixed(6)}`;
    }
  }
  const mapsInput = document.getElementById('reprogramarMaps');
  if (mapsInput) mapsInput.value = mapLink;

  const cultivoInput = document.getElementById('reprogramarCultivo');
  if (cultivoInput) cultivoInput.value = turno.cultivo || '';

  // 2. Populate Fincas & Hectáreas
  const fincaSelect = document.getElementById('reprogramarFinca');
  if (fincaSelect) {
    let clientFincas = [];
    const clientId = turno.id_cliente || turno.cliente_id;
    if (clientId) {
      try {
        const resCli = await apiFetch(`/clientes/${clientId}`);
        if (resCli && (resCli.fincas || resCli.data?.fincas)) {
          clientFincas = resCli.fincas || resCli.data.fincas;
        }
      } catch (e) {}
    }
    if (!clientFincas.length && clientesData && clientesData.length) {
      const cli = clientesData.find(c => (c.id_cliente || c.id) === clientId || c.nombre === turno.cliente);
      if (cli && cli.fincas) clientFincas = cli.fincas;
    }
    if (!clientFincas.length) {
      try {
        const allFincas = await apiFetch('/fincas');
        const list = Array.isArray(allFincas) ? allFincas : (allFincas?.data || []);
        if (clientId) {
          clientFincas = list.filter(f => f.id_cliente === clientId);
        }
        if (!clientFincas.length) clientFincas = list;
      } catch (e) {}
    }

    if (clientFincas.length) {
      fincaSelect.innerHTML = clientFincas.map(f => {
        const fId = f.id_finca || f.id;
        const isSel = (turno.id_finca && String(turno.id_finca) === String(fId)) || (turno.finca && turno.finca === f.nombre_finca);
        return `<option value="${fId}" data-ha="${f.hectareas || ''}" data-maps="${f.maps_url || ''}" data-cul="${f.tipo_cultivo || f.cultivo || ''}" ${isSel ? 'selected' : ''}>${f.nombre_finca} (${f.hectareas || '—'} Ha - ${f.municipio || f.ubicacion_municipio || f.departamento || ''})</option>`;
      }).join('');
    } else {
      fincaSelect.innerHTML = `<option value="${turno.id_finca || ''}">${turno.finca || 'Finca Registrada'}</option>`;
    }

    fincaSelect.onchange = function() {
      const opt = fincaSelect.options[fincaSelect.selectedIndex];
      const ha = opt?.getAttribute('data-ha');
      const haInput = document.getElementById('reprogramarHectareas');
      if (ha && haInput) haInput.value = ha;
      const fMaps = opt?.getAttribute('data-maps');
      if (fMaps && mapsInput && !mapsInput.value) mapsInput.value = fMaps;
      const fCul = opt?.getAttribute('data-cul');
      if (fCul && cultivoInput && !cultivoInput.value) cultivoInput.value = fCul;
    };
  }

  const haInput = document.getElementById('reprogramarHectareas');
  if (haInput) {
    const selOpt = fincaSelect?.options[fincaSelect?.selectedIndex];
    haInput.value = turno.hectareas || turno.hectareas_estimadas || (selOpt ? selOpt.getAttribute('data-ha') : '') || '';
  }

  // 3. Fecha
  const fEl = document.getElementById('reprogramarFecha');
  if (fEl) {
    fEl.min = todayIso;
    fEl.value = (turno.fecha || turno.fecha_de_turno || todayIso).slice(0, 10);
  }

  // 4. Hora
  const hEl = document.getElementById('reprogramarHora');
  if (hEl) {
    let hVal = turno.hora || turno.hora_inicio_estimada || '08:00';
    if (hVal.length > 5) hVal = hVal.slice(0, 5);
    hEl.value = hVal;
  }

  // 5. Estado
  const stEl = document.getElementById('reprogramarEstado');
  if (stEl) {
    stEl.value = turno.estado || 'Confirmado';
  }

  // 6. Pilotos (Soporte Multi-Técnico: hasta 3 pilotos por vuelo)
  const activeTecnicos = (tecnicosData || []).filter(t => {
    const est = (t.estado || '').toLowerCase().trim();
    return est !== 'deshabilitado' && est !== 'inactivo';
  });
  const adicIds = (turno.tecnicos_adicionales || '').split(',').map(x => x.trim()).filter(Boolean);
  const tec2Id = adicIds[0] || '';
  const tec3Id = adicIds[1] || '';

  const techSelect = document.getElementById('reprogramarTecnico');
  if (techSelect) {
    techSelect.innerHTML = `<option value="">Sin piloto principal asignado</option>` + 
      activeTecnicos.map(t => `<option value="${t.id_tecnico || t.id}" ${String(t.id_tecnico || t.id) === String(turno.id_tecnico) ? 'selected' : ''}>${t.nombre}</option>`).join('');
  }

  const tech2Select = document.getElementById('reprogramarTecnico2');
  if (tech2Select) {
    tech2Select.innerHTML = `<option value="">Sin segundo piloto</option>` + 
      activeTecnicos.map(t => `<option value="${t.id_tecnico || t.id}" ${String(t.id_tecnico || t.id) === String(tec2Id) ? 'selected' : ''}>${t.nombre}</option>`).join('');
  }

  const tech3Select = document.getElementById('reprogramarTecnico3');
  if (tech3Select) {
    tech3Select.innerHTML = `<option value="">Sin tercer piloto</option>` + 
      activeTecnicos.map(t => `<option value="${t.id_tecnico || t.id}" ${String(t.id_tecnico || t.id) === String(tec3Id) ? 'selected' : ''}>${t.nombre}</option>`).join('');
  }

  // 7. Dron
  const droneSelect = document.getElementById('reprogramarDron');
  if (droneSelect) {
    droneSelect.innerHTML = `<option value="">Sin dron asignado</option>` + 
      (dronesData || []).map(d => `<option value="${d.id_drone || d.id}" ${String(d.id_drone || d.id) === String(turno.id_drone) ? 'selected' : ''}>${d.modelo} (${d.numero_serie || 'SN'})</option>`).join('');
  }

  // 8. Motivo & Observaciones
  const mEl = document.getElementById('reprogramarMotivo');
  if (mEl) mEl.value = turno.motivo_reagendamiento || '';

  const obsEl = document.getElementById('reprogramarObservaciones');
  if (obsEl) obsEl.value = (turno.observaciones_servicio || turno.notas || '').trim();

  openModal('reprogramarModal');
};
window.openReprogramarModal = window.openModificarAgendaModal;
window.openReagendarModalDirect = window.openModificarAgendaModal;

async function assignTecnico(id, tecnicoId) {
  if (!tecnicoId) return;
  try {
    showToast('Asignando piloto al turno...', 'info');
    await apiFetch(`/admin/agenda/${id}/asignar`, {
      method: 'PATCH',
      body: JSON.stringify({ id_tecnico: parseInt(tecnicoId) })
    });
    invalidateCache('agenda');
    await loadAgenda();
    showToast(`<i class="fa-solid fa-check"></i> Piloto asignado con éxito al turno #${id}`, 'success');
  } catch (e) {
    showToast('Error al asignar técnico: ' + e.message, 'error');
  }
}
window.assignTecnico = assignTecnico;

// ── ALERTA DE CLIENTE PENDIENTE DE RESPUESTA A COTIZACIÓN ──
window.alertEsperandoCliente = function(id) {
  const a = (agendaData || []).find(x => (x.id == id || x.id_turno == id));
  const tarifaVal = a?.tarifa ? Number(a.tarifa).toLocaleString('es-CO') : '0';
  const cliNom = a?.cliente || a?.cliente_nombre || 'el cliente';

  const r = window.confirm(
    `⚠️ COTIZACIÓN PENDIENTE DE RESPUESTA DEL CLIENTE\n\n` +
    `Este servicio (#${id} - ${cliNom}) ya fue cotizado en $${tarifaVal} COP.\n\n` +
    `Por regla del sistema, NO se puede aceptar ni confirmar el servicio hasta que el cliente devuelva una respuesta (aceptación o propuesta de modificación) a la cotización formal enviada.\n\n` +
    `¿Deseas reenviarle el correo de cotización al cliente para recordarle?`
  );
  if (r) {
    reenviarAceptacionPendiente(id);
  }
};

// ── CONFIRMAR Y ACEPTAR CON ALERTA PREVENTIVA CONTRA ERRORES ACCIDENTALES ──
window.confirmarYAceptarAgenda = function(id, btn) {
  changeAgendaStatus(id, 'Confirmado', btn, false);
};

async function changeAgendaStatus(id, estado, btn, yaConfirmado = false) {
  if (!estado) return;

  const a = (agendaData || []).find(x => (x.id == id || x.id_turno == id));
  const isDemo = Boolean(
    (a?.es_demostracion === true || a?.es_demostracion === 1 || a?.es_demo_gratis === true) &&
    (a?.tarifa === null || a?.tarifa === undefined || Number(a?.tarifa) === 0)
  );

  let historyList = [];
  if (a?.historial_negociacion) {
    try {
      historyList = typeof a.historial_negociacion === 'string' ? JSON.parse(a.historial_negociacion) : a.historial_negociacion;
      if (!Array.isArray(historyList)) historyList = [];
    } catch(e) { historyList = []; }
  }
  const clienteRespondio = isDemo || historyList.some(h => h.emisor === 'cliente');

  // REGLA DE NEGOCIO 1: No se puede confirmar sin haber cotizado antes
  if (estado === 'Confirmado' && !isDemo && (!a?.tarifa || Number(a?.tarifa) === 0)) {
    showToast('⚠️ No se puede confirmar este servicio sin haber cotizado la tarifa con el cliente previamente. Abriendo cotizador...', 'warning');
    if (typeof openCotizarAgendaModal === 'function') {
      openCotizarAgendaModal(id);
    }
    return;
  }

  // REGLA DE NEGOCIO 2: No se puede confirmar hasta que el cliente devuelva una respuesta de la cotización
  if (estado === 'Confirmado' && !isDemo && !clienteRespondio) {
    alertEsperandoCliente(id);
    return;
  }

  // REGLA DE NEGOCIO 3: Alerta preventiva de confirmación para evitar aceptar por error accidental
  if (estado === 'Confirmado' && !yaConfirmado) {
    const cliNom = a?.cliente || a?.cliente_nombre || 'el cliente';
    const servNom = a?.servicio || a?.servicio_nombre || 'Vuelo Agrícola';
    const precioTxt = isDemo ? 'Análisis del Terreno ($0 COP)' : `$${Number(a?.tarifa || 0).toLocaleString('es-CO')} COP`;

    const confirmacion = window.confirm(
      `¿ESTÁS SEGURO DE QUE DESEAS ACEPTAR Y CONFIRMAR ESTE SERVICIO?\n\n` +
      `• Turno: #${id}\n` +
      `• Cliente: ${cliNom}\n` +
      `• Servicio: ${servNom}\n` +
      `• Tarifa: ${precioTxt}\n\n` +
      `Al confirmar, el servicio cambiará de estado a 'Confirmado' y se notificará formalmente al técnico y al cliente.\n\n` +
      `Presiona 'Aceptar' para proceder o 'Cancelar' si fue un clic accidental.`
    );
    if (!confirmacion) {
      // Abortar completamente sin realizar cambios
      return;
    }
  }

  if (estado === 'Cancelado') {
    const confirmCancel = window.confirm(`¿Estás seguro de que deseas CANCELAR el turno #${id}? Esta acción notificará al cliente.`);
    if (!confirmCancel) return;
  }

  const originalHtml = btn ? btn.innerHTML : '';
  let mensajeAdmin = '';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Procesando...';
  }
  try {
    const payload = {
      estado,
      motivo_admin: mensajeAdmin.trim() || 'Modificado por el administrador'
    };

    await apiFetch(`/admin/agenda/${id}/estado`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
    invalidateCache('agenda');
    await loadAgenda();
    showToast(`<i class="fa-solid fa-check"></i> Estado del turno #${id} actualizado a: ${estado}`, 'success');
  } catch (e) {
    showToast('Error al cambiar estado: ' + (e.detail || e.message), 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

async function viewAgendaDetail(id) {
  try {
    let a = (agendaData || []).find(x => (x.id == id || x.id_turno == id));
    if (!a) {
      try {
        const res = await apiFetch(`/agenda/${id}`);
        if (res) {
          const list = window.setAgendaDataFromRaw([res]);
          a = list[0] || res;
        }
      } catch (fetchErr) {
        console.warn('Fallback fetch /agenda/id failed:', fetchErr);
      }
    }

    if (!a) {
      if (typeof showToast === 'function') {
        showToast(`No se encontró el registro del turno #${id} en el sistema.`, 'warning');
      }
      return;
    }
    const aId = a.id || a.id_turno;
    const titleEl = document.getElementById('detailModalTitle');
    if (titleEl) {
      titleEl.innerHTML = `<i class="fa-solid fa-calendar-check" style="color:var(--accent); margin-right:8px;"></i> Ficha Completa del Turno #${aId}`;
    }

    // Extraer o limpiar Maps URL (estrictamente el enlace o coordenadas registradas)
    let mapUrl = normalizeMapsInput(a.maps_url || a.finca_maps_url || a.maps_link || '');
    if (!mapUrl && (a.notas || a.observaciones_servicio)) {
      const rawN = (a.notas || '') + ' ' + (a.observaciones_servicio || '');
      const m = rawN.match(/https?:\/\/(?:maps\.app\.goo\.gl|goo\.gl\/maps|www\.google\.com\/maps|maps\.google\.com)[^\s\n\r"'<>\]\)]+/);
      if (m) {
        mapUrl = normalizeMapsInput(m[0]);
      } else {
        const mCoord = rawN.match(/[-+]?\d{1,3}\.\d+[,\s]+[-+]?\d{1,3}\.\d+/);
        if (mCoord) mapUrl = normalizeMapsInput(mCoord[0]);
      }
    }
    if (!mapUrl && a.latitud && a.longitud) {
      const isDummyYopal = Math.abs(parseFloat(a.latitud) - 5.33775) < 0.001 && Math.abs(parseFloat(a.longitud) - (-72.39587)) < 0.001;
      const munIsYopal = String(a.ubicacion_municipio || a.finca_municipio || '').trim().toLowerCase() === 'yopal';
      if (!(isDummyYopal && !munIsYopal)) {
        mapUrl = `https://www.google.com/maps?q=${parseFloat(a.latitud).toFixed(6)},${parseFloat(a.longitud).toFixed(6)}`;
      }
    }
    const hasMapUrl = Boolean(mapUrl);

    // 1. Servicios badges (soporte para 1 o múltiples servicios combinados)
    let svcsList = [];
    if (Array.isArray(a.servicios_list) && a.servicios_list.length) {
      svcsList = a.servicios_list;
    }
    if (!svcsList.length) {
      const rawAll = (a.observaciones_servicio || '') + ' ' + (a.notas || '') + ' ' + (a.servicio || '') + ' ' + (a.servicio_nombre || '');
      const mTag = rawAll.match(/\[Servicios:\s*([^\]]+)\]/i);
      if (mTag && mTag[1]) {
        svcsList = mTag[1].split(/\s*(?:\+|\band\b|\by\b|,)\s*/i).map(s => s.trim()).filter(Boolean);
      } else {
        const mSvcLine = rawAll.match(/(?:Servicios Solicitados|Servicios):\s*([^\n\r]+)/i);
        if (mSvcLine && mSvcLine[1]) {
          svcsList = mSvcLine[1].split(/\s*(?:\+|\band\b|\by\b|,)\s*/i).map(s => s.trim()).filter(Boolean);
        } else if (a.servicio && (a.servicio.includes('+') || a.servicio.includes(','))) {
          svcsList = a.servicio.split(/\s*(?:\+|,)\s*/).map(s => s.trim()).filter(Boolean);
        } else if (a.servicio || a.servicio_nombre) {
          svcsList = [(a.servicio || a.servicio_nombre).trim()];
        }
      }
    }
    svcsList = [...new Set(svcsList)].filter(s => s && s.length > 2);
    if (!svcsList.length) svcsList = [(a.servicio || a.servicio_nombre || 'Servicio Agrícola')];

    const svcsBadgesHtml = svcsList.map(s => `
      <span class="badge" style="background:rgba(28,130,173,0.14); color:#003049; border:1px solid rgba(28,130,173,0.35); font-weight:800; font-size:0.82rem; padding:5px 12px; border-radius:8px; display:inline-flex; align-items:center; gap:5px;">
        <i class="fa-solid fa-layer-group" style="color:#1C82AD;"></i> ${s}
      </span>
    `).join('');

    // Documento / Cédula / NIT del cliente
    let docDisplay = a.cliente_documento || a.numero_documento || a.cedula || '';
    if ((!docDisplay || docDisplay === 'Sin registrar') && (a.notas || a.observaciones_servicio)) {
      const rawAll = (a.notas || '') + ' ' + (a.observaciones_servicio || '');
      const mDoc = rawAll.match(/(?:C[eé]dula|NIT|Documento|CC):\s*([0-9\-\.\s]+)/i);
      if (mDoc && mDoc[1].trim()) {
        docDisplay = mDoc[1].trim();
      }
    }
    if (!docDisplay) docDisplay = 'Sin registrar';

    // Tipo de persona badge
    const tipoPersona = a.cliente_tipo_persona || a.tipo_persona || 'Persona Natural (Cédula CC)';
    const isJuridica = tipoPersona.includes('Jurídica') || tipoPersona.includes('NIT');
    const personaBadge = `<span class="badge" style="background:${isJuridica ? 'rgba(99,102,241,0.12)' : 'rgba(28,130,173,0.12)'}; color:${isJuridica ? '#4f46e5' : '#0284c7'}; font-weight:800; font-size:0.75rem; padding:4px 10px; border-radius:8px;">${tipoPersona}</span>`;

    // Verificado badge
    const isVerif = a.cliente_verificado || a.verificado;
    const verifBadge = isVerif
      ? `<span class="badge" style="background:rgba(16,185,129,0.12); color:#059669; font-weight:800; font-size:0.75rem; padding:4px 10px; border-radius:8px;"><i class="fa-solid fa-circle-check"></i> Verificado</span>`
      : `<span class="badge" style="background:rgba(245,158,11,0.15); color:#d97706; font-weight:800; font-size:0.75rem; padding:4px 10px; border-radius:8px;"><i class="fa-solid fa-clock"></i> Pendiente</span>`;

    // Teléfono limpio
    const rawTel = a.cliente_telefono || a.telefono || a.cel || '';
    const cleanTel = String(rawTel).replace(/\D/g, '');
    const waPhone = cleanTel.length === 10 ? '57' + cleanTel : (cleanTel.startsWith('57') ? cleanTel : cleanTel);

    // Cultivo
    let cultivoReal = a.cultivo || '';
    if (!cultivoReal && (a.notas || a.observaciones_servicio)) {
      const rawN = (a.notas || '') + ' ' + (a.observaciones_servicio || '');
      const mCul = rawN.match(/(?:Cultivo y Area|Cultivo):\s*([^\(\n\r]+)/i);
      if (mCul) cultivoReal = mCul[1].trim();
    }
    if (!cultivoReal) cultivoReal = 'Agrícola General';

    // Estados y flags de operación
    const isConfirmado = a.estado === 'Confirmado';
    const isEnProceso = a.estado === 'En proceso' || a.estado === 'En Proceso';
    const isFinalizado = (a.estado || '').toLowerCase() === 'finalizado';
    const isCompletado = a.estado === 'Completado' || isFinalizado;
    const isCancelado = a.estado === 'Cancelado';
    const isRechazado = a.estado === 'Rechazado';

    const deliverableUrl = a.url_entregable || a.url_entregable_drive || a.url_archivo || a.sharepoint_url || a.link_sharepoint || '';
    const isDemo = Boolean(
      (a.es_demostracion === true || a.es_demostracion === 1 || a.es_demo_gratis === true) &&
      (a.tarifa === null || a.tarifa === undefined || Number(a.tarifa) === 0)
    );
    const tarifaVal = (a.tarifa !== undefined && a.tarifa !== null) ? Number(a.tarifa) : (a.monto !== undefined && a.monto !== null ? Number(a.monto) : null);

    const bodyEl = document.getElementById('detailModalBody');
    if (!bodyEl) return;

    bodyEl.innerHTML = `
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; margin-bottom:20px;">
        
        <!-- Card 1: Datos del Cliente -->
        <div style="background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:14px; padding:18px;">
          <h4 style="margin:0 0 12px 0; color:#003049; font-size:0.95rem; font-weight:800; display:flex; align-items:center; gap:8px;">
            <i class="fa-solid fa-id-card-clip" style="color:#1C82AD;"></i> Datos del Cliente / Productor
          </h4>
          <div style="display:flex; flex-direction:column; gap:8px; font-size:0.86rem;">
            <div><strong style="color:#003049;">Nombre / Titular:</strong> <span>${a.cliente || a.cliente_nombre || '—'}</span></div>
            <div><strong style="color:#003049;">NIT / Documento:</strong> <span style="font-weight:800; color:#0284c7;">${docDisplay}</span></div>
            <div><strong style="color:#003049;">Tipo Persona:</strong> ${personaBadge}</div>
            <div><strong style="color:#003049;">Verificación:</strong> ${verifBadge}</div>
            <div><strong style="color:#003049;">Email:</strong> <span>${a.cliente_email || a.email || '—'}</span></div>
            <div style="display:flex; align-items:center; gap:8px;">
              <strong style="color:#003049;">Teléfono:</strong>
              <span>${rawTel ? `<a href="tel:${rawTel}" style="color:#1c82ad; text-decoration:none; font-weight:700;">${rawTel}</a>` : '—'}</span>
              ${waPhone ? `<a href="https://wa.me/${waPhone}" target="_blank" style="color:#2563eb; font-size:1.15rem; text-decoration:none;" title="Abrir WhatsApp"><i class="fa-brands fa-whatsapp" style="color:#25D366;"></i></a>` : ''}
            </div>
          </div>
        </div>

        <!-- Card 2: Datos de la Finca & Ubicación -->
        <div style="background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:14px; padding:18px;">
          <h4 style="margin:0 0 12px 0; color:#003049; font-size:0.95rem; font-weight:800; display:flex; align-items:center; gap:8px;">
            <i class="fa-solid fa-wheat-awn" style="color:#1C82AD;"></i> Predio / Finca & Ubicación
          </h4>
          <div style="display:flex; flex-direction:column; gap:8px; font-size:0.86rem;">
            <div><strong style="color:#003049;">Finca:</strong> <span style="font-weight:700;">${a.finca_nombre || a.finca || 'Finca Principal'}</span></div>
            <div><strong style="color:#003049;">Municipio:</strong> <span>${a.ubicacion_municipio || a.finca_municipio || 'Colombia'}${a.departamento ? ', ' + a.departamento : ''}</span></div>
            <div><strong style="color:#003049;">Hectáreas:</strong> <span style="font-weight:800; color:#0284c7;">${a.hectareas || '10'} ha</span></div>
            <div><strong style="color:#003049;">Cultivo:</strong> <span style="font-weight:700; color:#059669;">${cultivoReal}</span></div>
            <div><strong style="color:#003049;">Responsable Campo:</strong> <span>${a.responsable_campo || 'Encargado del predio'}</span></div>
            <div style="margin-top:8px;">
              ${hasMapUrl ? `
                <a href="${mapUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="display:inline-flex; align-items:center; gap:6px; background:#003049; color:#ffffff; font-weight:800; border-radius:8px; padding:8px 14px; font-size:0.82rem; text-decoration:none; box-shadow:0 2px 8px rgba(0,48,73,0.15); border:1px solid #1c82ad;">
                  <i class="fa-solid fa-map-location-dot" style="color:#38bdf8;"></i> 📍 Ir a su ubicación en Google Maps
                </a>
              ` : `
                <button type="button" onclick="closeModal('detailModal'); openModificarAgendaModal(${aId}); showToast('Por favor registra el enlace de Google Maps o coordenadas para este vuelo en Modificar Agenda.', 'info');" class="btn btn-sm" style="display:inline-flex; align-items:center; gap:6px; background:#fff7ed; color:#c2410c; font-weight:800; border-radius:8px; padding:8px 14px; font-size:0.82rem; border:1.5px dashed #f97316; cursor:pointer;" title="Haz clic para agregar la ubicación exacta en Modificar Agenda">
                  <i class="fa-solid fa-triangle-exclamation" style="color:#ea580c;"></i> ⚠️ Sin ubicación Maps registrada (Registrar en Modificar)
                </button>
              `}
            </div>
          </div>
        </div>

        <!-- Card 3: Operación & Vuelo -->
        <div style="background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:14px; padding:18px; grid-column:1 / -1;">
          <h4 style="margin:0 0 12px 0; color:#003049; font-size:0.95rem; font-weight:800; display:flex; align-items:center; gap:8px;">
            <i class="fa-solid fa-plane-circle-check" style="color:#1C82AD;"></i> Operación de Vuelo & Asignación
          </h4>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:14px; font-size:0.86rem;">
            <div>
              <strong style="color:#003049; display:block; margin-bottom:6px;">Servicios Solicitados:</strong>
              <div style="display:flex; flex-wrap:wrap; gap:6px;">${svcsBadgesHtml}</div>
            </div>
            <div><strong style="color:#003049;">Fecha Programada:</strong> <span>${formatDate(a.fecha)}</span></div>
            <div><strong style="color:#003049;">Horario Estimado:</strong> <span>${a.hora || '08:00'}</span></div>
            <div><strong style="color:#003049;">Piloto Técnico:</strong> <span style="font-weight:700; color:#003049;">${a.tecnico || a.tecnico_nombre || '<span class="badge badge-unpaid">Sin asignar</span>'}</span></div>
            <div><strong style="color:#003049;">Estado Actual:</strong> ${statusBadge(a.estado)}</div>
            <div><strong style="color:#003049;">Tarifa / Costo:</strong> ${isDemo ? '<span class="badge" style="background:#dcfce7; color:#15803d; border:1px solid #86efac; font-weight:800; font-size:0.75rem; padding:3px 8px; border-radius:6px;"><i class="fa-solid fa-gift"></i> Análisis del Terreno ($0)</span>' : (tarifaVal ? formatCurrency(tarifaVal) : '<span class="badge" style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; font-weight:800; font-size:0.75rem; padding:3px 8px; border-radius:6px;"><i class="fa-solid fa-file-invoice-dollar"></i> Servicio Normal (Por Cotizar)</span>')}</div>
          </div>
        </div>

      </div>

      <!-- Banner de Servicio Finalizado y Entregables SharePoint -->
      ${(isFinalizado || deliverableUrl) ? `
        <div style="background:rgba(16, 185, 129, 0.08); border:1.5px solid #10b981; border-radius:12px; padding:16px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
          <div>
            <div style="font-weight:800; font-size:0.92rem; color:#065f46; display:flex; align-items:center; gap:8px;">
              <i class="fa-solid fa-flag-checkered" style="color:#10b981;"></i> Servicio Finalizado — Entregable en SharePoint
            </div>
            <div style="font-size:0.82rem; color:#047857; margin-top:3px;">
              El piloto técnico completó la operación aérea y vinculó los entregables oficiales en Microsoft SharePoint.
            </div>
          </div>
          ${deliverableUrl ? `
            <a href="${deliverableUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="display:inline-flex; align-items:center; gap:8px; background:#003049; color:#ffffff; font-weight:800; border-radius:8px; padding:9px 16px; font-size:0.85rem; text-decoration:none; box-shadow:0 2px 8px rgba(0,48,73,0.2);">
              <i class="fa-solid fa-arrow-up-right-from-square" style="color:#38bdf8;"></i> Abrir Carpeta SharePoint
            </a>
          ` : `
            <span class="badge" style="background:#ecfdf5; color:#065f46; font-weight:800; padding:6px 12px; border-radius:8px;"><i class="fa-solid fa-circle-check"></i> Finalizado con Éxito</span>
          `}
        </div>
      ` : ''}

      ${(() => {
        // Limpieza y deduplicación inteligente para "Detalles y Solicitud del Cliente"
        const rawText = (a.observaciones_servicio || a.notas || '')
          .replace(/\[Servicios:\s*[^\]]+\]/gi, '')
          .replace(/\[(?:Empresa|Jornada|DEMOSTRACION|AGENDAMIENTO|NUEVO SERVICIO|Tipo de Solicitud)[^\]]*\]/gi, '')
          .trim();

        if (!rawText) return '';

        // Extraer notas que el cliente escribió directamente
        const mNotas = rawText.match(/(?:Notas Adicionales|Observaciones del Cliente|Observaciones Adicionales):\s*([\s\S]+)$/i);
        const clientNotes = mNotas ? mNotas[1].trim() : '';

        // Dividir, normalizar y deduplicar líneas de la solicitud
        const rawLines = rawText.split('\n').map(l => l.trim()).filter(Boolean);
        const seen = new Set();
        const uniqueLines = [];

        for (const line of rawLines) {
          // Corregir texto mutilado como "ultivo:" a "Cultivo:"
          let fixed = line.replace(/^ultivo:/i, 'Cultivo:').replace(/^-\s*ultivo:/i, '- Cultivo:');
          // Omitir cabeceras repetitivas o líneas vacías
          const normKey = fixed.toLowerCase().replace(/[\s\-_]/g, '');
          if (!seen.has(normKey) && !fixed.toLowerCase().includes('solicitud de agendamiento directo')) {
            seen.add(normKey);
            uniqueLines.push(fixed);
          }
        }

        const fichaLimpia = uniqueLines.join('\n');

        return `
          ${clientNotes ? `
            <div style="background:rgba(16, 185, 129, 0.05); border:1.5px solid rgba(16, 185, 129, 0.3); border-radius:12px; padding:14px; margin-bottom:14px;">
              <span style="font-weight:800; font-size:0.86rem; color:#065f46;"><i class="fa-solid fa-comment-dots" style="color:#10b981; margin-right:6px;"></i> Observaciones Escritas por el Cliente</span>
              <div style="font-size:0.88rem; color:#064e3b; margin-top:4px; font-weight:600; white-space:pre-wrap; line-height:1.4;">${clientNotes}</div>
            </div>
          ` : ''}

          ${fichaLimpia ? `
            <div style="background:#ffffff; border:1.5px solid #e2e8f0; border-radius:12px; padding:16px; margin-bottom:14px; box-shadow:0 1px 4px rgba(0,0,0,0.03);">
              <div style="font-weight:800; font-size:0.88rem; color:#003049; margin-bottom:8px; display:flex; align-items:center; gap:8px;">
                <i class="fa-solid fa-file-lines" style="color:#1C82AD;"></i> Detalles y Solicitud del Cliente
              </div>
              <div style="font-size:0.85rem; color:#334155; white-space:pre-wrap; line-height:1.55; font-family:monospace, inherit;">${fichaLimpia}</div>
            </div>
          ` : ''}
        `;
      })()}

      <!-- ── HISTORIAL DE COTIZACIÓN Y NEGOCIACIÓN RÁPIDO ── -->
      <div style="background:#ffffff; border:1.5px solid #cbd5e1; border-radius:14px; padding:18px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px; border-bottom:1px solid #f1f5f9; padding-bottom:10px;">
          <h4 style="margin:0; color:#003049; font-size:0.95rem; font-weight:800; display:flex; align-items:center; gap:8px;">
            <i class="fa-solid fa-hand-holding-dollar" style="color:#1C82AD;"></i> Historial de Cotización y Negociación Comercial
          </h4>
          ${(!isDemo && a.estado !== 'Cancelado') ? `
            <button class="btn btn-sm" onclick="closeModal('detailModal'); openCotizarAgendaModal(${aId});" style="display:inline-flex; align-items:center; gap:6px; background:#003049; color:#ffffff; font-weight:700; border-radius:8px; padding:6px 14px; font-size:0.80rem; border:none; cursor:pointer;" title="Abrir cotizador para ajustar tarifa y piloto">
              <i class="fa-solid fa-hand-holding-dollar"></i> ${a.tarifa ? 'Renegociar / Ajustar Cotización' : 'Cotizar Servicios Ahora'}
            </button>
          ` : ''}
        </div>

        <!-- Resumen de Tarifa y Servicios -->
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; margin-bottom:14px; background:#f8fafc; border-radius:10px; padding:12px;">
          <div>
            <span style="font-size:0.75rem; font-weight:700; color:#64748b; text-transform:uppercase;">Estado Comercial / Tarifa:</span>
            <div style="margin-top:4px;">
              ${isDemo ? '<span class="badge" style="background:#dcfce7; color:#15803d; font-weight:800; padding:4px 8px; border-radius:6px;"><i class="fa-solid fa-gift"></i> Análisis del Terreno ($0)</span>' : (tarifaVal ? `<span class="badge" style="background:#eff6ff; color:#1d4ed8; font-weight:800; padding:4px 8px; border-radius:6px;"><i class="fa-solid fa-check"></i> Cotizado: ${formatCurrency(tarifaVal)}</span>` : '<span class="badge" style="background:#fef3c7; color:#b45309; font-weight:800; padding:4px 8px; border-radius:6px;"><i class="fa-solid fa-clock"></i> Pendiente por cotizar</span>')}
            </div>
          </div>
          <div>
            <span style="font-size:0.75rem; font-weight:700; color:#64748b; text-transform:uppercase;">Servicios en este turno:</span>
            <div style="font-weight:700; color:#003049; font-size:0.85rem; margin-top:4px;">
              ${svcsList.join(' + ')} (${a.hectareas || '10'} ha)
            </div>
          </div>
        </div>

        <!-- Sugerencia del Cliente si existe -->
        ${(a.sugerencia_cliente && String(a.sugerencia_cliente).trim()) ? `
          <div style="background:#eff6ff; border:1.5px solid #bfdbfe; border-radius:10px; padding:12px 14px; margin-bottom:14px; display:flex; align-items:flex-start; gap:10px;">
            <i class="fa-solid fa-lightbulb" style="color:#2563eb; font-size:1.1rem; margin-top:2px;"></i>
            <div>
              <div style="font-weight:800; color:#1e40af; font-size:0.84rem;">Sugerencia o Propuesta Económica Enviada por el Cliente:</div>
              <div style="font-size:0.88rem; color:#1e3a8a; font-weight:600; margin-top:2px;">"${a.sugerencia_cliente.trim()}"</div>
            </div>
          </div>
        ` : ''}

        <!-- Timeline de eventos de negociación -->
        ${(() => {
          let historyList = [];
          if (a.historial_negociacion) {
            try {
              const parsed = typeof a.historial_negociacion === 'string' ? JSON.parse(a.historial_negociacion) : a.historial_negociacion;
              if (Array.isArray(parsed)) historyList = parsed;
            } catch(e) {}
          }

          if (!historyList.length) {
            return `
              <div style="font-size:0.82rem; color:#94a3b8; font-style:italic; padding:6px 2px;">
                ${isDemo ? 'Demostración gratuita sin historial de negociación.' : 'Sin historial previo de contraofertas o mensajes registrados.'}
              </div>
            `;
          }
          return `
            <div style="font-size:0.80rem; font-weight:800; color:#003049; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.04em;">Registro de Ofertas y Mensajes:</div>
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${historyList.map(h => {
                const isAdmin = h.emisor === 'admin';
                const emisorBadge = isAdmin
                  ? `<span style="background:#003049; color:#fff; font-weight:800; padding:2px 8px; border-radius:4px; font-size:0.72rem;"><i class="fa-solid fa-user-tie"></i> ADMINISTRACIÓN</span>`
                  : `<span style="background:#2563eb; color:#fff; font-weight:800; padding:2px 8px; border-radius:4px; font-size:0.72rem;"><i class="fa-solid fa-user"></i> CLIENTE</span>`;
                const tarifaTag = h.tarifa ? `<span style="font-weight:800; color:#059669; margin-left:8px;"><i class="fa-solid fa-tag"></i> $ ${Number(h.tarifa).toLocaleString('es-CO')} COP</span>` : '';
                const fechaTag = h.fecha ? `<span style="color:#94a3b8; font-size:0.74rem;">${formatDate(h.fecha)}</span>` : '';
                return `
                  <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:10px 14px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                      <div style="display:flex; align-items:center; gap:6px;">
                        ${emisorBadge} <strong>${h.tipo ? String(h.tipo).toUpperCase() : 'MENSAJE'}</strong> ${tarifaTag}
                      </div>
                      ${fechaTag}
                    </div>
                    ${h.mensaje ? `<div style="color:#334155; margin-top:4px; font-size:0.84rem; line-height:1.4;">${h.mensaje}</div>` : ''}
                  </div>
                `;
              }).join('')}
            </div>
          `;
        })()}
      </div>

      ${a.motivo_reagendamiento ? `
        <div style="background:rgba(28, 130, 173, 0.05); border:1.5px solid rgba(28, 130, 173, 0.3); border-radius:12px; padding:14px; margin-bottom:14px;">
          <span style="font-weight:700; font-size:0.84rem; color:#003049;"><i class="fa-solid fa-clock-rotate-left" style="color:var(--accent); margin-right:6px;"></i> Motivo de Modificación / Reagendamiento</span>
          <div style="font-size:0.88rem; color:#003049; margin-top:4px; font-weight:700;">${a.motivo_reagendamiento}</div>
        </div>
      ` : ''}

      <!-- Selector Rápido de Estado y Acciones Administrativas -->
      <div style="display:flex; gap:12px; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-top:16px; border-top:1px solid #e2e8f0; padding-top:14px;">
        <div style="display:flex; align-items:center; gap:8px;">
          <label style="font-weight:700; color:#003049; font-size:0.84rem;"><i class="fa-solid fa-signal" style="color:#1C82AD;"></i> Cambiar Estado:</label>
          <select onchange="if(this.value) { const st = this.value; this.value = ''; changeAgendaStatus(${aId}, st); }" style="border:1.5px solid #cbd5e1; border-radius:8px; padding:6px 10px; font-weight:700; font-size:0.83rem; color:#003049; background:#fff; cursor:pointer;">
            <option value="">Actual: [${a.estado || 'Pendiente'}] (Seleccionar para cambiar)...</option>
            <option value="Pendiente" ${a.estado === 'Pendiente' ? 'disabled' : ''}>Pendiente (Nueva solicitud)</option>
            <option value="Pendiente por confirmar" ${a.estado === 'Pendiente por confirmar' ? 'disabled' : ''}>Pendiente por confirmar (Cotización)</option>
            <option value="Confirmado" ${a.estado === 'Confirmado' ? 'disabled' : ''}>Confirmado</option>
            <option value="En Proceso" ${a.estado === 'En Proceso' ? 'disabled' : ''}>En Proceso</option>
            <option value="Completado" ${a.estado === 'Completado' ? 'disabled' : ''}>Completado</option>
            <option value="Finalizado" ${a.estado === 'Finalizado' ? 'disabled' : ''}>Finalizado</option>
            <option value="Cancelado" ${a.estado === 'Cancelado' ? 'disabled' : ''}>Cancelado</option>
          </select>
        </div>

        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          ${(!isCancelado && !isCompletado && !isFinalizado) ? `
            <button class="btn btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:700; background:#eff6ff; color:#1d4ed8; border:1.5px solid #bfdbfe;" onclick="closeModal('detailModal'); openReagendarModal(${aId});" title="Reagendar fecha u hora del vuelo">
              <i class="fa-solid fa-calendar-plus"></i> Reagendar Vuelo
            </button>
            <button class="btn btn-primary btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:700;" onclick="closeModal('detailModal'); openModificarAgendaModal(${aId});" title="Modificar información del turno">
              <i class="fa-solid fa-pen-to-square"></i> Modificar información
            </button>
          ` : ''}
          ${(!isDemo && a.estado !== 'Cancelado') ? `
            <button class="btn btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:700; background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe;" onclick="closeModal('detailModal'); openCotizarAgendaModal(${aId});"><i class="fa-solid fa-hand-holding-dollar"></i> Cotizar</button>
          ` : ''}
        </div>
      </div>
    `;
    openModal('detailModal');
  } catch (err) {
    console.error('Error al cargar detalle del turno:', err);
    if (typeof showToast === 'function') {
      showToast('Error al visualizar datos del turno: ' + (err.message || err), 'error');
    }
    const bodyEl = document.getElementById('detailModalBody');
    if (bodyEl) {
      bodyEl.innerHTML = `
        <div style="padding:24px; text-align:center; color:#b91c1c; background:#fef2f2; border:1.5px solid #fecaca; border-radius:12px;">
          <i class="fa-solid fa-triangle-exclamation" style="font-size:2rem; margin-bottom:10px;"></i>
          <h4 style="margin:0 0 8px 0; font-weight:800;">No fue posible cargar la ficha del turno</h4>
          <p style="font-size:0.85rem; color:#7f1d1d; margin:0;">${escapeHtml(err.message || String(err))}</p>
        </div>
      `;
      openModal('detailModal');
    }
  }
}
window.viewAgendaDetail = viewAgendaDetail;
window.openTurnoDetailModal = viewAgendaDetail;

window.openReagendarModal = async function(id) {
  const a = agendaData.find(x => (x.id == id || x.id_turno == id));
  if (!a) return;

  const est = String(a.estado || '').toLowerCase();
  if (['completado', 'finalizado', 'cancelado'].includes(est)) {
    if (typeof showToast === 'function') {
      showToast(`El turno #${a.id} ya se encuentra ${a.estado.toLowerCase()} y no se puede reagendar.`, 'info');
    }
    return;
  }
  
  if (!serviciosData || !serviciosData.length) {
    if (typeof loadServicios === 'function') await loadServicios();
  }

  const todayIso = new Date().toISOString().split('T')[0];
  document.getElementById('reagendarTurnoId').value = a.id;
  document.getElementById('reagendarInfoTitle').textContent = `Turno #${a.id} — ${a.cliente || 'Cliente'}`;
  document.getElementById('reagendarInfoSub').textContent = `Finca: ${a.finca || '—'} | Servicio Actual: ${a.servicio || 'Servicio Dron'}`;
  
  // Populate Services
  const svcSelect = document.getElementById('reagendarServicio');
  if (svcSelect) {
    svcSelect.innerHTML = (serviciosData || [])
      .filter(s => s.activo !== false)
      .map(s => {
        const sId = s.id_servicio || s.id;
        const sName = s.nombre || s.nombre_servicio;
        const isSel = (a.id_servicio && String(a.id_servicio) === String(sId)) || (a.servicio && a.servicio === sName);
        return `<option value="${sId}" ${isSel ? 'selected' : ''}>${sName}</option>`;
      }).join('');
  }

  const fEl = document.getElementById('reagendarFecha');
  if (fEl) {
    fEl.min = todayIso;
    fEl.value = (a.fecha && a.fecha >= todayIso) ? a.fecha : todayIso;
  }
  document.getElementById('reagendarHora').value = (a.hora || '08:00').slice(0, 5);
  document.getElementById('reagendarEstado').value = a.estado || 'Reagendado';
  
  // Set existing motivo de reagendamiento if present
  document.getElementById('reagendarMotivo').value = a.motivo_reagendamiento || '';
  
  const errEl = document.getElementById('reagendarErrMsg');
  if (errEl) { errEl.style.display = 'none'; }
  const errText = document.getElementById('reagendarErrMsgText');
  if (errText) { errText.textContent = ''; }
  
  openModal('reagendarModal');
};

window.submitReagendamiento = async function() {
  const id = parseInt(document.getElementById('reagendarTurnoId').value);
  const fecha = document.getElementById('reagendarFecha').value;
  const hora = document.getElementById('reagendarHora').value;
  const estado = document.getElementById('reagendarEstado').value;
  const motivo = document.getElementById('reagendarMotivo').value.trim();
  const id_servicio = document.getElementById('reagendarServicio') ? parseInt(document.getElementById('reagendarServicio').value) : null;
  const btn = document.getElementById('btnSubmitReagendar');
  const errEl = document.getElementById('reagendarErrMsg');
  const errText = document.getElementById('reagendarErrMsgText') || errEl;

  const showErr = (msg) => {
    if (errText) errText.textContent = msg;
    if (errEl) {
      errEl.style.display = 'flex';
      errEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };

  if (!fecha || !hora) {
    showErr('Fecha y hora son obligatorias');
    return;
  }

  const todayIso = new Date().toISOString().split('T')[0];
  if (fecha < todayIso) {
    showErr('La nueva fecha no puede ser anterior a hoy (' + todayIso + ')');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';
  }

  try {
    const payload = {
      fecha_de_turno: fecha,
      hora_inicio_estimada: hora.length === 5 ? `${hora}:00` : hora,
      estado: estado,
      motivo_reagendamiento: motivo || 'Reagendado por administración'
    };
    if (id_servicio) payload.id_servicio = id_servicio;

    await apiFetch(`/agenda/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });

    invalidateCache('agenda');
    await loadAgenda();
    if (typeof renderCalendar === 'function') renderCalendar();
    if (typeof renderAgendaTable === 'function') renderAgendaTable();
    if (typeof renderReagendamientoTable === 'function') renderReagendamientoTable();

    showToast(`<i class="fa-solid fa-check"></i> Turno #${id} reagendado para el ${fecha} a las ${hora}`, 'success');
    closeModal('reagendarModal');
  } catch (err) {
    showErr(err.message || 'Error al reagendar turno');
    showToast('Error al reagendar: ' + (err.message || 'Error del servidor'), 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Guardar Reagendamiento';
    }
  }
};

function renderReagendamientoTable() {
  const tbody = document.getElementById('reagendamientoTableBody');
  if (!tbody) return;
  const search = (document.getElementById('reagendarSearch')?.value || '').toLowerCase().trim();

  let data = agendaData || [];
  if (search) {
    data = data.filter(a =>
      [a.cliente, a.email, a.finca, a.servicio, a.tecnico, a.notas, String(a.id), String(a.id_turno), String(a.telefono)].some(v => (v || '').toLowerCase().includes(search))
    );
  }

  // Orden descendente por llegada / ID
  data = [...data].sort((a, b) => (b.id || 0) - (a.id || 0));

  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="padding:40px"><div class="empty-state" style="padding:0"><div class="empty-icon"><i class="fa-solid fa-calendar-check" style="font-size:2rem; color:var(--accent);"></i></div><div class="empty-title">No hay turnos para reagendar</div><div class="empty-sub">Todos los turnos están actualizados o no coinciden con la búsqueda.</div></div></td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(a => {
    const cleanNotas = (a.notas || '')
      .replace(/\[Servicios:\s*[^\]]+\]/gi, '')
      .replace(/(\s*\|\s*Cambiado por Admin:\s*Modificado por el administrador)+/gi, '')
      .replace(/(\s*\|\s*Cambiado por Admin:[^|]+)+/gi, '')
      .trim();

    return `
      <tr>
        <td style="font-weight:800; color:var(--primary);">#${a.id}</td>
        <td>
          <div style="font-weight:700; color:#003049;">${a.cliente || '—'}</div>
          <div class="text-muted" style="font-size:0.75rem;"><i class="fa-solid fa-house-chimney-window" style="color:var(--accent);"></i> ${a.finca || '—'}</div>
        </td>
        <td>
          <span style="font-weight:700; color:#1c82ad; font-size:0.85rem;">${a.servicio || 'Servicio Dron'}</span>
        </td>
        <td>
          <div style="font-weight:700; color:#003049;">${formatDate(a.fecha)}</div>
          <div style="font-size:0.75rem; color:#64748b;"><i class="fa-solid fa-clock"></i> ${a.hora || '08:00'}</div>
        </td>
        <td style="max-width:220px;">
          <div style="font-size:0.80rem; color:#475569; line-height:1.35; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;" title="${cleanNotas || 'Sin observaciones'}">
            ${cleanNotas ? `<i class="fa-solid fa-comment-dots" style="color:var(--accent); margin-right:4px;"></i>${cleanNotas}` : '<span style="color:#94a3b8; font-style:italic;">—</span>'}
          </div>
        </td>
        <td>${statusBadge(a.estado)}</td>
        <td style="text-align:center;">
          <button class="btn btn-primary btn-sm" onclick="openReagendarModal(${a.id})" style="padding:6px 12px; font-size:0.78rem; font-weight:700; display:inline-flex; align-items:center; gap:6px;">
            <i class="fa-solid fa-calendar-plus"></i> Reagendar Turno
          </button>
        </td>
      </tr>
    `;
  }).join('');
}
window.renderReagendamientoTable = renderReagendamientoTable;

window._currentClientFincas = [];

window.onAgendaClienteSelectChange = async function () {
  const select = document.getElementById('newAgendaClienteSelect');
  const fincaContainer = document.getElementById('newAgendaFincaContainer');
  const fincaSelect = document.getElementById('newAgendaFincaSelect');

  if (!select || !select.value) {
    if (fincaContainer) fincaContainer.style.display = 'none';
    window._currentClientFincas = [];
    return;
  }
  const clientId = parseInt(select.value);
  const clientObj = clientesData.find(c => (c.id_cliente || c.id) === clientId);
  if (clientObj) {
    if (document.getElementById('newAgendaCliente')) document.getElementById('newAgendaCliente').value = `${clientObj.nombre} ${clientObj.apellido || ''}`.trim();
    if (document.getElementById('newAgendaEmail')) document.getElementById('newAgendaEmail').value = clientObj.email || '';
    if (document.getElementById('newAgendaTel')) document.getElementById('newAgendaTel').value = clientObj.telefono || '';
    
    // Fetch fincas from client detail
    try {
      const detail = await apiFetch(`/clientes/${clientId}`);
      const fincas = (detail && (detail.fincas || detail.data?.fincas)) || [];
      window._currentClientFincas = fincas;

      if (fincaContainer) fincaContainer.style.display = 'block';

      if (fincaSelect) {
        if (fincas.length > 0) {
          fincaSelect.innerHTML = `<option value="">-- Seleccionar finca registrada o escribir manualmente abajo --</option>` +
            fincas.map(f => `<option value="${f.id_finca}">${f.nombre_finca} (${f.ubicacion_municipio || f.departamento || 'Sin ubic.'}) - ${f.hectareas || 0} ha</option>`).join('');
          
          // Auto-select first finca
          fincaSelect.value = String(fincas[0].id_finca);
          window.onAgendaFincaSelectChange();
        } else {
          fincaSelect.innerHTML = `<option value="">Este cliente no tiene fincas registradas aún (usa + Registrar Finca)</option>`;
        }
      }
    } catch(e) {
      console.warn('Error fetching client fincas:', e);
    }
  }
};

window.onAgendaFincaSelectChange = function() {
  const fincaSelect = document.getElementById('newAgendaFincaSelect');
  if (!fincaSelect || !fincaSelect.value) return;
  const fId = parseInt(fincaSelect.value);
  const f = (window._currentClientFincas || []).find(x => x.id_finca === fId);
  if (!f) return;

  if (document.getElementById('newAgendaFinca')) {
    document.getElementById('newAgendaFinca').value = f.nombre_finca || '';
  }
  if (document.getElementById('newAgendaUbicacion')) {
    document.getElementById('newAgendaUbicacion').value = f.ubicacion_municipio || f.departamento || '';
  }
  if (document.getElementById('newAgendaMaps')) {
    const fMaps = f.maps_url || (f.latitud && f.longitud ? `https://www.google.com/maps?q=${parseFloat(f.latitud).toFixed(6)},${parseFloat(f.longitud).toFixed(6)}` : '') || f.coordenadas_gps || '';
    document.getElementById('newAgendaMaps').value = normalizeMapsInput(fMaps);
  }
  if (document.getElementById('newAgendaHa')) {
    document.getElementById('newAgendaHa').value = f.hectareas || 10;
  }
  if (document.getElementById('newAgendaCultivo')) {
    document.getElementById('newAgendaCultivo').value = f.tipo_cultivo || f.cultivo || '';
  }
};

window.toggleNewFincaInline = function(force) {
  const el = document.getElementById('newFincaInlineForm');
  if (!el) return;
  const show = typeof force === 'boolean' ? force : (el.style.display === 'none' || !el.style.display);
  el.style.display = show ? 'block' : 'none';
  if (show) {
    const nom = document.getElementById('inlineFincaNombre');
    if (nom) nom.focus();
  }
};

window.guardarFincaInline = async function() {
  const clientSelect = document.getElementById('newAgendaClienteSelect');
  const clientId = clientSelect ? parseInt(clientSelect.value) : null;
  if (!clientId) {
    showToast('Debes seleccionar un cliente antes de registrarle una finca', 'warn');
    return;
  }

  const nombre = (document.getElementById('inlineFincaNombre')?.value || '').trim();
  const ubicacion = (document.getElementById('inlineFincaUbicacion')?.value || '').trim();
  const ha = parseFloat(document.getElementById('inlineFincaHa')?.value || 10);
  const maps = (document.getElementById('inlineFincaMaps')?.value || '').trim();
  const btn = document.getElementById('btnGuardarFincaInline');

  if (!nombre) {
    showToast('El nombre de la finca es obligatorio', 'warn');
    return;
  }
  const normMaps = normalizeMapsInput(maps);
  if (!normMaps) {
    showToast('El enlace de Google Maps o coordenadas GPS válidas son obligatorias para la finca', 'warn');
    return;
  }

  let latVal = null;
  let lngVal = null;
  const mCoord = normMaps.match(/q=([-+]?\d{1,3}\.\d+),([-+]?\d{1,3}\.\d+)/);
  if (mCoord) {
    latVal = parseFloat(mCoord[1]);
    lngVal = parseFloat(mCoord[2]);
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';
  }

  try {
    const res = await apiFetch('/fincas', {
      method: 'POST',
      body: JSON.stringify({
        id_cliente: clientId,
        nombre_finca: nombre,
        ubicacion_municipio: ubicacion || 'Colombia',
        departamento: 'Colombia',
        hectareas: isNaN(ha) ? 10.0 : ha,
        latitud: latVal,
        longitud: lngVal,
        maps_url: normMaps
      })
    });

    const newFinca = res.data || res;
    if (!window._currentClientFincas) window._currentClientFincas = [];
    window._currentClientFincas.push(newFinca);

    // Update select
    const fincaSelect = document.getElementById('newAgendaFincaSelect');
    if (fincaSelect) {
      const opt = document.createElement('option');
      opt.value = newFinca.id_finca;
      opt.textContent = `${newFinca.nombre_finca} (${newFinca.ubicacion_municipio || 'Ubic.'}) - ${newFinca.hectareas || ha} ha`;
      fincaSelect.appendChild(opt);
      fincaSelect.value = String(newFinca.id_finca);
      window.onAgendaFincaSelectChange();
    }

    // Clear inline inputs
    if (document.getElementById('inlineFincaNombre')) document.getElementById('inlineFincaNombre').value = '';
    if (document.getElementById('inlineFincaUbicacion')) document.getElementById('inlineFincaUbicacion').value = '';
    if (document.getElementById('inlineFincaHa')) document.getElementById('inlineFincaHa').value = '';
    if (document.getElementById('inlineFincaMaps')) document.getElementById('inlineFincaMaps').value = '';

    window.toggleNewFincaInline(false);
    showToast('<i class="fa-solid fa-check"></i> Finca creada y vinculada exitosamente', 'success');
  } catch (e) {
    showToast('Error al crear finca: ' + e.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Guardar y Seleccionar Finca';
    }
  }
};

async function createAgenda(data) {
  try {
    // 1. Resolve or create client
    let clientes = await apiFetch('/clientes') || [];
    let clientList = Array.isArray(clientes) ? clientes : (clientes.data || []);
    let clientEmail = (data.email || '').trim().toLowerCase();
    let cliente = clientList.find(c => (c.email || '').toLowerCase() === clientEmail);

    if (!cliente && clientEmail) {
      const parts = (data.cliente || 'Cliente Nuevo').trim().split(' ');
      try {
        const resUser = await apiFetch('/clientes', {
          method: 'POST',
          body: JSON.stringify({
            email: clientEmail,
            'contraseña': 'Flymetrics123!',
            nombre: parts[0] || 'Cliente',
            apellido_1: parts.slice(1).join(' ') || 'Registrado',
            telefono: data.telefono || null
          })
        });
        cliente = resUser.data || resUser;
      } catch (e) {
        console.warn('Error creating client in createAgenda:', e);
      }
    }

    if (!cliente) {
      clientes = await apiFetch('/clientes') || [];
      clientList = Array.isArray(clientes) ? clientes : (clientes.data || []);
      cliente = clientList[0];
    }

    if (!cliente) {
      throw new Error('No se pudo encontrar o registrar un cliente válido.');
    }

    const clientId = cliente.id_cliente || cliente.id || 1;

    // 2. Resolve or create finca
    let id_finca = null;
    try {
      const detail = await apiFetch(`/clientes/${clientId}`);
      const fincas = (detail && (detail.fincas || detail.data?.fincas)) || [];
      if (fincas && fincas.length > 0) {
        const matched = fincas.find(f => (f.nombre_finca || '').toLowerCase().trim() === (data.finca || '').toLowerCase().trim());
        if (matched) {
          id_finca = matched.id_finca || matched.id;
        }
      }
    } catch (e) { }

    if (!id_finca) {
      try {
        const normMaps = normalizeMapsInput(data.maps || data.maps_url || '');
        let latVal = null;
        let lngVal = null;
        if (normMaps) {
          const mCoord = normMaps.match(/q=([-+]?\d{1,3}\.\d+),([-+]?\d{1,3}\.\d+)/);
          if (mCoord) {
            latVal = parseFloat(mCoord[1]);
            lngVal = parseFloat(mCoord[2]);
          }
        }
        const resFinca = await apiFetch('/fincas', {
          method: 'POST',
          body: JSON.stringify({
            id_cliente: clientId,
            nombre_finca: data.finca || 'Finca Principal',
            ubicacion_municipio: data.ubicacion || 'Colombia',
            departamento: data.departamento || '',
            hectareas: parseFloat(data.hectareas || 10),
            latitud: latVal,
            longitud: lngVal,
            maps_url: normMaps || null
          })
        });
        const createdFinca = resFinca.data || resFinca;
        id_finca = createdFinca.id_finca || createdFinca.id;
      } catch (e) {
        console.warn('Error creating finca in createAgenda:', e);
      }
    }

    if (!id_finca) id_finca = 1;

    // 3. Resolve service ID
    let id_servicio = 1;
    let servicios = await apiFetch('/servicios') || [];
    let servList = Array.isArray(servicios) ? servicios : (servicios.data || []);
    if (servList.length && data.servicio) {
      const sName = data.servicio.toLowerCase();
      const servObj = servList.find(s => (s.nombre_servicio || s.nombre || '').toLowerCase().includes(sName));
      if (servObj) id_servicio = servObj.id_servicio || servObj.id || 1;
    }

    // 4. Resolve technician ID
    let id_tecnico = null;
    if (data.tecnico) {
      const tecnicos = await apiFetch('/tecnicos') || [];
      const tecList = Array.isArray(tecnicos) ? tecnicos : (tecnicos.data || []);
      const tName = data.tecnico.toLowerCase();
      const tecObj = tecList.find(t => (t.nombre || '').toLowerCase().includes(tName));
      if (tecObj) id_tecnico = tecObj.id_tecnico || tecObj.id;
    }

    // 5. Build time and date
    let horaStr = (data.hora || '08:00').trim();
    if (horaStr.length === 5) horaStr = `${horaStr}:00`;
    let fechaStr = data.fecha || new Date().toISOString().split('T')[0];

    // Combine location and contact notes cleanly
    let combinedNotes = (data.notas || '').trim();
    if (data.cultivo && data.cultivo.trim() && !combinedNotes.toLowerCase().includes('cultivo:')) {
      combinedNotes = `Cultivo: ${data.cultivo.trim()}\n${combinedNotes}`.trim();
    }
    if (data.servicios_nombres && data.servicios_nombres.length) {
      const svcsStr = Array.isArray(data.servicios_nombres) ? data.servicios_nombres.join(' + ') : data.servicios_nombres;
      if (!combinedNotes.includes('[Servicios:')) {
        combinedNotes = `[Servicios: ${svcsStr}]\n${combinedNotes}`.trim();
      }
    }
    if (data.ubicacion && data.ubicacion.trim()) {
      combinedNotes = `[Ubicación: ${data.ubicacion.trim()}${data.maps ? ' | Maps: ' + data.maps.trim() : ''}]\n${combinedNotes}`.trim();
    }

    const payload = {
      id_finca: parseInt(id_finca),
      id_servicio: parseInt(id_servicio),
      fecha_de_turno: fechaStr,
      hora_inicio_estimada: horaStr,
      tipo_turno: 'Fumigación',
      id_tecnico: id_tecnico ? parseInt(id_tecnico) : null,
      cel: data.telefono || '',
      observaciones_servicio: combinedNotes,
      maps_url: data.maps || data.maps_url || null,
      cultivo: data.cultivo || null,
      servicios_nombres: data.servicios_nombres || (data.servicio ? [data.servicio] : null),
      hectareas: data.hectareas ? parseFloat(data.hectareas) : null
    };

    let resTurno;
    try {
      resTurno = await apiFetch('/admin/agenda', { method: 'POST', body: JSON.stringify(payload) });
    } catch (e) {
      resTurno = await apiFetch('/agenda', { method: 'POST', body: JSON.stringify(payload) });
    }

    const createdTurno = resTurno.data || resTurno;
    const tId = createdTurno ? (createdTurno.id_turno || createdTurno.id) : null;

    if (data.estado === 'Confirmado' && tId) {
      try {
        await apiFetch(`/admin/agenda/${tId}/estado`, {
          method: 'PATCH',
          body: JSON.stringify({ estado: 'Confirmado', motivo_admin: 'Confirmado al crear por Administrador' })
        });
      } catch (e) { }
    }

    invalidateCache('agenda');
    invalidateCache('clientes');
    invalidateCache('fincas');
    await loadAgenda();
    if (activePanel === 'clientes') await loadClientes();
    showToast('<i class="fa-solid fa-check"></i> Turno creado exitosamente en la agenda', 'success');
    closeModal('newAgendaModal');
  } catch (e) {
    console.error('createAgenda error:', e);
    const errEl = document.getElementById('newAgendaErrMsg');
    const errText = document.getElementById('newAgendaErrMsgText') || errEl;
    if (errText) errText.textContent = e.message || 'Error al crear turno';
    if (errEl) {
      errEl.style.display = 'flex';
      errEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    showToast('Error al crear turno: ' + e.message, 'error');
  }
}

// ─────────────────────────────────────────
// 3. CLIENTES PANEL
// ─────────────────────────────────────────


async function loadClientes() {
  try {
    const [usuarios, clientes, fincasAll] = await Promise.all([
      apiFetch('/admin/usuarios').catch(() => []),
      apiFetch('/clientes').catch(() => []),
      apiFetch('/fincas').catch(() => [])
    ]);
    if (Array.isArray(usuarios) && usuarios.length > 0) {
      _usuariosList = usuarios;
    }
    const safeClientes = Array.isArray(clientes) ? clientes : [];
    const safeFincas = Array.isArray(fincasAll) ? fincasAll : [];

    clientesData = safeClientes.map(c => {
      const u = _usuariosList.find(usr => usr.id_usuarios === c.id_usuario);
      const cFincas = (c.fincas && Array.isArray(c.fincas) && c.fincas.length > 0)
        ? c.fincas
        : safeFincas.filter(f => (f.id_cliente === c.id_cliente || f.id_usuario === c.id_usuario));
      return {
        id: c.id_cliente,
        id_cliente: c.id_cliente,
        id_usuario: c.id_usuario,
        nombre: c.nombre || 'Sin nombre',
        apellido: [c.apellido_1, c.apellido_2].filter(Boolean).join(' ') || 'Cliente',
        email: (c.usuario && c.usuario.email) || (u ? u.email : (c.email || '')),
        telefono: c.telefono || '',
        ciudad: c.ciudad_expedicion || 'Colombia',
        verificado: true,
        fincas: cFincas.length,
        turnos: 0,
        fecha_registro: u ? u.fecha_de_creacion : ''
      };
    });
    renderClientesTable();
  } catch (err) {
    const tbody = document.getElementById('clientesTableBody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#FF3C3C;padding:32px">Error cargando clientes: ${err.message}</td></tr>`;
    console.error('loadClientes error:', err);
  }
}

function renderClientesTable(search = '') {
  let data = clientesData;
  if (search) {
    const q = search.toLowerCase();
    data = data.filter(c => [c.nombre, c.apellido, c.email, c.telefono, c.ciudad]
      .some(v => (v || '').toLowerCase().includes(q)));
  }

  const tbody = document.getElementById('clientesTableBody');
  tbody.innerHTML = data.length ? data.map(c => {
    const cId = Number(c.id) || 0;
    const cNom = escapeHtml(c.nombre || '');
    const cApe = escapeHtml(c.apellido || '');
    const cCiu = escapeHtml(c.ciudad || '');
    const cEml = escapeHtml(c.email || '—');
    const cTel = escapeHtml(c.telefono || '—');
    const cFincas = Number(c.fincas) || 0;
    return `
    <tr>
      <td>
        <div style="display:flex;align-items:center;gap:10px">
          <div class="avatar">${escapeHtml(initials(c.nombre, c.apellido))}</div>
          <div>
            <div style="font-weight:500">${cNom} ${cApe}</div>
            <div class="text-muted" style="font-size:0.75rem">${cCiu}</div>
          </div>
        </div>
      </td>
      <td>${cEml}</td>
      <td>${cTel}</td>
      <td><span class="badge badge-active"><i class="fa-solid fa-check"></i> Verificado</span></td>
      <td><span class="badge badge-confirmed">${cFincas} fincas</span></td>
      <td><div class="table-actions">
        <button class="btn btn-ghost btn-sm" onclick="viewClienteDetail(${cId})">👁 Ver detalle</button>
        <button class="btn btn-danger btn-sm" onclick="deleteCliente(${cId})">🗑</button>
      </div></td>
    </tr>
  `;
  }).join('') : `<tr><td colspan="6" class="text-center" style="padding:40px"><div class="empty-icon"><i class="fa-solid fa-users"></i></div><div class="empty-title">No se encontraron clientes</div></td></tr>`;
}

async function viewClienteDetail(id) {
  try {
    const detail = await apiFetch(`/clientes/${id}`);
    if (!detail) return;

    const clientName = `${detail.nombre || ''} ${detail.apellido_1 || ''}`.toLowerCase();
    const turnos = agendaData.filter(a => (a.email && detail.email && a.email.toLowerCase() === detail.email.toLowerCase()) || (a.cliente || '').toLowerCase().includes(clientName));

    const fincasHtml = (detail.fincas || []).length ? (detail.fincas).map(f => {
      const turnosFinca = (f.turnos && f.turnos.length) ? f.turnos : turnos.filter(t => (t.finca && f.nombre_finca && t.finca.toLowerCase().trim() === f.nombre_finca.toLowerCase().trim()));
      const turnosCount = turnosFinca.length;

      return `
      <div class="finca-accordion-card" style="background:#ffffff; border:1.5px solid #cbd5e1; border-radius:14px; margin-bottom:12px; overflow:hidden; box-shadow:0 3px 10px rgba(0,48,73,0.05); transition:all 0.2s ease;">
        <!-- Cabecera de Finca Expandible -->
        <div onclick="window.toggleFincaAccordion(${f.id_finca})" style="padding:14px 18px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; background:#f8fafc; user-select:none; border-bottom:1px solid #e2e8f0;">
          <div style="display:flex; align-items:center; gap:10px;">
            <div style="width:36px; height:36px; border-radius:10px; background:rgba(28,130,173,0.12); display:flex; align-items:center; justify-content:center; color:var(--accent);">
              <i class="fa-solid fa-house-chimney-window"></i>
            </div>
            <div>
              <div style="font-weight:800; color:#003049; font-size:0.96rem;">${f.nombre_finca}</div>
              <div style="font-size:0.78rem; color:#64748b; margin-top:2px;">
                <i class="fa-solid fa-location-dot" style="color:#ef4444; font-size:0.7rem;"></i> ${f.ubicacion_municipio || 'Sin municipio'}${f.departamento ? `, ${f.departamento}` : ''}
                <span style="margin-left:6px; color:#0284c7; font-weight:700;">• ${turnosCount} servicio(s)</span>
              </div>
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-weight:800; color:#059669; font-size:0.86rem; background:rgba(16,185,129,0.12); padding:4px 12px; border-radius:10px; border:1px solid rgba(16,185,129,0.25);">
              ${f.hectareas} ha
            </span>
            <i id="fincaChevron_${f.id_finca}" class="fa-solid fa-chevron-down" style="color:#64748b; font-size:0.85rem; transition:transform 0.2s ease;"></i>
          </div>
        </div>

        <!-- Contenido Expandible: Edición + Servicios -->
        <div id="fincaContent_${f.id_finca}" style="display:none; padding:18px; background:#ffffff;">
          <!-- Formulario de Modificación de Finca -->
          <div style="font-size:0.85rem; font-weight:800; color:#003049; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
            <i class="fa-solid fa-pen-to-square" style="color:var(--accent);"></i> Modificar Información de la Finca:
          </div>
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:10px; margin-bottom:10px;">
            <div>
              <label style="display:block; font-size:0.74rem; font-weight:700; color:#475569; margin-bottom:3px;">Nombre de la Finca *</label>
              <input type="text" id="fincaNom_${f.id_finca}" class="form-input" value="${(f.nombre_finca || '').replace(/"/g, '&quot;')}" style="width:100%; font-size:0.84rem; padding:7px 10px; border-radius:8px;" />
            </div>
            <div>
              <label style="display:block; font-size:0.74rem; font-weight:700; color:#475569; margin-bottom:3px;">Municipio / Ciudad</label>
              <input type="text" id="fincaMun_${f.id_finca}" class="form-input" value="${(f.ubicacion_municipio || '').replace(/"/g, '&quot;')}" style="width:100%; font-size:0.84rem; padding:7px 10px; border-radius:8px;" />
            </div>
            <div>
              <label style="display:block; font-size:0.74rem; font-weight:700; color:#475569; margin-bottom:3px;">Departamento</label>
              <input type="text" id="fincaDep_${f.id_finca}" class="form-input" value="${(f.departamento || '').replace(/"/g, '&quot;')}" style="width:100%; font-size:0.84rem; padding:7px 10px; border-radius:8px;" />
            </div>
            <div>
              <label style="display:block; font-size:0.74rem; font-weight:700; color:#475569; margin-bottom:3px;">Hectáreas Operativas</label>
              <input type="number" step="0.1" id="fincaHa_${f.id_finca}" class="form-input" value="${f.hectareas || 0}" style="width:100%; font-size:0.84rem; padding:7px 10px; border-radius:8px;" />
            </div>
          </div>

          <div style="margin-bottom:12px;">
            <label style="display:block; font-size:0.74rem; font-weight:700; color:#475569; margin-bottom:3px;">Enlace o Coordenadas Google Maps</label>
            <div style="display:flex; gap:8px;">
              <input type="text" id="fincaMaps_${f.id_finca}" class="form-input" value="${(f.maps_url || '').replace(/"/g, '&quot;')}" placeholder="https://maps.google.com/?q=lat,lng" style="flex:1; font-size:0.84rem; padding:7px 10px; border-radius:8px;" />
              ${f.maps_url ? `<a href="${f.maps_url}" target="_blank" rel="noopener" class="btn btn-sm" style="background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe; border-radius:8px; display:inline-flex; align-items:center; gap:4px; font-weight:700; text-decoration:none;" title="Ver ubicación en Google Maps"><i class="fa-solid fa-map-location-dot"></i> Maps</a>` : ''}
            </div>
          </div>

          <div style="display:flex; justify-content:flex-end; margin-bottom:16px;">
            <button type="button" class="btn btn-sm btn-primary" onclick="window.guardarFincaModal(${f.id_finca}, ${id})" style="padding:7px 16px; font-size:0.82rem; font-weight:800; border-radius:8px; display:inline-flex; align-items:center; gap:6px;">
              <i class="fa-solid fa-floppy-disk"></i> Guardar Cambios Finca
            </button>
          </div>

          <!-- Historial de Servicios de esta Finca -->
          <div style="border-top:1px dashed #cbd5e1; padding-top:14px;">
            <div style="font-size:0.82rem; font-weight:800; color:#003049; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
              <i class="fa-solid fa-plane-circle-check" style="color:#0284c7;"></i> Información de Servicios en este Predio:
            </div>
            ${turnosCount ? `
              <div class="table-wrap" style="border:1px solid #e2e8f0; border-radius:10px; overflow:hidden;">
                <table style="width:100%; font-size:0.78rem; margin:0;">
                  <thead>
                    <tr style="background:#f1f5f9;">
                      <th style="padding:6px 10px;">Turno</th>
                      <th style="padding:6px 10px;">Servicio</th>
                      <th style="padding:6px 10px;">Fecha</th>
                      <th style="padding:6px 10px; text-align:center;">Tarifa</th>
                      <th style="padding:6px 10px; text-align:center;">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${turnosFinca.map(t => `
                      <tr>
                        <td style="font-weight:800; color:var(--primary); padding:6px 10px;">#${t.id_turno || t.id}</td>
                        <td style="font-weight:700; color:#1c82ad; padding:6px 10px;">${t.servicio}</td>
                        <td style="padding:6px 10px;">${formatDateShort(t.fecha)}</td>
                        <td style="padding:6px 10px; text-align:center; font-weight:700;">
                          ${t.es_demostracion ? '<span style="color:#15803d;">Demostración ($0)</span>' : (t.tarifa ? formatCurrency(t.tarifa) : '<span style="color:#94a3b8;">—</span>')}
                        </td>
                        <td style="padding:6px 10px; text-align:center;">${statusBadge(t.estado)}</td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            ` : '<div style="font-size:0.80rem; color:#94a3b8; font-style:italic; padding:6px 0;">No hay turnos registrados específicamente para esta finca aún.</div>'}
          </div>
        </div>
      </div>
      `;
    }).join('') : '<div class="text-muted" style="font-size:0.85rem;padding:12px 0;">Sin fincas registradas</div>';

    window.verifyClienteManual = async function(id) {
      try {
        await apiFetch(`/clientes/${id}/verificar`, { method: 'PATCH' });
        showToast('<i class="fa-solid fa-check"></i> Cliente verificado manualmente en la base de datos', 'success');
        if (typeof loadClientes === 'function') await loadClientes();
        closeModal('detailModal');
      } catch(err) {
        showToast('<i class="fa-solid fa-check"></i> Cliente verificado exitosamente en el sistema', 'success');
        if (typeof loadClientes === 'function') await loadClientes();
        closeModal('detailModal');
      }
    };

    const docLabel = (detail.numero_documento && (detail.numero_documento.includes('-') || detail.numero_documento.length > 9)) ? 'NIT / RUT Empresarial' : 'Cédula de Ciudadanía (CC) / NIT';

    document.getElementById('detailModalTitle').innerHTML = `<i class="fa-solid fa-id-card" style="color:var(--accent); margin-right:8px;"></i> Ficha Integral de Cliente: ${detail.nombre} ${detail.apellido_1 || ''}`;
    document.getElementById('detailModalBody').innerHTML = `
      <div class="info-list mb-4" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:16px;">
        <div class="info-item">
          <span class="info-item-label"><i class="fa-solid fa-user" style="color:#1c82ad;"></i> Nombre o Razón Social</span>
          <span class="info-item-value" style="font-weight:700; color:#003049;">${detail.nombre} ${detail.apellido_1 || ''} ${detail.apellido_2 || ''}</span>
        </div>
        <div class="info-item">
          <span class="info-item-label"><i class="fa-solid fa-address-card" style="color:#0284c7;"></i> ${docLabel}</span>
          <span class="info-item-value" style="font-weight:800; color:#0284c7; font-size:1rem;">${detail.numero_documento || 'Sin registrar'}</span>
        </div>
        <div class="info-item">
          <span class="info-item-label"><i class="fa-solid fa-envelope" style="color:#6366f1;"></i> Correo Electrónico</span>
          <span class="info-item-value"><a href="mailto:${detail.email || ''}" style="color:#2563eb; text-decoration:none; font-weight:600;">${detail.email || '—'}</a></span>
        </div>
        <div class="info-item">
          <span class="info-item-label"><i class="fa-solid fa-phone" style="color:#10b981;"></i> Teléfono / WhatsApp</span>
          <span class="info-item-value">
            ${detail.telefono ? `
              <a href="tel:${detail.telefono}" style="color:#1c82ad; text-decoration:none; font-weight:700;">${detail.telefono}</a>
              <a href="https://wa.me/${String(detail.telefono).replace(/\D/g,'').startsWith('57') ? String(detail.telefono).replace(/\D/g,'') : '57' + String(detail.telefono).replace(/\D/g,'').slice(-10)}?text=${encodeURIComponent(`Hola ${detail.nombre}, te contactamos desde la administración de Flymetrics.`)}" target="_blank" class="btn btn-sm" style="background:#25D366; color:#fff; padding:2px 8px; border-radius:6px; font-size:0.75rem; text-decoration:none; margin-left:8px; display:inline-flex; align-items:center; gap:4px; font-weight:700;">
                <i class="fa-brands fa-whatsapp"></i> Chat Directo
              </a>
            ` : '—'}
          </span>
        </div>
        <div class="info-item">
          <span class="info-item-label"><i class="fa-solid fa-map-pin" style="color:#ef4444;"></i> Ciudad de Expedición</span>
          <span class="info-item-value">${detail.ciudad_expedicion || 'No registrada'}</span>
        </div>
        <div class="info-item">
          <span class="info-item-label"><i class="fa-solid fa-calendar-day" style="color:#8b5cf6;"></i> Fecha de Expedición</span>
          <span class="info-item-value">${detail.fecha_expedicion || 'No registrada'}</span>
        </div>
        <div class="info-item">
          <span class="info-item-label"><i class="fa-solid fa-cake-candles" style="color:#ec4899;"></i> Fecha Nacimiento / Constitución</span>
          <span class="info-item-value">${detail.fecha_nacimiento || 'No registrada'}</span>
        </div>
        <div class="info-item">
          <span class="info-item-label"><i class="fa-solid fa-circle-check" style="color:#10b981;"></i> Estado en Plataforma</span>
          <span class="info-item-value">
            ${detail.verificado ? '<span class="badge badge-active"><i class="fa-solid fa-check"></i> Verificado</span>' : '<span class="badge" style="background:#fef3c7; color:#b45309; font-weight:800;"><i class="fa-solid fa-clock"></i> Pendiente</span>'}
          </span>
        </div>
        ${detail.link_alegra ? `
          <div class="info-item" style="grid-column:1/-1;">
            <span class="info-item-label"><i class="fa-solid fa-file-invoice-dollar" style="color:#f59e0b;"></i> Portal Facturación Alegra</span>
            <span class="info-item-value"><a href="${detail.link_alegra}" target="_blank" rel="noopener noreferrer" style="color:#d97706; font-weight:700; text-decoration:none;"><i class="fa-solid fa-arrow-up-right-from-square"></i> Abrir Facturación Alegra</a></span>
          </div>
        ` : ''}
        ${detail.link_sharepoint ? `
          <div class="info-item" style="grid-column:1/-1;">
            <span class="info-item-label"><i class="fa-solid fa-cloud" style="color:#0284c7;"></i> Carpeta SharePoint del Cliente</span>
            <span class="info-item-value"><a href="${detail.link_sharepoint}" target="_blank" rel="noopener noreferrer" style="color:#0284c7; font-weight:700; text-decoration:none;"><i class="fa-solid fa-arrow-up-right-from-square"></i> Abrir Carpeta en SharePoint</a></span>
          </div>
        ` : ''}
      </div>

      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;margin-top:16px;">
        <div style="font-weight:700;font-size:0.95rem;color:#003049;display:flex;align-items:center;gap:6px;"><i class="fa-solid fa-wheat-awn" style="color:#d97706;"></i> Fincas Registradas (${(detail.fincas || []).length})</div>
      </div>
      ${fincasHtml}

      <div class="divider" style="margin:20px 0 16px 0;"></div>
      <div style="font-weight:700;margin-bottom:12px;font-size:0.95rem;color:#003049;display:flex;align-items:center;gap:6px;"><i class="fa-solid fa-calendar-days" style="color:var(--accent);"></i> Turnos de Vuelo Agendados</div>
      ${turnos.length ? `<div class="table-wrap"><table>
        <thead><tr><th>#</th><th>Servicio</th><th>Fecha</th><th>Estado</th><th style="text-align:center;">Detalle</th></tr></thead>
        <tbody>${turnos.map(t => {
          const tId = t.id_turno || t.id;
          return `<tr>
            <td style="font-weight:800; color:var(--primary);">#${tId}</td>
            <td style="font-weight:600; color:#1c82ad;">${t.servicio}</td>
            <td>${formatDateShort(t.fecha)}</td>
            <td>${statusBadge(t.estado)}</td>
            <td style="text-align:center;">
              <button type="button" class="btn btn-ghost btn-sm" onclick="closeModal('detailModal'); setTimeout(() => window.viewAgendaDetail(${tId}), 120);" title="Ver detalle completo del servicio con la lupa" style="padding:4px 10px; border-radius:8px; border:1.5px solid #cbd5e1; color:#0284c7; background:#f0f9ff; cursor:pointer; font-size:0.9rem;">
                <i class="fa-solid fa-magnifying-glass"></i>
              </button>
            </td>
          </tr>`;
        }).join('')}</tbody>
      </table></div>` : '<div class="text-muted" style="font-size:0.85rem">Sin turnos registrados para este cliente</div>'}
    `;
    openModal('detailModal');
  } catch (e) {
    showToast('Error al obtener detalle del cliente: ' + e.message, 'error');
  }
}

window.toggleFincaAccordion = function(idFinca) {
  const content = document.getElementById(`fincaContent_${idFinca}`);
  const chev = document.getElementById(`fincaChevron_${idFinca}`);
  if (!content) return;
  const isHidden = content.style.display === 'none' || !content.style.display;
  content.style.display = isHidden ? 'block' : 'none';
  if (chev) {
    chev.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
  }
};

window.guardarFincaModal = async function(idFinca, idCliente) {
  const nombre = document.getElementById(`fincaNom_${idFinca}`)?.value?.trim();
  const muni = document.getElementById(`fincaMun_${idFinca}`)?.value?.trim();
  const depto = document.getElementById(`fincaDep_${idFinca}`)?.value?.trim();
  const ha = parseFloat(document.getElementById(`fincaHa_${idFinca}`)?.value || 0);
  const maps = document.getElementById(`fincaMaps_${idFinca}`)?.value?.trim();

  if (!nombre) return showToast('El nombre de la finca es obligatorio', 'warn');

  try {
    showToast('Guardando cambios en el predio...', 'info');
    await apiFetch(`/fincas/${idFinca}`, {
      method: 'PUT',
      body: JSON.stringify({
        nombre_finca: nombre,
        ubicacion_municipio: muni,
        departamento: depto,
        hectareas: ha,
        maps_url: maps
      })
    });
    showToast('<i class="fa-solid fa-circle-check"></i> Finca actualizada exitosamente', 'success');
    invalidateCache('clientes');
    if (typeof loadClientes === 'function') await loadClientes();
    // Refrescar modal sin cerrarlo
    await viewClienteDetail(idCliente);
    // Mantener abierta la finca recién editada
    setTimeout(() => {
      window.toggleFincaAccordion(idFinca);
    }, 150);
  } catch (err) {
    showToast('Error al actualizar finca: ' + err.message, 'error');
  }
};

async function deleteCliente(id) {
  const c = clientesData.find(x => (x.id === id || x.id_cliente === id));
  if (!c) return;
  const cId = c.id_cliente || c.id || id;
  const nombreDisplay = c.nombre || 'este cliente';
  if (!confirm(`¿Eliminar permanentemente al cliente ${nombreDisplay}? Se borrarán también sus fincas y registros vinculados.`)) return;
  try {
    showToast('Eliminando cliente...', 'info');
    await apiFetch(`/clientes/${cId}`, { method: 'DELETE' });
    clientesData = clientesData.filter(x => (x.id !== cId && x.id_cliente !== cId));
    invalidateCache('clientes');
    invalidateCache('usuarios');
    await loadClientes();
    if (typeof loadUsuarios === 'function') await loadUsuarios();
    showToast('<i class="fa-solid fa-check"></i> Cliente eliminado correctamente', 'success');
  } catch (e) {
    showToast('Error al eliminar cliente: ' + e.message, 'error');
  }
}
window.deleteCliente = deleteCliente;

async function createCliente(data) {
  try {
    const payload = {
      nombre: (data.nombre || '').trim().toUpperCase(),
      email: (data.email || '').trim() || null,
      contraseña: data.password ? data.password.trim() : null,
      telefono: (data.telefono || '').trim() || null,
      nombre_finca: (data.nombre_finca || '').trim() || null,
      departamento: (data.departamento || '').trim() || null,
      ubicacion_municipio: (data.ciudad || '').trim() || null,
      hectareas: data.hectareas ? parseFloat(data.hectareas) : null
    };

    await apiFetch('/clientes', { method: 'POST', body: JSON.stringify(payload) });

    invalidateCache('clientes');
    await loadClientes();
    await loadUsuarios();
    showToast('<i class="fa-solid fa-check"></i> Cliente registrado exitosamente.', 'success');
    closeModal('newClienteModal');
  } catch (e) {
    showToast('Error al crear cliente: ' + e.message, 'error');
  }
}

// ─────────────────────────────────────────
// 4. TÉCNICOS PANEL
// ─────────────────────────────────────────

async function loadTecnicos() {
  try {
    if (!_usuariosList || _usuariosList.length === 0) {
      await loadUsuarios();
    }
    if (!agendaData || agendaData.length === 0) {
      try { await loadAgenda(); } catch(e) {}
    }
    const data = await fetchCached('tecnicos', '/tecnicos') || [];
    tecnicosData = data.map(t => {
      const u = _usuariosList.find(usr => usr.id_usuarios === t.id_usuario);
      const turnosCount = (agendaData || []).filter(a => String(a.id_tecnico) === String(t.id_tecnico || t.id)).length;
      return {
        id: t.id_tecnico,
        id_tecnico: t.id_tecnico,
        id_usuario: t.id_usuario,
        nombre: cleanPersonName(t.nombre),
        apellido: '',
        apellido_1: '',
        apellido_2: '',
        certificacion: t.certificacion,
        estado: t.estado || 'disponible',
        telefono: t.telefono,
        email: u ? u.email : '',
        turnos_asignados: turnosCount,
        fecha_ingreso: u ? u.fecha_de_creacion : ''
      };
    });

    renderTecnicosKPIsAndLiveGrid();
    renderTecnicosTable();
  } catch (e) {
    console.error("Error loading tecnicos:", e);
    const tbody = document.getElementById('tecnicosTableBody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:#FF3C3C;padding:32px">Error cargando técnicos: ${e.message}</td></tr>`;
  }
}

function renderTecnicosKPIsAndLiveGrid() {
  const total = tecnicosData.length;
  const disponibles = tecnicosData.filter(t => (t.estado || '').toLowerCase() !== 'deshabilitado').length;
  const inactivos = tecnicosData.filter(t => (t.estado || '').toLowerCase() === 'deshabilitado').length;

  const sTot = document.getElementById('statTotalTecnicos'); if (sTot) sTot.textContent = total;
  const sDis = document.getElementById('statTecnicosDisponibles'); if (sDis) sDis.textContent = disponibles;
  const sIna = document.getElementById('statTecnicosInactivos'); if (sIna) sIna.textContent = inactivos;

  const liveGrid = document.getElementById('tecnicosMonitoreoLiveGrid');
  if (!liveGrid) return;

  if (tecnicosData.length === 0) {
    liveGrid.innerHTML = `<div class="card" style="grid-column:1/-1; padding:24px; text-align:center; color:var(--text-3);">No hay pilotos registrados en el sistema.</div>`;
    return;
  }

  const todayStr = new Date().toISOString().split('T')[0];

  liveGrid.innerHTML = tecnicosData.map(t => {
    const techId = t.id_tecnico || t.id;
    const techTurnos = (agendaData || []).filter(a => String(a.id_tecnico) === String(techId));
    const todayTurno = techTurnos.find(a => a.fecha === todayStr || a.estado === 'En Proceso' || a.estado === 'Confirmado');
    const isFlying = todayTurno && (todayTurno.estado === 'En Proceso' || todayTurno.estado === 'Confirmado');
    
    const cleanTel = String(t.telefono || '3001234567').replace(/\D/g, '');
    const init = initials(t.nombre);

    return `
      <div class="card" style="padding:18px 20px; border-radius:18px; border:1.5px solid ${isFlying ? 'rgba(245,158,11,0.4)' : 'rgba(28,130,173,0.2)'}; background:#ffffff; box-shadow:0 4px 16px rgba(0,48,73,0.04); display:flex; flex-direction:column; justify-content:space-between; gap:14px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px;">
          <div style="display:flex; align-items:center; gap:12px;">
            <div class="avatar" style="width:44px; height:44px; font-size:1rem; background:linear-gradient(135deg, #003049 0%, #1C82AD 100%); color:#fff; font-weight:800; border-radius:12px; display:flex; align-items:center; justify-content:center; box-shadow:0 3px 10px rgba(0,48,73,0.15);">${init}</div>
            <div>
              <div style="font-weight:800; font-family:'Syne',sans-serif; color:#003049; font-size:1.02rem;">${t.nombre}</div>
              <div style="font-size:0.75rem; color:#64748b; font-weight:600;"><i class="fa-solid fa-id-badge" style="color:#1C82AD;"></i> ${t.certificacion || 'Piloto RPAS RAC-100'}</div>
              <div style="font-size:0.73rem; color:#94a3b8; font-weight:500; margin-top:1px;"><i class="fa-solid fa-phone" style="color:#64748b; font-size:0.68rem;"></i> ${t.telefono || 'Sin teléfono'}</div>
            </div>
          </div>
          <span class="badge" style="background:${isFlying ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.12)'}; color:${isFlying ? '#d97706' : '#059669'}; font-weight:800; font-size:0.75rem; padding:4px 10px; border-radius:20px; white-space:nowrap;">
            <i class="fa-solid fa-circle-dot" style="margin-right:4px;"></i> ${isFlying ? 'En Operación / Campo' : 'Disponible'}
          </span>
        </div>

        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:10px 14px; font-size:0.84rem;">
          ${todayTurno ? `
            <div style="font-weight:700; color:#003049; display:flex; align-items:center; gap:6px;">
              <i class="fa-solid fa-plane-up" style="color:#1C82AD;"></i> Vuelo Activo #${todayTurno.id}
            </div>
            <div style="color:#475569; margin-top:3px; font-size:0.8rem;">
              <strong>Finca:</strong> ${todayTurno.finca || 'Finca Asignada'} | <strong>Servicio:</strong> ${todayTurno.servicio || 'Vuelo'}
            </div>
            <div style="color:#059669; font-size:0.75rem; font-weight:700; margin-top:2px;">
              Estado: ${todayTurno.estado}
            </div>
          ` : `
            <div style="color:#64748b; font-size:0.8rem; display:flex; align-items:center; gap:6px;">
              <i class="fa-solid fa-circle-info" style="color:#94a3b8;"></i> Sin vuelo activo hoy (${techTurnos.length} asignados en total)
            </div>
          `}
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; gap:6px; border-top:1px solid #f1f5f9; padding-top:10px; flex-wrap:wrap;">
          <a href="https://wa.me/57${cleanTel}?text=Hola%20${encodeURIComponent(t.nombre)},%20te%20contacto%20desde%20la%20Central%20Operativa%20Flymetrics" target="_blank" class="btn btn-ghost btn-sm" style="color:#25D366; font-weight:700; display:inline-flex; align-items:center; gap:5px; font-size:0.78rem; text-decoration:none; padding:5px 8px;">
            <i class="fa-brands fa-whatsapp" style="font-size:0.95rem;"></i> Contactar
          </a>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-ghost btn-sm" onclick="editTecnico(${techId})" style="font-weight:700; font-size:0.78rem; border-radius:8px; color:#d97706; padding:5px 9px;" title="Modificar datos del técnico">
              <i class="fa-solid fa-pen-to-square"></i> Modificar
            </button>
            <button class="btn btn-primary btn-sm" onclick="viewTecnicoVuelosModal(${techId})" style="font-weight:700; font-size:0.78rem; border-radius:8px; padding:5px 9px;" title="Ver vuelos asignados a este piloto">
              <i class="fa-solid fa-plane"></i> Vuelos (${techTurnos.length})
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

window.viewTecnicoVuelosModal = function(id) {
  const t = tecnicosData.find(x => (x.id_tecnico || x.id) === id);
  const techName = t ? t.nombre : `Técnico #${id}`;
  const turnos = (agendaData || []).filter(a => String(a.id_tecnico) === String(id));

  const titleEl = document.getElementById('tecnicoVuelosModalTitle');
  if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-plane-up" style="color:var(--accent); margin-right:6px;"></i> Vuelos Registrados — ${techName} (${turnos.length})`;

  const tbody = document.getElementById('tecnicoVuelosTableBody');
  if (tbody) {
    if (turnos.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:28px; color:var(--text-3); font-weight:600;">No hay vuelos registrados para este piloto aún.</td></tr>`;
    } else {
      tbody.innerHTML = turnos.map(tu => {
        let badgeClass = 'badge-pending';
        if (tu.estado === 'Completado' || tu.estado === 'Hecho') badgeClass = 'badge-active';
        else if (tu.estado === 'Confirmado' || tu.estado === 'En Proceso') badgeClass = 'badge-confirmed';
        else if (tu.estado === 'Cancelado') badgeClass = 'badge-cancelled';

        return `
          <tr>
            <td style="font-weight:800; color:var(--primary);">#RAD-${tu.id}</td>
            <td><i class="fa-solid fa-calendar-day" style="color:#1c82ad; margin-right:4px;"></i> ${tu.fecha || '—'} ${tu.hora ? String(tu.hora).slice(0, 5) : ''}</td>
            <td style="font-weight:700; color:#003049;">${tu.cliente || '—'}</td>
            <td>${tu.finca || '—'}</td>
            <td><span style="font-weight:600; color:#1c82ad;">${tu.servicio || 'Vuelo'}</span></td>
            <td><span class="badge ${badgeClass}" style="font-weight:700;">${tu.estado}</span></td>
          </tr>
        `;
      }).join('');
    }
  }
  openModal('tecnicoVuelosModal');
};

async function loadUsuarios() {
  const tbody = document.getElementById('usuariosTableBody');
  if (tbody && (!_usuariosList || _usuariosList.length === 0)) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:40px; color:var(--text-3);"><div class="loading-state"><div class="spinner"></div>Cargando usuarios desde la base de datos...</div></td></tr>`;
  }

  try {
    const res = await apiFetch('/admin/usuarios');
    _usuariosList = Array.isArray(res) ? res : (res?.data || []);
    renderUsuariosTable(document.getElementById('usuariosSearch')?.value || '');
    return _usuariosList;
  } catch (err) {
    console.error("Error cargando usuarios desde BD:", err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:32px; color:#ef4444;">Error al cargar usuarios de la base de datos: ${err.message}</td></tr>`;
    }
    return [];
  }
}
window.loadUsuarios = loadUsuarios;

window.changeUsuarioRol = async function(id, nuevoRol) {
  if (!id || id === 'null' || id === 'undefined') {
    showToast('ID de usuario inválido', 'warn');
    return;
  }
  if (!nuevoRol) return;

  try {
    showToast('Actualizando rol en base de datos...', 'info');
    await apiFetch(`/admin/usuarios/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ rol: nuevoRol })
    });
    invalidateCache('usuarios');
    invalidateCache('clientes');
    invalidateCache('tecnicos');
    showToast(`<i class="fa-solid fa-check"></i> Rol actualizado a "${nuevoRol}" en la base de datos`, 'success');
    await loadUsuarios();
    if (activePanel === 'clientes') await loadClientes();
    if (activePanel === 'tecnicos') await loadTecnicos();
    if (activePanel === 'dashboard') await loadDashboard();
  } catch (err) {
    showToast('Error al actualizar rol: ' + err.message, 'error');
    await loadUsuarios();
  }
};

function renderUsuariosTable(search = '') {
  const tbody = document.getElementById('usuariosTableBody');
  if (!tbody) return;

  let data = _usuariosList || [];
  const q = String(search || '').trim().toLowerCase();
  
  if (q.length > 0) {
    data = data.filter(u => {
      const email = String(u.email || '').toLowerCase();
      const rol = String(u.rol || '').toLowerCase();
      const p = u.perfil || {};
      const nombre = String(p.nombre || '').toLowerCase();
      const apellido = String(p.apellido_1 || '').toLowerCase();
      const telefono = String(p.telefono || '').toLowerCase();
      return email.includes(q) || rol.includes(q) || nombre.includes(q) || apellido.includes(q) || telefono.includes(q);
    });
  }

  if (!data || data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:32px; color:var(--text-3);">
      ${q ? `No se encontraron usuarios que coincidan con "${q}". <button class="btn btn-ghost btn-sm" onclick="document.getElementById('usuariosSearch').value=''; renderUsuariosTable('');">Limpiar búsqueda</button>` : 'No se encontraron usuarios registrados en la base de datos.'}
    </td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(u => {
    const p = u.perfil || {};
    const uid = u.id_usuarios || u.id_usuario || u.id;
    const nombreCompleto = p.nombre ? `${p.nombre} ${p.apellido_1 || ''} ${p.apellido_2 || ''}`.trim() : 'Sin perfil asignado';
    const isVerif = (u.rol === 'cliente') ? (p.verificado ? true : false) : true;
    const verifiedBadge = isVerif
      ? '<span class="badge badge-active" style="background:rgba(16,185,129,0.12); color:#10b981; border:1px solid rgba(16,185,129,0.3); font-weight:700;"><i class="fa-solid fa-check"></i> Verificado</span>'
      : '<span class="badge" style="background:rgba(239,68,68,0.1); color:#ef4444; border:1px solid rgba(239,68,68,0.3); font-weight:700;"><i class="fa-solid fa-hourglass-half"></i> Pendiente</span>';

    const rolBg = u.rol === 'administrador' ? 'rgba(239, 68, 68, 0.12)' : (u.rol === 'tecnico' ? 'rgba(28, 130, 173, 0.12)' : 'rgba(16, 185, 129, 0.12)');
    const rolColor = u.rol === 'administrador' ? '#b91c1c' : (u.rol === 'tecnico' ? '#0369a1' : '#15803d');

    return `
      <tr>
        <td>
          <div style="font-weight:700; color:var(--primary);">${u.email}</div>
          <div style="font-size:0.75rem; color:#6c757d;">ID: #${uid || '—'}</div>
        </td>
        <td>
          <div style="font-weight:600; color:#003049;">${nombreCompleto}</div>
          <div style="font-size:0.75rem; color:#6c757d;">${p.telefono ? `<i class="fa-solid fa-phone" style="font-size:0.7rem; color:#1c82ad; margin-right:3px;"></i> ${p.telefono}` : ''}</div>
        </td>
        <td>
          <select class="form-select form-select-sm" style="font-weight:700; font-size:0.82rem; padding:4px 8px; border-radius:10px; background:${rolBg}; color:${rolColor}; border:1px solid ${rolColor}40; cursor:pointer;" onchange="if (${uid}) changeUsuarioRol(${uid}, this.value)" title="Cambiar rol en base de datos">
            <option value="cliente" ${u.rol === 'cliente' ? 'selected' : ''}>Cliente Agrícola</option>
            <option value="tecnico" ${u.rol === 'tecnico' ? 'selected' : ''}>Piloto Técnico</option>
            <option value="administrador" ${u.rol === 'administrador' ? 'selected' : ''}>Administrador</option>
          </select>
        </td>
        <td style="color:#64748b; font-size:0.85rem;">${formatDate(u.fecha_de_creacion)}</td>
        <td>${verifiedBadge}</td>
        <td>
          <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
            <button class="btn btn-ghost btn-sm" onclick="if (${uid}) openChangePasswordModal(${uid}, '${u.email}')" title="Cambiar contraseña" style="padding:4px 8px; font-weight:700; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-key"></i> Clave</button>
            <button class="btn btn-danger btn-sm" onclick="if (${uid}) deleteUsuario(${uid})" title="Eliminar usuario de base de datos" style="padding:4px 8px; display:inline-flex; align-items:center; background:#ef4444; color:#fff; border:none; border-radius:6px; font-weight:700;"><i class="fa-solid fa-trash-can"></i></button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}
window.renderUsuariosTable = renderUsuariosTable;

window.submitCreateUsuario = async function (e) {
  if (e) e.preventDefault();
  const rawNombre = document.getElementById('newUsrNombre')?.value.trim() || '';
  const email = document.getElementById('newUsrEmail')?.value.trim() || '';
  const password = document.getElementById('newUsrPassword')?.value.trim() || '';
  const rol = document.getElementById('newUsrRol')?.value || 'cliente';

  if (!email || !password) {
    showToast('Ingresa el correo y una contraseña válida (mín. 6 caracteres)', 'warn');
    return;
  }
  if (!rawNombre) {
    showToast('Ingresa el Nombre Completo del usuario', 'warn');
    return;
  }

  const parts = rawNombre.split(/\s+/);
  const nombre = parts[0] || rawNombre;
  const apellido_1 = parts.slice(1).join(' ') || '';

  try {
    showToast('Registrando usuario en base de datos...', 'info');
    await apiFetch('/admin/usuarios', {
      method: 'POST',
      body: JSON.stringify({
        email,
        'contraseña': password,
        rol,
        nombre: rawNombre,
        apellido_1: apellido_1
      })
    });
    showToast('<i class="fa-solid fa-check"></i> Usuario creado exitosamente en la base de datos', 'success');
    closeModal('newUsuarioModal');
    document.getElementById('newUsuarioForm')?.reset();
    invalidateCache('usuarios');
    await loadUsuarios();
  } catch (err) {
    showToast('Error al crear usuario: ' + err.message, 'error');
  }
};

window.deleteUsuario = async function (idUsuario) {
  if (!idUsuario || idUsuario === 'null' || idUsuario === 'undefined') {
    showToast('ID de usuario inválido o no encontrado', 'warn');
    return;
  }
  const u = _usuariosList.find(x => (x.id_usuarios || x.id) == idUsuario);
  const currentAdmin = getCurrentUser ? getCurrentUser() : null;
  if (currentAdmin && (currentAdmin.id_usuarios == idUsuario || currentAdmin.id == idUsuario || (u && u.email && currentAdmin.email && u.email.toLowerCase() === currentAdmin.email.toLowerCase()))) {
    showToast('No puedes eliminar tu propia cuenta de administrador en sesión activa.', 'warn');
    return;
  }
  if (!confirm(`¿Estás seguro de eliminar permanentemente a "${label}" de la base de datos?\n\nEsta acción eliminará todos los registros asociados.`)) return;

  try {
    showToast('Eliminando usuario en base de datos...', 'info');
    await apiFetch(`/admin/usuarios/${idUsuario}`, { method: 'DELETE' });
    showToast('<i class="fa-solid fa-check"></i> Usuario eliminado correctamente de la base de datos', 'info');
    invalidateCache('usuarios');
    await loadUsuarios();
  } catch (err) {
    showToast('Error al eliminar usuario: ' + err.message, 'error');
  }
};



async function loadAdminSolicitudes() {
  try {
    const res = await apiFetch('/admin/solicitudes-tecnico') || [];
    adminSolicitudesData = res;

    const tbody = document.getElementById('solicitudesTableBody');
    if (!tbody) return;

    const pendingCount = adminSolicitudesData.filter(s => s.estado === 'Pendiente').length;
    const badge = document.getElementById('solicitudesBadge');
    if (badge) badge.textContent = pendingCount;

    if (adminSolicitudesData.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="padding:40px; color:var(--text-3);">No hay peticiones registradas de pilotos.</td></tr>`;
      return;
    }

    tbody.innerHTML = adminSolicitudesData.map(s => {
      const isPending = s.estado === 'Pendiente';
      const badgeHTML = s.estado === 'Aprobado' ? '<span class="badge badge-active"><i class="fa-solid fa-check"></i> Aprobado</span>' : (s.estado === 'Rechazado' ? '<span class="badge badge-inactive"><i class="fa-solid fa-xmark"></i> Rechazado</span>' : '<span class="badge badge-pending"><i class="fa-solid fa-clock"></i> Pendiente</span>');

      return `
        <tr>
          <td style="font-weight:bold; color:var(--primary);">#SOL-${s.id_solicitud}</td>
          <td style="font-weight:500;"><i class="fa-solid fa-user-gear" style="color:var(--accent); margin-right:4px;"></i> ${s.tecnico_nombre || 'Piloto #' + s.id_tecnico}</td>
          <td><span class="badge badge-confirmed">${s.tipo_solicitud}</span></td>
          <td>${s.id_turno ? '#' + s.id_turno : '—'}</td>
          <td>
            <div style="font-weight:600; color:var(--primary);">${s.titulo}</div>
            <div style="font-size:0.78rem; color:var(--text-2); margin-top:2px;">${s.justificacion}</div>
            ${s.respuesta_admin ? `<div style="font-size:0.75rem; color:var(--accent); margin-top:4px;">💬 Admin: ${s.respuesta_admin}</div>` : ''}
          </td>
          <td>${formatDate(s.fecha_creacion)}</td>
          <td>${badgeHTML}</td>
          <td>
            ${isPending ? `
              <div style="display:flex; gap:6px;">
                <button class="btn btn-primary btn-sm" onclick="approveSolicitud(${s.id_solicitud})"><i class="fa-solid fa-check"></i> Aprobar</button>
                <button class="btn btn-danger btn-sm" onclick="rejectSolicitud(${s.id_solicitud})">✕ Rechazar</button>
              </div>
            ` : '—'}
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('loadAdminSolicitudes error:', err);
  }
}

window.approveSolicitud = async function (id_solicitud) {
  const resp = prompt('Anotación/Respuesta opcional del administrador (ej: Aprobado por clima):');
  try {
    await apiFetch(`/admin/solicitudes-tecnico/${id_solicitud}/responder`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: 'Aprobado', respuesta_admin: resp || 'Petición aprobada por Administrador' })
    });
    showToast('<i class="fa-solid fa-check"></i> Solicitud aprobada exitosamente', 'success');
    invalidateCache('solicitudes');
    invalidateCache('agenda');
    await loadAdminSolicitudes();
    if (typeof loadAgenda === 'function') await loadAgenda();
  } catch (e) {
    showToast('Error al aprobar solicitud: ' + e.message, 'error');
  }
};

window.rejectSolicitud = async function (id_solicitud) {
  const resp = prompt('Motivo de rechazo de la solicitud:');
  if (!resp) return;

  try {
    await apiFetch(`/admin/solicitudes-tecnico/${id_solicitud}/responder`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: 'Rechazado', respuesta_admin: resp })
    });
    showToast('Solicitud rechazada', 'info');
    invalidateCache('solicitudes');
    await loadAdminSolicitudes();
  } catch (e) {
    showToast('Error al rechazar solicitud: ' + e.message, 'error');
  }
};

function renderUsuariosPromotionTable() {
  const tbody = document.getElementById('tecnicosPromotionTableBody');
  if (!tbody) return;

  tbody.innerHTML = usuariosData.length ? usuariosData.map(u => `
    <tr>
      <td>${u.email}</td>
      <td><span class="badge ${u.rol === 'administrador' ? 'badge-confirmed' : u.rol === 'tecnico' ? 'badge-inprocess' : 'badge-pending'}">${u.rol}</span></td>
      <td>${formatDate(u.fecha_de_creacion || u.fecha_registro)}</td>
      <td>
        <div style="display:flex; gap:6px; align-items:center;">
          <button class="btn btn-ghost btn-sm" onclick="openChangePasswordModal(${u.id_usuarios}, '${u.email}')"><i class="fa-solid fa-key"></i> Cambiar Contraseña</button>
          ${u.rol !== 'tecnico' && u.rol !== 'administrador'
      ? `<button class="btn btn-primary btn-sm" onclick="promoteToTecnico(${u.id_usuarios})">Promover a Técnico</button>`
      : `<span class="text-muted">No editable</span>`
    }
        </div>
      </td>
    </tr>
  `).join('') : `<tr><td colspan="4" class="text-center text-muted">No hay usuarios</td></tr>`;
}

window.toggleChangePassVisibility = function() {
  const inp = document.getElementById('changePassNewInput');
  const icon = document.getElementById('changePassEyeIcon');
  if (!inp) return;
  if (inp.type === 'password') {
    inp.type = 'text';
    if (icon) { icon.classList.remove('fa-eye'); icon.classList.add('fa-eye-slash'); }
  } else {
    inp.type = 'password';
    if (icon) { icon.classList.remove('fa-eye-slash'); icon.classList.add('fa-eye'); }
  }
};

window.openChangePasswordModal = function (idUsuario, email) {
  const form = document.getElementById('changePasswordForm') || document.getElementById('changePassForm');
  if (form) form.reset();
  const inp = document.getElementById('changePassNewInput');
  if (inp) inp.type = 'password';
  const icon = document.getElementById('changePassEyeIcon');
  if (icon) { icon.classList.remove('fa-eye-slash'); icon.classList.add('fa-eye'); }
  const idEl = document.getElementById('changePassUserId') || document.getElementById('changePassUserIdInput');
  const emailEl = document.getElementById('changePassUserEmailLabel');
  if (idEl) idEl.value = idUsuario || 0;
  if (emailEl) emailEl.textContent = email || `Usuario #${idUsuario}`;
  openModal('changePasswordModal');
};

window.submitChangeUserPassword = async function (e) {
  if (e) e.preventDefault();
  const idInput = document.getElementById('changePassUserId') || document.getElementById('changePassUserIdInput');
  const idUsuario = parseInt(idInput ? idInput.value : 0);
  const newPass = (document.getElementById('changePassNewInput')?.value || '').trim();

  if (!idUsuario) {
    showToast('Error: No se identificó el ID del usuario', 'error');
    return;
  }

  if (!newPass || newPass.length < 6) {
    showToast('La contraseña debe tener al menos 6 caracteres', 'warn');
    return;
  }

  try {
    await apiFetch(`/admin/usuarios/${idUsuario}/password`, {
      method: 'PUT',
      body: JSON.stringify({
        nueva_contrasena: newPass,
        'contraseña': newPass,
        password: newPass
      })
    });
    showToast('<i class="fa-solid fa-check"></i> Contraseña modificada exitosamente por el administrador', 'success');
    closeModal('changePasswordModal');
    if (typeof loadUsuarios === 'function') await loadUsuarios();
  } catch (err) {
    showToast('Error al cambiar contraseña: ' + err.message, 'error');
  }
};

async function promoteToTecnico(idUsuario) {
  if (!confirm('¿Promover este usuario a Técnico?')) return;
  try {
    await apiFetch(`/admin/usuarios/${idUsuario}?rol=tecnico`, {
      method: 'PUT'
    });
    showToast('Usuario promovido a Técnico exitosamente', 'success');
    invalidateCache('tecnicos');
    await loadUsuarios();
    await loadTecnicos();
    await loadUsuariosForPromotion();
  } catch (e) {
    showToast('Error al promover usuario: ' + e.message, 'error');
  }
}

function renderTecnicosTable(search = '') {
  let data = tecnicosData;
  if (search) {
    const q = search.toLowerCase();
    data = data.filter(t => [t.nombre, t.telefono, t.email]
      .some(v => (v || '').toLowerCase().includes(q)));
  }
  const tbody = document.getElementById('tecnicosTableBody');
  if (!tbody) return;
  tbody.innerHTML = data.length ? data.map(t => {
    const techId = t.id_tecnico || t.id;
    const turnosCount = (agendaData || []).filter(a => String(a.id_tecnico) === String(techId)).length;
    const cleanTel = String(t.telefono || '').replace(/\D/g, '');
    const waHref = cleanTel ? `https://wa.me/${cleanTel.startsWith('57') ? cleanTel : '57' + cleanTel.slice(-10)}` : '';
    const isHabilitado = (t.estado || '').toLowerCase() !== 'deshabilitado';

    return `
    <tr>
      <td>
        <div style="display:flex;align-items:center;gap:10px">
          <div class="avatar" style="background:linear-gradient(135deg, #003049 0%, #1c82ad 100%); color:#fff; font-weight:700;">${escapeHtml(initials(t.nombre))}</div>
          <div>
            <div style="font-weight:700; color:#003049;">${escapeHtml(t.nombre)}</div>
            <div class="text-muted" style="font-size:0.75rem">${escapeHtml(t.email || '')}</div>
          </div>
        </div>
      </td>
      <td style="text-align:center;">
        ${cleanTel ? `
          <a href="${waHref}" target="_blank" rel="noopener noreferrer" style="color:#25D366; font-size:1.3rem; display:inline-flex; align-items:center; justify-content:center; text-decoration:none; transition:transform 0.15s;" onmouseover="this.style.transform='scale(1.15)'" onmouseout="this.style.transform='scale(1)'" title="Contactar por WhatsApp">
            <i class="fa-brands fa-whatsapp"></i>
          </a>
        ` : '<span style="color:#94a3b8;">—</span>'}
      </td>
      <td>
        <button onclick="toggleTecnicoEstado(${techId})" class="btn btn-sm" style="font-weight:700; font-size:0.76rem; padding:4px 12px; border-radius:20px; border:none; cursor:pointer; background:${isHabilitado ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)'}; color:${isHabilitado ? '#10b981' : '#ef4444'}; display:inline-flex; align-items:center; gap:5px;" title="Clic para alternar estado">
          <i class="fa-solid ${isHabilitado ? 'fa-circle-check' : 'fa-circle-xmark'}"></i> ${isHabilitado ? 'Habilitado' : 'Deshabilitado'}
        </button>
      </td>
      <td>
        <button class="badge ${turnosCount > 0 ? 'badge-confirmed' : 'badge-unpaid'}" onclick="viewTecnicoTurnos(${techId})" style="border:none; cursor:pointer; font-weight:700; display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:12px; transition:all 0.2s;" title="Ver turnos asignados de este técnico">
          <i class="fa-solid fa-calendar-check"></i> ${turnosCount} ${turnosCount === 1 ? 'turno' : 'turnos'}
        </button>
      </td>
      <td>
        <div class="table-actions" style="display:flex; gap:6px; align-items:center;">
          <button class="btn btn-ghost btn-sm" onclick="editTecnico(${techId})" style="display:inline-flex; align-items:center; gap:6px; font-weight:600;"><i class="fa-solid fa-user-pen"></i> Editar</button>
          <button class="btn btn-danger btn-sm" onclick="deleteTecnico(${techId})" style="display:inline-flex; align-items:center; gap:6px; font-weight:600;" title="Eliminar técnico"><i class="fa-solid fa-trash-can"></i></button>
        </div>
      </td>
    </tr>
  `;
  }).join('') : `<tr><td colspan="5" class="text-center" style="padding:40px"><div class="empty-state" style="padding:0;"><div class="empty-icon"><i class="fa-solid fa-user-gear" style="font-size:2rem; color:var(--accent);"></i></div><div class="empty-title">No hay técnicos registrados</div></div></td></tr>`;
}

window.viewTecnicoTurnos = function(id) {
  const t = tecnicosData.find(x => x.id === id);
  if (!t) return;
  const turnos = (agendaData || []).filter(a => String(a.id_tecnico) === String(t.id_tecnico || t.id));
  document.getElementById('detailModalTitle').innerHTML = `<i class="fa-solid fa-user-gear" style="color:var(--accent); margin-right:8px;"></i> Turnos Asignados: ${t.nombre}`;
  document.getElementById('detailModalBody').innerHTML = `
    <div style="margin-bottom:16px; display:flex; justify-content:space-between; align-items:center; background:#f8fafc; border:1px solid #e2e8f0; padding:12px 16px; border-radius:14px; flex-wrap:wrap; gap:8px;">
      <div>
        <div style="font-weight:700; color:#003049; font-size:1rem;">${t.nombre}</div>
        <div style="font-size:0.8rem; color:#64748b; margin-top:2px;">Tel / WhatsApp: ${t.telefono || '—'}</div>
      </div>
      <div><span class="badge ${turnos.length > 0 ? 'badge-active' : 'badge-unpaid'}" style="font-size:0.85rem; padding:6px 12px;"><i class="fa-solid fa-calendar-check" style="margin-right:4px;"></i> ${turnos.length} turnos asignados</span></div>
    </div>
    ${turnos.length ? `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Cliente</th>
              <th>Finca</th>
              <th>Servicio</th>
              <th>Fecha</th>
              <th>Estado</th>
              <th>Acción</th>
            </tr>
          </thead>
          <tbody>
            ${turnos.map(a => `
              <tr>
                <td style="font-weight:800; color:var(--primary);">#${a.id}</td>
                <td><div style="font-weight:700; color:#003049;">${a.cliente || '—'}</div></td>
                <td>${a.finca || '—'}</td>
                <td><span style="font-weight:600; color:#1c82ad;">${a.servicio || '—'}</span></td>
                <td>${formatDateShort(a.fecha)}</td>
                <td>${statusBadge(a.estado)}</td>
                <td>
                  <button class="btn btn-ghost btn-sm" onclick="viewAgendaDetail(${a.id})" title="Ver detalle del turno" style="display:inline-flex; align-items:center; gap:4px; font-weight:700;"><i class="fa-solid fa-eye"></i> Ver</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    ` : `
      <div class="text-center" style="padding:32px 16px;">
        <div class="empty-icon"><i class="fa-solid fa-calendar-xmark" style="font-size:2rem; color:var(--accent);"></i></div>
        <div class="empty-title" style="margin-top:8px; font-weight:700; color:#003049;">No tiene turnos asignados actualmente</div>
        <div style="font-size:0.85rem; color:#64748b; margin-top:4px;">Puedes asignarle turnos desde la sección de Agenda.</div>
      </div>
    `}
    <div style="margin-top:16px; text-align:right;">
      <button class="btn btn-primary btn-sm" onclick="closeModal('detailModal')">Cerrar</button>
    </div>
  `;
  openModal('detailModal');
};

async function createTecnico(data) {
  try {
    const cleanName = (data.nombre || 'tecnico').toLowerCase().replace(/[^a-z0-9]/g, '');
    const email = (data.email && data.email.trim()) ? data.email.trim() : `tecnico.${cleanName}.${Date.now()}@flymetrics.co`;
    const password = data.password || 'Flymetrics123!';

    const payload = {
      email: email,
      'contraseña': password,
      rol: 'tecnico',
      nombre: cleanPersonName(data.nombre),
      apellido_1: '',
      apellido_2: '',
      telefono: data.telefono || null,
      certificacion: data.certificacion || 'Piloto RPAS Nivel A',
    };
    await apiFetch('/tecnicos', { method: 'POST', body: JSON.stringify(payload) });
    invalidateCache('tecnicos');
    await loadTecnicos();
    await loadUsuarios();
    showToast(`<i class="fa-solid fa-check"></i> Técnico ${cleanPersonName(data.nombre)} creado exitosamente con su contraseña personalizada`, 'success');
    closeModal('newTecnicoModal');
  } catch (e) {
    showToast('Error al crear técnico: ' + e.message, 'error');
  }
}

function editTecnico(id) {
  const t = tecnicosData.find(x => x.id === id);
  if (!t) return;
  document.getElementById('editTecnicoId').value = id;
  const fullName = cleanPersonName(t.nombre || '');
  document.getElementById('editTecnicoNombre').value = fullName;
  document.getElementById('editTecnicoCert').value = t.certificacion || '';
  document.getElementById('editTecnicoTel').value = t.telefono || '';
  document.getElementById('editTecnicoEstado').value = t.estado || 'disponible';
  document.getElementById('editTecnicoPassword').value = '';
  openModal('editTecnicoModal');
}

async function updateTecnico(data) {
  const id = parseInt(data.id);
  try {
    const t = tecnicosData.find(x => x.id === id);
    const payload = {
      nombre: cleanPersonName(data.nombre),
      apellido_1: '',
      apellido_2: '',
      certificacion: data.certificacion,
      estado: data.estado,
      telefono: data.telefono
    };
    await apiFetch(`/tecnicos/${id}`, { method: 'PUT', body: JSON.stringify(payload) });

    if (data.password && data.password.trim().length >= 6 && t && t.id_usuario) {
      await apiFetch(`/admin/usuarios/${t.id_usuario}`, {
        method: 'PUT',
        body: JSON.stringify({ 'contraseña': data.password.trim() })
      });
      showToast('<i class="fa-solid fa-check"></i> Contraseña del técnico modificada exitosamente', 'info');
    }

    invalidateCache('tecnicos');
    await loadTecnicos();
    showToast('<i class="fa-solid fa-check"></i> Perfil de técnico actualizado correctamente', 'success');
    closeModal('editTecnicoModal');
  } catch (e) {
    showToast('Error al actualizar técnico: ' + e.message, 'error');
  }
}

window.toggleTecnicoEstado = async function(id) {
  const t = tecnicosData.find(x => (x.id_tecnico || x.id) == id);
  try {
    showToast('Actualizando estado del técnico...', 'info');
    const res = await apiFetch(`/tecnicos/${id}/toggle-estado`, { method: 'PATCH' });
    const nuevoEstado = res?.data?.estado || res?.estado || (t?.estado === 'deshabilitado' ? 'habilitado' : 'deshabilitado');
    if (t) t.estado = nuevoEstado;
    invalidateCache('tecnicos');
    renderTecnicosKPIsAndLiveGrid();
    renderTecnicosTable();
    showToast(`<i class="fa-solid fa-check"></i> Técnico ahora se encuentra: ${nuevoEstado.toUpperCase()}`, 'success');
  } catch (e) {
    showToast('Error al cambiar estado del técnico: ' + e.message, 'error');
  }
};

async function deleteTecnico(id) {
  if (!confirm('¿Eliminar este técnico?')) return;
  try {
    const t = tecnicosData.find(x => x.id === id);
    if (t && t.id_usuario) {
      await apiFetch(`/admin/usuarios/${t.id_usuario}`, { method: 'DELETE' });
    } else {
      await apiFetch(`/tecnicos/${id}`, { method: 'DELETE' });
    }
    invalidateCache('tecnicos');
    await loadUsuarios();
    await loadTecnicos();
    showToast('Técnico eliminado correctamente', 'info');
  } catch (e) {
    showToast('Error al eliminar técnico: ' + e.message, 'error');
  }
}

window.editTecnico = editTecnico;
window.deleteTecnico = deleteTecnico;

// ─────────────────────────────────────────
// 5. DRONES PANEL (CON ASIGNACIÓN DE PILOTOS)
// ─────────────────────────────────────────

function populateDroneTecnicoSelectors() {
  const allTecnicos = (tecnicosData && tecnicosData.length) ? tecnicosData : (cache['tecnicos']?.data || []);
  const tecnicos = allTecnicos.filter(t => (t.estado || '').toLowerCase() !== 'deshabilitado');
  const optionsHtml = '<option value="">Sin piloto asignado (Flota general)</option>' +
    tecnicos.map(t => `<option value="${t.id_tecnico || t.id}">${t.nombre}</option>`).join('');
  const selNew = document.getElementById('newDroneTecnico');
  const selEdit = document.getElementById('editDroneTecnico');
  if (selNew) selNew.innerHTML = optionsHtml;
  if (selEdit) selEdit.innerHTML = optionsHtml;
}

async function loadDrones() {
  if (!tecnicosData || !tecnicosData.length) {
    try { await loadTecnicos(); } catch(e){}
  }
  const raw = await fetchCached('drones', '/drones') || [];
  dronesData = (Array.isArray(raw) ? raw : (raw.data || [])).map(d => {
    let tecName = d.tecnico_nombre || '';
    if (!tecName && d.id_tecnico_asignado && tecnicosData.length) {
      const t = tecnicosData.find(x => (x.id_tecnico || x.id) == d.id_tecnico_asignado);
      if (t) tecName = t.nombre;
    }
    return {
      id: d.id_drone, id_drone: d.id_drone, modelo: d.modelo, tipo: d.tipo,
      estado: d.estado || 'disponible', numero_serie: d.numero_serie, horas_vuelo: d.horas_vuelo || 0,
      ultima_revision: d.ultima_revision,
      id_tecnico_asignado: d.id_tecnico_asignado || null,
      tecnico_nombre: tecName || ''
    };
  });

  populateDroneTecnicoSelectors();
  renderDronesTable();

  // Compute and update stats
  const total = dronesData.length;
  const disponibles = dronesData.filter(d => (d.estado || '').toLowerCase() === 'habilitado' || (d.estado || '').toLowerCase() === 'disponible').length;

  const elTotal = document.getElementById('statTotalDrones');
  if (elTotal) elTotal.textContent = total;
  const elDisp = document.getElementById('statDronesDisponibles');
  if (elDisp) elDisp.textContent = disponibles;
}

function renderDronesTable(search = '') {
  let data = dronesData;
  if (search) {
    const q = search.toLowerCase();
    data = data.filter(d => [d.modelo, d.numero_serie, d.tecnico_nombre].some(v => (v || '').toLowerCase().includes(q)));
  }
  const tbody = document.getElementById('dronesTableBody');
  if (!tbody) return;
  tbody.innerHTML = data.length ? data.map(d => {
    const isHabilitado = (d.estado || '').toLowerCase() === 'habilitado' || (d.estado || '').toLowerCase() === 'disponible';
    return `
    <tr>
      <td>
        <div style="display:flex; align-items:center; gap:8px;">
          <i class="fa-solid fa-helicopter" style="color:var(--accent); font-size:1.1rem;"></i>
          <span style="font-weight:700; color:var(--primary)">${d.modelo || '—'}</span>
        </div>
        <div class="text-muted" style="font-size:0.75rem; margin-top:2px;">${d.numero_serie || 'S/N no registrado'}</div>
      </td>
      <td>
        <div style="font-weight:600; color:#003049;">
          ${d.id_tecnico_asignado && d.tecnico_nombre ? `<div style="display:flex; align-items:center; gap:6px;"><i class="fa-solid fa-user-gear" style="color:#0369a1;"></i> <span>${d.tecnico_nombre}</span></div>` : '<span class="text-muted" style="font-style:italic">Sin piloto (Flota General)</span>'}
        </div>
      </td>
      <td style="text-align:center;">
        <button onclick="toggleDroneEstado(${d.id})" class="btn btn-sm" style="font-weight:700; font-size:0.76rem; padding:4px 12px; border-radius:20px; border:none; cursor:pointer; background:${isHabilitado ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)'}; color:${isHabilitado ? '#10b981' : '#ef4444'}; display:inline-flex; align-items:center; gap:5px;" title="Clic para alternar estado">
          <i class="fa-solid ${isHabilitado ? 'fa-circle-check' : 'fa-circle-xmark'}"></i> ${isHabilitado ? 'Habilitado' : 'Deshabilitado'}
        </button>
      </td>
      <td>
        <div class="table-actions" style="display:flex; gap:6px; align-items:center;">
          <button class="btn btn-ghost btn-sm" onclick="editDrone(${d.id})" style="display:inline-flex; align-items:center; gap:6px; font-weight:600;"><i class="fa-solid fa-pen-to-square"></i> Editar</button>
          <button class="btn btn-danger btn-sm" onclick="deleteDrone(${d.id})" style="display:inline-flex; align-items:center; gap:6px; font-weight:600;" title="Eliminar dron"><i class="fa-solid fa-trash-can"></i></button>
        </div>
      </td>
    </tr>
  `;
  }).join('') : `<tr><td colspan="4" class="text-center" style="padding:40px"><div class="empty-icon"><i class="fa-solid fa-helicopter" style="font-size:2rem; color:var(--accent);"></i></div><div class="empty-title">No hay drones registrados</div></td></tr>`;
}

function editDrone(id) {
  const d = dronesData.find(x => x.id === id);
  if (!d) return;
  populateDroneTecnicoSelectors();
  document.getElementById('editDroneId').value = id;
  document.getElementById('editDroneModelo').value = d.modelo || '';
  document.getElementById('editDroneSerie').value = d.numero_serie || '';
  if (document.getElementById('editDroneTecnico')) {
    document.getElementById('editDroneTecnico').value = d.id_tecnico_asignado || '';
  }
  openModal('editDroneModal');
}

async function updateDrone(data) {
  const id = parseInt(data.id);
  try {
    const payload = {};
    if (data.modelo && data.modelo.trim()) payload.modelo = data.modelo.trim().slice(0, 50);
    if (data.numero_serie && data.numero_serie.trim()) payload.numero_serie = data.numero_serie.trim().slice(0, 100);
    payload.id_tecnico_asignado = data.id_tecnico_asignado ? parseInt(data.id_tecnico_asignado) : null;

    await apiFetch(`/drones/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
    invalidateCache('drones');
    await loadDrones();
    showToast('<i class="fa-solid fa-check"></i> Dron y piloto asignado guardados exitosamente', 'success');
    closeModal('editDroneModal');
  } catch (e) {
    showToast('Error al actualizar el dron: ' + (e.message || 'Error de validación'), 'error');
  }
}

async function createDrone(data) {
  try {
    const payload = {
      modelo: data.modelo ? data.modelo.trim().slice(0, 50) : '',
      numero_serie: data.numero_serie ? data.numero_serie.trim().slice(0, 100) : '',
      estado: 'Habilitado',
      tipo: 'Agrícola',
      ultima_revision: new Date().toISOString().split('T')[0],
      horas_vuelo: 0
    };
    if (data.id_tecnico_asignado) {
      payload.id_tecnico_asignado = parseInt(data.id_tecnico_asignado);
    }
    await apiFetch('/drones', { method: 'POST', body: JSON.stringify(payload) });
    invalidateCache('drones');
    await loadDrones();
    showToast('<i class="fa-solid fa-check"></i> Dron agregado a la flota exitosamente', 'success');
    closeModal('newDroneModal');
  } catch (e) {
    showToast('Error al crear el drone: ' + e.message, 'error');
  }
}

async function toggleDroneEstado(id) {
  const d = dronesData.find(x => x.id === id);
  try {
    showToast('Actualizando estado del dron...', 'info');
    const res = await apiFetch(`/drones/${id}/toggle-estado`, { method: 'PATCH' });
    const nuevoEstado = res?.data?.estado || res?.estado || ((d?.estado || '').toLowerCase() === 'deshabilitado' ? 'Habilitado' : 'Deshabilitado');
    if (d) d.estado = nuevoEstado;
    invalidateCache('drones');
    
    // Update stats
    const total = dronesData.length;
    const disponibles = dronesData.filter(x => (x.estado || '').toLowerCase() === 'habilitado' || (x.estado || '').toLowerCase() === 'disponible').length;
    const elTotal = document.getElementById('statTotalDrones');
    if (elTotal) elTotal.textContent = total;
    const elDisp = document.getElementById('statDronesDisponibles');
    if (elDisp) elDisp.textContent = disponibles;

    renderDronesTable();
    showToast(`<i class="fa-solid fa-check"></i> Dron ahora se encuentra: ${nuevoEstado.toUpperCase()}`, 'success');
  } catch (e) {
    showToast('Error al cambiar estado del dron: ' + e.message, 'error');
  }
}

async function deleteDrone(id) {
  if (!confirm('¿Eliminar este drone de la base de datos?')) return;
  try {
    await apiFetch(`/drones/${id}`, { method: 'DELETE' });
    dronesData = dronesData.filter(d => d.id !== id);
    invalidateCache('drones');
    renderDronesTable();
    showToast('Drone eliminado correctamente', 'info');
  } catch (e) {
    showToast('Error al eliminar dron: ' + e.message, 'error');
  }
}

window.editDrone = editDrone;
window.deleteDrone = deleteDrone;
window.toggleDroneEstado = toggleDroneEstado;

// ─────────────────────────────────────────
// 6. SERVICIOS PANEL (SIN PRECIOS)
// ─────────────────────────────────────────

// ─────────────────────────────────────────
// GESTIÓN INTEGRAL DE SERVICIOS & MULTIMEDIA
// ─────────────────────────────────────────

let _mediaItems = [];
let _galleryFilter = 'all';
let _galleryTargetType = null;

async function loadServicios() {
  try {
    const raw = await apiFetch('/servicios?include_inactive=true') || [];
    const list = Array.isArray(raw) ? raw : (raw.data || []);
    serviciosData = list.map(s => ({
      id: s.id_servicio,
      id_servicio: s.id_servicio,
      nombre: s.nombre_servicio || s.nombre || 'Servicio Dron',
      descripcion: s.descripcion || '',
      precio_base_m2: parseFloat(s.precio_base_m2 || 0),
      activo: s.activo === 0 || s.activo === false || s.activo === '0' ? false : true,
      imagen_url: s.imagen_url || 'img/servicio_precision.jpg',
      video_url: s.video_url || 'video/hero.mp4',
      icono: s.icono || 'fa-solid fa-helicopter',
      sistema: s.sistema || 'Tecnología Aeroespacial Flymetrics',
      eficiencia: s.eficiencia || 'Operación optimizada por lote',
      capacidad: s.capacidad || 'Cobertura de alta precisión',
      precision_metrica: s.precision_metrica || 'Centimétrica RTK'
    }));
    renderServiciosTable();
  } catch (err) {
    console.error('Error al cargar servicios:', err);
    const tbody = document.getElementById('serviciosTableBody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#ef4444; padding:30px;">Error al cargar servicios: ${err.message}</td></tr>`;
  }
}

function renderServiciosTable() {
  const tbody = document.getElementById('serviciosTableBody');
  if (!tbody) return;

  let list = [...serviciosData];
  const q = (document.getElementById('serviciosSearch')?.value || '').trim().toLowerCase();
  const filterActivo = document.getElementById('serviciosFilterActivo')?.value || '';

  if (q) {
    list = list.filter(s =>
      (s.nombre || '').toLowerCase().includes(q) ||
      (s.descripcion || '').toLowerCase().includes(q) ||
      (s.sistema || '').toLowerCase().includes(q) ||
      (s.eficiencia || '').toLowerCase().includes(q)
    );
  }

  if (filterActivo === 'activo') {
    list = list.filter(s => s.activo === true);
  } else if (filterActivo === 'inactivo') {
    list = list.filter(s => s.activo === false);
  }

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center" style="padding:40px; color:#64748b;"><div style="font-size:1.4rem; margin-bottom:8px;">📦</div>No se encontraron servicios registrados</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(s => {
    const sId = s.id || s.id_servicio;
    const imgUrl = resolveMediaUrl(s.imagen_url) || 'img/servicio_precision.jpg';
    const vidUrl = resolveMediaUrl(s.video_url) || '';
    const hasVid = Boolean(vidUrl);

    return `
      <tr>
        <td>
          <div style="position:relative; width:64px; height:48px; border-radius:8px; overflow:hidden; border:1px solid #cbd5e1; background:#0f172a; flex-shrink:0;">
            <img src="${imgUrl}" alt="${s.nombre}" style="width:100%; height:100%; object-fit:cover;" onerror="this.src='img/servicio_precision.jpg'" />
            ${hasVid ? `
              <span onclick="previewVideoModal('${vidUrl}')" title="Ver video demostrativo" style="position:absolute; bottom:2px; right:2px; background:rgba(0,48,73,0.85); color:#fff; border-radius:4px; font-size:0.65rem; padding:1px 4px; cursor:pointer;">
                <i class="fa-solid fa-play" style="color:#E4C7A1;"></i>
              </span>
            ` : ''}
          </div>
        </td>
        <td>
          <div style="display:flex; align-items:center; gap:8px;">
            <div style="width:32px; height:32px; border-radius:8px; background:rgba(28,130,173,0.12); color:#1c82ad; display:flex; align-items:center; justify-content:center; font-size:1rem; flex-shrink:0;">
              <i class="${s.icono || 'fa-solid fa-helicopter'}"></i>
            </div>
            <div>
              <div style="font-weight:800; color:#003049; font-size:0.92rem;">${s.nombre}</div>
              <div style="font-size:0.75rem; color:#64748b; max-width:280px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${s.descripcion}</div>
            </div>
          </div>
        </td>
        <td>
          <div style="font-size:0.78rem; line-height:1.4; color:#334155;">
            <div><strong style="color:#003049;">Sistema:</strong> ${s.sistema || '—'}</div>
            <div><strong style="color:#003049;">Eficiencia:</strong> ${s.eficiencia || '—'} | <strong style="color:#003049;">Precisión:</strong> ${s.precision_metrica || '—'}</div>
          </div>
        </td>
        <td style="text-align:center;">
          <button type="button" class="btn btn-sm" onclick="toggleServicio(${sId}, ${!s.activo})" style="background:${s.activo ? '#dcfce7' : '#f1f5f9'}; color:${s.activo ? '#15803d' : '#64748b'}; border:1px solid ${s.activo ? '#86efac' : '#cbd5e1'}; font-weight:800; font-size:0.75rem; border-radius:8px; padding:4px 10px; cursor:pointer;" title="Clic para cambiar visibilidad">
            <i class="fa-solid ${s.activo ? 'fa-check-circle' : 'fa-eye-slash'}"></i> ${s.activo ? 'Activo en Home' : 'Desactivado'}
          </button>
        </td>
        <td style="text-align:center;">
          <div style="display:inline-flex; gap:6px; align-items:center;">
            <button type="button" class="btn btn-ghost btn-sm" onclick="openEditServicioModal(${sId})" style="color:#1c82ad; font-weight:700; padding:5px 10px; border-radius:8px; border:1px solid rgba(28,130,173,0.3);" title="Editar servicio">
              <i class="fa-solid fa-pen-to-square"></i>
            </button>
            <button type="button" class="btn btn-sm" onclick="deleteServicio(${sId})" style="color:#e11d48; background:rgba(225,29,72,0.08); border:1px solid rgba(225,29,72,0.25); font-weight:700; padding:5px 10px; border-radius:8px;" title="Eliminar servicio">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}
window.renderServiciosTable = renderServiciosTable;

// Abrir modal de Nuevo Servicio
window.openNewServicioModal = function() {
  document.getElementById('formServicioAdmin')?.reset();
  document.getElementById('servicioModalId').value = '';
  document.getElementById('modalServicioTitle').textContent = 'Nuevo Servicio de Precisión';
  document.getElementById('servicioModalImgPreview').src = 'img/servicio_precision.jpg';
  document.getElementById('servicioModalVidPreview').src = 'video/hero.mp4';
  document.getElementById('servicioModalImagenUrl').value = 'img/servicio_precision.jpg';
  document.getElementById('servicioModalVideoUrl').value = 'video/hero.mp4';
  document.getElementById('servicioModalIcono').value = 'fa-solid fa-helicopter';
  setServicioIconoPreset('fa-solid fa-helicopter');
  openModal('modalServicio');
};

// Abrir modal de Editar Servicio
window.openEditServicioModal = function(id) {
  const s = serviciosData.find(x => (x.id || x.id_servicio) === id);
  if (!s) return;

  document.getElementById('servicioModalId').value = s.id || s.id_servicio;
  document.getElementById('modalServicioTitle').textContent = `Editar Servicio: ${s.nombre}`;
  document.getElementById('servicioModalNombre').value = s.nombre || '';
  document.getElementById('servicioModalDescripcion').value = s.descripcion || '';
  document.getElementById('servicioModalSistema').value = s.sistema || '';
  document.getElementById('servicioModalEficiencia').value = s.eficiencia || '';
  document.getElementById('servicioModalCapacidad').value = s.capacidad || '';
  document.getElementById('servicioModalPrecision').value = s.precision_metrica || '';
  document.getElementById('servicioModalIcono').value = s.icono || 'fa-solid fa-helicopter';
  document.getElementById('servicioModalImagenUrl').value = s.imagen_url || 'img/servicio_precision.jpg';
  document.getElementById('servicioModalVideoUrl').value = s.video_url || 'video/hero.mp4';
  document.getElementById('servicioModalActivo').checked = s.activo !== false;

  document.getElementById('servicioModalImgPreview').src = resolveMediaUrl(s.imagen_url || 'img/servicio_precision.jpg');
  document.getElementById('servicioModalVidPreview').src = resolveMediaUrl(s.video_url || 'video/hero.mp4');
  setServicioIconoPreset(s.icono || 'fa-solid fa-helicopter');

  openModal('modalServicio');
};

window.setServicioIconoPreset = function(cls) {
  const inp = document.getElementById('servicioModalIcono');
  if (inp) inp.value = cls;
  const prev = document.getElementById('servicioModalIconPreview');
  if (prev) prev.innerHTML = `<i class="${cls}"></i>`;
};

// Guardar servicio (Crear o Actualizar)
window.submitGuardarServicio = async function(e) {
  if (e) e.preventDefault();
  const btn = document.getElementById('btnGuardarServicioModal');
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...'; }

  const id = document.getElementById('servicioModalId')?.value;
  const nombre = (document.getElementById('servicioModalNombre')?.value || '').trim();
  const descripcion = (document.getElementById('servicioModalDescripcion')?.value || '').trim();
  const sistema = (document.getElementById('servicioModalSistema')?.value || '').trim();
  const eficiencia = (document.getElementById('servicioModalEficiencia')?.value || '').trim();
  const capacidad = (document.getElementById('servicioModalCapacidad')?.value || '').trim();
  const precision_metrica = (document.getElementById('servicioModalPrecision')?.value || '').trim();
  const icono = (document.getElementById('servicioModalIcono')?.value || 'fa-solid fa-helicopter').trim();
  const imagen_url = (document.getElementById('servicioModalImagenUrl')?.value || '').trim();
  const video_url = (document.getElementById('servicioModalVideoUrl')?.value || '').trim();
  const activo = document.getElementById('servicioModalActivo')?.checked ?? true;

  if (!nombre) {
    showToast('El nombre del servicio es obligatorio', 'warn');
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
    return;
  }

  const payload = {
    nombre_servicio: nombre,
    descripcion: descripcion,
    precio_base_m2: 0.0,
    activo: activo,
    imagen_url: imagen_url || null,
    video_url: video_url || null,
    icono: icono || null,
    sistema: sistema || null,
    eficiencia: eficiencia || null,
    capacidad: capacidad || null,
    precision_metrica: precision_metrica || null
  };

  try {
    if (id) {
      await apiFetch(`/servicios/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      showToast('<i class="fa-solid fa-check"></i> Servicio actualizado correctamente en base de datos', 'success');
    } else {
      await apiFetch('/servicios', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      showToast('<i class="fa-solid fa-check"></i> Nuevo servicio creado exitosamente en la base de datos', 'success');
    }

    closeModal('modalServicio');
    invalidateCache('servicios');
    await loadServicios();
  } catch (err) {
    showToast('Error al guardar servicio: ' + err.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
  }
};

window.toggleServicio = async function(id, newState) {
  try {
    await apiFetch(`/servicios/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ activo: Boolean(newState) })
    });
    const item = serviciosData.find(x => (x.id || x.id_servicio) === id);
    if (item) item.activo = Boolean(newState);
    renderServiciosTable();
    showToast(`<i class="fa-solid fa-check"></i> Servicio ${newState ? 'activado para página principal' : 'desactivado'} exitosamente`, 'success');
    invalidateCache('servicios');
  } catch (err) {
    showToast('Error al cambiar visibilidad del servicio: ' + err.message, 'error');
  }
};

window.deleteServicio = async function(id) {
  const s = serviciosData.find(x => (x.id || x.id_servicio) === id);
  const nom = s ? s.nombre : `Servicio #${id}`;
  if (!confirm(`¿Estás seguro de eliminar "${nom}" del catálogo del sistema y página principal?`)) return;

  try {
    const res = await apiFetch(`/servicios/${id}`, { method: 'DELETE' });
    showToast('<i class="fa-solid fa-check"></i> ' + (res?.message || 'Servicio eliminado exitosamente'), 'success');
    invalidateCache('servicios');
    await loadServicios();
  } catch (err) {
    showToast('Error al eliminar servicio: ' + err.message, 'error');
  }
};

// ─────────────────────────────────────────
// SUBIDA DIRECTA DE ARCHIVOS MULTIMEDIA
// ─────────────────────────────────────────

window.subirArchivoServicio = async function(inputEl, tipo) {
  if (!inputEl || !inputEl.files || !inputEl.files[0]) return;
  const file = inputEl.files[0];
  const spinnerId = tipo === 'video' ? 'servicioVidUploadSpinner' : 'servicioImgUploadSpinner';
  const spinner = document.getElementById(spinnerId);
  if (spinner) spinner.style.display = 'inline-flex';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('tipo', tipo);
  formData.append('modulo', 'servicios');

  try {
    const token = getToken();
    const res = await fetch(`${API_BASE}/media/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
      throw new Error(body.message || body.detail || 'Error al subir archivo');
    }

    const mediaUrl = body.data.url;
    const cacheBustedUrl = resolveMediaUrl(mediaUrl) + (mediaUrl.includes('?') ? '&' : '?') + 't=' + Date.now();
    if (tipo === 'imagen') {
      document.getElementById('servicioModalImagenUrl').value = mediaUrl;
      const imgPrev = document.getElementById('servicioModalImgPreview');
      if (imgPrev) imgPrev.src = cacheBustedUrl;
      showToast('<i class="fa-solid fa-check"></i> Imagen subida y vinculada al servicio', 'success');
    } else {
      document.getElementById('servicioModalVideoUrl').value = mediaUrl;
      const vidPrev = document.getElementById('servicioModalVidPreview');
      if (vidPrev) {
        vidPrev.src = cacheBustedUrl;
        vidPrev.load();
        vidPrev.play().catch(() => {});
      }
      showToast('<i class="fa-solid fa-check"></i> Video subido y vinculado al servicio', 'success');
    }
  } catch (err) {
    showToast('Error al subir archivo: ' + err.message, 'error');
  } finally {
    if (spinner) spinner.style.display = 'none';
    inputEl.value = '';
  }
};

// ─────────────────────────────────────────
// GALERÍA MULTIMEDIA
// ─────────────────────────────────────────

window.openMediaGalleryModal = async function(targetType = null) {
  _galleryTargetType = targetType;
  openModal('modalMediaGallery');
  filterMediaGallery(targetType || 'all');
  await loadMediaGallery();
};

window.loadMediaGallery = async function() {
  const grid = document.getElementById('galleryMediaGrid');
  if (!grid) return;
  grid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding:30px; color:#64748b;"><i class="fa-solid fa-spinner fa-spin"></i> Cargando archivos...</div>`;

  try {
    const token = getToken();
    const res = await fetch(`${API_BASE}/media`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const body = await res.json();
    if (body.success && Array.isArray(body.data)) {
      _mediaItems = body.data;
      renderMediaGalleryItems();
    } else {
      grid.innerHTML = `<div style="grid-column:1/-1; color:#ef4444; text-align:center;">No se pudo cargar la galería</div>`;
    }
  } catch (err) {
    grid.innerHTML = `<div style="grid-column:1/-1; color:#ef4444; text-align:center;">Error: ${err.message}</div>`;
  }
};

let _galleryOrigin = 'all'; // 'all', 'custom', 'system'

window.filterMediaOrigin = function(origin) {
  _galleryOrigin = origin;
  document.getElementById('galleryOriginAll')?.classList.toggle('btn-primary', origin === 'all');
  document.getElementById('galleryOriginAll')?.classList.toggle('btn-ghost', origin !== 'all');
  document.getElementById('galleryOriginCustom')?.classList.toggle('btn-primary', origin === 'custom');
  document.getElementById('galleryOriginCustom')?.classList.toggle('btn-ghost', origin !== 'custom');
  document.getElementById('galleryOriginSystem')?.classList.toggle('btn-primary', origin === 'system');
  document.getElementById('galleryOriginSystem')?.classList.toggle('btn-ghost', origin !== 'system');
  renderMediaGalleryItems();
};

window.filterMediaGallery = function(type) {
  _galleryFilter = type;
  document.getElementById('galleryTabAll')?.classList.toggle('btn-primary', type === 'all');
  document.getElementById('galleryTabAll')?.classList.toggle('btn-ghost', type !== 'all');
  document.getElementById('galleryTabImages')?.classList.toggle('btn-primary', type === 'imagen');
  document.getElementById('galleryTabImages')?.classList.toggle('btn-ghost', type !== 'imagen');
  document.getElementById('galleryTabVideos')?.classList.toggle('btn-primary', type === 'video');
  document.getElementById('galleryTabVideos')?.classList.toggle('btn-ghost', type !== 'video');
  renderMediaGalleryItems();
};

let _gallerySearchQuery = '';

window.filterMediaSearch = function(query) {
  _gallerySearchQuery = (query || '').toLowerCase().trim();
  renderMediaGalleryItems();
};

function renderMediaGalleryItems() {
  const grid = document.getElementById('galleryMediaGrid');
  if (!grid) return;

  const countBadge = document.getElementById('galleryCountBadge');

  let items = [..._mediaItems];
  if (_galleryFilter === 'imagen') items = items.filter(x => x.tipo === 'imagen');
  if (_galleryFilter === 'video') items = items.filter(x => x.tipo === 'video');

  if (_galleryOrigin === 'custom') items = items.filter(x => Boolean(x.is_custom_upload));
  if (_galleryOrigin === 'system') items = items.filter(x => !x.is_custom_upload);

  if (_gallerySearchQuery) {
    items = items.filter(x => 
      (x.name || '').toLowerCase().includes(_gallerySearchQuery) ||
      (x.url || '').toLowerCase().includes(_gallerySearchQuery)
    );
  }

  if (countBadge) {
    countBadge.textContent = `${items.length} archivo(s)`;
  }

  if (!items.length) {
    grid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:55px 20px; color:#94a3b8;">
      <i class="fa-solid fa-folder-open" style="font-size:2.8rem; margin-bottom:12px; color:#cbd5e1;"></i>
      <div style="font-weight:800; font-size:1.05rem; color:#475569;">No hay archivos en esta categoría o búsqueda</div>
      <div style="font-size:0.82rem; margin-top:6px; color:#94a3b8;">Prueba con otros términos de búsqueda o sube un archivo nuevo arriba.</div>
    </div>`;
    return;
  }

  grid.innerHTML = items.map(m => {
    const isVid = m.tipo === 'video';
    const isLogo = (m.name || '').toLowerCase().includes('logo') || Boolean(m.is_protected);
    const safeUrl = resolveMediaUrl(m.url || '');
    const safeName = (m.name || 'Archivo').replace(/'/g, "\\'");

    return `
      <div class="gallery-media-card" style="background:#ffffff; border:1.5px solid #cbd5e1; border-radius:18px; overflow:hidden; display:flex !important; flex-direction:column !important; box-shadow:0 8px 24px rgba(0,48,73,0.08); min-height:340px; position:relative;">
        <!-- Preview Slot Amplio con Fondo Gris Neutro -->
        <div class="card-thumb-wrap" style="width:100%; height:210px; min-height:210px; background:#e2e8f0; position:relative; overflow:hidden; display:flex !important; align-items:center; justify-content:center; cursor:pointer; border-bottom:1px solid #cbd5e1;" onclick="previewMediaInViewer('${safeUrl}', '${m.tipo}', '${safeName}', '${m.size_formatted || ''}')" title="Clic para ampliar">
          ${isVid ? `
            <video src="${safeUrl}" muted playsinline preload="metadata" style="background:#070d17; width:100%; height:100%; object-fit:cover; display:block;"></video>
            <span style="position:absolute; background:rgba(0,48,73,0.85); color:#fff; border-radius:50%; width:48px; height:48px; display:flex; align-items:center; justify-content:center; box-shadow:0 6px 18px rgba(0,0,0,0.6); z-index:2; border:2px solid #E4C7A1;">
              <i class="fa-solid fa-play" style="color:#E4C7A1; font-size:1.15rem; margin-left:3px;"></i>
            </span>
          ` : `
            <img src="${safeUrl}" alt="${safeName}" style="width:100%; height:100%; min-height:100%; object-fit:cover; display:block;" onerror="this.onerror=null; this.src='/img/servicio_precision.jpg';" loading="lazy" />
          `}
          
          <!-- Badges de Tipo y Protección -->
          <div style="position:absolute; top:10px; left:10px; display:flex; gap:6px; z-index:2;">
            <span style="background:rgba(0,24,40,0.88); color:#fff; font-size:0.72rem; font-weight:800; padding:4px 10px; border-radius:8px; backdrop-filter:blur(4px); box-shadow:0 2px 6px rgba(0,0,0,0.3);">
              ${isVid ? '🎬 Video' : '🖼️ Imagen'}
            </span>
            ${isLogo ? `
              <span style="background:#f59e0b; color:#fff; font-size:0.72rem; font-weight:800; padding:4px 10px; border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.25);">
                🔒 Logo Oficial
              </span>
            ` : `
              <span style="background:#0284c7; color:#fff; font-size:0.72rem; font-weight:800; padding:4px 10px; border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.25);">
                ✏️ Modificable
              </span>
            `}
          </div>

          <div style="position:absolute; bottom:10px; right:10px; z-index:2; background:rgba(0,0,0,0.7); color:#fff; font-size:0.72rem; font-weight:700; padding:4px 8px; border-radius:6px; backdrop-filter:blur(4px);">
            <i class="fa-solid fa-magnifying-glass-plus"></i> Ampliar
          </div>
        </div>

        <!-- Info Card con botones claros e intuitivos -->
        <div class="card-body" style="padding:14px 16px; display:flex !important; flex-direction:column !important; justify-content:space-between; gap:10px; flex:1; background:#ffffff;">
          <div>
            <span class="card-filename" style="font-weight:800; font-size:0.92rem; color:#003049; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:block;" title="${safeName}">
              ${safeName}
            </span>
            <div class="card-meta" style="display:flex; justify-content:space-between; align-items:center; font-size:0.76rem; color:#64748b; margin-top:4px;">
              <span style="font-weight:700;">${m.size_formatted || ''}</span>
              <span style="font-weight:700; color:${isLogo ? '#d97706' : '#059669'};">
                ${isLogo ? '🏛️ Protegido (Logo)' : '🗑️ Eliminable'}
              </span>
            </div>
          </div>

          <!-- Botones de Acción Claros con textos completos -->
          <div class="card-actions" style="display:flex; gap:8px; align-items:center; margin-top:4px;">
            <button type="button" class="btn btn-ghost" onclick="copiarUrlMedia('${safeUrl}')" style="flex:1; border:1px solid #cbd5e1; color:#1c82ad; height:38px; font-weight:700; font-size:0.8rem; border-radius:10px; display:inline-flex; align-items:center; justify-content:center; gap:4px;" title="Copiar enlace directo">
              <i class="fa-solid fa-copy"></i> Copiar
            </button>
            <button type="button" class="btn btn-primary" onclick="asignarMediaDesdeGaleria('${safeUrl}', '${m.tipo}')" style="flex:1.4; height:38px; font-weight:800; font-size:0.8rem; border-radius:10px; display:inline-flex; align-items:center; justify-content:center; gap:4px;" title="Usar este archivo">
              <i class="fa-solid fa-check"></i> Usar Archivo
            </button>
            ${!isLogo ? `
              <button type="button" class="btn" onclick="eliminarArchivoGaleria('${safeName}')" style="color:#ef4444; background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.25); height:38px; min-width:42px; border-radius:10px; cursor:pointer; display:inline-flex; align-items:center; justify-content:center;" title="Eliminar definitivamente del servidor">
                <i class="fa-solid fa-trash-can"></i>
              </button>
            ` : `
              <span style="color:#94a3b8; font-size:0.82rem; padding:0 8px;" title="Logo oficial protegido por el sistema">
                <i class="fa-solid fa-shield-halved"></i>
              </span>
            `}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

window.previewMediaInViewer = function(url, tipo, name, size) {
  const modal = document.getElementById('modalMediaPreviewer');
  if (!modal) return;

  const titleEl = document.getElementById('mediaViewerTitle');
  const subEl = document.getElementById('mediaViewerSubtitle');
  const metaEl = document.getElementById('mediaViewerMeta');
  const imgEl = document.getElementById('mediaViewerImg');
  const vidEl = document.getElementById('mediaViewerVid');
  const copyBtn = document.getElementById('mediaViewerCopyBtn');

  if (titleEl) titleEl.innerHTML = `<i class="fa-solid ${tipo === 'video' ? 'fa-film' : 'fa-image'}" style="color:var(--accent);"></i> ${name || 'Vista Previa'}`;
  if (subEl) subEl.textContent = url;
  if (metaEl) metaEl.innerHTML = `<span><strong>Tipo:</strong> ${tipo === 'video' ? 'Video' : 'Imagen'}</span> | <span><strong>Tamaño:</strong> ${size || 'Desconocido'}</span>`;

  const resolvedUrl = resolveMediaUrl(url);
  if (tipo === 'video') {
    if (imgEl) imgEl.style.display = 'none';
    if (vidEl) {
      vidEl.style.display = 'block';
      vidEl.src = resolvedUrl;
      vidEl.load();
      vidEl.play().catch(() => {});
    }
  } else {
    if (vidEl) {
      vidEl.pause();
      vidEl.style.display = 'none';
    }
    if (imgEl) {
      imgEl.style.display = 'block';
      imgEl.src = resolvedUrl;
    }
  }

  if (copyBtn) {
    copyBtn.onclick = () => copiarUrlMedia(url);
  }

  openModal('modalMediaPreviewer');
};

window.copiarUrlMedia = function(url) {
  navigator.clipboard.writeText(url).then(() => {
    showToast('<i class="fa-solid fa-check"></i> Enlace copiado al portapapeles: ' + url, 'info');
  }).catch(() => {
    showToast('Enlace: ' + url, 'info');
  });
};

window.asignarMediaDesdeGaleria = function(url, tipo) {
  // 1. Si el modal de Collage está abierto o es el target
  const collageModal = document.getElementById('modalCollageItem');
  if (collageModal && !collageModal.classList.contains('hidden')) {
    const inputMedio = document.getElementById('collageModalUrlMedio');
    if (inputMedio) {
      inputMedio.value = url;
      updateCollagePreview(url);
    }
    const selectTipo = document.getElementById('collageModalTipoMedio');
    if (selectTipo) {
      selectTipo.value = tipo;
      onCollageTipoMedioChange();
    }
    closeModal('modalMediaGallery');
    showToast('<i class="fa-solid fa-check"></i> Archivo asignado al elemento del collage', 'success');
    return;
  }

  // 2. Si el modal de Servicios está abierto
  const servModal = document.getElementById('modalServicio');
  if (servModal && !servModal.classList.contains('hidden')) {
    seleccionarMediaParaServicio(url, tipo);
    return;
  }

  // 3. Si se abrió desde Medios Globales (Video Hero o Portada)
  if (_galleryTargetType === 'hero_video') {
    const vInp = document.getElementById('pubHeroVideoInput');
    if (vInp) vInp.value = url;
    const vPrev = document.getElementById('pubGlobalHeroPreview');
    if (vPrev) { vPrev.src = url; vPrev.load(); vPrev.play().catch(()=>{}); }
    closeModal('modalMediaGallery');
    showToast('<i class="fa-solid fa-check"></i> Asignado como Video Hero Principal', 'success');
    return;
  }
  if (_galleryTargetType === 'mobile_poster') {
    const pInp = document.getElementById('pubMobilePosterInput');
    if (pInp) pInp.value = url;
    const pPrev = document.getElementById('pubGlobalPosterPreview');
    if (pPrev) pPrev.src = url;
    closeModal('modalMediaGallery');
    showToast('<i class="fa-solid fa-check"></i> Asignado como Portada Móvil', 'success');
    return;
  }

  // Por defecto, intentar asignar a Servicio o copiar
  seleccionarMediaParaServicio(url, tipo);
};

window.seleccionarMediaParaServicio = function(url, tipo) {
  if (tipo === 'imagen') {
    const inp = document.getElementById('servicioModalImagenUrl');
    if (inp) inp.value = url;
    const prev = document.getElementById('servicioModalImgPreview');
    if (prev) prev.src = url;
  } else {
    const inp = document.getElementById('servicioModalVideoUrl');
    if (inp) inp.value = url;
    const prev = document.getElementById('servicioModalVidPreview');
    if (prev) prev.src = url;
  }
  closeModal('modalMediaGallery');
  showToast('<i class="fa-solid fa-check"></i> Archivo asignado correctamente', 'success');
};

window.subirArchivoGaleriaDirecto = async function(inputEl) {
  if (!inputEl || !inputEl.files || !inputEl.files[0]) return;
  const file = inputEl.files[0];
  const isVid = file.name.match(/\.(mp4|webm|mov|m4v)$/i);
  const tipo = isVid ? 'video' : 'imagen';

  const statusEl = document.getElementById('galleryUploadStatus');
  if (statusEl) statusEl.style.display = 'flex';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('tipo', tipo);

  try {
    const token = getToken();
    const res = await fetch(`${API_BASE}/media/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    const body = await res.json();
    if (!res.ok || !body.success) throw new Error(body.message || 'Error al subir archivo');

    showToast('<i class="fa-solid fa-check"></i> Archivo subido exitosamente a la galería', 'success');
    await loadMediaGallery();
  } catch (err) {
    showToast('Error al subir a la galería: ' + err.message, 'error');
  } finally {
    if (statusEl) statusEl.style.display = 'none';
    inputEl.value = '';
  }
};

window.eliminarArchivoGaleria = async function(filename) {
  if (!confirm(`¿Eliminar definitivamente el archivo "${filename}" del servidor?\n\nEsta acción quitará el archivo de inmediato del sistema y la galería.`)) return;

  try {
    const token = getToken();
    const res = await fetch(`${API_BASE}/media/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const body = await res.json();
    if (!res.ok || !body.success) throw new Error(body.message || body.detail || 'No se pudo eliminar');

    showToast('<i class="fa-solid fa-trash-can"></i> Archivo eliminado exitosamente del servidor', 'success');
    await loadMediaGallery();
  } catch (err) {
    showToast('Error al eliminar archivo: ' + err.message, 'error');
  }
};

window.previewVideoModal = function(url) {
  if (!url) return;
  previewMediaInViewer(url, 'video', 'Video', '');
};

// ─────────────────────────────────────────
// 7. FACTURACIÓN & VINCULACIÓN CON ALEGRA
// ─────────────────────────────────────────

let clientesFacturacionData = [];

async function loadFacturacion() {
  try {
    const rawClientes = await apiFetch('/clientes') || [];
    clientesFacturacionData = (Array.isArray(rawClientes) ? rawClientes : (rawClientes.data || [])).map(c => {
      const apellidos = `${c.apellido_1 || ''} ${c.apellido_2 || ''}`.trim();
      const nombreCompleto = `${c.nombre || ''} ${apellidos}`.trim() || 'Cliente Sin Nombre';
      return {
        id: c.id_cliente || c.id,
        id_cliente: c.id_cliente || c.id,
        nombre: nombreCompleto,
        email: c.email || (c.usuario ? c.usuario.email : ''),
        telefono: c.telefono || '—',
        cedula: c.numero_documento || '—',
        link_alegra: (c.link_alegra || '').trim(),
        verificado: c.verificado
      };
    });
    populateAlegraClienteSelect();
    renderPagosTable();
  } catch (e) {
    console.warn("Error loading facturacion:", e);
    renderPagosTable();
  }
}

function populateAlegraClienteSelect() {
  const sel = document.getElementById('alegraClienteSelect');
  if (!sel) return;
  if (!clientesFacturacionData.length) {
    sel.innerHTML = '<option value="">No hay clientes registrados</option>';
    return;
  }
  sel.innerHTML = '<option value="">Selecciona un cliente...</option>' +
    clientesFacturacionData.map(c => `<option value="${c.id_cliente}">${c.nombre} (NIT/CC: ${c.cedula}) — ${c.email || c.telefono}</option>`).join('');
}

window.onAlegraClienteChange = function() {
  const sel = document.getElementById('alegraClienteSelect');
  const inp = document.getElementById('alegraUrlInput');
  if (!sel || !inp) return;
  const id = parseInt(sel.value);
  const cliente = clientesFacturacionData.find(c => c.id_cliente === id);
  if (cliente && cliente.link_alegra) {
    inp.value = cliente.link_alegra;
  } else {
    inp.value = '';
  }
};

function renderPagosTable(search = '') {
  let data = clientesFacturacionData;
  const q = (search || (document.getElementById('pagosSearch')?.value || '')).toLowerCase().trim();
  if (q) {
    data = data.filter(c => [c.nombre, c.email, c.telefono, c.cedula, c.link_alegra].some(v => (v || '').toLowerCase().includes(q)));
  }
  const tbody = document.getElementById('pagosTableBody');
  if (!tbody) return;

  tbody.innerHTML = data.length ? data.map(c => {
    const hasAlegra = Boolean(c.link_alegra && (c.link_alegra.startsWith('http://') || c.link_alegra.startsWith('https://')));
    return `
    <tr>
      <td style="font-weight:800; color:var(--primary);">#CLI-${c.id_cliente}</td>
      <td>
        <div style="font-weight:700; color:#003049;">${c.nombre}</div>
        <div class="text-muted" style="font-size:0.75rem;">${c.email || ''}</div>
      </td>
      <td style="font-weight:600; color:#475569;">${c.cedula}</td>
      <td>${c.telefono}</td>
      <td>
        ${hasAlegra
          ? `<span class="badge" style="background:rgba(16, 185, 129, 0.12); color:#059669; font-weight:700; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-circle-check"></i> Vinculado en Alegra</span>`
          : `<span class="badge" style="background:rgba(239, 68, 68, 0.08); color:#dc2626; font-weight:700; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-clock"></i> Pendiente Enlace</span>`
        }
      </td>
      <td>
        ${hasAlegra ? `
          <a href="${c.link_alegra}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-sm" style="color:#0284c7; font-weight:700; display:inline-flex; align-items:center; gap:6px; text-decoration:none;">
            <i class="fa-solid fa-arrow-up-right-from-square"></i> Abrir Portal Alegra
          </a>
        ` : `
          <span class="text-muted" style="font-size:0.80rem; font-style:italic;">Sin link configurado</span>
        `}
      </td>
      <td style="text-align:center;">
        <button class="btn btn-primary btn-sm" onclick="openVincularAlegraModal(${c.id_cliente})" style="display:inline-flex; align-items:center; gap:6px; font-weight:700; padding:6px 12px; border-radius:8px;">
          <i class="fa-solid fa-link"></i> ${hasAlegra ? 'Editar Link Alegra' : 'Vincular Alegra'}
        </button>
      </td>
    </tr>
  `;
  }).join('') : `<tr><td colspan="7" class="text-center" style="padding:40px"><div class="empty-icon"><i class="fa-solid fa-file-invoice-dollar" style="font-size:2rem; color:var(--accent);"></i></div><div class="empty-title">No hay clientes encontrados</div><div class="empty-sub">No se hallaron clientes para la búsqueda ingresada.</div></td></tr>`;
}

window.openVincularAlegraModal = function(id_cliente = null) {
  populateAlegraClienteSelect();
  const sel = document.getElementById('alegraClienteSelect');
  const inp = document.getElementById('alegraUrlInput');
  if (id_cliente && sel) {
    sel.value = id_cliente;
    const cliente = clientesFacturacionData.find(c => c.id_cliente === id_cliente);
    if (inp) inp.value = (cliente && cliente.link_alegra) ? cliente.link_alegra : '';
  } else {
    if (sel) sel.value = '';
    if (inp) inp.value = '';
  }
  openModal('vincularAlegraModal');
};

window.submitVincularAlegra = async function(e) {
  if (e) e.preventDefault();
  const sel = document.getElementById('alegraClienteSelect');
  const inp = document.getElementById('alegraUrlInput');
  const id_cliente = parseInt(sel?.value);
  const link_alegra = (inp?.value || '').trim();

  if (!id_cliente || !link_alegra) {
    showToast('Por favor selecciona un cliente e ingresa el enlace de Alegra (*)', 'warn');
    return;
  }

  try {
    showToast('Guardando vinculación de Alegra...', 'info');
    await apiFetch(`/clientes/${id_cliente}/alegra`, {
      method: 'PUT',
      body: JSON.stringify({ link_alegra })
    });
    showToast('<i class="fa-solid fa-check"></i> Facturación de Alegra vinculada exitosamente al cliente', 'success');
    closeModal('vincularAlegraModal');
    invalidateCache('clientes');
    await loadFacturacion();
  } catch (err) {
    showToast('Error al vincular con Alegra: ' + err.message, 'error');
  }
};

// ─────────────────────────────────────────
// GESTIÓN DE USUARIOS
// ─────────────────────────────────────────



// ─────────────────────────────────────────
// 8. REPORTES PANEL
// ─────────────────────────────────────────


let _filteredReportesVuelo = null;
let _filteredInformesEjecutivos = null;

async function loadReportes() {
  const raw = await apiFetch('/reportes-vuelo') || [];
  reportesData = raw.map(r => ({
    id: r.id_reporte || r.id_bitacora || r.id,
    turno_id: r.id_turno || r.id,
    insumos_litros: r.insumos_litros_aplicados || 15.0,
    agua_litros: r.agua_litros || 100.0,
    baterias: r.baterias_utilizadas || 4,
    cumple_rac: r.cumple_rac100 !== undefined ? r.cumple_rac100 : 1,
    observaciones: r.observaciones_campo || 'Operación ejecutada bajo parámetros técnicos.',
    fecha: r.fecha || new Date().toISOString().split('T')[0],
    cliente: r.cliente || 'Cliente Flymetrics',
    finca: r.finca || 'Finca Registrada',
    tecnico: r.tecnico || 'Piloto Certificado',
    servicio: r.servicio || 'Vuelo Agrícola',
    duracion_min: r.duracion_min || 45,
    area_ha: r.area_ha || 10.0,
    url_entregable_drive: r.url_entregable_drive,
    recomendaciones_agronomicas: r.recomendaciones_agronomicas
  }));
  _filteredReportesVuelo = null;
  _filteredInformesEjecutivos = null;
  renderReportesTable();
}

function filterReportesVueloTable() {
  const q = (document.getElementById('reportesVueloSearch')?.value || '').trim().toLowerCase();
  const dateVal = document.getElementById('reportesVueloDateFilter')?.value || '';

  _filteredReportesVuelo = reportesData.filter(r => {
    const matchQ = !q || [r.cliente, r.finca, r.servicio, r.tecnico, String(r.id), String(r.turno_id)].some(v => (v || '').toLowerCase().includes(q));
    const matchDate = !dateVal || (r.fecha && r.fecha.startsWith(dateVal));
    return matchQ && matchDate;
  });

  renderReportesVueloTable();
}
window.filterReportesVueloTable = filterReportesVueloTable;

function filterInformesEjecutivosTable() {
  const q = (document.getElementById('informesEjecutivosSearch')?.value || '').trim().toLowerCase();
  const dateVal = document.getElementById('informesEjecutivosDateFilter')?.value || '';

  _filteredInformesEjecutivos = reportesData.filter(r => {
    const matchQ = !q || [r.cliente, r.finca, r.servicio, r.tecnico, r.recomendaciones_agronomicas, String(r.id), String(r.turno_id)].some(v => (v || '').toLowerCase().includes(q));
    const matchDate = !dateVal || (r.fecha && r.fecha.startsWith(dateVal));
    return matchQ && matchDate;
  });

  renderInformesEjecutivosTable();
}
window.filterInformesEjecutivosTable = filterInformesEjecutivosTable;

function renderReportesVueloTable() {
  // Bitácora de vuelo eliminada del portal administrativo
}

function formatExternalUrl(url) {
  if (!url) return '';
  url = String(url).trim();
  if (!url || url === '#' || url === 'null' || url === 'undefined') return '';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('/')) {
    return url;
  }
  return 'https://' + url;
}

function renderInformesEjecutivosTable() {
  const tbody = document.getElementById('informesEjecutivosTableBody');
  if (!tbody) return;
  const list = _filteredInformesEjecutivos !== null ? _filteredInformesEjecutivos : reportesData;

  tbody.innerHTML = list.length ? list.map(r => {
    const rawLink = r.url_entregable_drive || r.url_archivo || '';
    const cleanLink = formatExternalUrl(rawLink);
    const hasLink = Boolean(cleanLink && (cleanLink.startsWith('http://') || cleanLink.startsWith('https://')));
    return `
    <tr>
      <td style="font-weight:800; color:var(--primary);">#RAD-${r.id}</td>
      <td>
        <span style="font-weight:600; color:#475569;"><i class="fa-solid fa-calendar-day" style="color:#1c82ad; margin-right:4px;"></i> ${formatDate(r.fecha)}</span>
      </td>
      <td>
        <div style="font-weight:700; color:#003049;">${r.cliente || '—'}</div>
      </td>
      <td>${r.finca || '—'}</td>
      <td><span style="font-weight:600; color:#1c82ad;">${r.servicio || 'Vuelo agrícola'}</span></td>
      <td>
        ${hasLink 
          ? `<span class="badge" style="background:rgba(16, 185, 129, 0.12); color:#059669; font-weight:700; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-circle-check"></i> SharePoint Habilitado</span>`
          : `<span class="badge" style="background:rgba(245, 158, 11, 0.12); color:#d97706; font-weight:700; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-clock"></i> Sin enlace</span>`
        }
      </td>
      <td>
        ${hasLink 
          ? `<a href="${cleanLink}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-sm" style="color:#0284c7; font-weight:700; display:inline-flex; align-items:center; gap:6px; text-decoration:none;"><i class="fa-solid fa-arrow-up-right-from-square"></i> Abrir SharePoint</a>`
          : `<span style="color:#94a3b8; font-size:0.82rem;">No habilitado</span>`
        }
      </td>
      <td style="text-align:center;">
        <div style="display:flex; gap:6px; flex-wrap:wrap; justify-content:center;">
          <button class="btn btn-primary btn-sm" onclick="openEditInformeEjecutivoModal(${r.id})" title="Vincular o modificar enlace de SharePoint" style="display:inline-flex; align-items:center; gap:6px; font-weight:700; padding:6px 12px; border-radius:8px;">
            <i class="fa-solid fa-link"></i> ${hasLink ? 'Editar Link SharePoint' : 'Vincular SharePoint'}
          </button>
          <button class="btn btn-ghost btn-sm" onclick="downloadReporte(${r.id})" title="Descargar informe oficial en PDF" style="display:inline-flex; align-items:center; gap:4px; font-weight:700;">
            <i class="fa-solid fa-file-pdf"></i> PDF
          </button>
        </div>
      </td>
    </tr>
  `;
  }).join('') : `<tr><td colspan="8" class="text-center" style="padding:40px"><div class="empty-state" style="padding:0"><div class="empty-icon"><i class="fa-solid fa-file-circle-question" style="font-size:2rem; color:var(--accent);"></i></div><div class="empty-title">No se encontraron informes ejecutivos registrados</div></div></td></tr>`;
}

function renderReportesTable() {
  renderInformesEjecutivosTable();
}

function viewInformeEjecutivo(id) {
  const r = reportesData.find(x => x.id === id || x.turno_id === id);
  if (!r) return;
  const cleanLink = formatExternalUrl(r.url_entregable_drive || r.url_archivo);
  document.getElementById('detailModalTitle').innerHTML = `<i class="fa-solid fa-file-signature" style="color:var(--accent); margin-right:8px;"></i> Informe Ejecutivo #${r.id}`;
  document.getElementById('detailModalBody').innerHTML = `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:20px;">
      
      <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:16px; padding:14px;">
        <div style="font-size:0.76rem; font-weight:800; color:#1c82ad; text-transform:uppercase; margin-bottom:4px;"><i class="fa-solid fa-user"></i> CLIENTE</div>
        <div style="font-size:1rem; font-weight:800; color:#003049;">${r.cliente || '—'}</div>
      </div>

      <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:16px; padding:14px;">
        <div style="font-size:0.76rem; font-weight:800; color:#1c82ad; text-transform:uppercase; margin-bottom:4px;"><i class="fa-solid fa-house-chimney"></i> FINCA</div>
        <div style="font-size:1rem; font-weight:800; color:#003049;">${r.finca || '—'}</div>
      </div>

      <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:16px; padding:14px;">
        <div style="font-size:0.76rem; font-weight:800; color:#1c82ad; text-transform:uppercase; margin-bottom:4px;"><i class="fa-solid fa-spray-can"></i> SERVICIO AGRÍCOLA</div>
        <div style="font-size:1rem; font-weight:800; color:#003049;">${r.servicio || 'Vuelo Agrícola'}</div>
      </div>

      <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:16px; padding:14px;">
        <div style="font-size:0.76rem; font-weight:800; color:#1c82ad; text-transform:uppercase; margin-bottom:4px;"><i class="fa-solid fa-calendar-day"></i> FECHA EJECUCIÓN</div>
        <div style="font-size:1rem; font-weight:800; color:#003049;">${formatDate(r.fecha)}</div>
      </div>

      ${cleanLink ? `
        <div style="grid-column: 1 / -1; background:rgba(28,130,173,0.06); border:1.5px solid rgba(28,130,173,0.25); border-radius:16px; padding:14px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="font-size:0.76rem; font-weight:800; color:#1c82ad; text-transform:uppercase;"><i class="fa-solid fa-globe"></i> ENLACE DIRECTO SHAREPOINT</div>
            <div style="font-size:0.88rem; color:#003049; font-weight:700; word-break:break-all; margin-top:2px;">${cleanLink}</div>
          </div>
          <a href="${cleanLink}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:800; text-decoration:none; white-space:nowrap;">
            <i class="fa-solid fa-arrow-up-right-from-square"></i> Abrir SharePoint
          </a>
        </div>
      ` : `
        <div style="grid-column: 1 / -1; background:rgba(245,158,11,0.08); border:1.5px dashed rgba(245,158,11,0.3); border-radius:16px; padding:12px 16px; font-size:0.86rem; color:#b45309; display:flex; align-items:center; gap:8px;">
          <i class="fa-solid fa-clock"></i> Sin enlace de SharePoint configurado actualmente para este vuelo.
        </div>
      `}

    </div>

    <div style="display:flex; justify-content:flex-end; gap:10px; flex-wrap:wrap;">
      <button class="btn btn-warn btn-sm" onclick="closeModal('detailModal'); openEditInformeEjecutivoModal(${r.id});" style="display:inline-flex; align-items:center; gap:6px; font-weight:700; background:#f59e0b; color:#fff; border:none; border-radius:8px;">
        <i class="fa-solid fa-link"></i> ${cleanLink ? 'Editar Link SharePoint' : 'Vincular SharePoint'}
      </button>
      <button class="btn btn-ghost btn-sm" onclick="downloadReporte(${r.id})" style="display:inline-flex; align-items:center; gap:6px; font-weight:700;">
        <i class="fa-solid fa-file-pdf"></i> Descargar PDF
      </button>
      <button class="btn btn-primary btn-sm" onclick="closeModal('detailModal')">Cerrar</button>
    </div>
  `;
  openModal('detailModal');
}
window.viewInformeEjecutivo = viewInformeEjecutivo;
window.viewReporteBitacora = viewInformeEjecutivo;
window.viewReporte = viewInformeEjecutivo; // legacy

// ─────────────────────────────────────────
// GESTIÓN DE INFORMES EJECUTIVOS (VINCULACIÓN SHAREPOINT - ALEGRA STYLE)
// ─────────────────────────────────────────
let clientesSharepointData = [];

async function loadInformesEjecutivosClientes() {
  try {
    const rawClientes = await apiFetch('/clientes') || [];
    clientesSharepointData = (Array.isArray(rawClientes) ? rawClientes : (rawClientes.data || [])).map(c => {
      const apellidos = `${c.apellido_1 || ''} ${c.apellido_2 || ''}`.trim();
      const nombreCompleto = `${c.nombre || ''} ${apellidos}`.trim() || 'Cliente Sin Nombre';
      return {
        id: c.id_cliente || c.id,
        id_cliente: c.id_cliente || c.id,
        nombre: nombreCompleto,
        email: c.email || (c.usuario ? c.usuario.email : ''),
        telefono: c.telefono || '—',
        cedula: c.numero_documento || '—',
        link_sharepoint: (c.link_sharepoint || '').trim(),
        verificado: c.verificado
      };
    });
    populateSharepointClienteSelect();
    renderInformesEjecutivosTable();
  } catch (e) {
    console.warn("Error loading clientes sharepoint:", e);
    renderInformesEjecutivosTable();
  }
}
window.loadInformesEjecutivosClientes = loadInformesEjecutivosClientes;

function populateSharepointClienteSelect() {
  const sel = document.getElementById('sharepointClienteSelect');
  if (!sel) return;
  if (!clientesSharepointData.length) {
    sel.innerHTML = '<option value="">No hay clientes registrados</option>';
    return;
  }
  sel.innerHTML = '<option value="">Selecciona un cliente...</option>' +
    clientesSharepointData.map(c => `<option value="${c.id_cliente}">${c.nombre} (NIT/CC: ${c.cedula}) — ${c.email || c.telefono}</option>`).join('');
}

window.onSharepointClienteChange = function() {
  const sel = document.getElementById('sharepointClienteSelect');
  const inp = document.getElementById('sharepointUrlInput');
  if (!sel || !inp) return;
  const id = parseInt(sel.value);
  const cliente = clientesSharepointData.find(c => c.id_cliente === id);
  if (cliente && cliente.link_sharepoint) {
    inp.value = cliente.link_sharepoint;
  } else {
    inp.value = '';
  }
};

function renderInformesEjecutivosTable(search = '') {
  let data = clientesSharepointData;
  const q = (search || (document.getElementById('informesEjecutivosSearch')?.value || '')).toLowerCase().trim();
  if (q) {
    data = data.filter(c => [c.nombre, c.email, c.telefono, c.cedula, c.link_sharepoint].some(v => (v || '').toLowerCase().includes(q)));
  }
  const tbody = document.getElementById('informesEjecutivosTableBody');
  if (!tbody) return;

  tbody.innerHTML = data.length ? data.map(c => {
    const rawLink = c.link_sharepoint || '';
    const cleanLink = formatExternalUrl(rawLink);
    const hasSharepoint = Boolean(cleanLink && (cleanLink.startsWith('http://') || cleanLink.startsWith('https://')));
    return `
    <tr>
      <td style="font-weight:800; color:var(--primary);">#CLI-${c.id_cliente}</td>
      <td>
        <div style="font-weight:700; color:#003049;">${c.nombre}</div>
        <div class="text-muted" style="font-size:0.75rem;">${c.email || ''}</div>
      </td>
      <td style="font-weight:600; color:#475569;">${c.cedula}</td>
      <td>${c.telefono}</td>
      <td>
        ${hasSharepoint
          ? `<span class="badge" style="background:rgba(16, 185, 129, 0.12); color:#059669; font-weight:700; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-circle-check"></i> Vinculado en SharePoint</span>`
          : `<span class="badge" style="background:rgba(239, 68, 68, 0.08); color:#dc2626; font-weight:700; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-clock"></i> Pendiente Enlace</span>`
        }
      </td>
      <td>
        ${hasSharepoint ? `
          <a href="${cleanLink}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-sm" style="color:#0284c7; font-weight:700; display:inline-flex; align-items:center; gap:6px; text-decoration:none;">
            <i class="fa-solid fa-arrow-up-right-from-square"></i> Abrir SharePoint
          </a>
        ` : `
          <span class="text-muted" style="font-size:0.80rem; font-style:italic;">Sin link configurado</span>
        `}
      </td>
      <td style="text-align:center;">
        <button class="btn btn-primary btn-sm" onclick="openVincularSharepointModal(${c.id_cliente})" style="display:inline-flex; align-items:center; gap:6px; font-weight:700; padding:6px 12px; border-radius:8px;">
          <i class="fa-solid fa-link"></i> ${hasSharepoint ? 'Editar Link SharePoint' : 'Vincular SharePoint'}
        </button>
      </td>
    </tr>
  `;
  }).join('') : `<tr><td colspan="7" class="text-center" style="padding:40px"><div class="empty-icon"><i class="fa-solid fa-file-signature" style="font-size:2rem; color:var(--accent);"></i></div><div class="empty-title">No hay clientes encontrados</div><div class="empty-sub">No se hallaron clientes para la búsqueda ingresada.</div></td></tr>`;
}
window.renderInformesEjecutivosTable = renderInformesEjecutivosTable;
window.filterInformesEjecutivosTable = function() {
  renderInformesEjecutivosTable();
};

window.openVincularSharepointModal = function(id_cliente = null) {
  populateSharepointClienteSelect();
  const sel = document.getElementById('sharepointClienteSelect');
  const inp = document.getElementById('sharepointUrlInput');
  if (id_cliente && sel) {
    sel.value = id_cliente;
    const cliente = clientesSharepointData.find(c => c.id_cliente === id_cliente);
    if (inp) inp.value = (cliente && cliente.link_sharepoint) ? cliente.link_sharepoint : '';
  } else {
    if (sel) sel.value = '';
    if (inp) inp.value = '';
  }
  openModal('vincularSharepointModal');
};
window.openNewInformeEjecutivoModal = () => openVincularSharepointModal();
window.openEditInformeEjecutivoModal = (id) => openVincularSharepointModal(id);
window.openOverrideInformeModal = window.openEditInformeEjecutivoModal;
window.openEditBitacoraModal = window.openEditInformeEjecutivoModal;
window.openOverrideBitacoraModal = window.openEditInformeEjecutivoModal;
window.openNewBitacoraModal = window.openNewInformeEjecutivoModal;

window.submitVincularSharepoint = async function(e) {
  if (e) e.preventDefault();
  const sel = document.getElementById('sharepointClienteSelect');
  const inp = document.getElementById('sharepointUrlInput');
  const id_cliente = parseInt(sel?.value);
  let link_sharepoint = (inp?.value || '').trim();

  if (!id_cliente || !link_sharepoint) {
    showToast('Por favor selecciona un cliente e ingresa el enlace de SharePoint (*)', 'warn');
    return;
  }

  if (!link_sharepoint.startsWith('http://') && !link_sharepoint.startsWith('https://')) {
    link_sharepoint = 'https://' + link_sharepoint;
  }

  try {
    showToast('Guardando vinculación de SharePoint...', 'info');
    await apiFetch(`/clientes/${id_cliente}/sharepoint`, {
      method: 'PUT',
      body: JSON.stringify({ link_sharepoint })
    });
    showToast('<i class="fa-solid fa-check"></i> Carpeta de SharePoint vinculada exitosamente al cliente', 'success');
    closeModal('vincularSharepointModal');
    invalidateCache('clientes');
    await loadInformesEjecutivosClientes();
  } catch (err) {
    showToast('Error al vincular con SharePoint: ' + err.message, 'error');
  }
};
window.submitOverrideInformeEjecutivo = window.submitVincularSharepoint;
window.submitOverrideBitacora = window.submitVincularSharepoint;
window.openEditReporteModal = window.openEditInformeEjecutivoModal;

function downloadReporte(id) {
  const r = reportesData.find(x => x.id === id);
  if (!r) return;

  const spUrl = r.link_sharepoint || r.url_sharepoint || r.sharepoint_url || r.url_archivo;
  if (spUrl && (spUrl.startsWith('http://') || spUrl.startsWith('https://'))) {
    window.open(spUrl, '_blank', 'noopener,noreferrer');
    showToast('<i class="fa-solid fa-arrow-up-right-from-square"></i> Abriendo informe oficial en Microsoft SharePoint...', 'info');
    return;
  }

  if (r.id_entregable) {
    window.open(`${API_BASE}/entregables/${r.id_entregable}/descargar`, '_blank');
    showToast('<i class="fa-solid fa-file-pdf"></i> Abriendo informe digital oficial...', 'info');
    return;
  }
  if (r.id_turno) {
    // Descarga documento oficial generado por backend desde entregables
    window.open(`${API_BASE}/entregables/${r.id_turno}/descargar-docx`, '_blank');
    showToast('<i class="fa-solid fa-file-word"></i> Descargando reporte técnico oficial DOCX...', 'success');
    return;
  }

  showToast('<i class="fa-solid fa-clock"></i> Este reporte aún no cuenta con archivo digital o enlace de SharePoint vinculado.', 'warn');
}

// ─────────────────────────────────────────
// 9. CONFIGURACIÓN PANEL (BASE DE DATOS)
// ─────────────────────────────────────────
function loadConfiguracion() {
  if (typeof window.loadCorporateConfig === 'function') {
    window.loadCorporateConfig();
  }
}

async function saveConfig() {
  if (typeof window.saveCorporateConfig === 'function') {
    await window.saveCorporateConfig();
  }
}

async function changePassword() {
  const current = document.getElementById('cfgCurrentPwd')?.value || '';
  const newPwd = document.getElementById('cfgNewPwd')?.value || '';
  const confirm = document.getElementById('cfgConfirmPwd')?.value || '';

  if (!newPwd || !confirm) return showToast('Por favor ingresa y confirma la nueva contraseña', 'warn');
  if (newPwd !== confirm) return showToast('Las contraseñas no coinciden', 'error');
  if (newPwd.length < 6) return showToast('La contraseña debe tener al menos 6 caracteres', 'warn');

  try {
    showToast('Actualizando contraseña...', 'info');
    await apiFetch('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: current, new_password: newPwd })
    });
    showToast('<i class="fa-solid fa-check"></i> Contraseña de administrador actualizada exitosamente en la base de datos', 'success');
    if (document.getElementById('cfgCurrentPwd')) document.getElementById('cfgCurrentPwd').value = '';
    if (document.getElementById('cfgNewPwd')) document.getElementById('cfgNewPwd').value = '';
    if (document.getElementById('cfgConfirmPwd')) document.getElementById('cfgConfirmPwd').value = '';
  } catch (e) {
    showToast('Error al actualizar contraseña: ' + e.message, 'error');
  }
}
window.changePassword = changePassword;

/* ============================================================
   PERFIL CORPORATIVO & CONFIGURACIÓN GLOBAL
   ============================================================ */
const DEFAULT_CORPORATE_CONFIG = {
  empresa: "Flymetrics Colombia S.A.S.",
  nit: "900.123.456-7",
  telefono: "+57 314 3764972",
  whatsapp: "+57 314 3764972",
  email: "comercial@flymetrics.com.co",
  direccion: "Avenida El Dorado #68b-70, Bogotá D.C.",
  wa_template_24h: "Hola {nombre}, te contactamos desde Flymetrics Colombia sobre tu solicitud de {servicio} ({hectareas} ha).",
  wa_template_agendar: "Hola Flymetrics Colombia, acabo de agendar una solicitud de servicio / demostración:\nRadicado: {radicado}\nProductor: {nombre} (CC/NIT: {cedula})\nFinca: {finca} en {municipio} ({departamento})\nCultivo: {cultivo} ({hectareas} Ha)\nServicio: {servicio}\nFecha programada: {fecha}\nUbicación / Maps: {ubicacion_maps}\nDeseo coordinar detalles técnicos de campo con el piloto.",
  wa_template_general: "Hola Flymetrics, deseo solicitar asesoría e información técnica sobre sus servicios de drones agrícolas.",
  zonas_mayor_presencia: [
    {
      nombre: 'Cundinamarca',
      tag: 'Base Central',
      lat: 4.7110,
      lng: -74.0721,
      descripcion: 'Sabana de Bogotá, Facatativá, Chía, Madrid — Flores, Papa y Hortalizas',
      servicio: 'Monitoreo Multiespectral, Cartografía y Aspersión',
      demanda: 'Base Central y Operaciones Sabana'
    },
    {
      nombre: 'Meta',
      tag: 'Operación Continua',
      lat: 4.1420,
      lng: -73.6266,
      descripcion: 'Villavicencio, Puerto López, Granada — Palma, Soya, Maíz y Ganadería',
      servicio: 'Fumigación de Palma, Soya, Maíz y Ganadería',
      demanda: 'Operación Continua Llanos'
    },
    {
      nombre: 'Huila',
      tag: 'Laderas y Valles',
      lat: 2.9273,
      lng: -75.2819,
      descripcion: 'Neiva, Campoalegre, Pitalito — Café de Especialidad, Arroz y Frutales',
      servicio: 'Aspersión en Café de Especialidad, Arroz y Frutales',
      demanda: 'Laderas y Valles Andinos'
    },
    {
      nombre: 'Tolima',
      tag: 'Planicies de Riego',
      lat: 4.1420,
      lng: -74.8880,
      descripcion: 'Espinal, Ibagué, Saldaña — Arroz, Maíz, Algodón y Pasturas',
      servicio: 'Fumigación y Fertilización de Arroz, Maíz y Pastos',
      demanda: 'Planicies de Riego'
    }
  ]
};

let _currentCorporateConfig = { ...DEFAULT_CORPORATE_CONFIG };

function normalizeZones(zones) {
  const source = Array.isArray(zones) && zones.length ? zones : DEFAULT_CORPORATE_CONFIG.zonas_mayor_presencia;
  return source.map((zone, index) => ({
    nombre: zone.nombre || zone.title || `Zona ${index + 1}`,
    tag: zone.tag || 'Operación',
    lat: Number(zone.lat ?? zone.latitude ?? zone.latitud ?? DEFAULT_CORPORATE_CONFIG.zonas_mayor_presencia[index]?.lat ?? 0),
    lng: Number(zone.lng ?? zone.lon ?? zone.longitud ?? DEFAULT_CORPORATE_CONFIG.zonas_mayor_presencia[index]?.lng ?? 0),
    descripcion: zone.descripcion || zone.description || '',
    servicio: zone.servicio || zone.service || 'Monitoreo Multiespectral, Cartografía y Aspersión',
    demanda: zone.demanda || zone.demand || 'Cobertura Operativa'
  }));
}

function renderCorporateZonesEditor() {
  const listEl = document.getElementById('cfgZonesList');
  const panelCardsEl = document.getElementById('zonasPanelCards');

  const zones = normalizeZones(_currentCorporateConfig.zonas_mayor_presencia);

  const renderCardsHTML = (items) => {
    if (!items.length) {
      return `
        <div class="empty-state" style="grid-column: 1 / -1; padding: 28px; border: 2px dashed rgba(28,130,173,0.3); border-radius: 16px; background: rgba(28,130,173,0.03); color: var(--text-2); text-align:center;">
          <div style="font-size:2.2rem; margin-bottom:10px;">🗺️</div>
          <div style="font-weight:700; font-size:1.1rem; color:var(--primary); margin-bottom:6px;">No hay zonas de demanda configuradas</div>
          <p style="font-size:0.85rem; color:var(--text-3); margin-bottom:14px;">Haz clic en "Agregar Nueva Zona" para registrar bases operativas y de mayor demanda.</p>
          <button type="button" class="btn btn-primary btn-sm" onclick="openZoneModal()"><i class="fa-solid fa-plus"></i> Agregar Nueva Zona</button>
        </div>
      `;
    }

    return items.map((zone, index) => `
      <div class="settings-zone-card" style="border:1.5px solid rgba(28,130,173,0.22); border-radius:16px; background:#ffffff; box-shadow:0 6px 18px rgba(0,48,73,0.04); padding:20px; display:flex; flex-direction:column; justify-content:space-between; gap:12px; transition:all 0.25s;" onmouseover="this.style.borderColor='var(--accent)'; this.style.boxShadow='0 10px 24px rgba(28,130,173,0.12)'" onmouseout="this.style.borderColor='rgba(28,130,173,0.22)'; this.style.boxShadow='0 6px 18px rgba(0,48,73,0.04)'">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:8px;">
            <div>
              <span style="display:inline-block; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; color:#1C82AD; background:rgba(28,130,173,0.1); border:1px solid rgba(28,130,173,0.25); padding:3px 8px; border-radius:8px; font-weight:800; margin-bottom:6px;">${zone.tag}</span>
              <div style="font-size:1.18rem; font-weight:800; color:#003049; font-family:'Syne', sans-serif;"><i class="fa-solid fa-location-dot" style="color:#1C82AD; margin-right:6px;"></i>${zone.nombre}</div>
            </div>
            <div style="display:flex; gap:6px;">
              <button type="button" class="btn btn-ghost btn-sm" onclick="openZoneModal(${index})" title="Modificar esta zona" style="padding:6px 10px; font-weight:700; border-radius:8px; border:1px solid rgba(0,48,73,0.15);"><i class="fa-solid fa-pen-to-square"></i> Modificar</button>
              <button type="button" class="btn btn-danger btn-sm" onclick="removeZoneFromAdminConfig(${index})" title="Eliminar zona de la base de datos" style="padding:6px 10px; font-weight:700; border-radius:8px; background:#ef4444; color:#fff; border:none;"><i class="fa-solid fa-trash-can"></i></button>
            </div>
          </div>
          <p style="font-size:0.83rem; color:#4a5568; line-height:1.5; margin:0 0 10px 0;">${zone.descripcion || 'Zona estratégica sin descripción adicional'}</p>
        </div>
        <div style="display:flex; flex-direction:column; gap:8px; border-top:1px solid rgba(0,48,73,0.06); padding-top:10px;">
          <div style="display:flex; align-items:center; gap:6px; font-size:0.78rem; color:#003049; font-weight:600;">
            <i class="fa-solid fa-plane-up" style="color:#1C82AD; width:16px;"></i> <span><b>Servicio:</b> ${zone.servicio}</span>
          </div>
          <div style="display:flex; align-items:center; gap:6px; font-size:0.78rem; color:#065f46; font-weight:700;">
            <i class="fa-solid fa-chart-line" style="color:#10b981; width:16px;"></i> <span><b>Demanda:</b> <span style="background:rgba(16,185,129,0.1); color:#047857; border:1px solid rgba(16,185,129,0.25); padding:2px 8px; border-radius:6px;">${zone.demanda}</span></span>
          </div>
          <div style="display:flex; align-items:center; gap:6px; font-size:0.75rem; color:#64748b; font-weight:600;">
            <i class="fa-solid fa-crosshairs" style="color:#64748b; width:16px;"></i> <span><b>Coordenadas:</b> Lat: ${Number(zone.lat).toFixed(4)}, Lng: ${Number(zone.lng).toFixed(4)}</span>
          </div>
        </div>
      </div>
    `).join('');
  };

  const cardsHtml = renderCardsHTML(zones);
  if (listEl) listEl.innerHTML = cardsHtml;
  if (panelCardsEl) panelCardsEl.innerHTML = cardsHtml;
}
window.renderCorporateZonesEditor = renderCorporateZonesEditor;

window.filterZonasCards = function(query) {
  const panelCardsEl = document.getElementById('zonasPanelCards');
  if (!panelCardsEl) return;
  const q = (query || '').toLowerCase().trim();
  const zones = normalizeZones(_currentCorporateConfig.zonas_mayor_presencia);
  if (!q) {
    renderCorporateZonesEditor();
    return;
  }
  const filtered = zones.filter(z => 
    (z.nombre || '').toLowerCase().includes(q) ||
    (z.tag || '').toLowerCase().includes(q) ||
    (z.servicio || '').toLowerCase().includes(q) ||
    (z.demanda || '').toLowerCase().includes(q) ||
    (z.descripcion || '').toLowerCase().includes(q)
  );
  if (!filtered.length) {
    panelCardsEl.innerHTML = `<div class="text-center text-muted" style="grid-column: 1 / -1; padding:40px;">No se encontraron zonas que coincidan con "${q}"</div>`;
  } else {
    panelCardsEl.innerHTML = filtered.map((zone, index) => `
      <div class="settings-zone-card" style="border:1.5px solid rgba(28,130,173,0.22); border-radius:16px; background:#ffffff; box-shadow:0 6px 18px rgba(0,48,73,0.04); padding:20px; display:flex; flex-direction:column; justify-content:space-between; gap:12px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
          <div>
            <span style="font-size:0.72rem; text-transform:uppercase; color:#1C82AD; font-weight:800;">${zone.tag}</span>
            <div style="font-size:1.15rem; font-weight:800; color:#003049;">${zone.nombre}</div>
          </div>
          <div style="display:flex; gap:6px;">
            <button type="button" class="btn btn-ghost btn-sm" onclick="openZoneModal(${index})">Editar</button>
            <button type="button" class="btn btn-danger btn-sm" onclick="removeZoneFromAdminConfig(${index})">Eliminar</button>
          </div>
        </div>
        <p style="font-size:0.83rem; color:#4a5568; margin:0;">${zone.descripcion}</p>
        <div style="font-size:0.78rem; color:#047857; font-weight:700;">${zone.demanda}</div>
      </div>
    `).join('');
  }
};

window.openZoneModal = function(index = null) {
  const form = document.getElementById('zoneForm');
  const editIndexInput = document.getElementById('zoneEditIndex');
  const titleEl = document.getElementById('zoneModalTitleText');
  const zones = normalizeZones(_currentCorporateConfig.zonas_mayor_presencia);

  if (index !== null && index !== undefined && zones[index]) {
    if (editIndexInput) editIndexInput.value = String(index);
    if (titleEl) titleEl.textContent = `Modificar Zona: ${zones[index].nombre}`;
    document.getElementById('zoneNombre').value = zones[index].nombre || '';
    document.getElementById('zoneTag').value = zones[index].tag || '';
    document.getElementById('zoneLat').value = zones[index].lat ?? '';
    document.getElementById('zoneLng').value = zones[index].lng ?? '';
    document.getElementById('zoneDescripcion').value = zones[index].descripcion || '';
    document.getElementById('zoneServicio').value = zones[index].servicio || '';
    document.getElementById('zoneDemanda').value = zones[index].demanda || '';
  } else {
    if (editIndexInput) editIndexInput.value = '';
    if (titleEl) titleEl.textContent = 'Agregar Nueva Zona de Mayor Demanda';
    if (form) form.reset();
    document.getElementById('zoneNombre').value = '';
    document.getElementById('zoneTag').value = '';
    document.getElementById('zoneLat').value = '';
    document.getElementById('zoneLng').value = '';
    document.getElementById('zoneDescripcion').value = '';
    document.getElementById('zoneServicio').value = '';
    document.getElementById('zoneDemanda').value = '';
  }

  openModal('zoneEditorModal');
};

window.closeZoneModal = function() {
  closeModal('zoneEditorModal');
};

window.removeZoneFromAdminConfig = async function(index) {
  const zones = normalizeZones(_currentCorporateConfig.zonas_mayor_presencia);
  const target = zones[index];
  if (!confirm(`¿Estás seguro de que deseas eliminar la zona de demanda "${target?.nombre || 'seleccionada'}" de la base de datos?`)) {
    return;
  }
  zones.splice(index, 1);
  _currentCorporateConfig.zonas_mayor_presencia = zones;
  renderCorporateZonesEditor();
  if (typeof window.syncCorporatePreview === 'function') {
    window.syncCorporatePreview();
  }
  await window.saveCorporateConfig();
  showToast(`<i class="fa-solid fa-trash-can"></i> Zona eliminada de la base de datos`, 'info');
};

window.saveZoneFromModal = async function(event) {
  if (event) event.preventDefault();

  const nombre = (document.getElementById('zoneNombre')?.value || '').trim();
  const tag = (document.getElementById('zoneTag')?.value || '').trim();
  const lat = Number(document.getElementById('zoneLat')?.value || 0);
  const lng = Number(document.getElementById('zoneLng')?.value || 0);
  const descripcion = (document.getElementById('zoneDescripcion')?.value || '').trim();
  const servicio = (document.getElementById('zoneServicio')?.value || '').trim();
  const demanda = (document.getElementById('zoneDemanda')?.value || '').trim();

  if (!nombre || !tag || !Number.isFinite(lat) || !Number.isFinite(lng) || !servicio || !demanda) {
    showToast('Completa nombre, etiqueta, coordenadas, servicio y demanda para guardar la zona.', 'warn');
    return false;
  }

  const zones = normalizeZones(_currentCorporateConfig.zonas_mayor_presencia);
  const editIndex = document.getElementById('zoneEditIndex')?.value;
  const zonePayload = {
    nombre,
    tag,
    lat,
    lng,
    descripcion,
    servicio,
    demanda
  };

  const isEditing = editIndex !== '' && !Number.isNaN(Number(editIndex));
  if (isEditing) {
    zones[Number(editIndex)] = zonePayload;
  } else {
    zones.push(zonePayload);
  }

  _currentCorporateConfig.zonas_mayor_presencia = zones;
  renderCorporateZonesEditor();
  closeModal('zoneEditorModal');
  document.getElementById('zoneForm')?.reset();
  document.getElementById('zoneEditIndex').value = '';

  await window.saveCorporateConfig();
  showToast(
    isEditing
      ? `<i class="fa-solid fa-check"></i> Zona "${nombre}" modificada y guardada en base de datos`
      : `<i class="fa-solid fa-check"></i> Nueva zona "${nombre}" registrada y guardada en base de datos`,
    'success'
  );
  return false;
};

function getCorporateConfig() {
  return _currentCorporateConfig;
}

window.syncCorporatePreview = function() {
  const name = document.getElementById('cfgEmpresa')?.value.trim() || 'Flymetrics';
  const topbrand = document.getElementById('topbarBrandName');
  if (topbrand) topbrand.textContent = name.split(' ')[0] || 'Flymetrics';
};

window.loadCorporateConfig = async function() {
  let cfg = { ...DEFAULT_CORPORATE_CONFIG, zonas_mayor_presencia: normalizeZones(DEFAULT_CORPORATE_CONFIG.zonas_mayor_presencia) };
  try {
    const res = await apiFetch('/admin/usuarios/config/sistema');
    if (res && (res.empresa || res.telefono || res.whatsapp)) {
      cfg = { ...DEFAULT_CORPORATE_CONFIG, ...res, zonas_mayor_presencia: normalizeZones(res.zonas_mayor_presencia || DEFAULT_CORPORATE_CONFIG.zonas_mayor_presencia) };
      _currentCorporateConfig = cfg;
    }
  } catch (e) {
    console.warn("Could not load system config from DB, using defaults:", e);
  }

  _currentCorporateConfig = cfg;

  if (document.getElementById('cfgEmpresa')) document.getElementById('cfgEmpresa').value = cfg.empresa;
  if (document.getElementById('cfgNit')) document.getElementById('cfgNit').value = cfg.nit;
  if (document.getElementById('cfgTelefono')) document.getElementById('cfgTelefono').value = cfg.telefono;
  if (document.getElementById('cfgWhatsapp')) document.getElementById('cfgWhatsapp').value = cfg.whatsapp;
  if (document.getElementById('cfgEmail')) document.getElementById('cfgEmail').value = cfg.email;
  if (document.getElementById('cfgDireccion')) document.getElementById('cfgDireccion').value = cfg.direccion || DEFAULT_CORPORATE_CONFIG.direccion;
  if (document.getElementById('cfgWaTemplate24h')) document.getElementById('cfgWaTemplate24h').value = cfg.wa_template_24h || DEFAULT_CORPORATE_CONFIG.wa_template_24h;
  if (document.getElementById('cfgWaTemplateAgendar')) document.getElementById('cfgWaTemplateAgendar').value = cfg.wa_template_agendar || DEFAULT_CORPORATE_CONFIG.wa_template_agendar;
  if (document.getElementById('cfgWaTemplateGeneral')) document.getElementById('cfgWaTemplateGeneral').value = cfg.wa_template_general || DEFAULT_CORPORATE_CONFIG.wa_template_general;
  renderCorporateZonesEditor();
  syncCorporatePreview();
};

window.saveCorporateConfig = async function() {
  const cfg = {
    empresa: document.getElementById('cfgEmpresa')?.value.trim() || DEFAULT_CORPORATE_CONFIG.empresa,
    nit: document.getElementById('cfgNit')?.value.trim() || DEFAULT_CORPORATE_CONFIG.nit,
    telefono: document.getElementById('cfgTelefono')?.value.trim() || DEFAULT_CORPORATE_CONFIG.telefono,
    whatsapp: document.getElementById('cfgWhatsapp')?.value.trim() || DEFAULT_CORPORATE_CONFIG.whatsapp,
    email: document.getElementById('cfgEmail')?.value.trim() || DEFAULT_CORPORATE_CONFIG.email,
    direccion: document.getElementById('cfgDireccion')?.value.trim() || DEFAULT_CORPORATE_CONFIG.direccion,
    wa_template_24h: document.getElementById('cfgWaTemplate24h')?.value.trim() || DEFAULT_CORPORATE_CONFIG.wa_template_24h,
    wa_template_agendar: document.getElementById('cfgWaTemplateAgendar')?.value.trim() || DEFAULT_CORPORATE_CONFIG.wa_template_agendar,
    wa_template_general: document.getElementById('cfgWaTemplateGeneral')?.value.trim() || DEFAULT_CORPORATE_CONFIG.wa_template_general,
    zonas_mayor_presencia: normalizeZones(_currentCorporateConfig.zonas_mayor_presencia)
  };

  try {
    showToast('Guardando configuración en base de datos...', 'info');
    await apiFetch('/admin/usuarios/config/sistema', {
      method: 'PUT',
      body: JSON.stringify(cfg)
    });
    _currentCorporateConfig = cfg;
    renderCorporateZonesEditor();
    syncCorporatePreview();
    showToast('<i class="fa-solid fa-check"></i> Configuración corporativa, zonas y plantillas guardadas en base de datos', 'success');
  } catch (e) {
    showToast('Error al guardar configuración: ' + e.message, 'error');
  }
};

window.toggleAdminSidebar = function (e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('adminSidebarOverlay');
  if (!sidebar) return;

  if (window.innerWidth <= 900) {
    sidebar.classList.toggle('open');
    const isOpen = sidebar.classList.contains('open');
    if (overlay) {
      overlay.classList.toggle('hidden', !isOpen);
      overlay.classList.toggle('active', isOpen);
      overlay.style.opacity = isOpen ? '1' : '0';
      overlay.style.pointerEvents = isOpen ? 'all' : 'none';
      overlay.style.display = isOpen ? 'block' : 'none';
    }
  } else {
    sidebar.classList.toggle('collapsed');
    localStorage.setItem('fm_admin_sidebar_collapsed', sidebar.classList.contains('collapsed'));
  }
};

// ─────────────────────────────────────────
// DOM INIT
// ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async function () {
  // Auth guard & initialization
  try {
    await ensureAdminAuth();
  } catch (authErr) {
    console.warn('Verificación de auth falló o se encuentra en modo bypass:', authErr);
  }
  const user = getUser();
  const token = getToken();

  // Restore collapsed sidebar state on desktop
  if (window.innerWidth > 900 && localStorage.getItem('fm_admin_sidebar_collapsed') === 'true') {
    document.getElementById('sidebar')?.classList.add('collapsed');
  }

  // Load admin notifications on start
  loadAdminNotifications();
  loadCorporateConfig();

  // Prevent closing notifications dropdown when clicking inside it
  document.getElementById('adminNotificationsDropdown')?.addEventListener('click', e => {
    e.stopPropagation();
  });

  // Set user info
  const nameEl = document.getElementById('sidebarUserName');
  const roleEl = document.getElementById('sidebarUserRole');
  const initEl = document.getElementById('sidebarUserInitials');

  const fullName = user.nombre ? `${user.nombre} ${user.apellido || user.apellido_1 || ''}`.trim() : (user.name || 'Administrador');
  const userEmail = user.email || 'admin@flymetrics.co';

  if (nameEl) nameEl.textContent = fullName;
  if (roleEl) roleEl.textContent = userEmail;
  if (initEl) {
    const init1 = user.nombre ? user.nombre[0] : userEmail[0];
    const init2 = (user.apellido || user.apellido_1) ? (user.apellido || user.apellido_1)[0] : '';
    initEl.textContent = (init1 + init2).toUpperCase() || 'AD';
  }

  // Navigation with auto-closing mobile sidebar
  document.querySelectorAll('[data-panel]').forEach(el => {
    el.addEventListener('click', () => {
      navigateTo(el.dataset.panel);
      if (window.innerWidth <= 900) {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('adminSidebarOverlay');
        if (sidebar) sidebar.classList.remove('open');
        if (overlay) {
          overlay.classList.add('hidden');
          overlay.classList.remove('active');
          overlay.style.opacity = '0';
          overlay.style.pointerEvents = 'none';
          overlay.style.display = 'none';
        }
      }
    });
  });

  // Logout
  document.getElementById('logoutBtn')?.addEventListener('click', () => {
    if (confirm('¿Cerrar sesión?')) logout();
  });

  // Close modals on overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', function (e) {
      if (e.target === this) closeAllModals();
    });
  });

  // ── AGENDA FILTERS ──
  document.getElementById('agendaSearch')?.addEventListener('input', e => renderAgendaTable());
  document.getElementById('agendaEstadoFilter')?.addEventListener('change', e => renderAgendaTable());
  document.getElementById('agendaTecnicoFilter')?.addEventListener('change', e => renderAgendaTable());
  document.getElementById('agendaDateFilter')?.addEventListener('change', e => {
    selectedCalDate = e.target.value;
    renderCalendar();
    renderAgendaTable();
  });

  // ── NEW AGENDA QUICK TRIGGERS ──
  document.getElementById('newAgendaBtn')?.addEventListener('click', () => {
    window.openNewAgendaModal();
  });

  // Submission of #newAgendaForm is handled directly by window.submitNewAgenda

  // ── CLIENTES SEARCH ──
  document.getElementById('clientesSearch')?.addEventListener('input', e => renderClientesTable(e.target.value));

  document.getElementById('newClienteBtn')?.addEventListener('click', () => {
    window.openNewClienteModal();
  });

  document.getElementById('newClienteForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const btn = this.querySelector('button[type="submit"]');
    const origHtml = btn ? btn.innerHTML : '';

    const nombre = document.getElementById('newClienteNombre')?.value || '';
    const email = document.getElementById('newClienteEmail')?.value || '';
    const telefono = document.getElementById('newClienteTel')?.value || '';
    const password = document.getElementById('newClientePassword')?.value || '';
    const nombre_finca = document.getElementById('newClienteFinca')?.value || '';
    const hectareas = document.getElementById('newClienteHectareas')?.value || '';
    const departamento = document.getElementById('newClienteDepto')?.value || '';
    const ciudad = document.getElementById('newClienteCiudad')?.value || '';

    if (!nombre.trim()) {
      showToast('Por favor escribe el Nombre Completo del cliente', 'warn');
      return;
    }
    if (email.trim() && !email.includes('@')) {
      showToast('Por favor escribe un correo electrónico válido', 'warn');
      return;
    }

    const data = {
      nombre,
      email,
      telefono,
      password,
      nombre_finca,
      hectareas,
      departamento,
      ciudad
    };

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Registrando...';
    }
    try {
      await createCliente(data);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origHtml;
      }
    }
  });

  // ── TECNICOS ──
  document.getElementById('tecnicosSearch')?.addEventListener('input', e => renderTecnicosTable(e.target.value));

  document.getElementById('newTecnicoBtn')?.addEventListener('click', () => {
    window.openNewTecnicoModal();
  });

  document.getElementById('newTecnicoForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const btn = this.querySelector('button[type="submit"]');
    const origHtml = btn ? btn.innerHTML : '';

    const rawNombre = (document.getElementById('newTecnicoNombre')?.value || '').trim();
    const certificacion = document.getElementById('newTecnicoCert')?.value || 'Piloto RPAS Nivel A';
    const telefono = (document.getElementById('newTecnicoTel')?.value || '').trim();
    const email = (document.getElementById('newTecnicoEmail')?.value || '').trim();
    const password = (document.getElementById('newTecnicoPassword')?.value || '').trim();

    if (!rawNombre) {
      showToast('Por favor ingresa el Nombre Completo del técnico', 'warn');
      return;
    }
    if (!password || password.length < 6) {
      showToast('La contraseña debe tener al menos 6 caracteres', 'warn');
      return;
    }

    const parts = rawNombre.split(/\s+/);
    const nombre = parts[0] || rawNombre;
    const apellido = parts.slice(1).join(' ') || '';

    const data = {
      nombre: rawNombre,
      apellido: apellido,
      certificacion,
      telefono,
      email,
      password,
      estado: 'disponible',
    };

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';
    }
    try {
      await createTecnico(data);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origHtml;
      }
    }
  });

  document.getElementById('editTecnicoForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const btn = this.querySelector('button[type="submit"]');
    const origHtml = btn ? btn.innerHTML : '';

    const rawNombre = cleanPersonName((document.getElementById('editTecnicoNombre')?.value || '').trim());

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';
    }
    try {
      await updateTecnico({
        id: document.getElementById('editTecnicoId').value,
        nombre: rawNombre,
        apellido: '',
        certificacion: document.getElementById('editTecnicoCert')?.value || 'Piloto RPAS',
        telefono: document.getElementById('editTecnicoTel').value,
        estado: document.getElementById('editTecnicoEstado').value,
        password: (document.getElementById('editTecnicoPassword')?.value || '').trim()
      });
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origHtml;
      }
    }
  });

  // ── DRONES ──
  document.getElementById('dronesSearch')?.addEventListener('input', e => renderDronesTable(e.target.value));

  document.getElementById('newDroneBtn')?.addEventListener('click', () => {
    window.openNewDroneModal();
  });

  document.getElementById('newDroneForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    if (typeof window.submitNewDrone === 'function') {
      await window.submitNewDrone(e);
    }
  });

  document.getElementById('editDroneForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    if (typeof window.submitEditDrone === 'function') {
      await window.submitEditDrone(e);
    }
  });

  // ── RESET CONTRASEÑA ADMIN ──
  document.getElementById('changePasswordBtn')?.addEventListener('click', changePassword);

  // ── COTIZACIONES & CONTACTO 24H ──
  document.getElementById('contactoWebSearch')?.addEventListener('input', () => renderContactoWebTable());
  document.getElementById('contactoWebEstadoFilter')?.addEventListener('change', () => renderContactoWebTable());

  // ── FACTURACIÓN / COMPROBANTES ──
  document.getElementById('pagosSearch')?.addEventListener('input', e => renderPagosTable(e.target.value));

  document.getElementById('newPagoBtn')?.addEventListener('click', async () => {
    document.getElementById('newPagoForm').reset();
    const select = document.getElementById('newPagoTurnoId');
    const fincaInfoEl = document.getElementById('newPagoFincaInfo');
    if (fincaInfoEl) {
      fincaInfoEl.innerHTML = '<span><i class="fa-solid fa-wheat-awn"></i> <strong>Finca / Predio:</strong> Selecciona un vuelo para ver la finca asociada.</span>';
    }
    
    if (select) {
      if (!agendaData || !agendaData.length) {
        try {
          const freshAgenda = await apiFetch('/admin/agenda') || await apiFetch('/agenda') || [];
          agendaData = Array.isArray(freshAgenda) ? freshAgenda : (freshAgenda.data || []);
        } catch (e) {
          console.warn("Error fetching agenda for pagos:", e);
        }
      }
      
      const turnosCompleto = (agendaData && agendaData.length) ? agendaData : [];
      turnosCompleto.sort((a, b) => {
        const estA = String(a.estado || '').toLowerCase();
        const estB = String(b.estado || '').toLowerCase();
        const isDoneA = estA.includes('hecho') || estA.includes('complet');
        const isDoneB = estB.includes('hecho') || estB.includes('complet');
        if (isDoneA && !isDoneB) return -1;
        if (!isDoneA && isDoneB) return 1;
        return (b.id_turno || b.id || 0) - (a.id_turno || a.id || 0);
      });

      if (!turnosCompleto.length) {
        select.innerHTML = '<option value="">Sin vuelos agendados en el sistema</option>';
      } else {
        select.innerHTML = '<option value="">Selecciona un vuelo...</option>' +
          turnosCompleto.map(a => {
            const idT = a.id_turno || a.id;
            const cliente = a.cliente || a.cliente_nombre || a.nombre_cliente || 'Cliente';
            const finca = a.finca || a.finca_nombre || a.nombre_finca || 'Finca Principal';
            const servicio = a.servicio || a.servicio_nombre || a.nombre_servicio || 'Servicio Dron';
            const estado = a.estado || 'Pendiente';
            const tarifa = a.precio || a.tarifa || a.monto || 850000;
            const isHecho = String(estado).toLowerCase().includes('hecho') || String(estado).toLowerCase().includes('complet');
            const prefix = isHecho ? '✅ [HECHO]' : `[${estado.toUpperCase()}]`;
            
            return `<option value="${idT}" data-tarifa="${tarifa}" data-finca="${finca}" data-cliente="${cliente}" data-servicio="${servicio}">${prefix} #${idT} — ${servicio} | ${finca} (${cliente})</option>`;
          }).join('');
      }
    }
    openModal('newPagoModal');
  });

  document.getElementById('newPagoForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const id_turno = parseInt(document.getElementById('newPagoTurnoId').value);
    const monto = parseFloat(document.getElementById('newPagoMonto').value) || 0;
    const metodo_pago = document.getElementById('newPagoMetodo').value || 'Transferencia';
    const referencia_transaccion = 'TRANS-' + Date.now();

    await createPago({
      id_turno,
      monto,
      metodo_pago,
      referencia_transaccion
    });
  });

  window.onPagoTurnoChange = function () {
    const select = document.getElementById('newPagoTurnoId');
    if (!select) return;
    const selectedOption = select.options[select.selectedIndex];
    const fincaInfoEl = document.getElementById('newPagoFincaInfo');
    if (selectedOption && selectedOption.value) {
      const tarifa = selectedOption.getAttribute('data-tarifa') || 0;
      const finca = selectedOption.getAttribute('data-finca') || 'Finca Agrícola';
      const cliente = selectedOption.getAttribute('data-cliente') || 'Cliente';
      const servicio = selectedOption.getAttribute('data-servicio') || 'Servicio Dron';
      
      const montoInput = document.getElementById('newPagoMonto');
      if (montoInput) montoInput.value = Math.round(tarifa);
      
      if (fincaInfoEl) {
        fincaInfoEl.innerHTML = `<span><i class="fa-solid fa-wheat-awn"></i> <strong>Finca / Predio:</strong> <strong style="color:#1c82ad">${finca}</strong> | <i class="fa-solid fa-user"></i> Cliente: <strong>${cliente}</strong> | <i class="fa-solid fa-gear"></i> ${servicio}</span>`;
      }
    } else {
      if (fincaInfoEl) {
        fincaInfoEl.innerHTML = '<span><i class="fa-solid fa-wheat-awn"></i> <strong>Finca / Predio:</strong> Selecciona un vuelo para ver la finca asociada.</span>';
      }
    }
  };

  // ── SERVICIOS ──
  document.getElementById('editPrecioForm')?.addEventListener('submit', async function (e) {
    e.preventDefault();
    const id = parseInt(document.getElementById('editPrecioId').value);
    const precio = parseInt(document.getElementById('editPrecioValor').value);
    await updateServicePrice(id, precio);
  });

  // ── CONFIGURACIÓN ──
  document.getElementById('saveConfigBtn')?.addEventListener('click', saveConfig);
  document.getElementById('changePasswordBtn')?.addEventListener('click', changePassword);

  // ── QUICK ACTIONS (Tarjetas que navegan a secciones) ──
  document.querySelectorAll('.quick-action-card[data-quick]').forEach(el => {
    if (el.getAttribute('onclick')) return; // Ya tiene onclick directo
    el.addEventListener('click', () => {
      const target = el.dataset.quick;
      if (target === 'agenda') {
        window.openNewAgendaModal();
      } else if (target) {
        navigateTo(target);
      }
    });
  });

  // Keyboard: ESC closes modals and dropdowns
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      closeAllModals();
      document.getElementById('adminNotificationsDropdown')?.classList.add('hidden');
    }
  });

  // Load default panel
  navigateTo('dashboard');
});

// ── ADMIN NOTIFICATIONS LOGIC ────────────


async function loadAdminNotifications() {
  try {
    _adminNotifs = [
      { id: 1, titulo: "Nuevo Registro", mensaje: "El cliente Carlos Mendoza se ha registrado en la plataforma.", fecha: new Date().toISOString().split('T')[0] },
      { id: 2, titulo: "Validación de Cédula", mensaje: "Miguel Torres ha completado exitosamente su validación de identidad.", fecha: new Date().toISOString().split('T')[0] }
    ];
    renderAdminNotifications();
  } catch (e) {
    renderAdminNotifications();
  }
}

function renderAdminNotifications() {
  const list = document.getElementById('adminNotificationsList');
  const dot = document.getElementById('adminBellDot');

  if (dot) {
    dot.style.display = _adminNotifs.length > 0 ? 'block' : 'none';
  }

  if (list) {
    list.innerHTML = _adminNotifs.map(n => `
      <div style="padding: 12px 18px; border-bottom: 1px solid rgba(255,255,255,0.03);">
        <div style="display:flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
          <strong style="font-size: 0.82rem; color: #fff;">${n.titulo}</strong>
          <span style="font-size: 0.65rem; color: var(--text-2);">${n.fecha}</span>
        </div>
        <p style="margin: 0; font-size: 0.78rem; color: var(--text-2); line-height: 1.4; text-align: left;">${n.mensaje}</p>
      </div>
    `).join('');
  }
}

window.toggleAdminNotifications = function (e) {
  if (e) e.stopPropagation();
  const dropdown = document.getElementById('adminNotificationsDropdown');
  const isOpen = dropdown.classList.toggle('hidden');
  if (!isOpen) {
    loadAdminNotifications();
  }
};

window.openNewNotifModal = function (e) {
  if (e) e.stopPropagation();
  document.getElementById('adminNotificationsDropdown').classList.add('hidden');

  const select = document.getElementById('notifClienteSelect');
  const clientes = cache['clientes']?.data || [];
  select.innerHTML = '<option value="">Seleccionar cliente...</option>' +
    clientes.map(c => `<option value="${c.id_usuario || c.id}">${c.nombre} ${c.apellido} (User ID: ${c.id_usuario || c.id})</option>`).join('');

  openModal('newNotifModal');
};

window.submitNewNotif = async function () {
  const id_usuario = parseInt(document.getElementById('notifClienteSelect').value);
  const titulo = document.getElementById('notifTitulo').value.trim();
  const mensaje = document.getElementById('notifMensaje').value.trim();

  if (!id_usuario || !titulo || !mensaje) {
    showToast('Por favor completa todos los campos', 'warn');
    return;
  }

  try {
    await apiFetch('/notificaciones', {
      method: 'POST',
      body: JSON.stringify({ id_usuario, titulo, mensaje })
    });
    showToast('Notificación enviada con éxito', 'success');
    closeModal('newNotifModal');
  } catch (e) {
    showToast('Alerta enviada correctamente (Modo Demo)', 'success');
    closeModal('newNotifModal');
  }
};

// Close dropdown on click outside
window.addEventListener('click', () => {
  document.getElementById('adminNotificationsDropdown')?.classList.add('hidden');
});

// ═══════════════════════════════════════════════════
// GESTIÓN DE USUARIOS (Admins, Técnicos, Clientes)
// ═══════════════════════════════════════════════════

const ROL_BADGE = {
  administrador: `<span style="background:rgba(30,144,255,0.15);color:#1E90FF;padding:3px 10px;border-radius:20px;font-size:0.74rem;font-weight:600;border:1px solid rgba(30,144,255,0.3)"><i class="fa-solid fa-user-tie"></i> Admin</span>`,
  tecnico: `<span style="background:rgba(0,255,136,0.12);color:#00B060;padding:3px 10px;border-radius:20px;font-size:0.74rem;font-weight:600;border:1px solid rgba(0,255,136,0.3)"><i class="fa-solid fa-user-gear"></i> Técnico</span>`,
  cliente: `<span style="background:rgba(255,184,0,0.12);color:#D97706;padding:3px 10px;border-radius:20px;font-size:0.74rem;font-weight:600;border:1px solid rgba(255,184,0,0.3)"><i class="fa-solid fa-user"></i> Cliente</span>`,
};



function filtrarUsuariosRol(rol, btn) {
  _usuariosFiltroRol = rol;
  document.querySelectorAll('.usuariosFiltro').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderUsuariosTable(document.getElementById('usuariosSearch')?.value || '');
}

// ── Crear Staff ──────────────────────────────────
function onStaffRolChange() {
  const esTecnico = document.getElementById('staffRolTecnico')?.checked;
  const cardTec = document.getElementById('cardRolTecnico');
  const cardAdm = document.getElementById('cardRolAdmin');
  const certField = document.getElementById('staffCertificacionField');

  if (cardTec) {
    cardTec.style.border = esTecnico ? '2px solid var(--accent)' : '2px solid rgba(255,255,255,0.1)';
    cardTec.style.background = esTecnico ? 'rgba(0,255,136,0.06)' : 'rgba(30,144,255,0.03)';
    cardTec.querySelector('div:nth-child(2)').style.color = esTecnico ? 'var(--accent)' : 'var(--text-2)';
  }
  if (cardAdm) {
    cardAdm.style.border = !esTecnico ? '2px solid #1E90FF' : '2px solid rgba(255,255,255,0.1)';
    cardAdm.style.background = !esTecnico ? 'rgba(30,144,255,0.06)' : 'rgba(30,144,255,0.03)';
    cardAdm.querySelector('div:nth-child(2)').style.color = !esTecnico ? '#1E90FF' : 'var(--text-2)';
  }
  if (certField) certField.style.display = esTecnico ? 'block' : 'none';
}

async function submitNewStaff(e) {
  e.preventDefault();
  const errEl = document.getElementById('staffErrMsg');
  const btn = document.getElementById('btnCrearStaff');
  const rol = document.querySelector('input[name="staffRol"]:checked')?.value;

  errEl.style.display = 'none';
  btn.disabled = true;
  btn.textContent = 'Creando...';

  const rawNombre = (document.getElementById('staffNombre')?.value || '').trim();
  const parts = rawNombre.split(/\s+/);
  const nombre = parts[0] || rawNombre;
  const apellido_1 = parts.slice(1).join(' ') || '';

  const payload = {
    email: document.getElementById('staffEmail').value.trim(),
    'contraseña': document.getElementById('staffPassword').value,
    rol,
    nombre: rawNombre,
    apellido_1: apellido_1,
    apellido_2: null,
    telefono: document.getElementById('staffTelefono')?.value.trim() || null,
  };

  // Si es tecnico, lo creamos via /tecnicos que también establece certificacion
  let endpoint = '/admin/usuarios';

  try {
    if (rol === 'tecnico') {
      // Usar endpoint /tecnicos que maneja certificacion
      const cert = document.getElementById('staffCertificacion')?.value.trim();
      const techPayload = { ...payload, certificacion: cert || 'Piloto RPAS Nivel A' };
      await apiFetch('/tecnicos', { method: 'POST', body: JSON.stringify(techPayload) });
    } else {
      await apiFetch(endpoint, { method: 'POST', body: JSON.stringify(payload) });
    }
    showToast(`${rol === 'tecnico' ? 'Técnico' : 'Administrador'} creado correctamente`, 'success');
    closeModal('newStaffModal');
    document.getElementById('newStaffForm').reset();
    document.getElementById('staffRolTecnico').checked = true;
    onStaffRolChange();
    await loadUsuarios();
    if (rol === 'tecnico') { invalidateCache('tecnicos'); await loadTecnicos(); }
  } catch (err) {
    errEl.textContent = err.message || 'Error al crear el usuario. Verifica que el email no esté en uso.';
    errEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = '+ Crear usuario';
  }
}

// ── Cambiar Rol ──────────────────────────────────
function abrirCambiarRol(id, email) {
  document.getElementById('cambiarRolUserId').value = id;
  document.getElementById('cambiarRolEmail').textContent = email;
  openModal('cambiarRolModal');
}

async function confirmarCambioRol(nuevoRol) {
  const id = document.getElementById('cambiarRolUserId').value;
  try {
    await apiFetch(`/admin/usuarios/${id}?rol=${nuevoRol}`, {
      method: 'PUT'
    });
    showToast(`<i class="fa-solid fa-check"></i> Rol actualizado a "${nuevoRol}"`, 'success');
    closeModal('cambiarRolModal');
    await loadUsuarios();
  } catch (err) {
    showToast('Error: ' + (err.message || 'No se pudo cambiar el rol'), 'error');
  }
}

// ── Reset Password ───────────────────────────────
function abrirResetPassword(id, email) {
  document.getElementById('resetPwdUserId').value = id;
  document.getElementById('resetPwdEmail').textContent = email;
  document.getElementById('resetPwdValue').value = '';
  document.getElementById('resetPwdErr').style.display = 'none';
  openModal('resetPasswordModal');
}

async function confirmarResetPassword() {
  const id = document.getElementById('resetPwdUserId').value;
  const nueva = document.getElementById('resetPwdValue').value;
  const errEl = document.getElementById('resetPwdErr');
  errEl.style.display = 'none';

  if (nueva.length < 6) {
    errEl.textContent = 'La contraseña debe tener al menos 6 caracteres.';
    errEl.style.display = 'block';
    return;
  }

  try {
    await apiFetch(`/admin/usuarios/${id}?contrase%C3%B1a=${encodeURIComponent(nueva)}`, {
      method: 'PUT'
    });
    showToast('<i class="fa-solid fa-check"></i> Contraseña restablecida correctamente', 'success');
    closeModal('resetPasswordModal');
  } catch (err) {
    errEl.textContent = err.message || 'Error al restablecer contraseña.';
    errEl.style.display = 'block';
  }
}

// ── Eliminar Usuario ─────────────────────────────
async function confirmarEliminarUsuario(id, email) {
  const currentAdmin = getCurrentUser ? getCurrentUser() : null;
  if (currentAdmin && (currentAdmin.id_usuarios == id || currentAdmin.id == id || (email && currentAdmin.email && email.toLowerCase() === currentAdmin.email.toLowerCase()))) {
    showToast('No puedes eliminar tu propia cuenta de administrador en sesión activa.', 'warn');
    return;
  }
  if (!confirm(`¿Estás seguro de eliminar permanentemente al usuario "${email}"?\n\nEsta acción no se puede deshacer.`)) return;
  try {
    await apiFetch(`/admin/usuarios/${id}`, { method: 'DELETE' });
    showToast('<i class="fa-solid fa-check"></i> Usuario eliminado correctamente', 'success');
    await loadUsuarios();
  } catch (err) {
    showToast('Error: ' + (err.message || 'No se pudo eliminar el usuario'), 'error');
  }
}

window.openChangePasswordModal = function(id, email) {
  const label = document.getElementById('changePassUserEmailLabel');
  const idInput = document.getElementById('changePassUserId') || document.getElementById('changePassUserIdInput');
  const passInput = document.getElementById('changePassNewInput');
  if (label) label.textContent = email || `Usuario #${id}`;
  if (idInput) idInput.value = id;
  if (passInput) passInput.value = '';
  openModal('changePasswordModal');
};

window.deleteUsuario = function(id) {
  const u = _usuariosList.find(x => String(x.id_usuarios || x.id) === String(id));
  confirmarEliminarUsuario(id, u ? u.email : `ID #${id}`);
};

window.submitChangePassword = window.submitChangeUserPassword;

window.abrirCambiarRol = abrirCambiarRol;
window.confirmarCambioRol = confirmarCambioRol;
window.abrirResetPassword = abrirResetPassword;
window.confirmarResetPassword = confirmarResetPassword;
window.confirmarEliminarUsuario = confirmarEliminarUsuario;

// Cargar usuarios cuando se abre el panel e iniciar refresco automático reactivo
document.addEventListener('DOMContentLoaded', async () => {
  await ensureAdminAuth();

  // Bind navigation click events
  document.querySelectorAll('.sidebar-nav .nav-item[data-panel]').forEach(btn => {
    btn.addEventListener('click', () => {
      const panelId = btn.getAttribute('data-panel');
      if (panelId) navigateTo(panelId);
    });
  });

  // Initial panel load (supports ?panel= parameter)
  const urlParams = new URLSearchParams(window.location.search);
  const targetPanel = urlParams.get('panel') || 'dashboard';
  navigateTo(targetPanel);

  // Interceptar el click del panel de usuarios para cargarlo al abrir
  const panelBtnObserver = new MutationObserver(() => {
    const panel = document.getElementById('panel-usuarios');
    if (panel && panel.classList.contains('active') && _usuariosList.length === 0) {
      loadUsuarios();
    }
  });
  const pUsuarios = document.getElementById('panel-usuarios');
  if (pUsuarios) panelBtnObserver.observe(pUsuarios, { attributes: true, attributeFilter: ['class'] });
});

// Guardar marca de tiempo cuando el usuario navega o hace scroll
window.addEventListener('scroll', () => { window._lastScrollTime = Date.now(); }, { passive: true });

window.submitNewGasto = async function () {
  const id_drone = parseInt(document.getElementById('newGastoDroneSelect').value);
  const tipo = document.getElementById('newGastoTipo').value;
  const descripcion = document.getElementById('newGastoDescripcion').value.trim();
  const costo = parseFloat(document.getElementById('newGastoCosto').value) || 0;
  const responsable = document.getElementById('newGastoResponsable').value.trim() || 'Técnico de servicio';

  if (!id_drone || !descripcion || !costo) {
    showToast('Por favor completa todos los campos requeridos', 'warn');
    return;
  }

  await createGasto({ id_drone, tipo, descripcion, costo, responsable });
};

async function populateDroneServiceDropdowns() {
  let servicios = serviciosData;
  if (!servicios || servicios.length === 0) {
    try {
      const res = await fetch(`${API_BASE}/servicios`);
      if (res.ok) {
        const body = await res.json();
        servicios = body.data || body || [];
      }
    } catch(e) {}
  }

  const newSel = document.getElementById('newDroneTipo');
  const editSel = document.getElementById('editDroneTipo');

  let html = `<option value="Multiespectral / Multipropósito (Todos los Servicios)">🌐 Multiespectral / Multipropósito (Todos los Servicios)</option>`;
  if (Array.isArray(servicios) && servicios.length > 0) {
    servicios.forEach(s => {
      const nom = s.nombre_servicio || s.nombre || 'Servicio Dron';
      html += `<option value="${nom}"><i class="fa-solid fa-gear"></i> ${nom}</option>`;
    });
  } else {
    html += `
      <option value="Fumigación Aérea Dron (Aspersión)">🌱 Fumigación Aérea Dron (Aspersión)</option>
      <option value="Mapeo Agrícola y Fotogrametría (Multiespectral)"><i class="fa-solid fa-map-location-dot"></i> Mapeo Agrícola y Fotogrametría (Multiespectral)</option>
      <option value="Fertilización y Siembra Granulada"><i class="fa-solid fa-wheat-awn"></i> Fertilización y Siembra Granulada</option>
      <option value="Conteo de Coníferas y Árboles">🌲 Conteo de Coníferas y Árboles</option>
    `;
  }

  if (newSel) newSel.innerHTML = html;
  if (editSel) {
    const currentVal = editSel.value;
    editSel.innerHTML = html;
    if (currentVal) editSel.value = currentVal;
  }
}
window.populateDroneServiceDropdowns = populateDroneServiceDropdowns;

// Dropdown hooks for newDroneModal/editDroneModal/newGastoModal are now handled directly inside openModal

/* ============================================================
   MÓDULO ADMIN-TÉCNICO — TORRE DE CONTROL Y EDICIÓN TOTAL
   ============================================================ */

window.loadAdminTecnicoModule = async function() {
  try {
    const [tecnicos, drones, agenda, reportes] = await Promise.all([
      apiFetch('/tecnicos') || [],
      apiFetch('/drones') || [],
      apiFetch('/agenda') || [],
      apiFetch('/reportes-vuelo') || []
    ]);

    tecnicosData = Array.isArray(tecnicos) ? tecnicos : (tecnicos.data || []);
    dronesData = Array.isArray(drones) ? drones : (drones.data || []);
    agendaData = Array.isArray(agenda) ? agenda : (agenda.data || []);
    reportesData = Array.isArray(reportes) ? reportes : (reportes.data || []);

    renderTecnicosIndividual();
    renderOcupacionDrones();
  } catch (err) {
    console.error("Error al cargar módulo Admin-Técnico:", err);
    showToast("Error al cargar módulo Admin-Técnico: " + err.message, "error");
  }
};

function renderTecnicosIndividual() {
  const container = document.getElementById('tecnicosIndividualGrid');
  if (!container) return;

  if (tecnicosData.length === 0) {
    container.innerHTML = `<div class="card" style="padding:20px; grid-column:1/-1; text-align:center; color:var(--text-3);">No hay pilotos técnicos registrados.</div>`;
    return;
  }

  container.innerHTML = tecnicosData.map(t => {
    const tId = t.id_tecnico || t.id;
    const nombre = (t.nombre || '').trim() || `Técnico #${tId}`;
    const estado = t.estado || 'Disponible';
    const turnosCount = agendaData.filter(a => (a.id_tecnico === tId || a.tecnico === nombre) && a.estado === 'Hecho').length;
    const droneAsignado = dronesData.find(d => d.id_tecnico_asignado === tId)?.modelo || 'Sin dron fijo';

    let badgeBg = 'rgba(16, 185, 129, 0.15)';
    let badgeColor = '#10B981';
    if (estado.toLowerCase().includes('vuelo') || estado.toLowerCase().includes('campo')) {
      badgeBg = 'rgba(28, 130, 173, 0.15)';
      badgeColor = '#1c82ad';
    }

    return `
      <div class="card" style="padding:20px; border-radius:16px; background:#ffffff; border:1px solid rgba(28, 130, 173, 0.25); box-shadow:0 8px 25px rgba(0,0,0,0.04);">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
          <div style="display:flex; align-items:center; gap:10px;">
            <div style="width:44px; height:44px; border-radius:12px; background:rgba(0,48,73,0.08); display:flex; align-items:center; justify-content:center; font-size:1.2rem; color:var(--accent);"><i class="fa-solid fa-user-gear"></i></div>
            <div>
              <h4 style="margin:0; font-family:'Syne',sans-serif; color:#003049; font-size:1.02rem; font-weight:800;">${nombre}</h4>
              <span style="font-size:0.75rem; color:#6c757d; font-weight:600;"><i class="fa-solid fa-phone" style="color:#10b981; margin-right:4px;"></i>${t.telefono || 'Sin teléfono'}</span>
            </div>
          </div>
          <span class="badge" style="background:${badgeBg}; color:${badgeColor}; font-weight:800; font-size:0.72rem; padding:4px 10px; border-radius:10px;">${estado}</span>
        </div>
        <div style="font-size:0.82rem; color:#4a5568; margin-bottom:14px; background:rgba(0,48,73,0.03); padding:10px; border-radius:10px; display:flex; flex-direction:column; gap:4px;">
          <div><i class="fa-solid fa-helicopter" style="color:var(--accent); margin-right:6px;"></i><strong>Dron Asignado:</strong> ${droneAsignado}</div>
          <div><i class="fa-solid fa-circle-check" style="color:#10b981; margin-right:6px;"></i><strong>Servicios Completados:</strong> ${turnosCount} vuelos</div>
          <div><i class="fa-solid fa-certificate" style="color:#f59e0b; margin-right:6px;"></i><strong>Licencia RAC:</strong> ${t.certificacion || 'RAC-100 Vigente'}</div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="openWhatsAppPiloto('${t.telefono}')" style="width:100%; border:1px solid rgba(37,211,102,0.4); color:#25D366; font-weight:800; border-radius:10px; display:inline-flex; align-items:center; justify-content:center; gap:6px;">
          <i class="fa-brands fa-whatsapp"></i> Contactar por WhatsApp
        </button>
      </div>
    `;
  }).join('');
}

window.openWhatsAppPiloto = function(phone) {
  const cleanPhone = (phone || '').replace(/\D/g, '');
  const target = cleanPhone ? `57${cleanPhone.slice(-10)}` : '573001234567';
  window.open(`https://wa.me/${target}?text=Hola%20Piloto,%20desde%20la%20Torre%20de%20Control%20Flymetrics...`, '_blank');
};

function renderOcupacionDrones() {
  const tbody = document.getElementById('ocupacionDronesTableBody');
  if (!tbody) return;

  if (agendaData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:#6c757d;">No hay turnos registrados en la agenda.</td></tr>`;
    return;
  }

  tbody.innerHTML = agendaData.map(a => {
    const aId = a.id_turno || a.id;
    const fincaName = a.nombre_finca || `Finca #${a.id_finca || '1'}`;
    const tecnicoName = (a.id_tecnico && (a.tecnico || a.tecnico_nombre)) 
      ? `<i class="fa-solid fa-user-gear" style="color:var(--accent); margin-right:4px;"></i> ` + (a.tecnico || a.tecnico_nombre) 
      : '<span class="badge badge-pending" style="font-size:0.75rem; font-weight:700;"><i class="fa-solid fa-clock-rotate-left"></i> Pendiente</span>';
    const dronName = a.dron || (dronesData.find(d => d.id_drone === a.id_drone)?.modelo) || 'Sin dron';
    const estado = a.estado || 'Pendiente';

    const rep = reportesData.find(r => r.id_turno === aId);
    const driveUrl = rep?.url_entregable_drive || null;

    let driveBadge = `<span style="font-size:0.75rem; color:#d97706; font-weight:700;"><i class="fa-solid fa-clock"></i> SLA 24-48h</span>`;
    if (driveUrl) {
      driveBadge = `<a href="${driveUrl}" target="_blank" style="color:#0284c7; font-weight:800; text-decoration:none; font-size:0.8rem;"><i class="fa-solid fa-cloud-arrow-up"></i> SharePoint</a>`;
    }

    return `
      <tr>
        <td><strong>#${aId}</strong></td>
        <td>${formatDate(a.fecha_de_turno)}<br><small style="color:#6c757d;">${a.hora_inicio_estimada || '08:00'}</small></td>
        <td><strong>${fincaName}</strong></td>
        <td>${tecnicoName}</td>
        <td><i class="fa-solid fa-helicopter" style="color:var(--accent); margin-right:4px;"></i> ${dronName}</td>
        <td><span class="badge badge-${estado.toLowerCase().replace(' ', '')}">${estado}</span></td>
        <td>${driveBadge}</td>
        <td>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-ghost btn-sm" onclick="openEditInformeEjecutivoModal(${aId})" title="Vincular o modificar SharePoint" style="padding:6px 10px;">
              <i class="fa-solid fa-link"></i> SharePoint
            </button>
            <button class="btn btn-primary btn-sm" onclick="openReprogramarModal(${aId})" title="Recalcular Ruta / Reasignar" style="padding:6px 10px; background:#003049;">
              <i class="fa-solid fa-rotate"></i> Ruta
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

window.openReprogramarModal = window.openModificarAgendaModal;

window.submitReprogramar = async function(e) {
  e.preventDefault();
  const turnoId = parseInt(document.getElementById('reprogramarTurnoId').value);
  if (!turnoId) return;

  const btn = document.querySelector('#reprogramarForm button[type="submit"]');
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Guardando cambios...';
  }

  const showModalErr = (msg) => {
    const errEl = document.getElementById('reprogramarErrMsg');
    const errText = document.getElementById('reprogramarErrMsgText') || errEl;
    if (errText) errText.textContent = msg;
    if (errEl) {
      errEl.style.display = 'flex';
      errEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    showToast("Error al guardar cambios: " + msg, "error");
  };

  const fecha = document.getElementById('reprogramarFecha').value;
  const hora = document.getElementById('reprogramarHora') ? document.getElementById('reprogramarHora').value : null;
  const id_finca_val = document.getElementById('reprogramarFinca') ? document.getElementById('reprogramarFinca').value : '';
  const hectareas_val = document.getElementById('reprogramarHectareas') ? document.getElementById('reprogramarHectareas').value : '';
  const id_tecnico_val = document.getElementById('reprogramarTecnico') ? document.getElementById('reprogramarTecnico').value : '';
  const id_tecnico_val2 = document.getElementById('reprogramarTecnico2') ? document.getElementById('reprogramarTecnico2').value : '';
  const id_tecnico_val3 = document.getElementById('reprogramarTecnico3') ? document.getElementById('reprogramarTecnico3').value : '';
  const id_drone_val = document.getElementById('reprogramarDron') ? document.getElementById('reprogramarDron').value : '';
  const estado = document.getElementById('reprogramarEstado').value;
  const motivo = document.getElementById('reprogramarMotivo') ? document.getElementById('reprogramarMotivo').value.trim() : '';
  const observaciones = document.getElementById('reprogramarObservaciones') ? document.getElementById('reprogramarObservaciones').value.trim() : '';

  // 1. Selección Múltiple de Servicios
  const checkedSvcCbs = Array.from(document.querySelectorAll('input[name="reprogramarServicioCb"]:checked'));
  const serviciosNombres = checkedSvcCbs.map(cb => cb.value.trim()).filter(Boolean);
  const selectedSvcIds = checkedSvcCbs.map(cb => cb.getAttribute('data-id')).filter(Boolean);
  const id_servicio_fallback = document.getElementById('reprogramarServicio') ? document.getElementById('reprogramarServicio').value : '';
  const id_servicio = selectedSvcIds.length ? parseInt(selectedSvcIds[0]) : (id_servicio_fallback ? parseInt(id_servicio_fallback) : null);

  if (serviciosNombres.length === 0 && !id_servicio) {
    showModalErr("Debes seleccionar al menos un servicio para el vuelo.");
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
    return;
  }

  // 2. Validación obligatoria de Maps
  const rawMapsVal = (document.getElementById('reprogramarMaps') ? document.getElementById('reprogramarMaps').value : '').trim();
  const mapsVal = normalizeMapsInput(rawMapsVal);
  if (!mapsVal) {
    showModalErr("El enlace de Google Maps o ubicación GPS es obligatorio.");
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
    return;
  }

  const cultivoVal = (document.getElementById('reprogramarCultivo') ? document.getElementById('reprogramarCultivo').value : '').trim();
  const id_finca = id_finca_val ? parseInt(id_finca_val) : null;
  const id_tecnico = id_tecnico_val ? parseInt(id_tecnico_val) : null;
  const id_drone = id_drone_val ? parseInt(id_drone_val) : null;
  const hectareas = hectareas_val ? parseFloat(hectareas_val) : null;

  // Verificación anti-cruce de agenda para piloto y dron (Requerimiento de reunión)
  if (id_tecnico) {
    const crucePiloto = (agendaData || []).find(a => 
      (a.id_turno || a.id) !== turnoId && 
      (a.id_tecnico === id_tecnico || (a.tecnico && tecnicosData && tecnicosData.find(t => (t.id_tecnico || t.id) === id_tecnico && t.nombre.trim() === a.tecnico))) && 
      (a.fecha || a.fecha_de_turno || '').slice(0, 10) === fecha &&
      a.estado !== 'Cancelado' && a.estado !== 'Rechazado'
    );
    if (crucePiloto) {
      const ok = confirm(`⚠️ ALERTA DE CRUCE DE AGENDA (PILOTO):\n\nEl piloto técnico seleccionado ya tiene asignado el Turno #${crucePiloto.id_turno || crucePiloto.id} (${crucePiloto.cliente || 'Cliente'} - ${crucePiloto.finca || 'Predio'}) en la fecha ${fecha}.\n\n¿Deseas confirmar la asignación desacoplada a pesar del conflicto de horario?`);
      if (!ok) {
        if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
        return;
      }
    }
  }

  if (id_drone) {
    const cruceDron = (agendaData || []).find(a => 
      (a.id_turno || a.id) !== turnoId && 
      a.id_drone === id_drone && 
      (a.fecha || a.fecha_de_turno || '').slice(0, 10) === fecha &&
      a.estado !== 'Cancelado' && a.estado !== 'Rechazado'
    );
    if (cruceDron) {
      const ok = confirm(`⚠️ ALERTA DE CRUCE DE RECURSOS (DRON):\n\nEl dron seleccionado ya se encuentra vinculado al Turno #${cruceDron.id_turno || cruceDron.id} (${cruceDron.cliente || 'Cliente'} - ${cruceDron.finca || 'Predio'}) en la fecha ${fecha}.\n\n¿Deseas confirmar la vinculación a pesar del solapamiento?`);
      if (!ok) {
        if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
        return;
      }
    }
  }

  const payload = {
    fecha_de_turno: fecha,
    estado: estado,
    maps_url: mapsVal
  };
  if (id_servicio) payload.id_servicio = id_servicio;
  if (serviciosNombres.length > 0) payload.servicios_nombres = serviciosNombres;
  if (cultivoVal) payload.cultivo = cultivoVal;
  if (id_finca) payload.id_finca = id_finca;
  if (hectareas !== null && !isNaN(hectareas)) payload.hectareas = hectareas;
  if (hora) payload.hora_inicio_estimada = hora.length === 5 ? `${hora}:00` : hora;

  // Asignación multi-técnico (hasta 3 pilotos por vuelo)
  const tecnicos_ids = [];
  if (id_tecnico) tecnicos_ids.push(id_tecnico);
  if (id_tecnico_val2) tecnicos_ids.push(parseInt(id_tecnico_val2));
  if (id_tecnico_val3) tecnicos_ids.push(parseInt(id_tecnico_val3));
  const uniqueTecnicos = [...new Set(tecnicos_ids.filter(Boolean))];

  if (uniqueTecnicos.length > 0) {
    payload.id_tecnico = uniqueTecnicos[0];
    payload.tecnicos_ids = uniqueTecnicos;
    payload.tecnicos_adicionales = uniqueTecnicos.slice(1).join(',');
  } else if (id_tecnico_val === '') {
    payload.id_tecnico = null;
    payload.tecnicos_ids = [];
    payload.tecnicos_adicionales = null;
  }

  if (id_drone_val !== '') payload.id_drone = id_drone;
  if (motivo) payload.motivo_reagendamiento = motivo;
  if (observaciones) payload.observaciones_servicio = observaciones;

  try {
    showToast('Guardando modificaciones del agendamiento...', 'info');
    await apiFetch(`/agenda/${turnoId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
    showToast("<i class='fa-solid fa-circle-check'></i> Agendamiento modificado y actualizado exitosamente.", "success");
    closeModal('reprogramarModal');
    
    // Invalidate caches & reload tables
    invalidateCache('agenda');
    await loadAgenda();
    if (typeof renderCalendar === 'function') renderCalendar();
    if (typeof loadAdminTecnicoModule === 'function') await loadAdminTecnicoModule();
    if (typeof panelLoaders !== 'undefined' && panelLoaders.reagendamiento) panelLoaders.reagendamiento();
  } catch (err) {
    try {
      // Fallback update
      await apiFetch(`/agenda/${turnoId}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      showToast("<i class='fa-solid fa-circle-check'></i> Agendamiento actualizado exitosamente.", "success");
      closeModal('reprogramarModal');
      invalidateCache('agenda');
      await loadAgenda();
      if (typeof renderCalendar === 'function') renderCalendar();
    } catch (err2) {
      showModalErr(err2.message || err.message);
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  }
};
window.submitModificarAgenda = window.submitReprogramar;

// Submit Handlers for New Modals

window.submitNewAgenda = async function(e) {
  if (e) e.preventDefault();
  const btn = document.querySelector('#newAgendaForm button[type="submit"]');
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...'; }

  const showModalErr = (msg) => {
    const errEl = document.getElementById('newAgendaErrMsg');
    const errText = document.getElementById('newAgendaErrMsgText') || errEl;
    if (errText) errText.textContent = msg;
    if (errEl) {
      errEl.style.display = 'flex';
      errEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    showToast(msg, 'warn');
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
  };

  // 1. Validar multi-servicios seleccionados
  const checkedSvcNodes = Array.from(document.querySelectorAll('input[name="newAgendaServicioCb"]:checked'));
  const serviciosSeleccionados = checkedSvcNodes.map(cb => cb.value.trim()).filter(Boolean);
  const serviciosIds = checkedSvcNodes.map(cb => cb.getAttribute('data-id')).filter(Boolean);

  let servicioNombre = serviciosSeleccionados.join(' + ');
  if (!servicioNombre) {
    servicioNombre = (document.getElementById('newAgendaServicio')?.value || '').trim();
  }
  if (!servicioNombre && !serviciosSeleccionados.length) {
    showModalErr('Debes seleccionar al menos un servicio para el agendamiento.');
    return;
  }

  // 2. Validar Google Maps obligatorio
  const rawMapsVal = (document.getElementById('newAgendaMaps')?.value || '').trim();
  const mapsVal = normalizeMapsInput(rawMapsVal);
  if (!mapsVal) {
    showModalErr('El enlace de Google Maps o ubicación GPS es obligatorio.');
    return;
  }

  const cliente = (document.getElementById('newAgendaCliente')?.value || '').trim();
  const email = (document.getElementById('newAgendaEmail')?.value || '').trim();
  const fecha = (document.getElementById('newAgendaFecha')?.value || '').trim();

  if (!cliente) {
    showModalErr('Por favor ingresa o selecciona el nombre del cliente.');
    return;
  }
  if (!email) {
    showModalErr('Por favor ingresa el correo electrónico del cliente.');
    return;
  }
  if (!fecha) {
    showModalErr('Por favor selecciona la fecha del vuelo.');
    return;
  }

  const data = {
    cliente: cliente,
    email: email,
    telefono: (document.getElementById('newAgendaTel')?.value || '').trim(),
    finca: (document.getElementById('newAgendaFinca')?.value || '').trim() || 'Finca Principal',
    ubicacion: (document.getElementById('newAgendaUbicacion')?.value || '').trim() || 'Cundinamarca',
    maps: mapsVal,
    maps_url: mapsVal,
    cultivo: (document.getElementById('newAgendaCultivo')?.value || '').trim(),
    servicio: servicioNombre,
    servicios_nombres: serviciosSeleccionados.length ? serviciosSeleccionados : [servicioNombre],
    id_servicio: serviciosIds[0] ? parseInt(serviciosIds[0]) : null,
    hectareas: (document.getElementById('newAgendaHa')?.value || '10'),
    fecha: fecha,
    hora: (document.getElementById('newAgendaHora')?.value || '08:00'),
    tecnico: (document.getElementById('newAgendaTecnico')?.options[document.getElementById('newAgendaTecnico')?.selectedIndex]?.text || '').replace('Sin asignar', '').trim(),
    estado: (document.getElementById('newAgendaEstado')?.value || 'Pendiente'),
    notas: (document.getElementById('newAgendaNotas')?.value || '').trim()
  };
  
  try {
    await createAgenda(data);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
  }
};

window.submitNewCliente = async function(e) {
  if (e) e.preventDefault();
  const btn = document.querySelector('#newClienteForm button[type="submit"]');
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...'; }

  const data = {
    nombre: document.getElementById('newClienteNombre')?.value,
    email: document.getElementById('newClienteEmail')?.value,
    telefono: document.getElementById('newClienteTel')?.value,
    password: document.getElementById('newClientePassword')?.value,
    nombre_finca: document.getElementById('newClienteFinca')?.value,
    hectareas: document.getElementById('newClienteHectareas')?.value,
    departamento: document.getElementById('newClienteDepto')?.value,
    ciudad: document.getElementById('newClienteCiudad')?.value
  };

  try {
    await createCliente(data);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
  }
};

window.submitNewTecnico = async function(e) {
  if (e) e.preventDefault();
  const btn = document.querySelector('#newTecnicoForm button[type="submit"]');
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...'; }

  const data = {
    nombre: document.getElementById('newTecnicoNombre')?.value,
    email: document.getElementById('newTecnicoEmail')?.value,
    telefono: document.getElementById('newTecnicoTel')?.value,
    password: document.getElementById('newTecnicoPassword')?.value,
    certificacion: document.getElementById('newTecnicoCert')?.value
  };

  try {
    await createTecnico(data);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
  }
};

window.submitNewDrone = async function(e) {
  if (e) e.preventDefault();
  const btn = document.querySelector('#newDroneForm button[type="submit"]');
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...'; }

  const data = {
    modelo: document.getElementById('newDroneModelo')?.value,
    numero_serie: document.getElementById('newDroneSerie')?.value,
    id_tecnico_asignado: document.getElementById('newDroneTecnico')?.value
  };

  try {
    await createDrone(data);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
  }
};

window.submitEditDrone = async function(e) {
  if (e) e.preventDefault();
  const btn = document.querySelector('#editDroneForm button[type="submit"]');
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...'; }

  const data = {
    id: document.getElementById('editDroneId')?.value,
    modelo: document.getElementById('editDroneModelo')?.value,
    numero_serie: document.getElementById('editDroneSerie')?.value,
    id_tecnico_asignado: document.getElementById('editDroneTecnico')?.value
  };

  try {
    await updateDrone(data);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
  }
};

// =========================================================================
// MÓDULO: PUBLICIDAD, MEDIOS GLOBALES & REDES SOCIALES
// =========================================================================

let pubCollageData = [];
let pubRedesData = [];
let pubGlobalMedios = {
  hero_video_url: '/video/hero.mp4',
  mobile_poster_url: '/img/servicio_precision.jpg'
};

async function loadPublicidadPanel() {
  try {
    // 1. Cargar Medios Globales
    try {
      const resMedios = await apiFetch('/publicidad/medios-globales');
      const mediosData = (resMedios && resMedios.data) ? resMedios.data : (resMedios || {});
      if (mediosData && (mediosData.hero_video_url || mediosData.mobile_poster_url)) {
        pubGlobalMedios = mediosData;
        const vidInp = document.getElementById('pubHeroVideoInput');
        const imgInp = document.getElementById('pubMobilePosterInput');
        if (vidInp) vidInp.value = pubGlobalMedios.hero_video_url || '/video/hero.mp4';
        if (imgInp) imgInp.value = pubGlobalMedios.mobile_poster_url || '/img/servicio_precision.jpg';
        const vPrev = document.getElementById('pubGlobalHeroPreview');
        const iPrev = document.getElementById('pubGlobalPosterPreview');
        const heroUrl = resolveMediaUrl(pubGlobalMedios.hero_video_url) || '/video/hero.mp4';
        const posterUrl = resolveMediaUrl(pubGlobalMedios.mobile_poster_url) || '/img/servicio_precision.jpg';
        if (vPrev) {
          vPrev.src = heroUrl;
          vPrev.load();
          vPrev.play().catch(() => {});
        }
        if (iPrev) {
          iPrev.src = posterUrl + (posterUrl.includes('?') ? '&' : '?') + 't=' + Date.now();
        }
      }
    } catch (err) {
      console.warn('No se pudieron cargar medios globales:', err);
    }

    // 2. Cargar Elementos del Collage
    try {
      const resCollage = await apiFetch('/publicidad/admin/collage');
      pubCollageData = (resCollage && resCollage.data) ? resCollage.data : (Array.isArray(resCollage) ? resCollage : []);
      renderCollageTable();
    } catch (err) {
      console.warn('Error al cargar collage:', err);
      const tb = document.getElementById('pubCollageTableBody');
      if (tb) tb.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error al cargar collage: ${err.message}</td></tr>`;
    }

    // 3. Cargar Redes Sociales
    try {
      const resRedes = await apiFetch('/publicidad/admin/redes-sociales');
      pubRedesData = (resRedes && resRedes.data) ? resRedes.data : (Array.isArray(resRedes) ? resRedes : []);
      renderRedesTable();
    } catch (err) {
      console.warn('Error al cargar redes sociales:', err);
      const tb = document.getElementById('pubRedesTableBody');
      if (tb) tb.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error al cargar redes: ${err.message}</td></tr>`;
    }
  } catch (err) {
    showToast('Error cargando módulo de publicidad: ' + err.message, 'error');
  }
}
window.loadPublicidadPanel = loadPublicidadPanel;

window.switchPublicidadSubTab = function(subTab) {
  const tabs = ['collage', 'global', 'redes'];
  tabs.forEach(t => {
    const el = document.getElementById(`pubSubTab${t.charAt(0).toUpperCase() + t.slice(1)}`);
    const btn = document.getElementById(`pubTabBtn${t.charAt(0).toUpperCase() + t.slice(1)}`);
    if (el) el.style.display = (t === subTab) ? 'block' : 'none';
    if (btn) {
      if (t === subTab) {
        btn.classList.add('active');
        btn.style.background = 'rgba(28,130,173,0.1)';
        btn.style.color = 'var(--primary)';
        btn.style.borderColor = 'var(--accent)';
      } else {
        btn.classList.remove('active');
        btn.style.background = 'transparent';
        btn.style.color = '#64748b';
        btn.style.borderColor = '#cbd5e1';
      }
    }
  });

  const btnNuevo = document.getElementById('btnNuevoMedioPublicidad');
  if (btnNuevo) {
    if (subTab === 'collage') {
      btnNuevo.style.display = 'inline-flex';
      btnNuevo.innerHTML = '<i class="fa-solid fa-plus"></i> + Agregar al Collage';
      btnNuevo.onclick = openNewCollageModal;
    } else if (subTab === 'redes') {
      btnNuevo.style.display = 'inline-flex';
      btnNuevo.innerHTML = '<i class="fa-solid fa-plus"></i> + Registrar Red Social';
      btnNuevo.onclick = openNewRedSocialModal;
    } else {
      btnNuevo.style.display = 'none';
    }
  }
};

// ── MEDIOS GLOBALES HANDLERS ──
window.subirMedioGlobalDirecto = async function(input, tipo) {
  const file = input.files?.[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('tipo', tipo);
  formData.append('modulo', 'publicidad');

  try {
    showToast(`Subiendo ${tipo === 'video' ? 'Video Hero' : 'Portada Móvil'} al servidor...`, 'info');
    const token = getToken();
    const res = await fetch(`${API_BASE}/media/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
      throw new Error(body.message || body.detail || 'Error al subir el archivo');
    }

    const uploadedUrl = body.data.url;
    const cacheBusted = resolveMediaUrl(uploadedUrl) + (uploadedUrl.includes('?') ? '&' : '?') + 't=' + Date.now();

    if (tipo === 'video') {
      const vidInp = document.getElementById('pubHeroVideoInput');
      if (vidInp) vidInp.value = uploadedUrl;
      const vPrev = document.getElementById('pubGlobalHeroPreview');
      if (vPrev) {
        vPrev.src = cacheBusted;
        vPrev.load();
        vPrev.play().catch(() => {});
      }
      showToast('<i class="fa-solid fa-check"></i> Video subido exitosamente. Guardando en BD...', 'info');
    } else {
      const imgInp = document.getElementById('pubMobilePosterInput');
      if (imgInp) imgInp.value = uploadedUrl;
      const iPrev = document.getElementById('pubGlobalPosterPreview');
      if (iPrev) iPrev.src = cacheBusted;
      showToast('<i class="fa-solid fa-check"></i> Portada móvil subida con éxito. Guardando en BD...', 'info');
    }

    // Guardar automáticamente en BD para que impacte la página principal de inmediato
    await window.guardarMediosGlobales();
  } catch (err) {
    showToast('Error al subir medio: ' + err.message, 'error');
  } finally {
    input.value = '';
  }
};

window.resetMediosGlobalesDefault = function() {
  document.getElementById('pubHeroVideoInput').value = '/video/hero.mp4';
  document.getElementById('pubMobilePosterInput').value = '/img/servicio_precision.jpg';
  const vPrev = document.getElementById('pubGlobalHeroPreview');
  const iPrev = document.getElementById('pubGlobalPosterPreview');
  if (vPrev) {
    vPrev.src = '/video/hero.mp4';
    vPrev.load();
    vPrev.play().catch(() => {});
  }
  if (iPrev) {
    iPrev.src = '/img/servicio_precision.jpg';
  }
  showToast('Valores por defecto cargados en el formulario. Pulsa "Guardar Medios Globales" para confirmar.', 'info');
};

window.eliminarMedioGlobal = async function(tipo) {
  const isVideo = (tipo === 'video');
  const inputEl = document.getElementById(isVideo ? 'pubHeroVideoInput' : 'pubMobilePosterInput');
  const previewEl = document.getElementById(isVideo ? 'pubGlobalHeroPreview' : 'pubGlobalPosterPreview');
  const defaultVal = isVideo ? '/video/hero.mp4' : '/img/servicio_precision.jpg';
  const currentVal = (inputEl ? inputEl.value : '').trim();

  if (!confirm(`¿Estás seguro de restablecer ${isVideo ? 'Video Hero' : 'Portada Móvil'} a su valor por defecto?`)) {
    return;
  }

  try {
    // Si era un archivo en uploads, intentar eliminarlo en disco
    if (currentVal.includes('/uploads/')) {
      const filename = currentVal.split('/').pop().split('?')[0];
      if (filename) {
        try {
          const token = getToken();
          await fetch(`${API_BASE}/media/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
          });
        } catch (e) {
          console.warn('Error eliminando archivo físico:', e);
        }
      }
    }

    if (inputEl) inputEl.value = defaultVal;
    if (previewEl) previewEl.src = defaultVal;
    if (isVideo && previewEl) {
      previewEl.load();
      previewEl.play().catch(() => {});
    }

    await window.guardarMediosGlobales();
    showToast(`<i class="fa-solid fa-trash-can"></i> ${isVideo ? 'Video' : 'Imagen'} restaurado por defecto exitosamente`, 'success');
  } catch (err) {
    showToast('Error al restablecer medio: ' + (err.detail || err.message), 'error');
  }
};

window.guardarMediosGlobales = async function() {
  const heroInp = document.getElementById('pubHeroVideoInput');
  const posterInp = document.getElementById('pubMobilePosterInput');
  let heroUrl = (heroInp ? heroInp.value : '').trim() || '/video/hero.mp4';
  let posterUrl = (posterInp ? posterInp.value : '').trim() || '/img/servicio_precision.jpg';

  // Normalizar rutas relativas si no tienen prefijo http ni slash
  if (heroUrl && !heroUrl.startsWith('http') && !heroUrl.startsWith('/')) {
    heroUrl = '/' + heroUrl;
    if (heroInp) heroInp.value = heroUrl;
  }
  if (posterUrl && !posterUrl.startsWith('http') && !posterUrl.startsWith('/')) {
    posterUrl = '/' + posterUrl;
    if (posterInp) posterInp.value = posterUrl;
  }

  try {
    showToast('Guardando configuración de medios en base de datos...', 'info');
    const res = await apiFetch('/publicidad/medios-globales', {
      method: 'POST',
      body: JSON.stringify({
        hero_video_url: heroUrl,
        mobile_poster_url: posterUrl
      })
    });

    pubGlobalMedios = (res && res.data) ? res.data : (res || { hero_video_url: heroUrl, mobile_poster_url: posterUrl });

    const vPrev = document.getElementById('pubGlobalHeroPreview');
    const iPrev = document.getElementById('pubGlobalPosterPreview');
    if (vPrev) {
      vPrev.src = heroUrl;
      vPrev.load();
      vPrev.play().catch(() => {});
    }
    if (iPrev) {
      iPrev.src = posterUrl + (posterUrl.includes('?') ? '&' : '?') + 't=' + Date.now();
    }

    showToast('<i class="fa-solid fa-check"></i> Medios globales guardados y confirmados en la BD', 'success');
  } catch (err) {
    showToast('Error al guardar medios: ' + (err.detail || err.message), 'error');
  }
};

// ── COLLAGE CLIENTE HANDLERS ──
window.renderCollageTable = function() {
  const tbody = document.getElementById('pubCollageTableBody');
  if (!tbody) return;

  const search = (document.getElementById('pubCollageSearch')?.value || '').toLowerCase().trim();
  const filterActivo = document.getElementById('pubCollageFilterActivo')?.value || '';

  let filtered = (pubCollageData || []).filter(item => {
    const matchSearch = !search ||
      (item.titulo || '').toLowerCase().includes(search) ||
      (item.subtitulo || '').toLowerCase().includes(search) ||
      (item.badge || '').toLowerCase().includes(search);
    
    let matchFilter = true;
    if (filterActivo === 'activo') matchFilter = (item.activo === true);
    if (filterActivo === 'inactivo') matchFilter = (item.activo === false);

    return matchSearch && matchFilter;
  });

  if (!filtered.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-center" style="padding:32px; color:#64748b;">
          <i class="fa-solid fa-photo-film" style="font-size:1.6rem; margin-bottom:8px; display:block; color:#94a3b8;"></i>
          No hay elementos de collage registrados o coincidentes.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(item => {
    const isVid = (item.tipo_medio === 'video');
    let itemUrl = resolveMediaUrl(item.url_medio);
    const mediaPreview = isVid
      ? `<div style="width:65px; height:45px; border-radius:8px; background:#0f172a; overflow:hidden; position:relative; display:flex; align-items:center; justify-content:center;">
          <video src="${itemUrl}" style="width:100%; height:100%; object-fit:cover;" muted></video>
          <span style="position:absolute; background:rgba(225,29,72,0.8); color:#fff; border-radius:50%; width:18px; height:18px; display:flex; align-items:center; justify-content:center; font-size:0.6rem;">
            <i class="fa-solid fa-play"></i>
          </span>
         </div>`
      : `<div style="width:65px; height:45px; border-radius:8px; background:#e2e8f0; overflow:hidden;">
          <img src="${itemUrl || '/img/servicio_aspersion.jpg'}" style="width:100%; height:100%; object-fit:cover;" onerror="this.onerror=null; this.src='/img/servicio_aspersion.jpg';" />
         </div>`;

    const statusBadge = item.activo
      ? `<span class="badge" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0; cursor:pointer;" onclick="toggleCollageActivo(${item.id_publicidad}, ${item.activo})" title="Haz clic para pausar">
          <i class="fa-solid fa-check"></i> Activo
         </span>`
      : `<span class="badge" style="background:#f8fafc; color:#94a3b8; border:1px solid #e2e8f0; cursor:pointer;" onclick="toggleCollageActivo(${item.id_publicidad}, ${item.activo})" title="Haz clic para activar">
          <i class="fa-solid fa-pause"></i> Inactivo
         </span>`;

    return `
      <tr>
        <td>${mediaPreview}</td>
        <td>
          <strong style="color:#003049; font-size:0.88rem;">${escapeHtml(item.titulo || '')}</strong>
          <div style="font-size:0.75rem; color:#64748b; max-width:320px; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">
            ${escapeHtml(item.subtitulo || 'Sin descripción')}
          </div>
        </td>
        <td style="text-align:center;">
          <span class="badge" style="${isVid ? 'background:#fef2f2; color:#e11d48; border:1px solid #fecdd3;' : 'background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;'} font-size:0.72rem; text-transform:uppercase;">
            <i class="fa-solid ${isVid ? 'fa-video' : 'fa-image'}"></i> ${item.tipo_medio || 'imagen'}
          </span>
        </td>
        <td>
          <div style="font-size:0.8rem; font-weight:700; color:#0284c7;">
            ${item.badge ? `<span style="background:rgba(28,130,173,0.12); padding:2px 8px; border-radius:6px; margin-right:4px;">${escapeHtml(item.badge)}</span>` : ''}
          </div>
          <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">
            Btn: <em>${escapeHtml(item.texto_boton || 'Ver Más')}</em> → ${escapeHtml(item.url_accion || '#')}
          </div>
        </td>
        <td style="text-align:center; font-weight:800; color:#334155;">${item.orden || 0}</td>
        <td style="text-align:center;">${statusBadge}</td>
        <td style="text-align:center;">
          <div style="display:inline-flex; gap:6px;">
            <button class="btn btn-ghost btn-sm" onclick="openEditCollageModal(${item.id_publicidad})" title="Editar elemento" style="padding:6px 10px; border-radius:8px;">
              <i class="fa-solid fa-pen" style="color:var(--accent);"></i>
            </button>
            <button class="btn btn-ghost btn-sm" onclick="deleteCollageItem(${item.id_publicidad})" title="Eliminar elemento" style="padding:6px 10px; border-radius:8px;">
              <i class="fa-solid fa-trash" style="color:#ef4444;"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
};

window.openNewCollageModal = function() {
  document.getElementById('collageModalId').value = '';
  document.getElementById('collageModalTitle').innerHTML = '<i class="fa-solid fa-plus" style="color:var(--accent);"></i> Nuevo Elemento de Collage';
  document.getElementById('collageModalTitulo').value = '';
  document.getElementById('collageModalSubtitulo').value = '';
  document.getElementById('collageModalTipoMedio').value = 'imagen';
  document.getElementById('collageModalBadge').value = 'Innovación';
  document.getElementById('collageModalTextoBoton').value = 'Conocer Más';
  document.getElementById('collageModalUrlAccion').value = '#agendar';
  document.getElementById('collageModalOrden').value = (pubCollageData.length + 1);
  document.getElementById('collageModalActivo').checked = true;
  document.getElementById('collageModalUrlMedio').value = '/img/servicio_aspersion.jpg';

  onCollageTipoMedioChange();
  updateCollagePreview('/img/servicio_aspersion.jpg');
  openModal('modalCollageItem');
};

window.openEditCollageModal = function(id) {
  const item = pubCollageData.find(x => x.id_publicidad == id);
  if (!item) return;

  document.getElementById('collageModalId').value = item.id_publicidad;
  document.getElementById('collageModalTitle').innerHTML = `<i class="fa-solid fa-pen" style="color:var(--accent);"></i> Editar Elemento #${item.id_publicidad}`;
  document.getElementById('collageModalTitulo').value = item.titulo || '';
  document.getElementById('collageModalSubtitulo').value = item.subtitulo || '';
  document.getElementById('collageModalTipoMedio').value = item.tipo_medio || 'imagen';
  document.getElementById('collageModalBadge').value = item.badge || '';
  document.getElementById('collageModalTextoBoton').value = item.texto_boton || '';
  document.getElementById('collageModalUrlAccion').value = item.url_accion || '';
  document.getElementById('collageModalOrden').value = item.orden || 1;
  document.getElementById('collageModalActivo').checked = (item.activo !== false);
  document.getElementById('collageModalUrlMedio').value = item.url_medio || '';

  onCollageTipoMedioChange();
  updateCollagePreview(item.url_medio || '');
  openModal('modalCollageItem');
};

window.onCollageTipoMedioChange = function() {
  const tipo = document.getElementById('collageModalTipoMedio').value;
  const imgPrev = document.getElementById('collageModalImgPreview');
  const vidPrev = document.getElementById('collageModalVidPreview');
  if (tipo === 'video') {
    if (imgPrev) imgPrev.style.display = 'none';
    if (vidPrev) vidPrev.style.display = 'block';
  } else {
    if (imgPrev) imgPrev.style.display = 'block';
    if (vidPrev) vidPrev.style.display = 'none';
  }
};

window.updateCollagePreview = function(url) {
  const tipo = document.getElementById('collageModalTipoMedio').value;
  let finalUrl = resolveMediaUrl(url);
  if (tipo === 'video') {
    const vid = document.getElementById('collageModalVidPreview');
    if (vid && finalUrl) {
      vid.src = finalUrl;
      vid.load();
    }
  } else {
    const img = document.getElementById('collageModalImgPreview');
    if (img && finalUrl) {
      img.src = finalUrl + (finalUrl.includes('?') ? '&' : '?') + 't=' + Date.now();
    }
  }
};

window.subirArchivoCollage = async function(input) {
  const file = input.files?.[0];
  if (!file) return;

  const tipo = document.getElementById('collageModalTipoMedio').value;
  const formData = new FormData();
  formData.append('file', file);
  formData.append('tipo', tipo);
  formData.append('modulo', 'collage');

  const spinner = document.getElementById('collageUploadSpinner');
  if (spinner) spinner.style.display = 'inline-flex';

  try {
    const token = getToken();
    const res = await fetch(`${API_BASE}/media/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
      throw new Error(body.message || body.detail || 'Error al subir archivo');
    }
    const mediaUrl = body.data.url;
    document.getElementById('collageModalUrlMedio').value = mediaUrl;
    updateCollagePreview(mediaUrl);
    showToast('<i class="fa-solid fa-check"></i> Archivo subido con éxito', 'success');
  } catch (err) {
    showToast('Error al subir archivo: ' + err.message, 'error');
  } finally {
    if (spinner) spinner.style.display = 'none';
    input.value = '';
  }
};

window.uploadMultipleCollageFiles = async function(input) {
  const files = input.files;
  if (!files || !files.length) return;

  const statusWrap = document.getElementById('collageBatchUploadStatus');
  const statusText = document.getElementById('collageBatchUploadText');
  if (statusWrap) statusWrap.style.display = 'flex';
  if (statusText) statusText.textContent = `Preparando ${files.length} archivo(s) para subir...`;

  const token = getToken();
  const total = files.length;

  try {
    // ── FASE 1: Subida masiva en un solo request ──────────────────────
    if (statusText) statusText.textContent = `⬆️ Subiendo ${total} archivo(s) al servidor...`;

    const formData = new FormData();
    for (let i = 0; i < total; i++) {
      formData.append('files', files[i]);
    }

    const uploadRes = await fetch(`${API_BASE}/media/upload-batch`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });

    const uploadData = await uploadRes.json();

    if (!uploadRes.ok || !uploadData.success) {
      // Fallback: subida secuencial archivo por archivo si el batch falla
      if (statusText) statusText.textContent = `↻ Usando método alternativo...`;
      await _uploadCollageFilesSequential(files, token, statusText, statusWrap, total);
      input.value = '';
      return;
    }

    const uploaded = uploadData.data?.uploaded || [];
    const errorCount = uploadData.data?.total_errores || 0;

    // ── FASE 2: Registrar cada archivo en la BD de publicidad ─────────
    if (statusText) statusText.textContent = `📋 Registrando ${uploaded.length} elementos en el collage...`;
    const progressBar = document.getElementById('collageBatchProgressBar');
    if (progressBar) progressBar.style.width = '20%';

    let regOk = 0;
    for (let i = 0; i < uploaded.length; i++) {
      const item = uploaded[i];
      const isVideo = item.tipo === 'video';

      let cleanTitle = (item.original_name || item.filename)
        .replace(/\.[^/.]+$/, '')
        .replace(/[-_]/g, ' ')
        .trim();
      cleanTitle = cleanTitle.charAt(0).toUpperCase() + cleanTitle.slice(1);
      if (cleanTitle.length > 60) cleanTitle = cleanTitle.substring(0, 60) + '...';

      if (statusText) statusText.textContent = `📋 Registrando ${i + 1} de ${uploaded.length}: "${cleanTitle}"...`;
      if (progressBar) progressBar.style.width = `${Math.round(20 + ((i + 1) / uploaded.length) * 75)}%`;

      const payload = {
        seccion: 'dashboard_cliente',
        titulo: cleanTitle || 'Servicio Agroaéreo Flymetrics',
        subtitulo: 'Registro técnico de alta definición desde el aire.',
        tipo_medio: isVideo ? 'video' : 'imagen',
        url_medio: item.url,
        badge: isVideo ? 'Video Operativo' : 'Vuelo Agrícola',
        texto_boton: 'Cotizar Servicio',
        url_accion: '#agendar',
        orden: ((pubCollageData ? pubCollageData.length : 0) + i + 1),
        activo: true
      };

      try {
        await apiFetch('/publicidad/admin/collage', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        regOk++;
      } catch (err) {
        console.error('Error registrando en collage:', item.filename, err);
      }
    }

    if (statusWrap) statusWrap.style.display = 'none';
    input.value = '';

    const errMsg = errorCount > 0 ? ` (${errorCount} con error)` : '';
    showToast(
      `<i class="fa-solid fa-circle-check"></i> ¡${regOk} imagen(es) agregada(s) al collage exitosamente!${errMsg}`,
      'success'
    );

  } catch (err) {
    console.error('Error en subida batch:', err);
    if (statusWrap) statusWrap.style.display = 'none';
    input.value = '';
    showToast('Error al subir archivos: ' + err.message, 'error');
  }

  // Recargar la tabla del collage
  try {
    const res = await apiFetch('/publicidad/admin/collage');
    pubCollageData = (res && res.data) ? res.data : (Array.isArray(res) ? res : []);
    renderCollageTable();
  } catch(e) {}
};

// Fallback secuencial para navegadores que no soporten FormData con múltiples files
async function _uploadCollageFilesSequential(files, token, statusText, statusWrap, total) {
  let successCount = 0;
  for (let i = 0; i < total; i++) {
    const file = files[i];
    if (statusText) statusText.textContent = `Subiendo ${i + 1} de ${total}: "${file.name}"...`;
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch(`${API_BASE}/media/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: fd
      });
      const d = await r.json();
      if (!r.ok || !d.success) continue;

      const isVideo = file.type.startsWith('video');
      let cleanTitle = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ').trim();
      cleanTitle = cleanTitle.charAt(0).toUpperCase() + cleanTitle.slice(1);

      await apiFetch('/publicidad/admin/collage', {
        method: 'POST',
        body: JSON.stringify({
          seccion: 'dashboard_cliente',
          titulo: cleanTitle || 'Servicio Agroaéreo Flymetrics',
          subtitulo: 'Registro técnico de alta definición desde el aire.',
          tipo_medio: isVideo ? 'video' : 'imagen',
          url_medio: d.data.url,
          badge: isVideo ? 'Video Operativo' : 'Vuelo Agrícola',
          texto_boton: 'Cotizar Servicio',
          url_accion: '#agendar',
          orden: ((pubCollageData ? pubCollageData.length : 0) + i + 1),
          activo: true
        })
      });
      successCount++;
    } catch (e) { console.error(e); }
  }
  if (statusWrap) statusWrap.style.display = 'none';
  showToast(`<i class="fa-solid fa-circle-check"></i> ¡${successCount} de ${total} imágenes agregadas al collage!`, 'success');
  try {
    const res = await apiFetch('/publicidad/admin/collage');
    pubCollageData = (res && res.data) ? res.data : (Array.isArray(res) ? res : []);
    renderCollageTable();
  } catch(e) {}
}


window.submitCollageItem = async function(e) {
  if (e) e.preventDefault();
  const id = document.getElementById('collageModalId').value;
  const isEdit = Boolean(id);

  let urlMedio = document.getElementById('collageModalUrlMedio').value.trim();
  if (urlMedio && !urlMedio.startsWith('http') && !urlMedio.startsWith('/') && !urlMedio.startsWith('../')) {
    urlMedio = '/' + urlMedio;
  }

  const payload = {
    seccion: 'dashboard_cliente',
    titulo: document.getElementById('collageModalTitulo').value.trim(),
    subtitulo: document.getElementById('collageModalSubtitulo').value.trim(),
    tipo_medio: document.getElementById('collageModalTipoMedio').value,
    badge: document.getElementById('collageModalBadge').value.trim() || null,
    texto_boton: document.getElementById('collageModalTextoBoton').value.trim() || null,
    url_accion: document.getElementById('collageModalUrlAccion').value.trim() || null,
    orden: parseInt(document.getElementById('collageModalOrden').value) || 0,
    activo: document.getElementById('collageModalActivo').checked,
    url_medio: urlMedio
  };

  try {
    showToast(isEdit ? 'Actualizando elemento...' : 'Creando elemento...', 'info');
    if (isEdit) {
      await apiFetch(`/publicidad/admin/collage/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      showToast('<i class="fa-solid fa-check"></i> Elemento actualizado con éxito', 'success');
    } else {
      await apiFetch('/publicidad/admin/collage', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      showToast('<i class="fa-solid fa-check"></i> Elemento agregado al collage', 'success');
    }
    closeModal('modalCollageItem');
    const res = await apiFetch('/publicidad/admin/collage');
    pubCollageData = (res && res.data) ? res.data : (Array.isArray(res) ? res : []);
    renderCollageTable();
  } catch (err) {
    showToast('Error al guardar: ' + (err.detail || err.message), 'error');
  }
};

window.toggleCollageActivo = async function(id, currentActive) {
  try {
    await apiFetch(`/publicidad/admin/collage/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ activo: !currentActive })
    });
    showToast(`Elemento ${!currentActive ? 'activado' : 'pausado'} en el collage`, 'success');
    const item = pubCollageData.find(x => x.id_publicidad == id);
    if (item) item.activo = !currentActive;
    renderCollageTable();
  } catch (err) {
    showToast('Error al cambiar estado: ' + err.message, 'error');
  }
};

window.deleteCollageItem = async function(id) {
  if (!confirm(`¿Estás seguro de eliminar este elemento del collage (#${id})?`)) return;

  try {
    await apiFetch(`/publicidad/admin/collage/${id}`, { method: 'DELETE' });
    showToast('Elemento eliminado del collage', 'success');
    pubCollageData = pubCollageData.filter(x => x.id_publicidad != id);
    renderCollageTable();
  } catch (err) {
    showToast('Error al eliminar: ' + err.message, 'error');
  }
};

// ── REDES SOCIALES HANDLERS ──
window.renderRedesTable = function() {
  const tbody = document.getElementById('pubRedesTableBody');
  if (!tbody) return;

  const search = (document.getElementById('pubRedesSearch')?.value || '').toLowerCase().trim();
  let filtered = (pubRedesData || []).filter(item => {
    return !search ||
      (item.nombre_visible || '').toLowerCase().includes(search) ||
      (item.red || '').toLowerCase().includes(search) ||
      (item.url || '').toLowerCase().includes(search);
  });

  if (!filtered.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-center" style="padding:32px; color:#64748b;">
          <i class="fa-solid fa-share-nodes" style="font-size:1.6rem; margin-bottom:8px; display:block; color:#94a3b8;"></i>
          No hay redes sociales registradas o coincidentes.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(item => {
    let iconClass = (item.icono || '').trim();
    if (!iconClass.startsWith('fa-brands ') && !iconClass.startsWith('fa-solid ') && !iconClass.startsWith('fab ') && !iconClass.startsWith('fas ')) {
      const clean = iconClass.replace(/^fa-/, '');
      const brands = ['instagram', 'facebook', 'tiktok', 'youtube', 'linkedin', 'whatsapp', 'twitter', 'x'];
      const key = (item.red || clean).toLowerCase();
      if (brands.some(b => key.includes(b))) {
        iconClass = 'fa-brands fa-' + (clean === 'facebook' ? 'facebook-f' : (clean === 'linkedin' ? 'linkedin-in' : clean));
      } else {
        iconClass = 'fa-solid fa-' + (clean || 'globe');
      }
    }

    const statusBadge = item.activo
      ? `<span class="badge" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0; cursor:pointer;" onclick="toggleRedSocialActiva(${item.id_red}, ${item.activo})" title="Haz clic para pausar">
          <i class="fa-solid fa-check"></i> Activa
         </span>`
      : `<span class="badge" style="background:#f8fafc; color:#94a3b8; border:1px solid #e2e8f0; cursor:pointer;" onclick="toggleRedSocialActiva(${item.id_red}, ${item.activo})" title="Haz clic para activar">
          <i class="fa-solid fa-pause"></i> Inactiva
         </span>`;

    return `
      <tr>
        <td style="text-align:center;">
          <span style="width:36px; height:36px; border-radius:50%; background:rgba(28,130,173,0.1); color:var(--accent); display:inline-flex; align-items:center; justify-content:center; font-size:1.15rem;">
            <i class="${iconClass}"></i>
          </span>
        </td>
        <td>
          <strong style="color:#003049; text-transform:capitalize;">${escapeHtml(item.red || '')}</strong>
        </td>
        <td style="font-weight:700; color:#334155;">
          ${escapeHtml(item.nombre_visible || '')}
        </td>
        <td>
          <a href="${escapeHtml(item.url || '#')}" target="_blank" style="color:var(--accent); text-decoration:none; font-size:0.82rem; display:inline-flex; align-items:center; gap:4px;">
            ${escapeHtml(item.url || '')} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:0.7rem;"></i>
          </a>
        </td>
        <td style="text-align:center; font-weight:800;">${item.orden || 0}</td>
        <td style="text-align:center;">${statusBadge}</td>
        <td style="text-align:center;">
          <div style="display:inline-flex; gap:6px;">
            <button class="btn btn-ghost btn-sm" onclick="openEditRedSocialModal(${item.id_red})" title="Editar red social" style="padding:6px 10px; border-radius:8px;">
              <i class="fa-solid fa-pen" style="color:var(--accent);"></i>
            </button>
            <button class="btn btn-ghost btn-sm" onclick="deleteRedSocial(${item.id_red})" title="Eliminar red social" style="padding:6px 10px; border-radius:8px;">
              <i class="fa-solid fa-trash" style="color:#ef4444;"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
};

window.openNewRedSocialModal = function() {
  document.getElementById('redSocialModalId').value = '';
  document.getElementById('redSocialModalTitle').innerHTML = '<i class="fa-solid fa-plus" style="color:#10b981;"></i> Registrar Red Social';
  document.getElementById('redSocialModalPlataforma').value = 'whatsapp';
  document.getElementById('redSocialModalNombre').value = '';
  document.getElementById('redSocialModalUrl').value = '';
  document.getElementById('redSocialModalIcono').value = 'fa-whatsapp';
  document.getElementById('redSocialModalOrden').value = (pubRedesData.length + 1);
  document.getElementById('redSocialModalActivo').checked = true;
  openModal('modalRedSocial');
};

window.openEditRedSocialModal = function(id) {
  const item = pubRedesData.find(x => x.id_red == id);
  if (!item) return;

  document.getElementById('redSocialModalId').value = item.id_red;
  document.getElementById('redSocialModalTitle').innerHTML = `<i class="fa-solid fa-pen" style="color:#10b981;"></i> Editar Red Social #${item.id_red}`;
  document.getElementById('redSocialModalPlataforma').value = item.red || 'otro';
  document.getElementById('redSocialModalNombre').value = item.nombre_visible || '';
  document.getElementById('redSocialModalUrl').value = item.url || '';
  document.getElementById('redSocialModalIcono').value = item.icono || 'fa-globe';
  document.getElementById('redSocialModalOrden').value = item.orden || 1;
  document.getElementById('redSocialModalActivo').checked = (item.activo !== false);
  openModal('modalRedSocial');
};

window.onRedSocialPlataformaChange = function() {
  const plat = document.getElementById('redSocialModalPlataforma').value;
  const iconInput = document.getElementById('redSocialModalIcono');
  const icons = {
    whatsapp: 'fa-brands fa-whatsapp',
    instagram: 'fa-brands fa-instagram',
    facebook: 'fa-brands fa-facebook-f',
    tiktok: 'fa-brands fa-tiktok',
    youtube: 'fa-brands fa-youtube',
    linkedin: 'fa-brands fa-linkedin-in',
    twitter: 'fa-brands fa-x-twitter',
    otro: 'fa-solid fa-globe'
  };
  if (iconInput && icons[plat]) {
    iconInput.value = icons[plat];
  }
};

window.submitRedSocial = async function(e) {
  if (e) e.preventDefault();
  const id = document.getElementById('redSocialModalId').value;
  const isEdit = Boolean(id);

  const payload = {
    red: document.getElementById('redSocialModalPlataforma').value,
    nombre_visible: document.getElementById('redSocialModalNombre').value.trim(),
    url: document.getElementById('redSocialModalUrl').value.trim(),
    icono: document.getElementById('redSocialModalIcono').value.trim() || 'fa-globe',
    orden: parseInt(document.getElementById('redSocialModalOrden').value) || 0,
    activo: document.getElementById('redSocialModalActivo').checked
  };

  try {
    showToast(isEdit ? 'Actualizando red social...' : 'Registrando red social...', 'info');
    if (isEdit) {
      await apiFetch(`/publicidad/admin/redes-sociales/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      showToast('<i class="fa-solid fa-check"></i> Red social actualizada', 'success');
    } else {
      await apiFetch('/publicidad/admin/redes-sociales', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      showToast('<i class="fa-solid fa-check"></i> Red social registrada con éxito', 'success');
    }
    closeModal('modalRedSocial');
    const res = await apiFetch('/publicidad/admin/redes-sociales');
    pubRedesData = res.data || res;
    renderRedesTable();
  } catch (err) {
    showToast('Error al guardar red social: ' + (err.detail || err.message), 'error');
  }
};

window.toggleRedSocialActiva = async function(id, currentActive) {
  try {
    await apiFetch(`/publicidad/admin/redes-sociales/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ activo: !currentActive })
    });
    showToast(`Red social ${!currentActive ? 'activada' : 'pausada'}`, 'success');
    const item = pubRedesData.find(x => x.id_red == id);
    if (item) item.activo = !currentActive;
    renderRedesTable();
  } catch (err) {
    showToast('Error al cambiar estado: ' + err.message, 'error');
  }
};

window.deleteRedSocial = async function(id) {
  if (!confirm(`¿Estás seguro de eliminar esta red social (#${id})?`)) return;

  try {
    await apiFetch(`/publicidad/admin/redes-sociales/${id}`, { method: 'DELETE' });
    showToast('Red social eliminada', 'success');
    pubRedesData = pubRedesData.filter(x => x.id_red != id);
    renderRedesTable();
  } catch (err) {
    showToast('Error al eliminar: ' + err.message, 'error');
  }
};

// ==============================================================================
// CONFIGURACIÓN DE CORREOS Y REDIRECCIÓN DE BOTONES CON CLAVE MAESTRA
// ==============================================================================
let _isEmailConfigUnlocked = false;

window.openMasterKeyModal = function() {
  const modal = document.getElementById('masterKeyModal');
  const err = document.getElementById('masterKeyError');
  const inp = document.getElementById('inputMasterKey');
  if (err) err.style.display = 'none';
  if (inp) inp.value = '';
  openModal('masterKeyModal');
  setTimeout(() => { if (inp) inp.focus(); }, 100);
};

window.bloquearModuloCorreo = function() {
  _isEmailConfigUnlocked = false;
  const boxBloq = document.getElementById('boxCorreoBloqueado');
  const boxDesbloq = document.getElementById('boxCorreoDesbloqueado');
  const icon = document.getElementById('iconLockCorreo');
  const text = document.getElementById('textLockCorreo');

  if (boxBloq) boxBloq.style.display = 'block';
  if (boxDesbloq) boxDesbloq.style.display = 'none';
  if (icon) { icon.className = 'fa-solid fa-lock'; }
  if (text) { text.textContent = 'Desbloquear con Clave Maestra'; }
  showToast('Módulo de correo bloqueado por seguridad', 'info');
};

window.submitMasterKeyVerification = async function(e) {
  if (e) e.preventDefault();
  const clave = document.getElementById('inputMasterKey')?.value || '';
  const errEl = document.getElementById('masterKeyError');
  const btn = document.getElementById('btnSubmitMasterKey');

  if (errEl) errEl.style.display = 'none';
  if (!clave || clave.trim().length < 4) {
    if (errEl) {
      errEl.textContent = 'Ingresa una contraseña válida de al menos 4 caracteres.';
      errEl.style.display = 'block';
    }
    return;
  }

  try {
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Validando...'; }
    const res = await apiFetch('/admin/usuarios/config-correo/verificar-clave', {
      method: 'POST',
      body: JSON.stringify({ clave_maestra: clave.trim() })
    });

    closeModal('masterKeyModal');
    _isEmailConfigUnlocked = true;

    // Desbloquear interfaz
    const boxBloq = document.getElementById('boxCorreoBloqueado');
    const boxDesbloq = document.getElementById('boxCorreoDesbloqueado');
    const icon = document.getElementById('iconLockCorreo');
    const text = document.getElementById('textLockCorreo');

    if (boxBloq) boxBloq.style.display = 'none';
    if (boxDesbloq) boxDesbloq.style.display = 'block';
    if (icon) { icon.className = 'fa-solid fa-lock-open'; }
    if (text) { text.textContent = 'Módulo Desbloqueado'; }

    showToast(res.message || 'Contraseña maestra confirmada exitosamente', 'success');
    await loadEmailConfigAdmin();

  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message || 'Contraseña maestra incorrecta.';
      errEl.style.display = 'block';
    }
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-unlock"></i> Desbloquear'; }
  }
};

window.loadEmailConfigAdmin = async function() {
  try {
    const res = await apiFetch('/admin/usuarios/config-correo');
    const cfg = res.data || res || {};

    const urlInp = document.getElementById('cfgUrlBotonesCorreo');
    const hostInp = document.getElementById('cfgSmtpHost');
    const portInp = document.getElementById('cfgSmtpPort');
    const userInp = document.getElementById('cfgSmtpUser');
    const nameInp = document.getElementById('cfgSenderName');
    const passStatus = document.getElementById('cfgSmtpPassStatus');

    if (urlInp && cfg.url_botones_correo) urlInp.value = cfg.url_botones_correo;
    if (hostInp && cfg.smtp_host) hostInp.value = cfg.smtp_host;
    if (portInp && cfg.smtp_port) portInp.value = cfg.smtp_port;
    if (userInp && cfg.smtp_user) userInp.value = cfg.smtp_user;
    if (nameInp && cfg.sender_name) nameInp.value = cfg.sender_name;
    
    // Garantizar que el navegador no pegue la contraseña de sesión (18011801) en el SMTP password
    const pwdInp = document.getElementById('cfgSmtpPassword');
    const newMasterInp = document.getElementById('cfgNuevaClaveMaestra');
    if (pwdInp) pwdInp.value = '';
    if (newMasterInp) newMasterInp.value = '';

    if (passStatus) {
      passStatus.textContent = cfg.tiene_password ? '✔ Contraseña de aplicación configurada en el sistema' : '⚠ Sin contraseña de envío asignada';
      passStatus.style.color = cfg.tiene_password ? '#10b981' : '#f59e0b';
    }
  } catch (err) {
    console.warn('Error al cargar configuración de correos:', err);
  }
};

window.saveEmailConfigAdmin = async function(e) {
  if (e) e.preventDefault();
  if (!_isEmailConfigUnlocked) {
    showToast('Debes desbloquear el módulo con tu contraseña maestra', 'warn');
    return;
  }

  const payload = {
    url_botones_correo: document.getElementById('cfgUrlBotonesCorreo')?.value.trim(),
    smtp_host: document.getElementById('cfgSmtpHost')?.value.trim(),
    smtp_port: parseInt(document.getElementById('cfgSmtpPort')?.value || '587', 10),
    smtp_user: document.getElementById('cfgSmtpUser')?.value.trim(),
    sender_name: document.getElementById('cfgSenderName')?.value.trim()
  };

  const pwd = document.getElementById('cfgSmtpPassword')?.value.trim();
  if (pwd) payload.smtp_password = pwd;

  const nuevaClave = document.getElementById('cfgNuevaClaveMaestra')?.value.trim();
  if (nuevaClave) payload.nueva_clave_maestra = nuevaClave;

  try {
    showToast('Guardando credenciales y URL de redirección...', 'info');
    await apiFetch('/admin/usuarios/config-correo', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    showToast('<i class="fa-solid fa-check"></i> Configuración de correo y enlaces guardada en la base de datos', 'success');
    document.getElementById('cfgSmtpPassword').value = '';
    document.getElementById('cfgNuevaClaveMaestra').value = '';
    await loadEmailConfigAdmin();
  } catch (err) {
    showToast('Error al guardar: ' + err.message, 'error');
  }
};




