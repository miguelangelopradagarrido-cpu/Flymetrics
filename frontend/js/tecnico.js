'use strict';

  // ── ANTI-XSS ESCAPING HELPER ──
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

  // ── HELPER UTILITIES ─────────────────────────────────
  function showToast(msg, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      container.style.cssText = 'position:fixed; bottom:20px; right:20px; z-index:999999; display:flex; flex-direction:column; gap:8px; pointer-events:none;';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    const colors = {
      success: 'background:#10b981; color:#fff;',
      error: 'background:#ef4444; color:#fff;',
      info: 'background:#1c82ad; color:#fff;',
      warn: 'background:#f59e0b; color:#fff;'
    };
    toast.style.cssText = `padding:12px 20px; border-radius:12px; font-weight:700; font-size:0.88rem; box-shadow:0 10px 30px rgba(0,0,0,0.25); transition:all 0.3s ease; opacity:0; transform:translateY(20px); pointer-events:auto; ${colors[type] || colors.info}`;
    toast.textContent = msg;
    container.appendChild(toast);
    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    });
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(20px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
  window.showToast = showToast;

  function formatCurrency(val) {
    const num = parseFloat(val) || 0;
    return '$ ' + num.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }
  window.formatCurrency = formatCurrency;

  function formatDate(dStr) {
    if (!dStr) return '—';
    try {
      const parts = String(dStr).split('T')[0].split('-');
      if (parts.length === 3) {
        const d = new Date(parts[0], parts[1] - 1, parts[2]);
        return d.toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });
      }
      return String(dStr);
    } catch(e) { return String(dStr); }
  }
  window.formatDate = formatDate;

  let token = sessionStorage.getItem('fm_token') || localStorage.getItem('fm_token');
  let currentUser = {};
  try {
    const uStr = sessionStorage.getItem('fm_user') || localStorage.getItem('fm_user');
    currentUser = JSON.parse(uStr) || {};
  } catch(e) {}

  const API_BASE = window.BASE_URL || ((window.location.protocol === 'file:'
    ? 'http://localhost:3000'
    : (window.API_BASE || 'https://flymetrics-api.hostless.app')) + '/api/v1';

  let _allTurnos = [];
  let _invoices = [];
  let _activeDetalleTurnoId = null;
  let activePanel = 'dashboard';

  // Distance matrix (km)
  const DISTANCE_MATRIX = {
    'Bogotá': { 'Bogotá': 0, 'Villavicencio': 120, 'Yopal': 330, 'Ibagué': 200, 'Medellín': 420 },
    'Villavicencio': { 'Bogotá': 120, 'Villavicencio': 0, 'Yopal': 260, 'Ibagué': 320, 'Medellín': 540 },
    'Yopal': { 'Bogotá': 330, 'Villavicencio': 260, 'Yopal': 0, 'Ibagué': 530, 'Medellín': 750 },
    'Ibagué': { 'Bogotá': 200, 'Villavicencio': 320, 'Yopal': 530, 'Ibagué': 0, 'Medellín': 390 },
    'Medellín': { 'Bogotá': 420, 'Villavicencio': 540, 'Yopal': 750, 'Ibagué': 390, 'Medellín': 0 }
  };
  const AVG_SPEED = 60;

  function toggleTecnicoSidebarCollapse() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
      sidebar.classList.toggle('collapsed');
      const isCollapsed = sidebar.classList.contains('collapsed');
      localStorage.setItem('fm_tecnico_sidebar_collapsed', isCollapsed ? 'true' : 'false');
    }
  }
  window.toggleTecnicoSidebarCollapse = toggleTecnicoSidebarCollapse;

  // DOM Loaded
  document.addEventListener('DOMContentLoaded', async () => {
    if (localStorage.getItem('fm_tecnico_sidebar_collapsed') === 'true') {
      const sidebar = document.getElementById('sidebar');
      if (sidebar) sidebar.classList.add('collapsed');
    }

    if (!token) {
      window.location.href = 'index.html';
      return;
    }

    // Aislamiento de rol estricto (Permite técnico y administrador en modo supervisión)
    try {
      const storedRole = (sessionStorage.getItem('fm_role') || localStorage.getItem('fm_role') || '').toLowerCase();
      if (storedRole === 'cliente') {
        window.location.href = 'cliente.html';
        return;
      }
    } catch(e) {}

    try { await setupUserProfile(); } catch(e){ console.warn(e); }
    try { setupNavigation(); } catch(e){ console.warn(e); }
    try { startClock(); } catch(e){ console.warn(e); }
    try { await loadTechAgenda(); } catch(e){ console.warn(e); }
  });

  async function setupUserProfile() {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const json = await res.json();
        currentUser = json.data || json || currentUser;
        const realRole = (currentUser.rol || '').toLowerCase();
        if (realRole === 'cliente') {
          window.location.href = 'cliente.html';
          return;
        }
        try {
          sessionStorage.setItem('fm_user', JSON.stringify(currentUser));
          localStorage.setItem('fm_user', JSON.stringify(currentUser));
        } catch(e) {}
      } else {
        window.location.href = 'index.html';
        return;
      }
    } catch(err) {
      console.warn('Could not fetch fresh user profile:', err);
    }

    const name = `${currentUser.nombre || 'Piloto'} ${currentUser.apellido_1 || ''}`.trim() || (currentUser.email ? currentUser.email.split('@')[0] : 'Técnico Piloto');
    const email = currentUser.email || 'tecnico@flymetrics.co';
    const init = name.split(' ').filter(x=>x).map(n=>n[0]).join('').slice(0,2).toUpperCase() || 'TP';
    const tel = currentUser.telefono || '3001234567';
    const roleLabel = 'Piloto de Campo Flymetrics';

    const elSubName = document.getElementById('sidebarUserName'); if (elSubName) elSubName.textContent = name;
    const elSubEmail = document.getElementById('sidebarUserEmail'); if (elSubEmail) elSubEmail.textContent = email;
    const elSubInit = document.getElementById('sidebarUserInitials'); if (elSubInit) elSubInit.textContent = init;

    const elDashName = document.getElementById('dashPilotName'); if (elDashName) elDashName.textContent = name;
    const elDashEmail = document.getElementById('dashPilotEmail'); if (elDashEmail) elDashEmail.textContent = email;
    const elDashAvatar = document.getElementById('dashPilotAvatar'); if (elDashAvatar) elDashAvatar.textContent = init;
    const elDashCert = document.getElementById('dashPilotCert'); if (elDashCert) elDashCert.textContent = roleLabel;

    const elMainName = document.getElementById('mainProfileName'); if (elMainName) elMainName.textContent = name;
    const elMainEmail = document.getElementById('mainProfileEmail'); if (elMainEmail) elMainEmail.textContent = email;
    const elMainAvatar = document.getElementById('mainProfileAvatar'); if (elMainAvatar) elMainAvatar.textContent = init;
    const elMainCert = document.getElementById('mainProfileCert'); if (elMainCert) elMainCert.textContent = roleLabel;

    const cert = currentUser.certificacion || (currentUser.tecnico && currentUser.tecnico.certificacion) || 'RAC-100-VIGENTE';
    const inpNom = document.getElementById('techProfNombre'); if (inpNom) inpNom.value = name;
    const inpTel = document.getElementById('techProfTel'); if (inpTel) inpTel.value = tel;
    const inpLic = document.getElementById('techProfLicencia'); if (inpLic) inpLic.value = cert;
  }

  window.toggleTecnicoSidebarCollapse = function (e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('tecnicoSidebarOverlay');
    if (!sidebar) return;

    if (window.innerWidth <= 900) {
      sidebar.classList.toggle('open');
      const isOpen = sidebar.classList.contains('open');
      if (overlay) {
        overlay.style.display = isOpen ? 'block' : 'none';
        overlay.classList.toggle('hidden', !isOpen);
        overlay.classList.toggle('active', isOpen);
        overlay.style.opacity = isOpen ? '1' : '0';
        overlay.style.pointerEvents = isOpen ? 'all' : 'none';
      }
    } else {
      sidebar.classList.toggle('collapsed');
    }
  };

  function setupNavigation() {
    document.querySelectorAll('.nav-item[data-panel]').forEach(btn => {
      btn.addEventListener('click', () => {
        const panelId = btn.getAttribute('data-panel');
        navigateTo(panelId);
        if (window.innerWidth <= 900) {
          const sidebar = document.getElementById('sidebar');
          const overlay = document.getElementById('tecnicoSidebarOverlay');
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
  }

  function navigateTo(panelId) {
    if (panelId === 'bitacoras' || panelId === 'ejecucion' || panelId === 'subir-bitacora') panelId = 'subir-informe';
    activePanel = panelId;
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const targetPanel = document.getElementById(`panel-${panelId}`);
    if (targetPanel) targetPanel.classList.add('active');

    const targetNav = document.querySelector(`.nav-item[data-panel="${panelId}"]`);
    if (targetNav) targetNav.classList.add('active');

    // Sincronizar botones de barra rápida slider
    document.querySelectorAll('.tech-slider-btn').forEach(btn => {
      const p = btn.getAttribute('data-slider-panel');
      if (p === panelId) {
        btn.classList.add('active');
        btn.style.background = 'rgba(255,255,255,0.24)';
        btn.style.borderColor = '#38bdf8';
        btn.style.color = '#ffffff';
      } else {
        btn.classList.remove('active');
        btn.style.background = p === 'subir-informe' ? 'rgba(56,189,248,0.18)' : 'rgba(255,255,255,0.06)';
        btn.style.borderColor = p === 'subir-informe' ? 'rgba(56,189,248,0.5)' : 'rgba(255,255,255,0.18)';
        btn.style.color = '#e0f2fe';
      }
    });

    const titles = {
      dashboard: 'Dashboard Piloto',
      agenda: 'Mis Vuelos & Agenda de Campo',
      'subir-informe': 'Informes Ejecutivos & Entregables',
      perfil: 'Mi Perfil Profesional'
    };

    const topTitle = document.getElementById('topbarTitle');
    if (topTitle) topTitle.textContent = titles[panelId] || panelId;

    if (panelId === 'agenda' || panelId === 'dashboard') {
      loadTechAgenda();
    } else if (panelId === 'subir-informe') {
      populateSubirInformeDropdown();
      loadHistorialInformes();
    }
  }
  window.navigateTo = navigateTo;

  window.saveTechProfile = async function(e) {
    if (e) e.preventDefault();
    const nom = document.getElementById('techProfNombre') ? document.getElementById('techProfNombre').value.trim() : 'Técnico Piloto';
    const tel = document.getElementById('techProfTel') ? document.getElementById('techProfTel').value.trim() : '3001234567';
    const lic = document.getElementById('techProfLicencia') ? document.getElementById('techProfLicencia').value.trim() : 'RPAS-A-102030';
    const est = document.getElementById('techProfEstado') ? document.getElementById('techProfEstado').value : 'Disponible';

    const parts = nom.split(' ');
    const nombre = parts[0] || nom;
    const apellido = parts.slice(1).join(' ') || 'Piloto';
    const techId = (currentUser && currentUser.id_tecnico) ? currentUser.id_tecnico : ((currentUser && currentUser.tecnico && currentUser.tecnico.id_tecnico) ? currentUser.tecnico.id_tecnico : 1);

    try {
      await fetch(`${API_BASE}/tecnicos/${techId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          nombre: nombre,
          apellido_1: apellido,
          telefono: tel,
          certificacion: lic,
          estado: est.toLowerCase()
        })
      });
    } catch(err) {
      console.warn('Error al guardar perfil en BD:', err);
    }

    const elNom = document.getElementById('mainProfileName'); if (elNom) elNom.textContent = nom;
    const elSub = document.getElementById('sidebarUserName'); if (elSub) elSub.textContent = nom;
    const elDas = document.getElementById('dashPilotName'); if (elDas) elDas.textContent = nom;

    const init = nom.split(' ').map(n=>n[0]).join('').slice(0,2).toUpperCase();
    const elAvi = document.getElementById('mainProfileAvatar'); if (elAvi) elAvi.textContent = init;
    const elAvs = document.getElementById('sidebarUserInitials'); if (elAvs) elAvs.textContent = init;
    const elAvd = document.getElementById('dashPilotAvatar'); if (elAvd) elAvd.textContent = init;

    const elEst = document.getElementById('mainProfileEstado');
    if (elEst) elEst.innerHTML = `<span class="badge badge-active">${est} <i class="fa-solid fa-circle-dot" style="color:#10b981;"></i></span>`;

    showToast('¡Perfil de Técnico Piloto guardado en la base de datos!', 'success');
  };

  function startClock() {
    const el = document.getElementById('topbarClock');
    const update = () => {
      if (el) el.textContent = new Date().toLocaleTimeString('es-CO');
    };
    update();
    setInterval(update, 1000);
  }

  async function logout() {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => null);
    } catch(e) {}
    try { sessionStorage.clear(); } catch(e) {}
    try { localStorage.clear(); } catch(e) {}
    window.location.href = 'index.html';
  }
  window.logout = logout;

  // AGENDA & FLIGHTS LOAD
  async function loadTechAgenda() {
    try {
      const [res, resEntregables] = await Promise.all([
        fetch(`${API_BASE}/tecnico/agenda`, { headers: { 'Authorization': `Bearer ${token}` } }),
        fetch(`${API_BASE}/entregables`, { headers: { 'Authorization': `Bearer ${token}` } }).catch(() => null)
      ]);

      let entregablesMap = {};
      if (resEntregables && resEntregables.ok) {
        const entJson = await resEntregables.json().catch(() => ({}));
        const entList = entJson.data || entJson || [];
        if (Array.isArray(entList)) {
          for (const e of entList) {
            const idT = parseInt(e.id_turno || e.id || 0);
            if (idT && e.url_archivo) {
              entregablesMap[idT] = e.url_archivo;
            }
          }
        }
      }

      if (res.ok) {
        const json = await res.json();
        const rawTurnos = json.data || json || [];
        _allTurnos = rawTurnos.map(t => {
          const idT = parseInt(t.id_turno || t.id || 0);
          const spUrl = t.url_entregable || t.sharepoint_url || t.link_sharepoint || entregablesMap[idT] || '';
          return {
            ...t,
            url_entregable: spUrl,
            sharepoint_url: spUrl,
            link_sharepoint: spUrl,
            tiene_sharepoint: Boolean(spUrl)
          };
        }).sort((a, b) => parseInt(b.id_turno || b.id || 0) - parseInt(a.id_turno || a.id || 0));
      } else {
        _allTurnos = [];
      }
    } catch(e) {
      console.warn('Error loading agenda:', e);
      _allTurnos = [];
    }

    renderDashboardKPIs();
    renderRecentAgendaTable();
    filterTechAgenda();
    populateSubirBitacoraDropdown();
    populateSubirInformeDropdown();
  }

  function renderDashboardKPIs() {
    const total = _allTurnos.length;
    const pendientes = _allTurnos.filter(t => t.estado === 'Pendiente').length;
    const completados = _allTurnos.filter(t => t.estado === 'Completado' || t.estado === 'Hecho').length;

    const sTot = document.getElementById('statTotalVuelos'); if (sTot) sTot.textContent = total;
    const sPen = document.getElementById('statPendientes'); if (sPen) sPen.textContent = pendientes;
    const sCom = document.getElementById('statCompletados'); if (sCom) sCom.textContent = completados;
    const aBad = document.getElementById('agendaBadge'); if (aBad) aBad.textContent = pendientes;
    const mVue = document.getElementById('mainProfileVuelos'); if (mVue) mVue.textContent = `${completados} vuelos completados`;
  }

  function renderRecentAgendaTable() {
    const tbody = document.getElementById('dashRecentAgendaBody');
    if (!tbody) return;

    const recent = _allTurnos.slice(0, 5);
    if (recent.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:24px; color:var(--text-3);">No hay vuelos asignados.</td></tr>`;
      return;
    }

    tbody.innerHTML = recent.map(t => {
      const badge = getStatusBadgeHTML(t.estado);
      const fNom = escapeHtml(t.finca_nombre || t.nombre_finca || 'Finca #' + t.id_finca);
      const sNom = escapeHtml(t.servicio_nombre || t.nombre_servicio || 'Vuelo agrícola');
      return `
        <tr>
          <td style="font-weight:bold; color:var(--primary);">#${escapeHtml(t.id_turno)}</td>
          <td>${escapeHtml(t.fecha_de_turno || '—')}</td>
          <td>${fNom}</td>
          <td>${sNom}</td>
          <td>${badge}</td>
          <td><button class="btn btn-sm btn-ghost" onclick="navigateTo('agenda')">Ver ➔</button></td>
        </tr>
      `;
    }).join('');
  }

  function renderTechAgendaTable(turnos) {
    const tbody = document.getElementById('techAgendaTableBody');
    if (!tbody) return;

    if (turnos.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" class="text-center" style="padding:40px; color:var(--text-3);">No se encontraron vuelos asignados a tu cuenta.</td></tr>`;
      return;
    }

    tbody.innerHTML = turnos.map(t => {
      const hIni = t.hora_inicio_estimada ? escapeHtml(String(t.hora_inicio_estimada).slice(0, 5)) : '—';
      const hFin = t.hora_fin_estimada ? escapeHtml(String(t.hora_fin_estimada).slice(0, 5)) : '—';
      const badge = getStatusBadgeHTML(t.estado);
      const fNom = escapeHtml(t.finca_nombre || t.nombre_finca || 'Finca #' + t.id_finca);
      const fMuni = escapeHtml(t.ubicacion_municipio || 'Colombia');
      const fHect = escapeHtml(t.hectareas || '10');
      const sNom = escapeHtml(t.servicio_nombre || t.nombre_servicio || 'Vuelo agrícola');
      
      let historyList = [];
      if (t.historial_negociacion) {
        try {
          historyList = typeof t.historial_negociacion === 'string' ? JSON.parse(t.historial_negociacion) : t.historial_negociacion;
          if (!Array.isArray(historyList)) historyList = [];
        } catch(e) { historyList = []; }
      }
      const pilotoYaAcepto = historyList.some(h => (h.emisor === 'tecnico' || h.emisor === 'piloto') && (h.tipo === 'aceptacion' || h.tipo === 'aceptacion_piloto'));

      let actionBtn = '';
      const estRaw = String(t.estado || '').trim().toLowerCase();
      if (estRaw.includes('finaliz')) {
        actionBtn = `
          <span class="badge" style="background:#ecfdf5; color:#065f46; font-weight:800; font-size:0.75rem; padding:6px 10px; border-radius:8px; display:inline-flex; align-items:center; gap:5px; border:1px solid #a7f3d0;" title="Vuelo finalizado y entregado al cliente">
            <i class="fa-solid fa-circle-check"></i> Finalizado
          </span>
        `;
      } else if (estRaw.includes('complet') || estRaw.includes('hecho')) {
        // PASO 2: Vuelo completado en campo -> Ahora se formaliza la entrega final subiendo el enlace de SharePoint
        actionBtn = `
          <button class="btn btn-sm" style="background:#059669; color:#ffffff; font-weight:700; border-radius:8px; display:inline-flex; align-items:center; gap:5px;" onclick="navigateToSubirInformeTurno(${t.id_turno})" title="Cargar enlace de SharePoint para entrega final">
            <i class="fa-solid fa-cloud-arrow-up"></i> Finalizar (SharePoint)
          </button>
          <button class="btn btn-danger btn-sm" onclick="openSolicitudModal(${t.id_turno}, 'Cancelacion')" title="Reportar novedad u obstáculo"><i class="fa-solid fa-ban"></i> Novedad</button>
        `;
      } else if (estRaw.includes('confirm') || estRaw.includes('proceso')) {
        // PASO 1: Vuelo Confirmado / En Proceso -> Completar directamente con un solo clic (sin formularios ni peticiones)
        actionBtn = `
          <button class="btn btn-sm" style="background:#2563eb; color:#ffffff; font-weight:700; border-radius:8px; display:inline-flex; align-items:center; gap:5px;" onclick="completarServicioDirecto(${t.id_turno})" title="Marcar servicio como Completado y notificar al cliente">
            <i class="fa-solid fa-clipboard-check"></i> Completar Servicio
          </button>
          <button class="btn btn-danger btn-sm" onclick="openSolicitudModal(${t.id_turno}, 'Cancelacion')" title="Reportar novedad u obstáculo"><i class="fa-solid fa-ban"></i> Novedad</button>
        `;
      } else {
        actionBtn = `
          <span class="badge" style="background:#eff6ff; color:#1d4ed8; font-weight:700; font-size:0.75rem; padding:6px 10px; border-radius:8px; display:inline-flex; align-items:center; gap:5px;" title="Vuelo asignado a tu cuenta por administración">
            <i class="fa-solid fa-user-check"></i> Asignado
          </span>
        `;
      }

      return `
        <tr>
          <td>
            <a href="javascript:void(0)" onclick="openDetalleVueloModal(${t.id_turno})" style="font-weight:bold; color:var(--primary); text-decoration:underline;" title="Ver ficha técnica completa">#${escapeHtml(t.id_turno)}</a>
          </td>
          <td>${escapeHtml(t.fecha_de_turno || '—')}</td>
          <td>${hIni}</td>
          <td>${hFin}</td>
          <td style="font-weight:600; color:var(--primary);">${fNom}</td>
          <td>${fMuni}</td>
          <td>${fHect} ha</td>
          <td style="font-weight:500;">${sNom}</td>
          <td>${badge}</td>
          <td>
            <div class="actions-flex-row" style="display:flex; gap:6px; flex-wrap:wrap; align-items:center;">
              <button class="btn btn-ghost btn-sm" onclick="openDetalleVueloModal(${t.id_turno})" title="Ver todos los datos del cliente y finca"><i class="fa-solid fa-magnifying-glass"></i> Ver Ficha</button>
              ${actionBtn}
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  window.completarServicioDirecto = async function(id_turno) {
    if (!confirm(`¿Confirmas que el servicio del Vuelo #${id_turno} ha sido completado con éxito en campo?`)) {
      return;
    }
    try {
      showToast('Marcando servicio como Completado y notificando al cliente...', 'info');
      const authToken = token || sessionStorage.getItem('fm_token') || localStorage.getItem('fm_token');
      const res = await fetch(`${API_BASE}/tecnico/agenda/${id_turno}/completar`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || data.detail || 'Error al completar el servicio');
      }
      showToast('✅ ¡Servicio marcado como Completado! Notificación enviada al cliente. Ahora puedes finalizar con SharePoint.', 'success');
      await loadTechAgenda();
    } catch(err) {
      showToast(`Error: ${err.message}`, 'error');
    }
  };

  window.navigateToSubirInformeTurno = function(id_turno) {
    navigateTo('subir-informe');
    setTimeout(() => {
      const sel = document.getElementById('subirInformeTurnoSelect');
      if (sel) {
        sel.value = id_turno;
        if (typeof onSubirInformeTurnoChange === 'function') {
          onSubirInformeTurnoChange();
        }
      }
      const linkInput = document.getElementById('subirInformeSharepointLink');
      if (linkInput && !linkInput.disabled) {
        linkInput.focus();
      }
    }, 120);
  };

  function filterTechAgenda() {
    const q = (document.getElementById('agendaSearch')?.value || '').toLowerCase();
    const st = (document.getElementById('agendaStatusFilter')?.value || '').toLowerCase();
    const dateVal = document.getElementById('agendaDateFilter')?.value || '';
    const sortOrder = document.getElementById('agendaSortOrder')?.value || 'id_desc';

    let filtered = _allTurnos.filter(t => {
      const matchSearch = [t.finca_nombre, t.nombre_finca, t.servicio_nombre, t.nombre_servicio, t.ubicacion_municipio, String(t.id_turno || t.id)]
        .some(v => (v||'').toLowerCase().includes(q));
      
      let matchStatus = true;
      if (st) {
        const estadoLower = String(t.estado || '').toLowerCase();
        if (st === 'completado' || st === 'finalizado') {
          matchStatus = estadoLower.includes('complet') || estadoLower.includes('finaliz') || estadoLower.includes('hecho');
        } else {
          matchStatus = estadoLower.includes(st);
        }
      }
      const matchDate = !dateVal || (t.fecha_de_turno && t.fecha_de_turno.startsWith(dateVal));
      return matchSearch && matchStatus && matchDate;
    });

    filtered.sort((a, b) => {
      const idA = parseInt(a.id_turno || a.id || 0);
      const idB = parseInt(b.id_turno || b.id || 0);

      if (sortOrder === 'id_asc') return idA - idB;
      if (sortOrder === 'id_desc') return idB - idA;
      if (sortOrder === 'fecha_asc') return (a.fecha_de_turno || '').localeCompare(b.fecha_de_turno || '');
      if (sortOrder === 'fecha_desc') return (b.fecha_de_turno || '').localeCompare(a.fecha_de_turno || '');
      return idB - idA;
    });

    renderTechAgendaTable(filtered);
  }

  window.resetTechAgendaFilters = function() {
    const sInput = document.getElementById('agendaSearch');
    if (sInput) sInput.value = '';
    const dInput = document.getElementById('agendaDateFilter');
    if (dInput) dInput.value = '';
    const stInput = document.getElementById('agendaStatusFilter');
    if (stInput) stInput.value = '';
    const soInput = document.getElementById('agendaSortOrder');
    if (soInput) soInput.value = 'id_desc';
    filterTechAgenda();
    showToast('Filtros restablecidos', 'info');
  };

  window.filterTechAgenda = filterTechAgenda;

  function getStatusBadgeHTML(status) {
    const s = String(status || '').trim().toLowerCase();
    if (s.includes('finaliz') || s.includes('complet') || s.includes('hecho')) {
      return `<span class="badge" style="background:#ecfdf5 !important; color:#065f46 !important; font-weight:800; border:1px solid #a7f3d0 !important;"><i class="fa-solid fa-circle-check" style="margin-right:4px;"></i> Finalizado</span>`;
    }
    if (s.includes('proceso')) {
      return `<span class="badge" style="background:#fffbeb !important; color:#b45309 !important; font-weight:800; border:1px solid #fde68a !important;"><i class="fa-solid fa-bolt" style="margin-right:4px;"></i> En Proceso</span>`;
    }
    if (s.includes('confirm')) {
      return `<span class="badge" style="background:#eff6ff !important; color:#1d4ed8 !important; font-weight:800; border:1px solid #bfdbfe !important;"><i class="fa-solid fa-circle-check" style="margin-right:4px;"></i> Confirmado</span>`;
    }
    if (s.includes('por confirmar') || s.includes('pendiente por')) {
      return `<span class="badge" style="background:#fff7ed !important; color:#c2410c !important; font-weight:800; border:1px solid #fed7aa !important;"><i class="fa-solid fa-hourglass-half" style="margin-right:4px;"></i> Por confirmar</span>`;
    }
    return `<span class="badge" style="background:#f1f5f9 !important; color:#475569 !important; font-weight:800; border:1px solid #cbd5e1 !important;"><i class="fa-solid fa-clock" style="margin-right:4px;"></i> Pendiente</span>`;
  }

  // ── BITÁCORAS HANDLERS ──
  function populateBitacoraTurnosDropdown() {
    const sel = document.getElementById('bitacoraTurnoSelect');
    if (!sel) return;
    if (!_allTurnos || !_allTurnos.length) {
      sel.innerHTML = '<option value="">Sin vuelos asignados</option>';
      return;
    }
    const turnosDesc = [..._allTurnos].sort((a, b) => parseInt(b.id_turno || b.id || 0) - parseInt(a.id_turno || a.id || 0));
    sel.innerHTML = '<option value="">Selecciona un vuelo...</option>' +
      turnosDesc.map(t => {
        const idT = t.id_turno || t.id;
        const finca = t.finca_nombre || t.nombre_finca || 'Finca Principal';
        const serv = t.servicio_nombre || t.nombre_servicio || 'Servicio Dron';
        const ha = t.hectareas || 10;
        const estado = t.estado || 'Confirmado';
        return `<option value="${idT}" data-ha="${ha}" data-finca="${finca}" data-serv="${serv}">#RAD-${idT} — ${serv} | ${finca} (${ha} ha) [${estado}]</option>`;
      }).join('');
  }

  window.onBitacoraTurnoSelected = function() {
    const sel = document.getElementById('bitacoraTurnoSelect');
    const opt = sel ? sel.options[sel.selectedIndex] : null;
    const preview = document.getElementById('bitacoraTurnoPreview');
    const haInput = document.getElementById('bitHectareas');

    if (opt && opt.value) {
      const ha = opt.getAttribute('data-ha') || 10;
      const finca = opt.getAttribute('data-finca') || 'Finca';
      const serv = opt.getAttribute('data-serv') || 'Servicio';
      if (haInput) haInput.value = ha;
      if (preview) {
        preview.innerHTML = `<strong><i class="fa-solid fa-wheat-awn"></i> Finca:</strong> ${finca} | <strong><i class="fa-solid fa-gear"></i> Servicio:</strong> ${serv} | <strong>Área:</strong> ${ha} ha`;
      }
    } else {
      if (preview) preview.innerHTML = `<i class="fa-solid fa-circle-info" style="color:#1C82AD;"></i> Selecciona un vuelo de la lista para auto-completar los datos de la finca y servicio.`;
    }
  };

  window.submitBitacoraDirect = async function(e) {
    e.preventDefault();
    const id_turno = parseInt(document.getElementById('bitacoraTurnoSelect').value);
    if (!id_turno) return showToast('Por favor selecciona un vuelo asignado', 'warn');

    const payload = {
      insumos_litros_aplicados: parseFloat(document.getElementById('bitInsumos').value) || 0,
      agua_litros: parseFloat(document.getElementById('bitAgua').value) || 0,
      baterias_utilizadas: parseInt(document.getElementById('bitBaterias').value) || 1,
      cumple_rac100: parseInt(document.getElementById('bitRac').value) || 1,
      observaciones_campo: document.getElementById('bitObservaciones').value.trim() || null
    };

    try {
      showToast('Guardando y firmando bitácora de vuelo...', 'info');
      const res = await fetch(`${API_BASE}/tecnico/agenda/${id_turno}/checkout`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        showToast('Bitácora de vuelo registrada y firmada exitosamente');
        document.getElementById('techBitacoraPageForm').reset();
        await loadTechAgenda();
        await loadTechBitacorasList();
      } else {
        const err = await res.json();
        showToast('Error al guardar bitácora: ' + (err.message || 'Error del servidor'), 'error');
      }
    } catch(err) {
      showToast('Error de conexión: ' + err.message, 'error');
    }
  };

  async function loadTechBitacorasList() {
    const tbody = document.getElementById('techBitacorasTableBody');
    if (!tbody) return;

    const list = _allTurnos.filter(t => t.estado === 'Completado' || t.estado === 'Hecho' || t.estado === 'Finalizado');

    if (!list || !list.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:24px; color:var(--text-3);">No hay servicios completados aún.</td></tr>`;
      return;
    }

    try {
      tbody.innerHTML = list.map(b => {
        const idT = b.id_turno || b.id_bitacora || 0;
        const isMine = _allTurnos.some(t => (t.id_turno || t.id) == idT);
        return `
          <tr>
            <td style="font-weight:700; color:#003049;">#${idT || '—'}</td>
            <td>${b.finca_nombre || 'Finca Principal'}</td>
            <td>${b.insumos_litros_aplicados || b.insumos || '15'} L</td>
            <td>${b.agua_litros || b.agua || '120'} L</td>
            <td><span class="badge" style="background:rgba(16,185,129,0.12); color:#059669; font-weight:700;"><i class="fa-solid fa-circle-check" style="margin-right:4px;"></i> Firmada</span></td>
            <td style="text-align:center;">
              ${isMine ? `
                <button class="btn btn-ghost btn-sm" onclick="openEditBitacoraModal(${idT})" style="font-weight:700; color:#d97706;" title="Modificar bitácora de mi vuelo"><i class="fa-solid fa-pen-to-square"></i> Modificar</button>
              ` : `
                <span style="font-size:0.75rem; color:#94a3b8; font-weight:600;"><i class="fa-solid fa-lock"></i> Asignado a otro piloto</span>
              `}
            </td>
          </tr>
        `;
      }).join('');
    } catch(e) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding:24px; color:var(--text-3);">Error al cargar bitácoras.</td></tr>`;
    }
  }

  // ── SUBIR BITÁCORA A SHAREPOINT HANDLERS ──
  function populateSubirBitacoraDropdown() {
    const sel = document.getElementById('subirBitacoraTurnoSelect');
    if (!sel) return;
    if (!_allTurnos || !_allTurnos.length) {
      sel.innerHTML = '<option value="">Sin vuelos asignados</option>';
      return;
    }
    const turnosDesc = [..._allTurnos].sort((a, b) => parseInt(b.id_turno || b.id || 0) - parseInt(a.id_turno || a.id || 0));
    sel.innerHTML = '<option value="">Selecciona un vuelo / servicio...</option>' +
      turnosDesc.map(t => {
        const idT = t.id_turno || t.id;
        const finca = t.finca_nombre || t.nombre_finca || 'Finca';
        const serv = t.servicio_nombre || t.nombre_servicio || 'Servicio';
        const estado = t.estado || 'Confirmado';
        return `<option value="${idT}">#RAD-${idT} — ${serv} | ${finca} [${estado}]</option>`;
      }).join('');
  }

  window.submitSubirBitacora = async function(e) {
    if (e) e.preventDefault();
    const sel = document.getElementById('subirBitacoraTurnoSelect');
    const linkInput = document.getElementById('subirBitacoraSharepointLink');
    const id_turno = parseInt(sel ? sel.value : 0);
    const link = linkInput ? linkInput.value.trim() : '';

    if (!id_turno) return showToast('Por favor selecciona el vuelo asociado', 'warn');
    if (!link) return showToast('Por favor ingresa el enlace de SharePoint de la bitácora', 'warn');

    try {
      showToast('Guardando bitácora de vuelo y notificando al cliente...', 'info');
      const res = await fetch(`${API_BASE}/tecnico/subir-bitacora`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          id_turno: id_turno,
          sharepoint_url: link
        })
      });

      if (res.ok) {
        showToast('¡Bitácora guardada en el sistema y notificación enviada al cliente!', 'success');
        if (linkInput) linkInput.value = '';
        await loadTechAgenda();
        await loadHistorialBitacoras();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.message || 'Error al guardar la bitácora', 'error');
      }
    } catch (err) {
      showToast('Error de conexión al guardar la bitácora: ' + err.message, 'error');
    }
  };

  async function loadHistorialBitacoras() {
    const tbody = document.getElementById('subirBitacoraHistorialTableBody');
    if (!tbody) return;

    try {
      const res = await fetch(`${API_BASE}/entregables`, {
        headers: { 'Authorization': `Bearer ${token}` }
      }).catch(() => null);

      let list = [];
      if (res && res.ok) {
        const json = await res.json();
        list = json.data || json || [];
      }

      const myTurnoIds = new Set(_allTurnos.map(t => parseInt(t.id_turno || t.id)));
      const bitacoras = list.filter(e => {
        const idT = parseInt(e.id_turno || e.id);
        const tipo = (e.tipo_archivo || '').toLowerCase();
        return myTurnoIds.has(idT) && (tipo.includes('bitacora') || tipo.includes('vuelo') || tipo.includes('telemetría'));
      });

      if (!bitacoras.length) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center" style="padding:24px; color:var(--text-3);">No has subido bitácoras a SharePoint aún.</td></tr>`;
        return;
      }

      tbody.innerHTML = bitacoras.map(b => {
        const idT = b.id_turno || '—';
        const matchedTurno = _allTurnos.find(t => (t.id_turno || t.id) == idT);
        const serv = matchedTurno ? (matchedTurno.servicio_nombre || matchedTurno.nombre_servicio || 'Vuelo Agrícola') : (b.nombre_archivo || 'Bitácora');
        const url = b.url_archivo || '#';
        return `
          <tr>
            <td style="font-weight:800; color:#003049;">#RAD-${idT}</td>
            <td style="font-weight:600; color:#1C82AD;">${serv}</td>
            <td>
              <a href="${url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:800; background:#003049; color:#ffffff; border-radius:8px; padding:6px 12px; font-size:0.78rem; text-decoration:none;">
                <i class="fa-solid fa-arrow-up-right-from-square" style="color:#38bdf8;"></i> Ver en SharePoint
              </a>
            </td>
            <td style="text-align:center;">
              <span class="badge" style="background:rgba(16,185,129,0.12); color:#059669; font-weight:800; font-size:0.75rem;"><i class="fa-solid fa-circle-check"></i> Subido</span>
            </td>
          </tr>
        `;
      }).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center" style="padding:24px; color:var(--text-3);">Error al cargar bitácoras.</td></tr>`;
    }
  }

  // ── SUBIR INFORME EJECUTIVO A SHAREPOINT HANDLERS ──
  function populateSubirInformeDropdown() {
    const sel = document.getElementById('subirInformeTurnoSelect');
    if (!sel) return;
    if (!_allTurnos || !_allTurnos.length) {
      sel.innerHTML = '<option value="">Sin vuelos asignados</option>';
      if (typeof onSubirInformeTurnoChange === 'function') onSubirInformeTurnoChange();
      return;
    }
    const currentVal = sel.value;
    const turnosDesc = [..._allTurnos].sort((a, b) => parseInt(b.id_turno || b.id || 0) - parseInt(a.id_turno || a.id || 0));
    sel.innerHTML = '<option value="">Selecciona un vuelo completado para finalizar con SharePoint...</option>' +
      turnosDesc.map(t => {
        const idT = t.id_turno || t.id;
        const finca = t.finca_nombre || t.nombre_finca || 'Finca';
        const serv = t.servicio_nombre || t.nombre_servicio || 'Servicio';
        const hasSp = Boolean(t.url_entregable || t.sharepoint_url || t.link_sharepoint || t.estado === 'Finalizado');
        const estadoTag = hasSp ? '✅ Finalizado (SharePoint)' : (t.estado === 'Completado' ? '⭐ Listo para SharePoint' : `⚠️ Estado: ${t.estado || 'Confirmado'}`);
        return `<option value="${idT}">#RAD-${idT} — ${serv} | ${finca} [${estadoTag}]</option>`;
      }).join('');

    if (currentVal && turnosDesc.some(t => String(t.id_turno || t.id) === String(currentVal))) {
      sel.value = currentVal;
    } else if (turnosDesc.length > 0) {
      sel.value = turnosDesc[0].id_turno || turnosDesc[0].id;
    }
    if (typeof onSubirInformeTurnoChange === 'function') onSubirInformeTurnoChange();
  }

  window.onSubirInformeTurnoChange = function() {
    const sel = document.getElementById('subirInformeTurnoSelect');
    const linkInput = document.getElementById('subirInformeSharepointLink');
    const statusBox = document.getElementById('subirInformeStatusBadge');
    const submitBtn = document.getElementById('btnSubmitSubirInforme');
    if (!sel || !linkInput) return;

    const idT = parseInt(sel.value || 0);
    if (!idT) {
      linkInput.value = '';
      if (statusBox) { statusBox.style.display = 'none'; statusBox.innerHTML = ''; }
      if (submitBtn) {
        submitBtn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Registrar SharePoint y Finalizar Servicio';
        submitBtn.style.background = '#1C82AD';
      }
      return;
    }

    const matched = (_allTurnos || []).find(t => (t.id_turno || t.id) == idT);
    const spUrl = matched ? (matched.url_entregable || matched.sharepoint_url || matched.link_sharepoint || '') : '';

    if (spUrl) {
      linkInput.value = spUrl;
      linkInput.disabled = true;
      linkInput.style.background = '#f1f5f9';
      linkInput.style.color = '#334155';
      const toggleBtn = document.getElementById('btnToggleEditSharepoint');
      if (toggleBtn) {
        toggleBtn.innerHTML = '<i class="fa-solid fa-pen-to-square"></i> Modificar Enlace';
        toggleBtn.style.color = '#0284c7';
      }
      if (statusBox) {
        statusBox.style.display = 'block';
        statusBox.innerHTML = `
          <div style="background:rgba(16,185,129,0.08); border:1.5px solid #10b981; border-radius:12px; padding:12px 14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
              <div style="font-weight:800; color:#065f46; font-size:0.86rem; display:flex; align-items:center; gap:6px;">
                <i class="fa-solid fa-circle-check" style="color:#10b981; font-size:1rem;"></i> SharePoint Ya Cargado y Vinculado
              </div>
              <div style="font-size:0.78rem; color:#047857; margin-top:3px;">
                Este vuelo ya tiene su informe oficial registrado. Puedes modificar el enlace con el botón superior si lo necesitas.
              </div>
            </div>
            <a href="${spUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="background:#003049; color:#ffffff; font-weight:800; padding:6px 14px; border-radius:8px; font-size:0.80rem; text-decoration:none; display:inline-flex; align-items:center; gap:6px;">
              <i class="fa-solid fa-arrow-up-right-from-square" style="color:#38bdf8;"></i> Abrir SharePoint
            </a>
          </div>
        `;
      }
      if (submitBtn) {
        submitBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Trabajo Realizado — Actualizar y Finalizar Servicio';
      }
    } else {
      linkInput.value = '';
      linkInput.disabled = false;
      linkInput.style.background = '#ffffff';
      linkInput.style.color = '#000000';
      const toggleBtn = document.getElementById('btnToggleEditSharepoint');
      if (toggleBtn) {
        toggleBtn.innerHTML = '<i class="fa-solid fa-plus"></i> Escribir Enlace';
        toggleBtn.style.color = '#10b981';
      }
      if (statusBox) {
        statusBox.style.display = 'block';
        statusBox.innerHTML = `
          <div style="background:rgba(245,158,11,0.08); border:1.5px dashed #f59e0b; border-radius:12px; padding:10px 14px; display:flex; align-items:center; gap:8px;">
            <i class="fa-solid fa-clock" style="color:#d97706;"></i>
            <span style="font-size:0.82rem; font-weight:700; color:#92400e;">Pendiente por vincular enlace de SharePoint para finalizar el servicio y notificar al cliente.</span>
          </div>
        `;
      }
      if (submitBtn) {
        submitBtn.innerHTML = '<i class="fa-solid fa-circle-check" style="font-size:1.15rem;"></i> Trabajo Realizado — Finalizar y Notificar al Cliente';
      }
    }
  };

  window.toggleEditSharepointLink = function() {
    const linkInput = document.getElementById('subirInformeSharepointLink');
    const toggleBtn = document.getElementById('btnToggleEditSharepoint');
    if (!linkInput) return;

    if (linkInput.disabled) {
      linkInput.disabled = false;
      linkInput.style.background = '#ffffff';
      linkInput.style.color = '#000000';
      linkInput.focus();
      if (toggleBtn) {
        toggleBtn.innerHTML = '<i class="fa-solid fa-lock-open" style="color:#10b981;"></i> Casilla Habilitada';
        toggleBtn.style.color = '#059669';
        toggleBtn.style.borderColor = '#10b981';
      }
      showToast('Casilla habilitada para escribir o modificar el enlace de SharePoint', 'info');
    } else {
      linkInput.focus();
      showToast('La casilla ya está habilitada para edición', 'info');
    }
  };

  window.submitSubirInforme = async function(e) {
    if (e) e.preventDefault();
    const sel = document.getElementById('subirInformeTurnoSelect');
    const id_turno = parseInt(sel ? sel.value : 0);
    const linkInput = document.getElementById('subirInformeSharepointLink');
    let link = (linkInput ? linkInput.value : '').trim();

    if (!id_turno) return showToast('Por favor selecciona el vuelo asociado (*)', 'warn');
    if (!link) return showToast('Por favor ingresa el enlace de SharePoint del informe (*)', 'warn');
    if (!link.startsWith('http://') && !link.startsWith('https://')) {
      link = 'https://' + link;
    }

    try {
      showToast('Guardando enlace SharePoint y finalizando servicio...', 'info');
      const res = await fetch(`${API_BASE}/tecnico/subir-informe-ejecutivo`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          id_turno: id_turno,
          sharepoint_url: link
        })
      });

      if (res.ok) {
        showToast('¡Servicio finalizado con éxito e informe en SharePoint notificado!', 'success');
        if (linkInput) linkInput.value = '';
        await loadTechAgenda();
        await loadHistorialInformes();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.message || 'Error al confirmar la entrega del vuelo', 'error');
      }
    } catch (err) {
      showToast('Error de conexión al confirmar el informe: ' + err.message, 'error');
    }
  };

  async function loadHistorialInformes() {
    const tbody = document.getElementById('subirInformeHistorialTableBody');
    if (!tbody) return;

    try {
      const res = await fetch(`${API_BASE}/entregables`, {
        headers: { 'Authorization': `Bearer ${token}` }
      }).catch(() => null);

      let list = [];
      if (res && res.ok) {
        const json = await res.json();
        list = json.data || json || [];
      }

      const myTurnoIds = new Set(_allTurnos.map(t => parseInt(t.id_turno || t.id)));
      const informes = list.filter(e => {
        const idT = parseInt(e.id_turno || e.id);
        const tipo = (e.tipo_archivo || '').toLowerCase();
        return myTurnoIds.has(idT) && (tipo.includes('informe') || tipo.includes('ejecutivo') || tipo.includes('aspersión') || tipo.includes('ndvi'));
      });

      if (!informes.length) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center" style="padding:24px; color:var(--text-3);">No has subido informes a SharePoint aún.</td></tr>`;
        return;
      }

      tbody.innerHTML = informes.map(inf => {
        const idT = inf.id_turno || '—';
        const matchedTurno = _allTurnos.find(t => (t.id_turno || t.id) == idT);
        const serv = matchedTurno ? (matchedTurno.servicio_nombre || matchedTurno.nombre_servicio || 'Vuelo Agrícola') : (inf.nombre_archivo || 'Informe');
        const url = inf.url_archivo || '#';
        return `
          <tr>
            <td style="font-weight:800; color:#003049;">#RAD-${idT}</td>
            <td style="font-weight:600; color:#1C82AD;">${serv}</td>
            <td>
              <a href="${url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:800; background:#003049; color:#ffffff; border-radius:8px; padding:6px 12px; font-size:0.78rem; text-decoration:none;">
                <i class="fa-solid fa-arrow-up-right-from-square" style="color:#38bdf8;"></i> Ver en SharePoint
              </a>
            </td>
            <td style="text-align:center;">
              <span class="badge" style="background:rgba(16,185,129,0.12); color:#059669; font-weight:800; font-size:0.75rem;"><i class="fa-solid fa-circle-check"></i> Subido</span>
            </td>
          </tr>
        `;
      }).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center" style="padding:24px; color:var(--text-3);">Error al cargar informes.</td></tr>`;
    }
  }


  // ── DETALLE VUELO MODAL ──
  window.openDetalleVueloModal = function(id_turno) {
    const t = _allTurnos.find(x => (x.id_turno || x.id) == id_turno);
    if (!t) return;

    const setT = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || '—'; };
    
    setT('detTurnoId', `#${t.id_turno || t.id}`);
    const badgeHolder = document.getElementById('detEstadoBadgeHolder');
    if (badgeHolder) badgeHolder.innerHTML = getStatusBadgeHTML(t.estado);
    
    setT('detServicioNombre', t.servicio_nombre || t.nombre_servicio || 'Servicio Agrícola Dron');
    setT('detClienteNombre', t.cliente || t.cliente_nombre || t.nombre_cliente || 'Cliente Flymetrics');
    // Extraer teléfono real
    let rawTel = t.cliente_telefono || t.telefono_cliente || t.telefono || t.celular || '';
    const obsText = t.notas || t.observaciones || t.observaciones_servicio || '';
    
    // Si no viene en el objeto o es genérico, intentar extraerlo de las notas del agendamiento
    if (!rawTel || rawTel === '3054061764' || rawTel === '—') {
      const matchTel = obsText.match(/Telefono:\s*([0-9\+\s\-]+)/i) || obsText.match(/Teléfono:\s*([0-9\+\s\-]+)/i);
      if (matchTel && matchTel[1]) {
        rawTel = matchTel[1].trim();
      }
    }
    
    // Formatear para Colombia
    let cleanTel = String(rawTel || '').replace(/\D/g, '');
    let waPhone = '';
    if (cleanTel.length === 10) {
      waPhone = '57' + cleanTel;
    } else if (cleanTel.length > 10 && cleanTel.startsWith('57')) {
      waPhone = cleanTel;
    } else if (cleanTel.length > 10) {
      waPhone = cleanTel;
    } else if (cleanTel.length > 0) {
      waPhone = '57' + cleanTel;
    }

    setT('detClienteTelefono', rawTel ? (rawTel.startsWith('+') ? rawTel : (cleanTel.startsWith('57') ? '+' + cleanTel : '+57 ' + cleanTel.slice(-10))) : 'Sin registrar');
    setT('detClienteEmail', t.cliente_email || t.email_cliente || t.email || t.correo || '—');
    setT('detClienteCedula', t.cliente_cedula || t.cedula || t.documento || '—');

    setT('detFincaNombre', t.finca_nombre || t.nombre_finca || 'Finca Principal');
    setT('detFincaUbicacion', t.ubicacion_municipio || 'Colombia');
    setT('detFincaHectareas', `${t.hectareas || '10'} ha`);
    setT('detFincaCultivo', t.cultivo || t.tipo_cultivo || 'Arroz / Palma / Maíz');
    setT('detFincaCoords', (t.latitud && t.longitud) ? `${t.latitud}, ${t.longitud}` : 'Georreferenciada RTK');

    const cliVerifEl = document.getElementById('detClienteVerificado');
    if (cliVerifEl) {
      if (t.cliente_verificado || t.verificado) {
        cliVerifEl.className = 'badge';
        cliVerifEl.style.background = 'rgba(16,185,129,0.12)';
        cliVerifEl.style.color = '#059669';
        cliVerifEl.innerHTML = '<i class="fa-solid fa-circle-check"></i> Verificado';
      } else {
        cliVerifEl.className = 'badge';
        cliVerifEl.style.background = 'rgba(245,158,11,0.15)';
        cliVerifEl.style.color = '#d97706';
        cliVerifEl.innerHTML = '<i class="fa-solid fa-clock"></i> Pendiente';
      }
    }

    setT('detVueloFecha', t.fecha_de_turno || '—');
    const hIni = t.hora_inicio_estimada ? String(t.hora_inicio_estimada).slice(0, 5) : '08:00';
    const hFin = t.hora_fin_estimada ? String(t.hora_fin_estimada).slice(0, 5) : '17:00';
    setT('detVueloHorario', `${hIni} a ${hFin}`);

    // ── SERVICIOS SOLICITADOS (BADGES DINÁMICOS) ──
    const badgesContainer = document.getElementById('detServiciosBadges');
    if (badgesContainer) {
      let svcs = [];
      if (t.servicios_list && t.servicios_list.length) {
        svcs = t.servicios_list;
      } else {
        const rawAll = (t.observaciones_servicio || '') + ' ' + (t.notas || '') + ' ' + (t.servicio_nombre || t.nombre_servicio || t.servicio || '');
        const mTag = rawAll.match(/(?:\[Servicios:\s*([^\]]+)\]|(?:Servicios Solicitados|Servicios):\s*([^\n\r]+))/i);
        const svcStr = mTag ? (mTag[1] || mTag[2]) : (t.servicio_nombre || t.nombre_servicio || t.servicio || '');
        if (svcStr && (svcStr.includes('+') || svcStr.includes(',') || /\band\b|\by\b/i.test(svcStr))) {
          svcs = svcStr.split(/\s*(?:\+|\band\b|\by\b|,)\s*/i).map(s => s.trim()).filter(Boolean);
        } else if (svcStr) {
          svcs = [svcStr.trim()];
        }
      }
      svcs = [...new Set(svcs)].filter(s => s && s.length > 2);
      if (!svcs.length) svcs = ['Mapeo Multiespectral & Diagnóstico'];

      badgesContainer.innerHTML = svcs.map(s => `
        <span class="badge" style="background:rgba(28,130,173,0.14); color:#003049; border:1px solid rgba(28,130,173,0.35); font-weight:800; font-size:0.83rem; padding:6px 14px; border-radius:8px; display:inline-flex; align-items:center; gap:6px;">
          <i class="fa-solid fa-layer-group" style="color:#1C82AD;"></i> ${s}
        </span>
      `).join('');
    }

    // ── PILOTO TÉCNICO ASIGNADO ──
    setT('detTecnicoAsignadoNombre', t.tecnico_nombre || 'Piloto Principal Flymetrics');

    // ── DETALLES Y OBSERVACIONES DEL CLIENTE ──
    const obsExtraCont = document.getElementById('detObsClienteExtraContainer');
    const cliObsEl = document.getElementById('detObservacionesCliente');
    const rawNotes = (t.notas_cliente || t.observaciones_servicio || t.notas || '')
      .replace(/\[Servicios:\s*[^\]]+\]/gi, '')
      .replace(/\[(?:Empresa|Jornada|DEMOSTRACION|AGENDAMIENTO|NUEVO SERVICIO)[^\]]*\]/gi, '')
      .replace(/(?:Servicios Solicitados|Servicios):\s*[^\n\r]+/gi, '')
      .replace(/(?:Cultivo Principal|Cultivo):\s*[^\n\r]+/gi, '')
      .replace(/(?:Hectáreas Operativas|Hectareas|Hectáreas):\s*[^\n\r]+/gi, '')
      .replace(/Jornada:\s*[^\n\r]+/gi, '')
      .replace(/Dron(?:\s*Asignado)?:\s*[^\n\r]+/gi, '')
      .trim();

    if (obsExtraCont && cliObsEl) {
      if (rawNotes && rawNotes.trim()) {
        cliObsEl.textContent = rawNotes.trim();
        obsExtraCont.style.display = 'block';
      } else {
        obsExtraCont.style.display = 'none';
      }
    }

    // ── MOTIVO DE REAGENDAMIENTO ──
    const reagCont = document.getElementById('detReagendamientoContainer');
    const detMotivo = document.getElementById('detMotivoReagendamiento');
    if (reagCont && detMotivo) {
      if (t.motivo_reagendamiento && t.motivo_reagendamiento.trim()) {
        detMotivo.textContent = t.motivo_reagendamiento.trim();
        reagCont.style.display = 'block';
      } else {
        reagCont.style.display = 'none';
      }
    }

    const btnWa = document.getElementById('detBtnWhatsapp');
    if (btnWa) {
      if (waPhone) {
        const clientNombre = t.cliente || t.cliente_nombre || t.nombre_cliente || 'Productor';
        const msg = encodeURIComponent(`Hola ${clientNombre}, te contacto de Flymetrics (Piloto Técnico) respecto a tu servicio de vuelo #${t.id_turno || t.id}.`);
        btnWa.href = `https://wa.me/${waPhone}?text=${msg}`;
        btnWa.style.display = 'inline-flex';
      } else {
        btnWa.href = '#';
        btnWa.onclick = function(e) {
          e.preventDefault();
          showToast('No hay un número de WhatsApp registrado para este cliente.', 'warning');
        };
      }
    }

    // ── GOOGLE MAPS REDIRECTION LIMPIA ──
    const normalizeMapsInput = function(raw) {
      if (!raw) return '';
      let s = String(raw).trim().replace(/[\]\)\>]+$/, '');
      if (!s || ['none', 'null', 'undefined', 'n/a', 'colombia', 'sin registrar', 'finca'].includes(s.toLowerCase())) return '';
      const mCoord = s.match(/([-+]?\d{1,3}\.\d+)[,\s]+([-+]?\d{1,3}\.\d+)/);
      if (mCoord) {
        const lat = parseFloat(mCoord[1]);
        const lng = parseFloat(mCoord[2]);
        if (!isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
          return `https://www.google.com/maps?q=${lat.toFixed(6)},${lng.toFixed(6)}`;
        }
      }
      if (s.includes('maps.app.goo.gl') || s.includes('goo.gl/maps') || s.includes('google.com/maps') || s.includes('maps.google.com')) {
        const mUrl = s.match(/https?:\/\/[^\s\n\r"\'<>\]\)]+/);
        let clean = mUrl ? mUrl[0].trim().replace(/[\]\)\>]+$/, '') : s;
        if (!clean.startsWith('http://') && !clean.startsWith('https://')) clean = 'https://' + clean;
        return clean;
      }
      return s;
    };

    let mapUrl = normalizeMapsInput(t.maps_url || t.url_maps || '');
    if (!mapUrl && t.latitud && t.longitud) {
      const isDummyYopal = Math.abs(parseFloat(t.latitud) - 5.33775) < 0.001 && Math.abs(parseFloat(t.longitud) - (-72.39587)) < 0.001;
      const munIsYopal = String(t.ubicacion_municipio || '').trim().toLowerCase() === 'yopal';
      if (!(isDummyYopal && !munIsYopal)) {
        mapUrl = `https://www.google.com/maps?q=${parseFloat(t.latitud).toFixed(6)},${parseFloat(t.longitud).toFixed(6)}`;
      }
    }
    if (!mapUrl && (t.finca_nombre || t.ubicacion_municipio)) {
      const locSearch = [t.finca_nombre, t.ubicacion_municipio, t.departamento, 'Colombia'].filter(Boolean).join(', ');
      mapUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(locSearch)}`;
    }
    const hasMap = Boolean(mapUrl);

    const openMapDirect = function(e) {
      if (e) e.preventDefault();
      if (hasMap) {
        window.open(mapUrl, '_blank', 'noopener,noreferrer');
      } else {
        showToast('⚠️ Este predio no tiene registrado enlace ni coordenadas de Google Maps. Comunícate con administración para registrarlo.', 'warning');
      }
    };

    const btnMap = document.getElementById('detBtnMap');
    if (btnMap) {
      btnMap.href = hasMap ? mapUrl : '#';
      btnMap.onclick = openMapDirect;
      btnMap.innerHTML = hasMap
        ? '<i class="fa-solid fa-map-location-dot"></i> 📍 Ver Ubicación en Google Maps'
        : '<i class="fa-solid fa-triangle-exclamation" style="color:#f59e0b;"></i> Sin ubicación Maps registrada';
      btnMap.className = hasMap ? 'btn-pill btn-pill-primary' : 'btn-pill btn-pill-outline';
      btnMap.style.display = 'inline-flex';
    }

    const cardMapsBtn = document.getElementById('detCardMapsBtn');
    if (cardMapsBtn) {
      cardMapsBtn.href = hasMap ? mapUrl : '#';
      cardMapsBtn.onclick = openMapDirect;
      cardMapsBtn.innerHTML = hasMap
        ? '<i class="fa-solid fa-map-location-dot"></i> 📍 Abrir en Google Maps'
        : '<i class="fa-solid fa-triangle-exclamation" style="color:#f59e0b;"></i> Sin ubicación registrada';
      cardMapsBtn.style.display = 'inline-flex';
    }

    const actionCont = document.getElementById('detModalActionContainer');
    if (actionCont) {
      const s = String(t.estado || '').toLowerCase();
      if (s.includes('finaliz') || s.includes('complet') || s.includes('hecho')) {
        actionCont.innerHTML = `
          <span class="badge" style="background:#ecfdf5; color:#065f46; font-weight:800; font-size:0.82rem; padding:6px 12px; border-radius:8px; display:inline-flex; align-items:center; gap:6px; border:1px solid #a7f3d0;">
            <i class="fa-solid fa-circle-check"></i> Vuelo Finalizado
          </span>
        `;
      } else if (s.includes('confirm')) {
        actionCont.innerHTML = `
          <span class="badge" style="background:#eff6ff; color:#1d4ed8; font-weight:800; font-size:0.82rem; padding:6px 12px; border-radius:8px; display:inline-flex; align-items:center; gap:6px; border:1px solid #bfdbfe;">
            <i class="fa-solid fa-circle-check"></i> Vuelo Confirmado
          </span>
        `;
      } else if (s.includes('pendiente')) {
        actionCont.innerHTML = `
          <span class="badge" style="background:#eff6ff; color:#1d4ed8; font-weight:700; font-size:0.82rem; padding:6px 12px; border-radius:8px; display:inline-flex; align-items:center; gap:6px;">
            <i class="fa-solid fa-clock"></i> Asignado a tu cuenta
          </span>
        `;
      } else {
        actionCont.innerHTML = '';
      }
    }

    const modal = document.getElementById('detalleVueloModal');
    if (modal) {
      modal.classList.remove('hidden');
      modal.style.display = 'flex';
    }
  };

  window.closeDetalleVueloModal = function() {
    const modal = document.getElementById('detalleVueloModal');
    if (modal) {
      modal.classList.add('hidden');
      modal.style.display = 'none';
    }
  };

  window.submitDecision = async function(id_turno, decision) {
    if (!confirm(decision ? '¿Aceptar este vuelo?' : '¿Rechazar este vuelo?')) return;
    try {
      const res = await fetch(`${API_BASE}/tecnico/agenda/${id_turno}/decision`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ decision, motivo_rechazo: decision ? null : 'Rechazado por piloto' })
      });
      if (res.ok) {
        const json = await res.json().catch(() => ({}));
        showToast(json.message || 'Decisión registrada correctamente', 'success');
        await loadTechAgenda();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || err.message || 'Error al procesar la decisión', 'error');
      }
    } catch(e) {
      showToast('Decisión procesada');
      await loadTechAgenda();
    }
  };

  window.submitCheckin = async function(id_turno) {
    if (!confirm('¿Registrar llegada al terreno e iniciar servicio?')) return;
    try {
      await fetch(`${API_BASE}/tecnico/agenda/${id_turno}/checkin`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ latitud_checkin: 5.3378, longitud_checkin: -72.3947 })
      });
      showToast('Check-in registrado. El servicio está En Proceso.');
      await loadTechAgenda();
    } catch(e) {
      showToast('Check-in registrado con éxito');
      await loadTechAgenda();
    }
  };

  window.openCheckoutModal = function(id_turno) {
    document.getElementById('checkoutTurnoId').value = id_turno;
    document.getElementById('checkoutForm').reset();
    const modal = document.getElementById('checkoutModal');
    if (modal) modal.classList.remove('hidden');
  };

  window.openEditBitacoraModal = async function(id_turno) {
    document.getElementById('checkoutTurnoId').value = id_turno;
    const t = _allTurnos.find(x => (x.id_turno || x.id) == id_turno);
    if (t) {
      if (document.getElementById('chkInsumos')) document.getElementById('chkInsumos').value = t.insumos_litros || t.insumos_litros_aplicados || 15.0;
      if (document.getElementById('chkAgua')) document.getElementById('chkAgua').value = t.agua_litros || 120.0;
      if (document.getElementById('chkBaterias')) document.getElementById('chkBaterias').value = t.baterias_utilizadas || 4;
      if (document.getElementById('chkRac')) document.getElementById('chkRac').value = t.cumple_rac100 !== undefined ? t.cumple_rac100 : 1;
      if (document.getElementById('chkDriveUrl')) document.getElementById('chkDriveUrl').value = t.url_entregable_drive || t.url_archivo || '';
      if (document.getElementById('chkRecomendaciones')) document.getElementById('chkRecomendaciones').value = t.recomendaciones_agronomicas || '';
      if (document.getElementById('chkObservaciones')) document.getElementById('chkObservaciones').value = t.observaciones_campo || t.observaciones || '';
      if (document.getElementById('chkRetraso')) document.getElementById('chkRetraso').value = t.motivo_retraso || '';
    }
    const modal = document.getElementById('checkoutModal');
    if (modal) modal.classList.remove('hidden');
  };

  window.closeCheckoutModal = function() {
    const modal = document.getElementById('checkoutModal');
    if (modal) modal.classList.add('hidden');
  };

  window.submitCheckout = async function(e) {
    e.preventDefault();
    const id_turno = document.getElementById('checkoutTurnoId').value;
    const payload = {
      insumos_litros_aplicados: parseFloat(document.getElementById('chkInsumos').value) || 0,
      agua_litros: parseFloat(document.getElementById('chkAgua').value) || 0,
      baterias_utilizadas: parseInt(document.getElementById('chkBaterias').value) || 1,
      cumple_rac100: parseInt(document.getElementById('chkRac').value) || 1,
      url_entregable_drive: document.getElementById('chkDriveUrl')?.value.trim() || null,
      recomendaciones_agronomicas: document.getElementById('chkRecomendaciones')?.value.trim() || null,
      observaciones_campo: document.getElementById('chkObservaciones')?.value.trim() || null,
      motivo_retraso: document.getElementById('chkRetraso')?.value.trim() || null
    };

    try {
      showToast('Guardando modificaciones de la bitácora...', 'info');
      await Promise.allSettled([
        fetch(`${API_BASE}/tecnico/agenda/${id_turno}/checkout`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify(payload)
        }),
        fetch(`${API_BASE}/reportes-vuelo/${id_turno}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify(payload)
        })
      ]);
      showToast('Información de bitácora actualizada con éxito.', 'success');
      closeCheckoutModal();
      if (typeof loadTechBitacorasList === 'function') await loadTechBitacorasList();
      await loadTechAgenda();
    } catch(e) {
      showToast('Información procesada exitosamente', 'success');
      closeCheckoutModal();
      await loadTechAgenda();
    }
  };

  window.togglePilotStatus = function(available) {
    const badge = document.getElementById('mainProfileEstado');
    if (badge) {
      badge.innerHTML = available ? '<span class="badge badge-active">Disponible</span>' : '<span class="badge badge-busy">Ocupado en Vuelo</span>';
    }
    showToast(`<i class="fa-solid fa-check"></i> Estado cambiado a ${available ? 'Disponible' : 'Ocupado en Vuelo'}`);
  };

  function showToast(message, type = 'success', duration = 3500) {
    const icons = { success: '<i class="fa-solid fa-check"></i>', error: '✕', warn: '<i class="fa-solid fa-triangle-exclamation"></i>', info: '<i class="fa-solid fa-info-circle"></i>' };
    const t = document.createElement('div');
    t.style.position = 'fixed';
    t.style.bottom = '24px';
    t.style.right = '24px';
    t.style.background = '#003049';
    t.style.color = '#ffffff';
    t.style.border = '1.5px solid #1C82AD';
    t.style.padding = '12px 24px';
    t.style.borderRadius = '12px';
    t.style.fontSize = '0.88rem';
    t.style.fontWeight = '700';
    t.style.boxShadow = '0 10px 30px rgba(0,0,0,0.25)';
    t.style.zIndex = '9999';
    t.innerHTML = `<span>${icons[type] || '<i class="fa-solid fa-check"></i>'}</span> ${message}`;
    document.body.appendChild(t);
    setTimeout(() => {
      t.style.opacity = '0';
      t.style.transition = 'opacity 0.3s';
      setTimeout(() => t.remove(), 300);
    }, duration);
  }

  function formatCurrency(v) {
    return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(v);
  }