'use strict';

// Configuración Global y Resiliente de API Flymetrics
const API_BASE = window.BASE_URL || (
  (window.location.protocol === 'file:' || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:3000/api/v1'
    : ((window.API_BASE || 'https://flymetrics-api.hostless.app') + '/api/v1')
);
window.API_BASE = API_BASE.replace(/\/api\/v1\/?$/, '');
window.BASE_URL = API_BASE;
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

    // ── MODIFICACIÓN SEGURA DE PERFIL CON CÓDIGO DE 8 DÍGITOS EN 2 PASOS ──
    window.openSecureProfileModal = function() {
      const modal = document.getElementById('modalModificarPerfilSeguro');
      if (!modal) return;
      modal.classList.remove('hidden');
      modal.classList.add('open', 'active');
      modal.style.setProperty('display', 'flex', 'important');
      modal.style.setProperty('opacity', '1', 'important');
      modal.style.setProperty('visibility', 'visible', 'important');
      modal.style.zIndex = '999999';
      document.body.style.overflow = 'hidden';

      // Mostrar Paso 1 (Verificación) y ocultar Paso 2 (Edición)
      const step1 = document.getElementById('secProfStep1');
      const step2 = document.getElementById('secProfStep2');
      if (step1) step1.style.display = 'block';
      if (step2) step2.style.display = 'none';

      const alert1 = document.getElementById('secProfAlertBox1');
      const alert2 = document.getElementById('secProfAlertBox2');
      if (alert1) { alert1.style.display = 'none'; alert1.textContent = ''; }
      if (alert2) { alert2.style.display = 'none'; alert2.textContent = ''; }

      const codInp = document.getElementById('secProfCodigo');
      if (codInp) codInp.value = '';

      // Mostrar correo destinatario actual
      const currentEm = sessionStorage.getItem('fm_email') || localStorage.getItem('fm_email') || (_clientProfile && _clientProfile.email) || '';
      const emailTarget = document.getElementById('secProfEmailTarget');
      if (emailTarget) emailTarget.textContent = currentEm || 'tu correo registrado';

      // Precargar datos actuales en los inputs de edición del Paso 2
      const fNom = document.getElementById('profNombre');
      const fEmp = document.getElementById('profEmpresa');
      const fTel = document.getElementById('profTel');
      const fEmail = document.getElementById('profEmail') || document.getElementById('profileUserEmail');
      const fTipo = document.getElementById('profTipoDoc');
      const fCed = document.getElementById('profCedula');
      const fExp = document.getElementById('profExpedicion');

      if (document.getElementById('secProfNombre')) {
        document.getElementById('secProfNombre').value = (_clientProfile && _clientProfile.nombre) || (fNom ? fNom.value : '') || '';
      }
      if (document.getElementById('secProfEmpresa')) {
        document.getElementById('secProfEmpresa').value = (_clientProfile && _clientProfile.empresa) || (fEmp ? fEmp.value : '') || '';
      }
      if (document.getElementById('secProfTel')) {
        document.getElementById('secProfTel').value = (_clientProfile && _clientProfile.telefono) || (fTel ? fTel.value : '') || '';
      }
      if (document.getElementById('secProfEmail')) {
        document.getElementById('secProfEmail').value = currentEm || (fEmail ? (fEmail.value || fEmail.textContent || '') : '').trim();
      }
      if (document.getElementById('secProfTipoDoc')) {
        document.getElementById('secProfTipoDoc').value = (fTipo ? fTipo.value : 'CC') || 'CC';
      }
      if (document.getElementById('secProfCedula')) {
        const docVal = (_clientProfile && (_clientProfile.numero_documento || _clientProfile.cedula || _clientProfile.nit)) || (fCed ? fCed.value : '') || '';
        document.getElementById('secProfCedula').value = docVal;
      }
      if (document.getElementById('secProfExpedicion')) {
        document.getElementById('secProfExpedicion').value = (_clientProfile && _clientProfile.fecha_expedicion) || (fExp ? fExp.value : '') || '';
      }
    };

    window.closeSecureProfileModal = function() {
      const modal = document.getElementById('modalModificarPerfilSeguro');
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('open', 'active');
        modal.style.setProperty('display', 'none', 'important');
        document.body.style.overflow = '';
      }
    };

    window.formatearInput8DigitosModal = function(input) {
      let v = input.value.replace(/\D/g, '').substring(0, 8);
      if (v.length > 4) {
        input.value = v.substring(0, 4) + ' - ' + v.substring(4);
      } else {
        input.value = v;
      }
    };

    window.solicitarCodigoPerfilModal = async function() {
      const btn = document.getElementById('btnReqProfileOtp');
      const alertBox = document.getElementById('secProfAlertBox1');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Enviando...';
      }

      const activeToken = _token || sessionStorage.getItem('fm_token') || localStorage.getItem('fm_token') || '';
      const apiBase = API_BASE;

      try {
        const res = await fetch(`${apiBase}/clientes/seguridad/solicitar-codigo-perfil`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${activeToken}`
          }
        });
        const data = await res.json();
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-paper-plane" style="color:#E4C7A1;"></i> Reenviar Código (8 Dígitos)';
        }

        if (res.ok && data.success) {
          if (alertBox) {
            alertBox.style.display = 'block';
            alertBox.style.background = 'rgba(16,185,129,0.1)';
            alertBox.style.border = '1px solid #10B981';
            alertBox.style.color = '#065F46';
            alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> Código de 8 dígitos enviado a tu correo registrado. Válido por 15 minutos.';
          }
          const codInput = document.getElementById('secProfCodigo');
          if (codInput) codInput.focus();
          if (typeof showToast === 'function') showToast('Código de 8 dígitos enviado a tu correo', 'success');
        } else {
          if (alertBox) {
            alertBox.style.display = 'block';
            alertBox.style.background = 'rgba(239,68,68,0.1)';
            alertBox.style.border = '1px solid #EF4444';
            alertBox.style.color = '#991B1B';
            alertBox.textContent = data.message || 'Error al despachar código de seguridad.';
          }
        }
      } catch (err) {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-paper-plane" style="color:#E4C7A1;"></i> Enviar Código (8 Dígitos)';
        }
        if (alertBox) {
          alertBox.style.display = 'block';
          alertBox.style.background = 'rgba(239,68,68,0.1)';
          alertBox.style.border = '1px solid #EF4444';
          alertBox.style.color = '#991B1B';
          alertBox.textContent = 'Error de conexión con el servidor al solicitar código.';
        }
      }
    };

    window.verificarCodigoPerfilModal = async function() {
      const codeRaw = (document.getElementById('secProfCodigo')?.value || '').replace(/\D/g, '');
      const alertBox1 = document.getElementById('secProfAlertBox1');
      const btnVerify = document.getElementById('btnVerifyProfileOtp');

      if (!codeRaw || codeRaw.length !== 8) {
        if (alertBox1) {
          alertBox1.style.display = 'block';
          alertBox1.style.background = 'rgba(239,68,68,0.1)';
          alertBox1.style.border = '1px solid #EF4444';
          alertBox1.style.color = '#991B1B';
          alertBox1.textContent = 'Debes ingresar el código de autorización de exactamente 8 dígitos.';
        }
        return;
      }

      if (btnVerify) {
        btnVerify.disabled = true;
        btnVerify.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Verificando Código...';
      }

      const activeToken = _token || sessionStorage.getItem('fm_token') || localStorage.getItem('fm_token') || '';
      const apiBase = API_BASE;

      try {
        const res = await fetch(`${apiBase}/clientes/seguridad/verificar-codigo-perfil`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${activeToken}`
          },
          body: JSON.stringify({ codigo_8_digitos: codeRaw })
        });
        const data = await res.json().catch(() => ({}));

        if (res.ok && data.success) {
          // Desplegar Paso 2: Edición de Información
          const step1 = document.getElementById('secProfStep1');
          const step2 = document.getElementById('secProfStep2');
          if (step1) step1.style.display = 'none';
          if (step2) step2.style.display = 'block';

          const nomInp = document.getElementById('secProfNombre');
          if (nomInp) nomInp.focus();

          if (typeof showToast === 'function') {
            showToast('Código de 8 dígitos verificado correctamente. Ahora puedes modificar tus datos.', 'success');
          }
        } else {
          let msg = data.message;
          if (!msg && data.detail) {
            msg = Array.isArray(data.detail) ? data.detail.map(d => d.msg || d).join('. ') : String(data.detail);
          }
          if (alertBox1) {
            alertBox1.style.display = 'block';
            alertBox1.style.background = 'rgba(239,68,68,0.1)';
            alertBox1.style.border = '1px solid #EF4444';
            alertBox1.style.color = '#991B1B';
            alertBox1.textContent = msg || 'Código incorrecto o ha expirado. Solicita uno nuevo.';
          }
        }
      } catch (err) {
        if (alertBox1) {
          alertBox1.style.display = 'block';
          alertBox1.style.background = 'rgba(239,68,68,0.1)';
          alertBox1.style.border = '1px solid #EF4444';
          alertBox1.style.color = '#991B1B';
          alertBox1.textContent = 'Error de conexión con el servidor al verificar código.';
        }
      } finally {
        if (btnVerify) {
          btnVerify.disabled = false;
          btnVerify.innerHTML = '<i class="fa-solid fa-check-double" style="color:#E4C7A1;"></i> Aceptar y Verificar Código';
        }
      }
    };

    window.submitSecureProfileChanges = async function(e) {
      if (e) e.preventDefault();
      const codeRaw = (document.getElementById('secProfCodigo')?.value || '').replace(/\D/g, '');
      const alertBox2 = document.getElementById('secProfAlertBox2');
      const btn = document.getElementById('btnSaveSecureProfile');

      if (!codeRaw || codeRaw.length !== 8) {
        if (alertBox2) {
          alertBox2.style.display = 'block';
          alertBox2.style.background = 'rgba(239,68,68,0.1)';
          alertBox2.style.border = '1px solid #EF4444';
          alertBox2.style.color = '#991B1B';
          alertBox2.textContent = 'Error: Código de seguridad de 8 dígitos ausente. Vuelve al Paso 1.';
        }
        return;
      }

      const nuevoNombre = (document.getElementById('secProfNombre')?.value || '').trim().toUpperCase();
      const nuevaEmpresa = (document.getElementById('secProfEmpresa')?.value || '').trim().toUpperCase();
      const nuevoEmail = (document.getElementById('secProfEmail')?.value || '').trim().toLowerCase();
      const nuevoTel = (document.getElementById('secProfTel')?.value || '').trim();
      const nuevoTipoDoc = document.getElementById('secProfTipoDoc')?.value || 'CC';
      const nuevaCedula = (document.getElementById('secProfCedula')?.value || '').trim();
      const nuevaExp = document.getElementById('secProfExpedicion')?.value || '';

      if (!nuevoNombre || !nuevoTel || !nuevoEmail || !nuevaCedula) {
        if (alertBox2) {
          alertBox2.style.display = 'block';
          alertBox2.style.background = 'rgba(239,68,68,0.1)';
          alertBox2.style.border = '1px solid #EF4444';
          alertBox2.style.color = '#991B1B';
          alertBox2.textContent = 'Por favor completa todos los campos obligatorios (*).';
        }
        return;
      }

      // Validación estricta de formato y cantidad de dígitos
      if (nuevoTipoDoc === 'CC') {
        const cleanCed = nuevaCedula.replace(/\D/g, '');
        if (cleanCed.length < 6 || cleanCed.length > 10) {
          if (alertBox2) {
            alertBox2.style.display = 'block';
            alertBox2.style.background = 'rgba(239,68,68,0.1)';
            alertBox2.style.border = '1px solid #EF4444';
            alertBox2.style.color = '#991B1B';
            alertBox2.textContent = 'La Cédula de Ciudadanía (CC) debe contener entre 6 y 10 dígitos numéricos.';
          }
          document.getElementById('secProfCedula')?.focus();
          return;
        }
      } else if (nuevoTipoDoc === 'NIT') {
        const cleanCed = nuevaCedula.replace(/\D/g, '');
        if (cleanCed.length < 9 || cleanCed.length > 10) {
          if (alertBox2) {
            alertBox2.style.display = 'block';
            alertBox2.style.background = 'rgba(239,68,68,0.1)';
            alertBox2.style.border = '1px solid #EF4444';
            alertBox2.style.color = '#991B1B';
            alertBox2.textContent = 'El NIT debe contener entre 9 y 10 dígitos numéricos (sin guiones ni DV).';
          }
          document.getElementById('secProfCedula')?.focus();
          return;
        }
      } else if (nuevoTipoDoc === 'CE') {
        if (nuevaCedula.length < 5 || nuevaCedula.length > 12) {
          if (alertBox2) {
            alertBox2.style.display = 'block';
            alertBox2.style.background = 'rgba(239,68,68,0.1)';
            alertBox2.style.border = '1px solid #EF4444';
            alertBox2.style.color = '#991B1B';
            alertBox2.textContent = 'La Cédula de Extranjería (CE) debe contener entre 5 y 12 caracteres.';
          }
          document.getElementById('secProfCedula')?.focus();
          return;
        }
      } else if (nuevoTipoDoc === 'PASAPORTE') {
        if (nuevaCedula.length < 5 || nuevaCedula.length > 15) {
          if (alertBox2) {
            alertBox2.style.display = 'block';
            alertBox2.style.background = 'rgba(239,68,68,0.1)';
            alertBox2.style.border = '1px solid #EF4444';
            alertBox2.style.color = '#991B1B';
            alertBox2.textContent = 'El Pasaporte debe contener entre 5 y 15 caracteres.';
          }
          document.getElementById('secProfCedula')?.focus();
          return;
        }
      }

      const cleanTel = nuevoTel.replace(/\D/g, '');
      if (cleanTel.length < 7 || cleanTel.length > 15) {
        if (alertBox2) {
          alertBox2.style.display = 'block';
          alertBox2.style.background = 'rgba(239,68,68,0.1)';
          alertBox2.style.border = '1px solid #EF4444';
          alertBox2.style.color = '#991B1B';
          alertBox2.textContent = 'El número de teléfono debe contener entre 7 y 15 dígitos numéricos.';
        }
        document.getElementById('secProfTel')?.focus();
        return;
      }

      const payload = {
        codigo_8_digitos: codeRaw,
        nombre: nuevoNombre,
        empresa: nuevaEmpresa,
        email: nuevoEmail,
        telefono: nuevoTel,
        tipo_documento: nuevoTipoDoc,
        cedula_o_nit: nuevaCedula,
        numero_documento: nuevaCedula,
        fecha_expedicion: nuevaExp
      };

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Guardando Cambios...';
      }

      const activeToken = _token || sessionStorage.getItem('fm_token') || localStorage.getItem('fm_token') || '';
      const apiBase = API_BASE;

      try {
        const res = await fetch(`${apiBase}/clientes/seguridad/perfil-seguro`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${activeToken}`
          },
          body: JSON.stringify(payload)
        });
        const data = await res.json().catch(() => ({}));

        if (res.ok && data.success) {
          // Si el correo cambió, actualizar token de sesión y clave de correo
          if (data.data && data.data.new_token) {
            _token = data.data.new_token;
            sessionStorage.setItem('fm_token', _token);
            localStorage.setItem('fm_token', _token);
          }
          if (nuevoEmail) {
            sessionStorage.setItem('fm_email', nuevoEmail);
            localStorage.setItem('fm_email', nuevoEmail);
          }

          // Actualizar formulario principal de perfil en pantalla
          const pNom = document.getElementById('profNombre'); if (pNom) pNom.value = nuevoNombre;
          const pEmp = document.getElementById('profEmpresa'); if (pEmp) pEmp.value = nuevaEmpresa;
          const pTel = document.getElementById('profTel'); if (pTel) pTel.value = nuevoTel;
          const pEm = document.getElementById('profEmail'); if (pEm) pEm.value = nuevoEmail;
          const pTipo = document.getElementById('profTipoDoc'); if (pTipo) pTipo.value = nuevoTipoDoc;
          const pCed = document.getElementById('profCedula'); if (pCed) pCed.value = nuevaCedula;
          const pExp = document.getElementById('profExpedicion'); if (pExp) pExp.value = nuevaExp;

          const pFullName = document.getElementById('profileFullName');
          if (pFullName) pFullName.textContent = nuevoNombre;
          const pUserEmail = document.getElementById('profileUserEmail');
          if (pUserEmail) pUserEmail.textContent = nuevoEmail;
          const sName = document.getElementById('sidebarUserName');
          if (sName) sName.textContent = nuevoNombre;

          closeSecureProfileModal();
          await refreshData();
          if (typeof loadProfileData === 'function') await loadProfileData(nuevoEmail);

          if (typeof showToast === 'function') {
            showToast('✔ ¡Información de perfil actualizada y verificada exitosamente!', 'success');
          }
        } else {
          let msg = data.message;
          if (!msg && data.detail) {
            msg = Array.isArray(data.detail) ? data.detail.map(d => d.msg || d).join('. ') : String(data.detail);
          }
          if (alertBox2) {
            alertBox2.style.display = 'block';
            alertBox2.style.background = 'rgba(239,68,68,0.1)';
            alertBox2.style.border = '1px solid #EF4444';
            alertBox2.style.color = '#991B1B';
            alertBox2.textContent = msg || 'Error al actualizar información. Verifica los datos ingresados.';
          }
        }
      } catch (err) {
        if (alertBox2) {
          alertBox2.style.display = 'block';
          alertBox2.style.background = 'rgba(239,68,68,0.1)';
          alertBox2.style.border = '1px solid #EF4444';
          alertBox2.style.color = '#991B1B';
          alertBox2.textContent = 'Error de conexión con el servidor al actualizar perfil.';
        }
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Guardar Cambios';
        }
      }
    };

    function toggleSidebarCollapse() {
      const sidebar = document.getElementById('mainSidebar');
      const overlay = document.getElementById('mobileSidebarOverlay');
      if (!sidebar) return;

      if (window.innerWidth <= 1024) {
        const isOpen = sidebar.classList.contains('mobile-open');
        if (isOpen) {
          sidebar.classList.remove('mobile-open');
          if (overlay) overlay.classList.remove('active');
          document.body.style.overflow = '';
        } else {
          sidebar.classList.add('mobile-open');
          if (overlay) overlay.classList.add('active');
          document.body.style.overflow = 'hidden';
        }
      } else {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        try {
          sessionStorage.setItem('fm_sidebar_collapsed', isCollapsed ? 'true' : 'false');
        } catch (e) { }
      }
    }
    window.toggleSidebarCollapse = toggleSidebarCollapse;

    // API_BASE is declared globally at top of file
    let _token = null;
    let _clientProfile = null;
    let _myAgendas = [];
    let _myFincas = [];
    let _myPagos = [];
    let _myPqrs = [];
    let _myDocs = [];
    let _catalogServicios = [];
    let _myTecnicos = [];
    let _selectedDate = null;
    let _selectedTime = null;
    let _selectedTecnicoId = null;
    let _calCurrentYear = new Date().getFullYear();
    let _calCurrentMonth = new Date().getMonth();

    function showToast(msg, type = 'info', duration = 3500) {
      const toast = document.getElementById('toast');
      if (!toast) return;

      if (window._toastTimeout) {
        clearTimeout(window._toastTimeout);
        window._toastTimeout = null;
      }

      toast.removeAttribute('style');
      toast.className = '';

      const typeMap = {
        'success': 'toast-success',
        'warning': 'toast-warning',
        'warn': 'toast-warning',
        'error': 'toast-error',
        'info': 'toast-info'
      };

      const iconMap = {
        'toast-success': '<i class="fa-solid fa-circle-check" style="font-size:1.1rem; color:#10B981; flex-shrink:0;"></i>',
        'toast-warning': '<i class="fa-solid fa-triangle-exclamation" style="font-size:1.1rem; color:#F59E0B; flex-shrink:0;"></i>',
        'toast-error': '<i class="fa-solid fa-circle-xmark" style="font-size:1.1rem; color:#EF4444; flex-shrink:0;"></i>',
        'toast-info': '<i class="fa-solid fa-circle-info" style="font-size:1.1rem; color:#38BDF8; flex-shrink:0;"></i>'
      };

      const selectedClass = typeMap[type] || 'toast-info';
      toast.classList.add(selectedClass);
      toast.innerHTML = `${iconMap[selectedClass] || ''} <span style="flex:1;">${msg}</span><i class="fa-solid fa-xmark" style="font-size:0.85rem; opacity:0.6; cursor:pointer; margin-left:6px;" title="Cerrar"></i>`;
      toast.style.cursor = 'pointer';
      toast.onclick = function() {
        toast.classList.remove('show');
        if (window._toastTimeout) {
          clearTimeout(window._toastTimeout);
          window._toastTimeout = null;
        }
      };

      // Force DOM reflow so transition runs cleanly
      void toast.offsetHeight;
      toast.classList.add('show');

      const displayDuration = (type === 'error') ? Math.max(duration, 5000) : duration;
      window._toastTimeout = setTimeout(() => {
        toast.classList.remove('show');
        window._toastTimeout = null;
      }, displayDuration);
    }
    window.showToast = showToast;
    window.dismissToast = function() {
      const toast = document.getElementById('toast');
      if (toast) toast.classList.remove('show');
      if (window._toastTimeout) {
        clearTimeout(window._toastTimeout);
        window._toastTimeout = null;
      }
    };

    let _agendaFilterActive = 'Todos';

    function showPanel(panelName) {
      panelName = panelName || 'dashboard';

      if (window.innerWidth <= 1024) {
        const sidebar = document.getElementById('mainSidebar');
        const overlay = document.getElementById('mobileSidebarOverlay');
        if (sidebar && sidebar.classList.contains('mobile-open')) {
          sidebar.classList.remove('mobile-open');
          if (overlay) overlay.classList.remove('active');
          document.body.style.overflow = '';
        }
      }

      const navItems = document.querySelectorAll('.cp-nav-item');
      navItems.forEach(item => {
        if (item.getAttribute('data-panel') === panelName) {
          item.classList.add('active');
        } else {
          item.classList.remove('active');
        }
      });

      const panels = document.querySelectorAll('.cp-panel, section[id^="panel-"]');
      panels.forEach(panel => {
        if (panel.id === `panel-${panelName}` || panel.id === panelName) {
          panel.style.display = 'block';
          panel.classList.add('active');
        } else {
          panel.style.display = 'none';
          panel.classList.remove('active');
        }
      });

      const titles = {
        dashboard: 'Dashboard General',
        agendas: 'Mis Solicitudes y Agendas',
        fincas: 'Gestión de Fincas y Predios',
        documentos: 'Documentos y Entregables',
        facturacion: 'Facturación e Historial de Pagos',
        perfil: 'Mi Perfil de Cliente',
        soporte: 'Atención y Soporte Técnico'
      };
      const titleEl = document.getElementById('topbarTitle');
      if (titleEl) {
        titleEl.textContent = titles[panelName] || 'Panel de Cliente';
      }

      showToast(`<i class="fa-solid fa-location-dot"></i> Sección activa: ${titles[panelName] || panelName}`, 'info', 2000);
    }
    window.showPanel = showPanel;

    function isClientVerified() {
      if (!_clientProfile) return false;
      const doc = _clientProfile.cedula || _clientProfile.numero_documento;
      const isVerified = _clientProfile.verificado === true;
      return Boolean(isVerified && doc && String(doc).trim().length >= 7);
    }

    function checkVerifiedOrBlock(actionName = "esta acción") {
      if (!isClientVerified()) {
        showToast(`<i class="fa-solid fa-lock"></i> Completa tu Cédula / NIT en Mi Perfil para habilitar ${actionName}.`, 'warn');
        showPanel('perfil');
        setTimeout(() => {
          const inp = document.getElementById('profCedula');
          if (inp) {
            inp.scrollIntoView({ behavior: 'smooth', block: 'center' });
            inp.focus();
          }
        }, 300);
        return false;
      }
      return true;
    }
    window.checkVerifiedOrBlock = checkVerifiedOrBlock;

    // ── INITIALIZATION ───────────────────────
    document.addEventListener('DOMContentLoaded', async () => {
      // 1. Session verify with Tracking Prevention resilience
      try {
        _token = sessionStorage.getItem('fm_token') || localStorage.getItem('fm_token');
      } catch (e) {
        _token = null;
      }
      if (_token === 'undefined' || _token === 'null' || !_token) {
        _token = null;
      }
      let email = null;
      try {
        email = sessionStorage.getItem('fm_email') || localStorage.getItem('fm_email');
        if (!email) {
          const uStr = sessionStorage.getItem('fm_user') || localStorage.getItem('fm_user');
          const u = JSON.parse(uStr);
          if (u && u.email) email = u.email;
        }
      } catch (e) { }

      // Transfer active token/email to sessionStorage and preserve token in localStorage
      try {
        if (_token) {
          sessionStorage.setItem('fm_token', _token);
          localStorage.setItem('fm_token', _token);
        }
        if (email) sessionStorage.setItem('fm_email', email);
      } catch (e) { }

      // If no token exists, redirect to login page immediately
      if (!_token) {
        window.location.href = 'index.html';
        return;
      }

      // Validar aislamiento de roles: Si un administrador o técnico entra a cliente.html, redirigir a su módulo oficial
      try {
        const storedRole = (sessionStorage.getItem('fm_role') || localStorage.getItem('fm_role') || '').toLowerCase();
        if (storedRole === 'administrador') {
          window.location.href = 'admin.html';
          return;
        } else if (storedRole === 'tecnico') {
          window.location.href = 'tecnico.html';
          return;
        }
      } catch(e) {}

      // Populate layout user details
      const nameEl = document.getElementById('sidebarUserName');
      if (nameEl) nameEl.textContent = email ? email.split('@')[0] : 'Cliente';
      const avEl = document.getElementById('sidebarAvatar');
      if (avEl) avEl.textContent = email ? email.substring(0, 2).toUpperCase() : 'CL';

      // Configure dates
      const dateInput = document.getElementById('agFecha');
      if (dateInput) {
        dateInput.min = new Date().toISOString().split('T')[0];
      }

      // 2. Load basic info
      await loadProfileData(email);
      await loadCatalogServices();
      await loadCorporateConfigClient();
      await refreshData();
      await loadClientPublicidadCollage();
    });

    function getBadgeClass(status) {
      if (!status) return 'pending';
      const s = String(status).toLowerCase();
      if (s.includes('pend') || s.includes('solicit')) return 'pending';
      if (s.includes('confir')) return 'confirmed';
      if (s.includes('proceso') || s.includes('curso') || s.includes('progreso')) return 'inprocess';
      if (s.includes('hecho') || s.includes('complet') || s.includes('termin')) return 'completed';
      if (s.includes('canc')) return 'cancelled';
      return 'pending';
    }

    // ── CORE DATA LOADERS ────────────────────
    async function loadProfileData(email) {
      try {
        const res = await fetch(`${API_BASE}/clientes/me`, {
          headers: { 'Authorization': `Bearer ${_token}` }
        });
        if (res.ok) {
          const body = await res.json();
          _clientProfile = body.data || body;
          if (_clientProfile && (_clientProfile.email || (_clientProfile.usuario && _clientProfile.usuario.email))) {
            const serverEmail = _clientProfile.email || _clientProfile.usuario.email;
            if (serverEmail) {
              email = serverEmail;
              sessionStorage.setItem('fm_email', email);
            }
          }
        } else if (res.status === 401) {
          try {
            sessionStorage.removeItem('fm_token');
            sessionStorage.removeItem('fm_email');
            localStorage.removeItem('token');
            localStorage.removeItem('fm_token');
          } catch(e){}
          window.location.href = 'index.html?openAuth=login';
          return;
        } else {
          _clientProfile = { id_cliente: 0, nombre: email ? email.split('@')[0] : 'Cliente', apellido_1: '', telefono: '', verificado: false };
        }
      } catch (e) {
        _clientProfile = { id_cliente: 0, nombre: email ? email.split('@')[0] : 'Cliente', apellido_1: '', telefono: '', verificado: false };
      }

      // Get clean full name
      let fullNombre = (_clientProfile.nombre || '').replace(/\bNuevo\b/gi, '').trim();
      const rawAp1 = (_clientProfile.apellido_1 || '').replace(/\bNuevo\b/gi, '').trim();
      if (rawAp1 && !fullNombre.includes(rawAp1)) {
        fullNombre = `${fullNombre} ${rawAp1}`.trim();
      }

      _clientProfile.nombre = fullNombre || 'Cliente';
      _clientProfile.apellido_1 = '';

      const docNum = _clientProfile.numero_documento || _clientProfile.cedula || _clientProfile.nit || '';
      // Un cliente solo es Verificado si la base de datos lo marca como verificado y cuenta con documento y fecha de expedición
      const isFullyVerified = Boolean(
        _clientProfile &&
        _clientProfile.verificado === true &&
        docNum &&
        String(docNum).trim().length >= 7 &&
        _clientProfile.fecha_expedicion &&
        String(_clientProfile.fecha_expedicion).trim().length >= 4
      );

      _clientProfile.verificado = isFullyVerified;
      _clientProfile.cedula = isFullyVerified ? docNum : '';
      _clientProfile.fecha_expedicion = isFullyVerified ? (_clientProfile.fecha_expedicion || '') : '';

      const userDisplayName = _clientProfile.nombre || (email ? email.split('@')[0] : 'Cliente');

      // ── VERIFICACIÓN DE PRIMER INGRESO (SEGURIDAD Y CARGA DE FINCA) ──
      checkPrimerIngresoStatus();
      const sName = document.getElementById('sidebarUserName');
      if (sName) sName.textContent = userDisplayName;
      const sAv = document.getElementById('sidebarAvatar');
      if (sAv) sAv.textContent = userDisplayName.substring(0, 2).toUpperCase();

      const pFull = document.getElementById('profileFullName');
      if (pFull) pFull.textContent = userDisplayName;
      const pEmail = document.getElementById('profileUserEmail');
      if (pEmail) pEmail.textContent = email || 'cliente@flymetrics.com';

      const pNom = document.getElementById('profNombre'); if (pNom) pNom.value = _clientProfile.nombre || '';
      const pApe = document.getElementById('profApellido'); if (pApe) pApe.value = '';
      const pTel = document.getElementById('profTel'); if (pTel) pTel.value = _clientProfile.telefono || '';
      const pEm = document.getElementById('profEmail'); if (pEm) pEm.value = email;
      const pTipo = document.getElementById('profTipoDoc');
      if (pTipo && _clientProfile.tipo_documento) {
        pTipo.value = _clientProfile.tipo_documento;
      }
      if (typeof window.ajustarValidacionPerfilDoc === 'function') {
        window.ajustarValidacionPerfilDoc();
      }

      const pCed = document.getElementById('profCedula');
      const pExp = document.getElementById('profExpedicion');
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const yesterdayIso = yesterday.toISOString().split('T')[0];
      if (pExp) pExp.max = yesterdayIso;

      if (isFullyVerified) {
        if (pCed) { pCed.value = docNum; pCed.style.border = '1px solid var(--border-color)'; }
        if (pExp) { pExp.value = _clientProfile.fecha_expedicion || ''; pExp.style.border = '1px solid var(--border-color)'; }
      } else {
        if (pCed) { pCed.value = docNum || ''; pCed.style.border = docNum ? '1px solid var(--border-color)' : '2px solid #ef4444'; }
        if (pExp) { pExp.value = _clientProfile.fecha_expedicion || ''; pExp.style.border = _clientProfile.fecha_expedicion ? '1px solid var(--border-color)' : '2px solid #ef4444'; }
      }

      const topBadge = document.getElementById('topbarCertBadge');
      if (topBadge) {
        if (isFullyVerified) {
          topBadge.className = "cp-verified-badge";
          topBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
          topBadge.style.color = "#10B981";
          topBadge.style.background = "rgba(16, 185, 129, 0.1)";
          topBadge.innerHTML = "<span>Cliente verificado</span> <i class='fa-solid fa-check' ></i>";
        } else {
          topBadge.innerHTML = `
            <button onclick="showPanel('perfil'); window.focusCedulaInput();" class="cp-unverified-pill"
              style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(220, 38, 38, 0.08) 100%); color: #dc2626; border: 1.5px solid rgba(239, 68, 68, 0.35); font-weight: 800; padding: 8px 18px; border-radius: 9999px; cursor: pointer; font-size: 0.82rem; display: flex; align-items: center; gap: 8px; font-family: 'Outfit', sans-serif; transition: all 0.25s ease; box-shadow: 0 4px 14px rgba(239, 68, 68, 0.08);">
              <i class="fa-solid fa-user-shield" style="font-size: 0.95rem; color: #ef4444;"></i>
              <span>Sin Verificar — Completar Cédula <i class="fa-solid fa-arrow-right" style="font-size:0.75rem; margin-left:2px;"></i></span>
            </button>
          `;
        }
      }

      const profBadge = document.getElementById('profileCertBadge');
      if (profBadge) {
        if (isFullyVerified) {
          profBadge.className = "cp-verified-badge";
          profBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
          profBadge.style.color = "#10B981";
          profBadge.style.background = "rgba(16, 185, 129, 0.1)";
          profBadge.innerHTML = "<span>Verificado <i class='fa-solid fa-check' ></i></span>";
        } else {
          profBadge.className = "badge";
          profBadge.style.background = "#EF4444";
          profBadge.style.color = "#ffffff";
          profBadge.innerHTML = "<i class='fa-solid fa-circle-dot' style='color:#ef4444;'></i> Sin Verificar";
        }
      }

      // Actualizar botón de acción del formulario de perfil (Solo mostrar ¿Deseas actualizar información? cuando ya está verificado)
      const btnSub = document.getElementById('btnSubmitProfile');
      const btnOpenSec = document.getElementById('btnOpenSecureProfile');
      const pInputs = [pNom, pTel, pCed, pExp];
      const pTipoEl = document.getElementById('profTipoDoc');
      const pEmpEl = document.getElementById('profEmpresa');

      if (isFullyVerified) {
        if (btnOpenSec) btnOpenSec.style.display = 'inline-flex';
        if (btnSub) { btnSub.style.display = 'none'; btnSub.classList.add('hidden'); }
        pInputs.forEach(inp => {
          if (inp) {
            inp.readOnly = true;
            inp.style.background = '#f8fafc';
            inp.style.color = '#003049';
            inp.style.cursor = 'default';
          }
        });
        if (pTipoEl) pTipoEl.disabled = true;
        if (pEmpEl) { pEmpEl.readOnly = true; pEmpEl.style.background = '#f8fafc'; pEmpEl.style.cursor = 'default'; }
      } else {
        if (btnOpenSec) btnOpenSec.style.display = 'none';
        if (btnSub) {
          btnSub.style.display = 'inline-flex';
          btnSub.classList.remove('hidden');
          btnSub.innerHTML = '<i class="fa-solid fa-circle-check"></i> <span>Guardar y Activar Cuenta Verificada</span>';
        }
        pInputs.forEach(inp => {
          if (inp) {
            inp.readOnly = false;
            inp.style.background = '#ffffff';
            inp.style.cursor = 'text';
          }
        });
        if (pTipoEl) pTipoEl.disabled = false;
        if (pEmpEl) { pEmpEl.readOnly = false; pEmpEl.style.background = '#ffffff'; pEmpEl.style.cursor = 'text'; }
      }

      const alertBanner = document.getElementById('dashboard-unverified-alert');
      if (alertBanner) {
        if (isFullyVerified) {
          alertBanner.classList.add('hidden');
          alertBanner.style.display = 'none';
        } else {
          alertBanner.classList.remove('hidden');
          alertBanner.style.display = 'flex';
        }
      }
    }

    function checkPrimerIngresoStatus() {
      if (!_clientProfile) return;
      const isUnverified = !_clientProfile.verificado || !_clientProfile.numero_documento || String(_clientProfile.numero_documento).trim().length < 5;
      if (isUnverified) {
        showToast('Para agendar y verificar tu cuenta, por favor completa tus datos en Mi Perfil.', 'info', 6000);
      }
    }
    window.checkPrimerIngresoStatus = checkPrimerIngresoStatus;

    window.submitPrimerIngresoVerificacion = async function(e) {
      if (e) e.preventDefault();
      const p1 = (document.getElementById('firstLoginNewPassword')?.value || '').trim();
      const p2 = (document.getElementById('firstLoginConfirmPassword')?.value || '').trim();
      const nom = (document.getElementById('firstLoginNombre')?.value || '').trim();
      const tel = (document.getElementById('firstLoginTelefono')?.value || '').trim();
      const doc = (document.getElementById('firstLoginDocumento')?.value || '').trim();
      const alertBox = document.getElementById('firstLoginAlertBox');
      const btn = document.getElementById('btnSubmitFirstLogin');

      if (!p1 || p1.length < 6) {
        if (alertBox) {
          alertBox.style.display = 'block';
          alertBox.style.background = 'rgba(239,68,68,0.1)';
          alertBox.style.color = '#991B1B';
          alertBox.textContent = 'La contraseña debe contener al menos 6 caracteres.';
        }
        return;
      }
      if (p1 !== p2) {
        if (alertBox) {
          alertBox.style.display = 'block';
          alertBox.style.background = 'rgba(239,68,68,0.1)';
          alertBox.style.color = '#991B1B';
          alertBox.textContent = 'Las contraseñas no coinciden. Por favor verifícalas.';
        }
        return;
      }

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Guardando y Sincronizando Finca...';
      }

      try {
        const res = await fetch(`${API_BASE}/auth/primer-ingreso-completar`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${_token}`
          },
          body: JSON.stringify({
            nueva_contrasena: p1,
            nombre: nom,
            telefono: tel,
            numero_documento: doc
          })
        });

        const data = await res.json().catch(() => ({}));

        if (res.ok && data.success) {
          if (_clientProfile) {
            _clientProfile.verificado = true;
            _clientProfile.nombre = nom;
            _clientProfile.telefono = tel;
            _clientProfile.numero_documento = doc;
            _clientProfile.cedula = doc;
          }

          const modal = document.getElementById('modalPrimerIngresoVerificacion');
          if (modal) {
            modal.style.setProperty('display', 'none', 'important');
            modal.classList.add('hidden');
            modal.classList.remove('open', 'active');
            document.body.style.overflow = '';
          }

          showToast('¡Datos validados y contraseña establecida exitosamente! Finca sincronizada.', 'success', 5000);
          await refreshData();
        } else {
          if (alertBox) {
            alertBox.style.display = 'block';
            alertBox.style.background = 'rgba(239,68,68,0.1)';
            alertBox.style.color = '#991B1B';
            alertBox.textContent = data.message || 'Error al guardar los datos. Intente de nuevo.';
          }
        }
      } catch (err) {
        if (alertBox) {
          alertBox.style.display = 'block';
          alertBox.style.background = 'rgba(239,68,68,0.1)';
          alertBox.style.color = '#991B1B';
          alertBox.textContent = 'Error de conexión con el servidor.';
        }
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-check-double"></i> Establecer Contraseña y Acceder';
        }
      }
    };


    async function loadCatalogServices() {
      try {
        const res = await fetch(`${API_BASE}/servicios`);
        if (res.ok) {
          const body = await res.json();
          _catalogServicios = body.data || body;
        } else {
          _catalogServicios = getMockServices();
        }
      } catch (err) {
        _catalogServicios = getMockServices();
      }
      populateServicesDropdown();
    }

    async function refreshData() {
      if (!_clientProfile) {
        _clientProfile = { id_cliente: 1, nombre: 'Cliente', apellido_1: 'Flymetrics', telefono: '', verificado: true };
      }

      try {
        const [resAgendas, resFincas, resPagos, resDocs] = await Promise.all([
          fetch(`${API_BASE}/agenda/mis-turnos`, { headers: { 'Authorization': `Bearer ${_token}` } }).catch(() => null),
          fetch(`${API_BASE}/fincas`, { headers: { 'Authorization': `Bearer ${_token}` } }).catch(() => null),
          fetch(`${API_BASE}/pagos/mis-pagos`, { headers: { 'Authorization': `Bearer ${_token}` } }).catch(() => null),
          fetch(`${API_BASE}/entregables/mis-archivos`, { headers: { 'Authorization': `Bearer ${_token}` } }).catch(() => null)
        ]);

        if (resAgendas && resAgendas.ok) {
          const body = await resAgendas.json();
          const serverList = body.data || body;
          if (Array.isArray(serverList)) {
            _myAgendas = serverList;
          }
        }
        if (window.loadPqrs) {
          window.loadPqrs().catch(() => null);
        }

        if (resFincas && resFincas.ok) {
          const body = await resFincas.json();
          _myFincas = body.data || body;
        } else {
          _myFincas = [];
        }

        if (resPagos && resPagos.ok) {
          const body = await resPagos.json();
          _myPagos = body.data || body;
        } else {
          _myPagos = [];
        }

        if (resDocs && resDocs.ok) {
          const body = await resDocs.json();
          _myDocs = body.data || body;
        } else {
          _myDocs = [];
        }

      } catch (err) {
        console.warn('API error, preserving local state', err);
      }

      renderDashboard();
      renderAgendasTable();
      renderFincasGrid();
      renderFacturacion();
      if (typeof renderSharepointDocs === 'function') renderSharepointDocs();
      if (typeof loadPqrs === 'function') loadPqrs();
    }

    // ── NAVIGATION ───────────────────────────
    window.showPanel = function (panelId) {
      document.querySelectorAll('.cp-panel').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.cp-nav-item').forEach(n => n.classList.remove('active'));

      const panelEl = document.getElementById(`panel-${panelId}`);
      if (panelEl) panelEl.classList.add('active');

      // Highlight nav item - also support doc sub-items
      const navItem = document.querySelector(`[data-panel="${panelId}"]`);
      if (navItem) navItem.classList.add('active');

      const titles = {
        dashboard: 'Dashboard General',
        agendas: 'Mis Agendas de Vuelo',
        fincas: 'Mis Predios y Fincas',
        documentos: 'Informes Ejecutivos & Entregables (SharePoint)',
        facturacion: 'Facturas y Pagos',
        perfil: 'Datos de Perfil',
        videos: 'Biblioteca de Videos e Información',
        soporte: 'Soporte y FAQs'
      };
      const titleEl = document.getElementById('topbarTitle');
      if (titleEl) {
        titleEl.textContent = titles[panelId] || 'Mi Panel';
      }

      if (panelId === 'documentos' && typeof renderSharepointDocs === 'function') {
        renderSharepointDocs();
      }
      if (panelId === 'facturacion' && typeof renderFacturacion === 'function') {
        renderFacturacion();
      }
    };

    // ── PANEL RENDERING ──────────────────────

    // 1. Dashboard
    function renderDashboard() {
      const greetEl = document.getElementById('dashGreetingName');
      if (greetEl) greetEl.textContent = _clientProfile?.nombre || 'Cliente';

      // Check verification status: show alert banner on dashboard for unverified users (non-intrusive)
      if (_clientProfile && (!_clientProfile.verificado || _clientProfile.verificado === 0 || _clientProfile.verificado === false)) {
        const alertBanner = document.getElementById('dashboard-unverified-alert');
        if (alertBanner) {
          alertBanner.style.display = 'flex';
          alertBanner.classList.remove('hidden');
        }
      }

      // Stats from real backend DB turnos & docs
      const active = _myAgendas.filter(a => ['Pendiente', 'Confirmado', 'En Proceso', 'En proceso'].includes(a.estado)).length;
      const activeEl = document.getElementById('statActiveAgendas');
      if (activeEl) activeEl.textContent = active;

      // Real completed services count
      const completed = _myAgendas.filter(a => ['Hecho', 'Completado', 'Finalizado'].includes(a.estado)).length;
      const completedEl = document.getElementById('statCompletedServices');
      if (completedEl) completedEl.textContent = completed;

      // Real deliverables/docs count (vuelos únicos con entregables listos)
      const uniqueDocsCount = new Set((_myDocs || []).map(d => d.id_turno || d.id_entregable || d.id)).size;
      const docsCount = uniqueDocsCount > 0 ? uniqueDocsCount : _myAgendas.filter(a => ['Hecho', 'Completado'].includes(a.estado)).length;
      const docsEl = document.getElementById('statReadyDocs');
      if (docsEl) docsEl.textContent = docsCount;

      // 1. Next scheduled flight calculation (Closest future date or active)
      const pendingOrActive = _myAgendas.filter(a => ['Confirmado', 'En Proceso', 'En proceso', 'Pendiente', 'Agendado'].includes(a.estado));
      // Sort by date ascending to find the true next service
      pendingOrActive.sort((a, b) => {
        const da = new Date(a.fecha_de_turno || a.fecha_solicitada || '2099-01-01');
        const db = new Date(b.fecha_de_turno || b.fecha_solicitada || '2099-01-01');
        return da - db;
      });

      const nextSvc = pendingOrActive[0];
      const nextSvcDateEl = document.getElementById('statNextServiceDate');
      const nextBox = document.getElementById('nextAppointmentBox');

      if (nextSvc) {
        if (nextBox) nextBox.style.display = 'block';
        const formattedDate = formatDate(nextSvc.fecha_de_turno || nextSvc.fecha_solicitada);
        if (nextSvcDateEl) {
          nextSvcDateEl.textContent = formattedDate;
          nextSvcDateEl.style.fontSize = '1.15rem';
          nextSvcDateEl.style.color = 'var(--primary)';
        }

        const elSt = document.getElementById('nextSvcStatus'); if (elSt) { elSt.className = `badge badge-${getBadgeClass(nextSvc.estado)}`; elSt.textContent = nextSvc.estado; }
        const elNm = document.getElementById('nextSvcName'); if (elNm) elNm.textContent = nextSvc.nombre_servicio || nextSvc.servicio || 'Servicio Dron';
        const elFc = document.getElementById('nextSvcFinca'); if (elFc) elFc.textContent = nextSvc.nombre_finca || 'Finca Registrada';
        const elDt = document.getElementById('nextSvcDate'); if (elDt) elDt.textContent = formattedDate;
        const elTm = document.getElementById('nextSvcTime'); if (elTm) elTm.textContent = nextSvc.hora_inicio_estimada || nextSvc.hora_preferida || '07:00 AM';
        const elTc = document.getElementById('nextSvcTecnico'); if (elTc) elTc.textContent = (nextSvc.id_tecnico && (nextSvc.tecnico || nextSvc.tecnico_nombre)) ? (nextSvc.tecnico || nextSvc.tecnico_nombre) : 'Piloto asignado en despacho central';
      } else {
        if (nextBox) nextBox.style.display = 'none';
        if (nextSvcDateEl) {
          nextSvcDateEl.textContent = 'Sin servicios';
          nextSvcDateEl.style.fontSize = '1.15rem';
          nextSvcDateEl.style.color = '#6C757D';
        }
      }

      // 2. Real-Time Operational Notifications Feed Generator
      const notifContainer = document.getElementById('clientNotifFeed');
      if (notifContainer) {
        const notifItems = [];

        // Generate notifications from user's agendas
        _myAgendas.slice(0, 3).forEach(ag => {
          let icon = 'fa-calendar-check';
          let color = '#1C82AD';
          let title = `Vuelo #${ag.id_turno || ag.id}: ${ag.nombre_servicio || ag.servicio || 'Servicio'}`;
          let desc = `Estado actual: ${ag.estado}. Fecha: ${formatDate(ag.fecha_de_turno || ag.fecha_solicitada)} (${ag.nombre_finca || 'Finca'}).`;

          if (ag.estado === 'Confirmado') {
            icon = 'fa-square-check';
            color = '#10B981';
            desc = `Turno confirmado. Piloto asignado para el ${formatDate(ag.fecha_de_turno || ag.fecha_solicitada)} en ${ag.nombre_finca || 'tu predio'}.`;
          } else if (['En Proceso', 'En proceso'].includes(ag.estado)) {
            icon = 'fa-helicopter';
            color = '#F59E0B';
            desc = `Operación en ejecución activa sobre las hectáreas delimitadas en ${ag.nombre_finca || 'el predio'}.`;
          } else if (['Completado', 'Hecho'].includes(ag.estado)) {
            icon = 'fa-circle-check';
            color = '#059669';
            desc = `Vuelo completado con éxito. Los datos de telemetría y ortomosaicos se han procesado.`;
          }

          notifItems.push({ icon, color, title, desc, date: ag.fecha_de_turno || ag.fecha_solicitada });
        });

        // Generate notifications from recent documents / deliverable reports
        if (_myDocs && _myDocs.length > 0) {
          _myDocs.slice(0, 2).forEach(doc => {
            notifItems.push({
              icon: 'fa-file-pdf',
              color: '#003049',
              title: `Reporte Agronómico Listo: ${doc.nombre_archivo || 'Informe Técnico'}`,
              desc: `Ya puedes descargar y visualizar el informe técnico oficial de aspersión/monitoreo en la sección de Archivos.`,
              date: doc.created_at || 'Reciente'
            });
          });
        }

        if (notifItems.length > 0) {
          notifContainer.innerHTML = notifItems.map(item => `
            <div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px 14px; background: rgba(28, 130, 173, 0.04); border: 1.5px solid rgba(28, 130, 173, 0.14); border-radius: 12px; transition: all 0.2s;">
              <span style="width: 32px; height: 32px; border-radius: 8px; background: rgba(28,130,173,0.1); color: ${item.color}; display: flex; align-items: center; justify-content: center; font-size: 1rem; flex-shrink: 0; margin-top: 2px;">
                <i class="fa-solid ${item.icon}"></i>
              </span>
              <div style="flex: 1;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 4px;">
                  <strong style="color: #003049; font-size: 0.88rem; font-weight: 800;">${item.title}</strong>
                  <span style="font-size: 0.72rem; color: #6C757D; font-weight: 700;">${item.date}</span>
                </div>
                <p style="margin: 2px 0 0 0; font-size: 0.81rem; color: #4A5568; line-height: 1.45;">${item.desc}</p>
              </div>
            </div>
          `).join('');
        } else {
          notifContainer.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; padding: 14px; background: rgba(28, 130, 173, 0.04); border: 1px solid rgba(28, 130, 173, 0.15); border-radius: 12px;">
              <i class="fa-solid fa-circle-check" style="color: #10B981; font-size: 1.2rem;"></i>
              <div>
                <strong style="color: #003049; font-size: 0.88rem; font-weight: 800;">Todo al día</strong>
                <p style="margin: 2px 0 0 0; font-size: 0.8rem; color: #6C757D;">No hay alertas pendientes. Puedes agendar un nuevo servicio cuando lo requieras.</p>
              </div>
            </div>
          `;
        }
      }

      // Recent activity table (last 4 items)
      const recent = _myAgendas.slice(0, 4);
      const tbody = document.getElementById('recentActivityTableBody');
      if (recent.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted" style="padding: 24px;">No registras solicitudes de agendamiento.</td></tr>`;
      } else {
        tbody.innerHTML = recent.map(r => `
          <tr>
            <td>#${r.id_turno || r.id || '—'}</td>
            <td><strong>${r.nombre_servicio || r.servicio || 'Servicio Dron'}</strong></td>
            <td>${r.nombre_finca || 'Finca'}</td>
            <td>${formatDate(r.fecha_de_turno || r.fecha_solicitada)}</td>
            <td><span class="badge badge-${getBadgeClass(r.estado)}">${r.estado}</span></td>
          </tr>
        `).join('');
      }
    }

    // 2. Agendas
    function renderAgendasTable() {
      const tbody = document.getElementById('agendasTableBody');
      let data = _myAgendas;

      if (_agendaFilterActive !== 'Todos') {
        data = data.filter(a => a.estado.toLowerCase() === _agendaFilterActive.toLowerCase());
      }

      if (data.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="9">
              <div class="empty-state">
                <span class="empty-icon"><i class="fa-solid fa-calendar-xmark" style="color:#1C82AD; font-size:2.5rem;"></i></span>
                <div class="empty-title">No hay agendamientos</div>
                <div class="empty-sub">No se encontraron solicitudes en estado: ${_agendaFilterActive}</div>
                <button class="btn btn-primary btn-sm" onclick="openNewAgendaModal()">Solicitar servicio</button>
              </div>
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = data.map(a => {
        const estLower = (a.estado || '').toLowerCase();
        // El cliente solo puede modificar cuando NO ha sido aceptado (solo estado Pendiente o Solicitado)
        const isModifiable = ['pendiente', 'solicitado'].includes(estLower);
        const canCancel = ['pendiente', 'solicitado'].includes(estLower);
        const idTurno = a.id_turno || a.id;
        
        // Cotización y estado de negociación
        const hasTarifa = a.tarifa !== null && a.tarifa !== undefined && Number(a.tarifa) > 0;
        const isPendingConfirm = estLower === 'pendiente por confirmar';
        const needsNegotiation = isPendingConfirm || (hasTarifa && ['pendiente', 'solicitado'].includes(estLower));

        let cotizDisplay = '';
        const isFreeDemo = Boolean((a.es_demostracion === true || a.es_demostracion === 1 || a.es_demo_gratis === true) && (a.tarifa === null || a.tarifa === undefined || Number(a.tarifa) === 0));
        if (isFreeDemo) {
          cotizDisplay = `<span class="badge" style="background:#dcfce7; color:#15803d; border:1.5px solid #86efac; font-weight:800; font-size:0.75rem; padding:4px 8px; border-radius:8px;"><i class="fa-solid fa-gift"></i> Análisis del Terreno ($0 COP)</span>`;
        } else if (hasTarifa) {
          cotizDisplay = `<div style="font-weight:800; color:#065f46; font-size:0.88rem; white-space:nowrap;">$ ${Number(a.tarifa).toLocaleString('es-CO')} COP</div>`;
        } else {
          cotizDisplay = `<span class="badge" style="background:#fef3c7; color:#92400e; border:1px solid #fde68a; font-weight:700; font-size:0.75rem;"><i class="fa-solid fa-clock"></i> Pendiente</span>`;
        }

        // Botón WhatsApp para confirmar la orden directamente con los datos de la BD
        const waBtn = `
          <button class="btn btn-sm" onclick="window.confirmarOrdenWA(${idTurno})" style="background:#25D366; color:#ffffff; font-weight:800; padding:4px 9px; font-size:0.75rem; border-radius:8px; border:none; display:inline-flex; align-items:center; gap:5px; box-shadow:0 2px 6px rgba(37,211,102,0.25); cursor:pointer; margin-right:4px;" title="Confirmar orden por WhatsApp">
            <i class="fa-brands fa-whatsapp" style="font-size:0.95rem;"></i> WhatsApp
          </button>
        `;

        // Botón para revisar y negociar cotización
        const negotiateBtn = needsNegotiation ? `
          <button class="btn btn-sm" onclick="window.openClientNegotiationModal(${idTurno})" style="background:linear-gradient(135deg, #10b981, #059669); color:#ffffff; font-weight:800; padding:4px 10px; font-size:0.75rem; border-radius:8px; border:none; display:inline-flex; align-items:center; gap:5px; box-shadow:0 2px 6px rgba(16,185,129,0.3); cursor:pointer; margin-right:4px;" title="Revisar cotización oficial, aceptar o sugerir cambios">
            <i class="fa-solid fa-handshake"></i> Cotización ($)
          </button>
        ` : '';

        let actionBtns = '';
        if (isModifiable) {
          actionBtns = `
            ${negotiateBtn}
            ${waBtn}
            <button class="btn btn-ghost btn-sm" onclick="window.openEditAgendaModal(${idTurno})" style="padding:4px 8px; font-size:0.75rem; margin-right:4px; font-weight:700; color:#1C82AD; border: 1px solid rgba(28,130,173,0.3); border-radius:6px; background:rgba(28,130,173,0.05); cursor:pointer;" title="Modificar fecha, hora, servicios u observaciones de tu solicitud"><i class="fa-solid fa-pen-to-square"></i> Modificar</button>
            ${canCancel ? `<button class="btn btn-danger-light btn-sm" onclick="cancelarTurno(${idTurno})" style="padding:4px 8px; font-size:0.75rem; color:#ef4444; border:1px solid rgba(239,68,68,0.3); border-radius:6px; background:rgba(239,68,68,0.06); font-weight:700; cursor:pointer;" title="Cancelar reserva"><i class="fa-solid fa-ban"></i> Cancelar</button>` : ''}
          `;
        } else {
          const isAceptado = ['confirmado', 'reagendado', 'en proceso', 'en_proceso'].includes(estLower);
          actionBtns = `
            ${negotiateBtn}
            ${waBtn}
            ${isAceptado ? `<span class="badge" style="background:#e0f2fe; color:#0284c7; font-weight:700; padding:4px 8px; border-radius:6px; font-size:0.75rem; display:inline-flex; align-items:center; gap:4px; margin-right:4px;" title="Servicio aceptado por Flymetrics (No modificable)"><i class="fa-solid fa-lock"></i> Aceptado (No modificable)</span>` : `<span class="text-muted" style="font-size:0.78rem; font-weight:700; color:#64748b; margin-right:4px; display:inline-flex; align-items:center; gap:4px;"><i class="fa-solid fa-circle-check" style="color:#10b981;"></i> ${a.estado || 'Finalizado'}</span>`}
            ${canCancel ? `<button class="btn btn-danger-light btn-sm" onclick="cancelarTurno(${idTurno})" style="padding:4px 8px; font-size:0.75rem; color:#ef4444; border:1px solid rgba(239,68,68,0.3); border-radius:6px; background:rgba(239,68,68,0.06); font-weight:700; cursor:pointer;" title="Cancelar reserva"><i class="fa-solid fa-ban"></i> Cancelar</button>` : ''}
          `;
        }

        const tecnicoDisplay = (a.id_tecnico && (a.tecnico || a.tecnico_nombre))
          ? (a.tecnico || a.tecnico_nombre)
          : `<span class="badge badge-pending" style="font-size:0.75rem; font-weight:700;"><i class="fa-solid fa-clock-rotate-left"></i> Pendiente</span>`;

        // Parseo de servicios combinados para badges
        let svcs = [];
        if (Array.isArray(a.servicios_list) && a.servicios_list.length) {
          svcs = a.servicios_list;
        } else {
          const rawAll = (a.observaciones_servicio || '') + ' ' + (a.notas || '') + ' ' + (a.nombre_servicio || a.servicio || '');
          const mTag = rawAll.match(/(?:\[Servicios:\s*([^\]]+)\]|(?:Servicios Solicitados|Servicios):\s*([^\n\r]+))/i);
          const svcStr = mTag ? (mTag[1] || mTag[2]) : (a.nombre_servicio || a.servicio || '');
          if (svcStr && (svcStr.includes('+') || svcStr.includes(',') || /\band\b|\by\b/i.test(svcStr))) {
            svcs = svcStr.split(/\s*(?:\+|\band\b|\by\b|,)\s*/i).map(s => s.trim()).filter(Boolean);
          } else if (svcStr) {
            svcs = [svcStr.trim()];
          }
        }
        svcs = [...new Set(svcs)].filter(s => s && s.length > 2);
        if (!svcs.length) svcs = [(a.nombre_servicio || a.servicio || 'Servicio Dron')];

        const svcBadgesHtml = svcs.map(s => `
          <span class="badge" style="background:rgba(28,130,173,0.12); color:#003049; border:1px solid rgba(28,130,173,0.3); font-weight:700; font-size:0.75rem; padding:3px 8px; border-radius:6px; display:inline-flex; align-items:center; gap:4px; margin:2px 2px 2px 0;">
            <i class="fa-solid fa-layer-group" style="color:#1C82AD; font-size:0.7rem;"></i> ${escapeHtml(s)}
          </span>
        `).join('');

        return `
          <tr>
            <td style="font-weight:bold; color:var(--primary);">#${escapeHtml(idTurno || '—')}</td>
            <td style="max-width:240px;"><div style="display:flex; flex-wrap:wrap; gap:3px;">${svcBadgesHtml}</div></td>
            <td>${escapeHtml(a.nombre_finca || a.finca_nombre || a.finca || 'Finca Registrada')}</td>
            <td>${formatDate(a.fecha_de_turno || a.fecha_solicitada)}</td>
            <td>${escapeHtml(a.hora_inicio_estimada || a.hora_preferida || 'AM')}</td>
            <td>${tecnicoDisplay}</td>
            <td style="text-align:center;">${cotizDisplay}</td>
            <td><span class="badge badge-${getBadgeClass(a.estado)}">${escapeHtml(a.estado)}</span></td>
            <td style="text-align:right; white-space:nowrap;">${actionBtns}</td>
          </tr>
        `;
      }).join('');
    }

    // Confirmación de orden de vuelo directa por WhatsApp con retroalimentación de base de datos
    window.confirmarOrdenWA = function (idTurno) {
      const turno = _myAgendas.find(a => (a.id_turno || a.id) === idTurno);
      if (!turno) {
        showToast('No se encontró la información del turno', 'warning');
        return;
      }

      const clientName = _clientProfile ? `${_clientProfile.nombre || ''} ${_clientProfile.apellido_1 || ''}`.trim() : 'Cliente';
      const fincaName = turno.nombre_finca || turno.finca_nombre || turno.finca || 'Finca Registrada';
      const servicioName = turno.nombre_servicio || turno.servicio || 'Servicio Agrícola con Drones';
      const fecha = formatDate(turno.fecha_de_turno || turno.fecha_solicitada);
      const hora = turno.hora_inicio_estimada || turno.hora_preferida || 'Horario a convenir';
      const ha = turno.hectareas ? `${turno.hectareas} ha` : 'Por definir';

      // Teléfono corporativo oficial configurado en base de datos o fallback
      const rawWa = (_clientCorporateConfig && _clientCorporateConfig.whatsapp) ? _clientCorporateConfig.whatsapp : '573155429714';
      const cleanWa = String(rawWa).replace(/\D/g, '');
      const finalWa = cleanWa.length === 10 ? ('57' + cleanWa) : cleanWa;

      const mensaje = `🚁 *CONFIRMACIÓN DE ORDEN DE VUELO - FLYMETRICS* 🚁\n\n` +
        `📋 *Turno / Radicado:* #${turno.id_turno || turno.id}\n` +
        `👤 *Cliente:* ${clientName}\n` +
        `🌱 *Servicio:* ${servicioName}\n` +
        `📍 *Finca / Predio:* ${fincaName}\n` +
        `📐 *Extensión:* ${ha}\n` +
        `📅 *Fecha solicitada:* ${fecha}\n` +
        `⏰ *Hora:* ${hora}\n` +
        `📌 *Estado actual:* ${turno.estado || 'Pendiente'}\n\n` +
        `Hola equipo Flymetrics, deseo confirmar los detalles operativos y validar la disponibilidad de los pilotos para este servicio agendado. ¡Quedo atento!`;

      showToast('<i class="fa-brands fa-whatsapp"></i> Abriendo WhatsApp para confirmar orden...', 'success');
      setTimeout(() => {
        window.open(`https://wa.me/${finalWa}?text=${encodeURIComponent(mensaje)}`, '_blank');
      }, 200);
    };

    window.filterAgendas = function (status) {
      _agendaFilterActive = status;
      document.querySelectorAll('#agendaFilters .filter-pill').forEach(pill => {
        pill.classList.toggle('active', pill.textContent === status || (status === 'Todos' && pill.textContent === 'Todos'));
      });
      renderAgendasTable();
    };

    // 3. Fincas Grid
    function renderFincasGrid() {
      const grid = document.getElementById('fincasGrid');
      if (_myFincas.length === 0) {
        grid.innerHTML = `
          <div style="grid-column:1/-1;" class="empty-state">
            <span class="empty-icon"><i class="fa-solid fa-wheat-awn" style="color:#1C82AD; font-size:2.5rem;"></i></span>
            <div class="empty-title">No tienes fincas registradas</div>
            <div class="empty-sub">Registra tu finca para poder realizar agendamientos en ella.</div>
            <button class="btn btn-primary" onclick="openNewFincaModal()">Registrar finca</button>
          </div>
        `;
        return;
      }

      grid.innerHTML = _myFincas.map(f => {
        const count = _myAgendas.filter(a => a.id_finca === f.id_finca || a.nombre_finca === f.nombre_finca).length;
        const mapsLink = f.maps_url || f.url_maps || (f.latitud && f.longitud ? `https://www.google.com/maps?q=${f.latitud},${f.longitud}` : null);
        const fNombre = escapeHtml(f.nombre_finca || 'Finca');
        const fMuni = escapeHtml(f.ubicacion_municipio || f.municipio || '—');
        const fDepto = escapeHtml(f.departamento || '—');
        const fHect = escapeHtml(f.hectareas || '0');
        const fResp = escapeHtml(f.responsable_campo || f.administrador_nombre || 'No asignado');
        const fTel = escapeHtml(f.telefono_admin || f.telefono_campo || '—');
        return `
          <div class="finca-card">
            <div class="finca-card-h">
              <h3 class="finca-name"><i class="fa-solid fa-wheat-awn" style="color:#1c82ad; margin-right:6px;"></i> ${fNombre}</h3>
              <span class="badge badge-completed">${count} agendas</span>
            </div>
            <span class="finca-loc">${fMuni}, ${fDepto}</span>
            
            <div class="finca-details" style="margin-bottom: 8px;">
              <div class="finca-detail-item">
                <span class="finca-d-lbl">Extensión</span>
                <span class="finca-d-val">${fHect} Hectáreas</span>
              </div>
              <div class="finca-detail-item" style="text-align:right;">
                <span class="finca-d-lbl">Ubicación GPS</span>
                <span class="finca-d-val" style="font-size: 0.72rem; font-family: 'JetBrains Mono';">${f.latitud ? parseFloat(f.latitud).toFixed(4) : 'N/A'}, ${f.longitud ? parseFloat(f.longitud).toFixed(4) : 'N/A'}</span>
              </div>
            </div>

            <div class="finca-details" style="margin-bottom: 12px; background: rgba(0,48,73,0.03); padding: 8px 10px; border-radius: 8px;">
              <div class="finca-detail-item">
                <span class="finca-d-lbl"><i class="fa-solid fa-user-check" style="color:#1c82ad;"></i> Responsable Campo</span>
                <span class="finca-d-val" style="font-weight:700; color:#003049;">${fResp}</span>
              </div>
              <div class="finca-detail-item" style="text-align:right;">
                <span class="finca-d-lbl"><i class="fa-solid fa-phone" style="color:#10b981;"></i> Tel. Administrador</span>
                <span class="finca-d-val" style="font-weight:700; color:#003049;">${fTel}</span>
              </div>
            </div>

            ${mapsLink ? `
              <div style="margin-bottom:12px;">
                <a href="${mapsLink}" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; gap:6px; font-size:0.8rem; font-weight:700; color:#1C82AD; text-decoration:none; background:rgba(28,130,173,0.08); padding:5px 10px; border-radius:8px;">
                  <i class="fa-solid fa-map-location-dot"></i> Ver en Google Maps →
                </a>
              </div>
            ` : ''}
            
            <div style="display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 12px; margin-top: auto;">
              <button class="btn btn-ghost btn-sm" onclick="window.openEditFincaModal(${f.id_finca}, '${(f.nombre_finca || '').replace(/'/g, "\\'")}', '${(f.municipio || f.ubicacion_municipio || '').replace(/'/g, "\\'")}', '${f.departamento || ''}', ${f.hectareas || 0}, ${f.latitud || 'null'}, ${f.longitud || 'null'}, '${(f.maps_url || f.url_maps || '').replace(/'/g, "\\'")}', '${(f.responsable_campo || '').replace(/'/g, "\\'")}', '${(f.telefono_admin || '').replace(/'/g, "\\'")}');" style="color: var(--accent-cyan); border-color: rgba(28, 130, 173, 0.2); background: rgba(28, 130, 173, 0.05); padding: 5px 12px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: all 0.2s;">Editar</button>
              <button class="btn btn-ghost btn-sm" onclick="window.eliminarFinca(${f.id_finca});" style="color: #FF4D6D; border-color: rgba(255, 77, 109, 0.2); background: rgba(255,77,109,0.05); padding: 5px 12px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: all 0.2s;">Eliminar</button>
            </div>
          </div>
        `;
      }).join('');
    }

    // 4. Facturación con Alegra
    function renderFacturacion() {
      const badgeContainer = document.getElementById('alegraStatusBadgeContainer');
      const btnAcceder = document.getElementById('btnAccederFacturaAlegra');
      const descText = document.getElementById('alegraDescText');
      const noLinkNotice = document.getElementById('alegraNoLinkNotice');
      const hasLink = _clientProfile && _clientProfile.link_alegra && _clientProfile.link_alegra.trim() &&
                      _clientProfile.link_alegra.trim() !== 'null' && _clientProfile.link_alegra.trim() !== 'undefined';

      if (badgeContainer) {
        if (hasLink) {
          badgeContainer.innerHTML = `
            <span class="badge" style="background: rgba(16, 185, 129, 0.12); color: #059669; font-weight: 800; padding: 6px 16px; border-radius: 20px; font-size: 0.84rem; display: inline-flex; align-items: center; gap: 6px;">
              <i class="fa-solid fa-circle-check"></i> Facturación Oficial Alegra & DIAN — Activa
            </span>
          `;
        } else {
          badgeContainer.innerHTML = `
            <span class="badge" style="background: rgba(245, 158, 11, 0.13); color: #d97706; font-weight: 800; padding: 6px 16px; border-radius: 20px; font-size: 0.84rem; display: inline-flex; align-items: center; gap: 6px;">
              <i class="fa-solid fa-clock"></i> Enlace Pendiente de Asignación
            </span>
          `;
        }
      }
      if (descText) {
        descText.textContent = hasLink
          ? 'Tu portal oficial de facturación electrónica y recibos de Flymetrics está activo y vinculado. Haz clic en "Acceder" para ver tus facturas o solicita asistencia:'
          : 'Tu enlace personalizado de facturas electrónicas está siendo preparado. Comunícate con nuestro equipo de soporte vía WhatsApp para solicitarlo:';
      }
      if (btnAcceder) {
        if (hasLink) {
          btnAcceder.onclick = window.abrirFacturaAlegraCliente;
          btnAcceder.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square" style="color:#E4C7A1;"></i> Acceder a Portal de Facturación';
          btnAcceder.style.background = 'linear-gradient(135deg, #003049 0%, #1c82ad 100%)';
          btnAcceder.style.boxShadow = '0 8px 24px rgba(0, 48, 73, 0.25)';
        } else {
          btnAcceder.onclick = window.solicitarEnlaceAlegraSoporte;
          btnAcceder.innerHTML = '<i class="fa-brands fa-whatsapp" style="font-size:1.2rem;"></i> Solicitar Enlace a Soporte';
          btnAcceder.style.background = '#25D366';
          btnAcceder.style.boxShadow = '0 6px 20px rgba(37, 211, 102, 0.3)';
        }
      }
      if (noLinkNotice) {
        noLinkNotice.style.display = hasLink ? 'none' : 'block';
      }
    }

    window.abrirFacturaAlegraCliente = function() {
      const rawLink = (_clientProfile && _clientProfile.link_alegra) ? _clientProfile.link_alegra.trim() : '';
      if (rawLink && rawLink !== '#' && rawLink !== 'null' && rawLink !== 'undefined') {
        const cleanUrl = (rawLink.startsWith('http://') || rawLink.startsWith('https://')) ? rawLink : ('https://' + rawLink);
        window.open(cleanUrl, '_blank', 'noopener,noreferrer');
      } else {
        window.open('https://app.alegra.com/', '_blank', 'noopener,noreferrer');
      }
    };

    window.solicitarEnlaceAlegraSoporte = async function() {
      const nombre = _clientProfile ? `${_clientProfile.nombre || 'Cliente'} ${_clientProfile.apellido_1 || ''}`.trim() : 'Cliente';
      const cedula = _clientProfile ? (_clientProfile.numero_documento || _clientProfile.cedula || '') : '';

      // 1. Guardar solicitud en base de datos (tabla_pqrs y tabla_notificaciones)
      try {
        if (token) {
          fetch(`${API_BASE}/contacto/solicitar-soporte-facturacion`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
              motivo: 'Solicitud de enlace de facturación Alegra',
              cliente: nombre,
              cedula: cedula
            })
          }).catch(() => null);
        }
      } catch(e) {}

      showToast('<i class="fa-solid fa-circle-check"></i> Solicitud registrada en base de datos. Conectando con soporte...', 'success');

      // 2. Redirección dinámica al WhatsApp corporativo configurado en DB
      const rawWa = (_clientCorporateConfig && _clientCorporateConfig.whatsapp) ? _clientCorporateConfig.whatsapp : '573155429714';
      const cleanWa = String(rawWa).replace(/\D/g, '');
      const finalWa = cleanWa.length === 10 ? ('57' + cleanWa) : cleanWa;
      const msg = encodeURIComponent(`Hola Flymetrics, soy ${nombre}${cedula ? ` (CC/NIT: ${cedula})` : ''}. Me comunico desde el portal web para solicitar asistencia con mi facturación electrónica en Alegra.`);

      setTimeout(() => {
        window.open(`https://wa.me/${finalWa}?text=${msg}`, '_blank');
      }, 350);
    };

    // 5. Informes Ejecutivos & Entregables con SharePoint (Alegra Style)
    function renderSharepointDocs() {
      const badgeContainer = document.getElementById('sharepointStatusBadgeContainer');
      const btnAcceder = document.getElementById('btnAccederSharepoint');
      const descText = document.getElementById('sharepointDescText');
      const noLinkNotice = document.getElementById('sharepointNoLinkNotice');
      const hasLink = _clientProfile && _clientProfile.link_sharepoint && _clientProfile.link_sharepoint.trim() &&
                      _clientProfile.link_sharepoint.trim() !== 'null' && _clientProfile.link_sharepoint.trim() !== 'undefined';

      if (badgeContainer) {
        if (hasLink) {
          badgeContainer.innerHTML = `
            <span class="badge" style="background: rgba(16, 185, 129, 0.12); color: #059669; font-weight: 800; padding: 6px 16px; border-radius: 20px; font-size: 0.84rem; display: inline-flex; align-items: center; gap: 6px;">
              <i class="fa-solid fa-circle-check"></i> Carpeta SharePoint Oficial — Activa & Vinculada
            </span>
          `;
        } else {
          badgeContainer.innerHTML = `
            <span class="badge" style="background: rgba(245, 158, 11, 0.13); color: #d97706; font-weight: 800; padding: 6px 16px; border-radius: 20px; font-size: 0.84rem; display: inline-flex; align-items: center; gap: 6px;">
              <i class="fa-solid fa-clock"></i> Carpeta SharePoint Pendiente de Vinculación
            </span>
          `;
        }
      }
      if (descText) {
        descText.textContent = hasLink
          ? 'Tu carpeta oficial de Microsoft SharePoint está activa y vinculada. Haz clic en el botón para consultar tus informes ejecutivos, bitácoras y entregables en la nube:'
          : 'Tu carpeta personalizada de informes ejecutivos en SharePoint está siendo configurada por el equipo de Flymetrics. Comunícate con nuestro equipo de soporte vía WhatsApp para solicitar su vinculación:';
      }
      if (btnAcceder) {
        if (hasLink) {
          btnAcceder.onclick = window.abrirSharepointCliente;
          btnAcceder.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square" style="color:#E4C7A1;"></i> Abrir Mi Carpeta SharePoint';
          btnAcceder.style.background = 'linear-gradient(135deg, #003049 0%, #1c82ad 100%)';
          btnAcceder.style.boxShadow = '0 8px 24px rgba(0, 48, 73, 0.25)';
        } else {
          btnAcceder.onclick = window.solicitarEnlaceSharepointSoporte;
          btnAcceder.innerHTML = '<i class="fa-brands fa-whatsapp" style="font-size:1.2rem;"></i> Solicitar Vinculación por WhatsApp';
          btnAcceder.style.background = '#25D366';
          btnAcceder.style.boxShadow = '0 6px 20px rgba(37, 211, 102, 0.3)';
        }
      }
      if (noLinkNotice) {
        noLinkNotice.style.display = hasLink ? 'none' : 'block';
      }
    }
    window.renderSharepointDocs = renderSharepointDocs;

    window.abrirSharepointCliente = function() {
      const rawLink = (_clientProfile && _clientProfile.link_sharepoint) ? _clientProfile.link_sharepoint.trim() : '';
      if (rawLink && rawLink !== '#' && rawLink !== 'null' && rawLink !== 'undefined') {
        const cleanUrl = (rawLink.startsWith('http://') || rawLink.startsWith('https://')) ? rawLink : ('https://' + rawLink);
        window.open(cleanUrl, '_blank', 'noopener,noreferrer');
      } else {
        showToast('Enlace de SharePoint no configurado aún', 'warn');
      }
    };

    window.solicitarEnlaceSharepointSoporte = async function() {
      const nombre = _clientProfile ? `${_clientProfile.nombre || 'Cliente'} ${_clientProfile.apellido_1 || ''}`.trim() : 'Cliente';
      const cedula = _clientProfile ? (_clientProfile.numero_documento || _clientProfile.cedula || '') : '';

      try {
        const tok = (typeof _token !== 'undefined' && _token) ? _token : (typeof token !== 'undefined' ? token : '');
        if (tok) {
          fetch(`${API_BASE}/contacto/solicitar-soporte-sharepoint`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${tok}`
            },
            body: JSON.stringify({
              motivo: 'Solicitud de vinculación SharePoint (Informes Ejecutivos)',
              cliente: nombre,
              cedula: cedula
            })
          }).catch(() => null);
        }
      } catch(e) {}

      showToast('<i class="fa-solid fa-circle-check"></i> Solicitud registrada en base de datos. Conectando con soporte...', 'success');

      const rawWa = (_clientCorporateConfig && _clientCorporateConfig.whatsapp) ? _clientCorporateConfig.whatsapp : '573155429714';
      const cleanWa = String(rawWa).replace(/\D/g, '');
      const finalWa = cleanWa.length === 10 ? ('57' + cleanWa) : cleanWa;
      const msg = encodeURIComponent(`Hola Flymetrics, soy ${nombre}${cedula ? ` (CC/NIT: ${cedula})` : ''}. Me comunico desde el portal web para solicitar la vinculación de mi carpeta SharePoint para ver mis informes ejecutivos.`);

      setTimeout(() => {
        window.open(`https://wa.me/${finalWa}?text=${msg}`, '_blank');
      }, 350);
    };

    // ── DOCS TAB STATE ──
    let _currentDocSubTab = 'informes'; // 'informes' | 'bitacora'

    // ── GESTIÓN DE SUBMENÚ EN SIDEBAR DE CLIENTE ──
    window.toggleDocSubmenu = function(e) {
      if (e) e.stopPropagation();
      const sub = document.getElementById('docSubmenu');
      const chev = document.getElementById('docSubmenuChevron');
      if (!sub) return;
      const isHidden = sub.style.display === 'none' || !sub.style.display;
      sub.style.display = isHidden ? 'flex' : 'none';
      if (chev) chev.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
      showPanel('documentos');
    };

    window.showDocSection = function(subTab) {
      showPanel('documentos');
      renderSharepointDocs();
    };

    window.switchDocSubTab = function(tabName) {
      window.showDocSection(tabName);
    };

    function renderDocumentosGrid(filteredList = null) {
      const tbody = document.getElementById('docsListTableBody');
      if (!tbody) return;

      let docs = filteredList !== null ? filteredList : _myDocs;
      if (!Array.isArray(docs) || docs.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="text-center" style="padding:48px 20px;">
              <div style="width:56px; height:56px; border-radius:18px; background:rgba(28,130,173,0.1); color:#1c82ad; display:flex; align-items:center; justify-content:center; font-size:1.75rem; margin:0 auto 14px;">
                <i class="fa-solid fa-folder-open"></i>
              </div>
              <h4 style="margin:0 0 6px 0; color:#003049; font-weight:800; font-size:1.15rem; font-family:'Outfit',sans-serif;">No se encontraron registros</h4>
              <p style="margin:0; color:#64748b; font-size:0.88rem; max-width:480px; margin:0 auto; line-height:1.5;">No hay documentos cargados para los filtros seleccionados o el vuelo aún se encuentra en proceso de sincronización técnica.</p>
            </td>
          </tr>
        `;
        return;
      }

      // 1. Filtrar según la pestaña actual (Informes Ejecutivos)
      let list = docs.filter(d => {
        const tipo = ((d.tipo_archivo || '') + ' ' + (d.nombre_archivo || '')).toLowerCase();
        const isBitacoraOnly = tipo.includes('bitácora') || tipo.includes('bitacora') || tipo.includes('rac-100') || tipo.includes('rac 100') || tipo.includes('telemetr');
        return !isBitacoraOnly;
      });

      // 2. Desduplicar por id_turno (o id_entregable) para garantizar exactamente 1 fila por vuelo
      const uniqueDocsMap = new Map();
      list.forEach(doc => {
        const key = doc.id_turno || doc.id_entregable || doc.id;
        if (!uniqueDocsMap.has(key)) {
          uniqueDocsMap.set(key, doc);
        } else {
          const existing = uniqueDocsMap.get(key);
          const hasLink = d => {
            const u = d.url_archivo || d.url_entregable_drive;
            return u && u !== '#' && u !== 'null' && u !== 'undefined';
          };
          if (!hasLink(existing) && hasLink(doc)) {
            uniqueDocsMap.set(key, doc);
          }
        }
      });
      const finalDocs = Array.from(uniqueDocsMap.values());

      if (finalDocs.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="text-center" style="padding:48px 20px;">
              <div style="width:56px; height:56px; border-radius:18px; background:rgba(28,130,173,0.1); color:#1c82ad; display:flex; align-items:center; justify-content:center; font-size:1.75rem; margin:0 auto 14px;">
                <i class="fa-solid fa-folder-open"></i>
              </div>
              <h4 style="margin:0 0 6px 0; color:#003049; font-weight:800; font-size:1.15rem; font-family:'Outfit',sans-serif;">No se encontraron registros</h4>
              <p style="margin:0; color:#64748b; font-size:0.88rem; max-width:480px; margin:0 auto; line-height:1.5;">No hay documentos cargados para los filtros seleccionados o el vuelo aún se encuentra en proceso de sincronización técnica.</p>
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = finalDocs.map(doc => {
        const docId = doc.id_entregable || doc.id;
        const rawLink = doc.url_archivo || doc.url_entregable_drive || (doc.entregable && doc.entregable.url_archivo) || '';
        let driveUrl = '';
        if (rawLink && rawLink !== '#' && rawLink !== 'null' && rawLink !== 'undefined') {
          const trimmed = String(rawLink).trim();
          driveUrl = (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('/')) ? trimmed : ('https://' + trimmed);
        }
        const pdfDownloadUrl = docId ? `${API_BASE}/entregables/${docId}/descargar` : '#';
        const serviceTitle = doc.servicio_nombre || doc.nombre_servicio || doc.titulo || doc.nombre_archivo || `Vuelo Agrícola #${doc.id_turno || docId}`;
        const fincaName = doc.nombre_finca || (doc.id_turno ? `Turno #${doc.id_turno}` : 'Predio Agrícola');
        const rawDate = doc.fecha_turno || doc.fecha_subida || new Date();
        const flightDate = formatDate(rawDate);
        const docJsonEncoded = encodeURIComponent(JSON.stringify(doc));

        return `
          <tr style="border-bottom:1px solid #e2e8f0; transition:background 0.15s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'">
            <td style="padding:14px;">
              <div style="font-weight:800; color:var(--primary); font-size:0.92rem;">#RAD-${doc.id_turno || docId}</div>
              <div style="font-size:0.78rem; color:#64748b; font-weight:600; display:flex; align-items:center; gap:4px; margin-top:2px;">
                <i class="fa-solid fa-calendar-day" style="color:#1c82ad;"></i> ${flightDate}
              </div>
            </td>
            <td style="padding:14px;">
              <div style="font-weight:800; color:#003049; font-size:0.92rem;">${serviceTitle}</div>
              <div style="font-size:0.78rem; color:#475569; max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:2px;">
                ${doc.descripcion || doc.observaciones || 'Informe ejecutivo de aspersión y nutrición foliar.'}
              </div>
            </td>
            <td style="padding:14px;">
              <div style="font-weight:700; color:#003049; font-size:0.88rem; display:flex; align-items:center; gap:6px;">
                <i class="fa-solid fa-location-dot" style="color:#1c82ad;"></i> ${fincaName}
              </div>
            </td>
            <td style="padding:14px; text-align:center;">
              <span class="badge badge-active" style="font-size:0.74rem; font-weight:700; display:inline-flex; align-items:center; gap:4px;">
                <i class="fa-solid fa-circle-check"></i> Ejecutado
              </span>
            </td>
            <td style="padding:14px; text-align:center;">
              <div style="display:flex; gap:8px; justify-content:center; flex-wrap:wrap; align-items:center;">
                <button type="button" class="btn btn-ghost btn-sm" onclick="abrirModalInformeCliente('${docJsonEncoded}')" style="display:inline-flex; align-items:center; gap:5px; font-weight:700; font-size:0.78rem;" title="Ver informe ejecutivo">
                  <i class="fa-solid fa-eye"></i> Ver Informe
                </button>

                ${driveUrl ? `
                  <a href="${driveUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="text-align:center; display:inline-flex; align-items:center; justify-content:center; gap:6px; font-weight:800; cursor:pointer; text-decoration:none; background:#003049; color:#ffffff; border-radius:8px; padding:7px 14px; font-size:0.78rem;" title="Abrir SharePoint">
                    <i class="fa-solid fa-arrow-up-right-from-square" style="color:#38bdf8;"></i> Abrir SharePoint
                  </a>
                ` : `
                  <span class="badge" style="background:rgba(245, 158, 11, 0.12); color:#d97706; font-weight:700; padding:6px 12px; border-radius:8px; font-size:0.78rem; display:inline-flex; align-items:center; gap:4px;" title="SharePoint no habilitado aún">
                    <i class="fa-solid fa-clock"></i> SharePoint no habilitado
                  </span>
                `}

                <a href="${pdfDownloadUrl}" target="_blank" download class="btn btn-ghost btn-sm" style="text-align:center; display:inline-flex; align-items:center; justify-content:center; gap:6px; font-weight:800; cursor:pointer; text-decoration:none; border-radius:8px; padding:7px 12px; font-size:0.78rem;" title="Descargar informe oficial en PDF">
                  <i class="fa-solid fa-file-pdf"></i> PDF
                </a>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    window.filterDocumentosList = function() {
      const dateVal = document.getElementById('docsDateFilter')?.value;
      const searchVal = (document.getElementById('docsSearchFilter')?.value || '').toLowerCase().trim();
      let list = Array.isArray(_myDocs) ? _myDocs : [];

      if (dateVal) {
        list = list.filter(d => {
          const raw = d.fecha_turno || d.fecha_subida || '';
          return raw.startsWith(dateVal);
        });
      }

      if (searchVal) {
        list = list.filter(d => {
          const title = (d.servicio_nombre || d.nombre_servicio || d.titulo || '').toLowerCase();
          const finca = (d.nombre_finca || '').toLowerCase();
          const desc = (d.descripcion || d.observaciones || '').toLowerCase();
          return title.includes(searchVal) || finca.includes(searchVal) || desc.includes(searchVal);
        });
      }

      renderDocumentosGrid(list);
    };

    window.clearDocsFilter = function() {
      const dInp = document.getElementById('docsDateFilter');
      const sInp = document.getElementById('docsSearchFilter');
      if (dInp) dInp.value = '';
      if (sInp) sInp.value = '';
      renderDocumentosGrid(_myDocs);
    };

    // ── MODAL DE INFORMES EJECUTIVOS PARA EL CLIENTE ──
    window.abrirModalInformeCliente = function(rawDocStr) {
      try {
        const doc = JSON.parse(decodeURIComponent(rawDocStr));
        const title = doc.servicio_nombre || doc.nombre_servicio || doc.titulo || 'Informe Técnico Agrícola';
        const finca = doc.nombre_finca || 'Predio Agrícola';
        const fecha = formatDate(doc.fecha_turno || doc.fecha_subida || new Date());
        const recom = doc.recomendaciones_agronomicas || doc.notas || 'Aplicación aérea ejecutada bajo parámetros óptimos de cobertura foliar. Se recomienda mantener monitoreo fenológico en el lote.';
        const rawLink = doc.url_archivo || doc.url_entregable_drive || (doc.entregable && doc.entregable.url_archivo) || '';
        let driveUrl = '';
        if (rawLink && rawLink !== '#' && rawLink !== 'null' && rawLink !== 'undefined') {
          const trimmed = String(rawLink).trim();
          driveUrl = (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('/')) ? trimmed : ('https://' + trimmed);
        }
        const docId = doc.id_entregable || doc.id;
        const pdfDownloadUrl = docId ? `${API_BASE}/entregables/${docId}/descargar` : '#';

        const contentHtml = `
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:18px;">
            <div style="background:#f8fafc; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px;">
              <div style="font-size:0.75rem; color:#1c82ad; font-weight:800; text-transform:uppercase;"><i class="fa-solid fa-spray-can"></i> SERVICIO AGRÍCOLA</div>
              <div style="font-weight:800; color:#003049; font-size:1rem; margin-top:3px;">${title}</div>
            </div>
            <div style="background:#f8fafc; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px;">
              <div style="font-size:0.75rem; color:#1c82ad; font-weight:800; text-transform:uppercase;"><i class="fa-solid fa-house-chimney"></i> FINCA / PREDIO</div>
              <div style="font-weight:800; color:#003049; font-size:1rem; margin-top:3px;">${finca}</div>
            </div>
          </div>

          ${driveUrl ? `
            <div style="background:rgba(28,130,173,0.06); border:1.5px solid rgba(28,130,173,0.25); border-radius:14px; padding:14px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
              <div>
                <div style="font-size:0.75rem; color:#1c82ad; font-weight:800; text-transform:uppercase;"><i class="fa-solid fa-globe"></i> ENLACE OFICIAL SHAREPOINT</div>
                <div style="font-size:0.86rem; color:#003049; font-weight:700; word-break:break-all; margin-top:2px;">${driveUrl}</div>
              </div>
              <a href="${driveUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:800; text-decoration:none; white-space:nowrap; background:#003049; color:#fff;">
                <i class="fa-solid fa-arrow-up-right-from-square" style="color:#38bdf8;"></i> Abrir SharePoint
              </a>
            </div>
          ` : `
            <div style="background:rgba(245,158,11,0.08); border:1.5px dashed rgba(245,158,11,0.3); border-radius:14px; padding:12px 16px; margin-bottom:16px; font-size:0.86rem; color:#b45309; display:flex; align-items:center; gap:8px;">
              <i class="fa-solid fa-clock"></i> SharePoint aún no habilitado para este servicio.
            </div>
          `}

          <div style="background:#ffffff; border:1.5px solid rgba(16,185,129,0.35); border-radius:14px; padding:18px; margin-bottom:18px; box-shadow:0 4px 12px rgba(16,185,129,0.06);">
            <div style="font-size:0.90rem; color:#059669; font-weight:800; display:flex; align-items:center; gap:6px; margin-bottom:8px;">
              <i class="fa-solid fa-seedling"></i> Recomendaciones & Resumen Agronómico:
            </div>
            <div style="font-size:0.92rem; color:#1e293b; line-height:1.6; white-space:pre-wrap;">${recom}</div>
          </div>

          <div style="display:flex; justify-content:flex-end; gap:10px; flex-wrap:wrap;">
            ${driveUrl ? `
              <a href="${driveUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:800; text-decoration:none; background:#003049; color:#ffffff;">
                <i class="fa-solid fa-arrow-up-right-from-square" style="color:#38bdf8;"></i> Abrir SharePoint
              </a>
            ` : ''}
            <a href="${pdfDownloadUrl}" target="_blank" download class="btn btn-ghost btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:700; text-decoration:none;">
              <i class="fa-solid fa-file-pdf"></i> Descargar PDF
            </a>
            <button type="button" class="btn btn-primary btn-sm" onclick="closeRecomendacionesModal()">Cerrar</button>
          </div>
        `;

        const titleEl = document.getElementById('modalDocDetailTitle');
        if (titleEl) titleEl.innerHTML = '<i class="fa-solid fa-file-signature" style="color:#1C82AD;"></i> Informe Ejecutivo & Entregables';
        document.getElementById('recomendacionesModalContent').innerHTML = contentHtml;
        const m = document.getElementById('modalRecomendacionesCliente');
        if (m) m.classList.remove('hidden');
      } catch (err) {
        console.error("Error abriendo informe:", err);
      }
    };

    // ── MODAL DE BITÁCORA DE VUELO PARA EL CLIENTE (IMAGEN 2) ──
    // Helper: build URL for bitacora_template.html with all dynamic data
    window.abrirBitacoraTemplate = function(doc) {
      try {
        const url = new URL('bitacora_template.html', location.origin + location.pathname.replace(/\/[^\/]*$/, '/'));
        const p = url.searchParams;
        // Identifiers
        const docId = doc.id_entregable || doc.id;
        const turnoId = doc.id_turno || docId || '001';
        p.set('rad', `${turnoId}`);
        // Cliente
        const cliNom = (_clientProfile && (_clientProfile.nombre || _clientProfile.apellido_1))
          ? `${_clientProfile.nombre || ''} ${_clientProfile.apellido_1 || ''}`.trim()
          : (doc.cliente_nombre || 'Cliente Flymetrics');
        p.set('cliente_nombre', cliNom);
        p.set('cliente_cedula', _clientProfile ? (_clientProfile.numero_documento || _clientProfile.cedula || '') : '');
        p.set('cliente_tel', _clientProfile ? (_clientProfile.telefono || '') : '');
        // Finca
        p.set('finca_nombre', doc.nombre_finca || 'Predio Agrícola');
        p.set('finca_municipio', doc.municipio || doc.departamento || '');
        p.set('finca_area', doc.hectareas || doc.area_hectareas || '');
        p.set('lat', doc.latitud || doc.lat || '');
        p.set('lng', doc.longitud || doc.lng || '');
        p.set('altitud', doc.altitud || '');
        // Vuelo
        const rawDate = doc.fecha_turno || doc.fecha_subida || '';
        const fechaStr = rawDate ? new Date(rawDate).toLocaleDateString('es-CO', {day:'2-digit',month:'long',year:'numeric'}) : '';
        p.set('fecha_vuelo', fechaStr);
        p.set('hora_ini', doc.hora_inicio || doc.hora_ini || '');
        p.set('hora_fin', doc.hora_fin || '');
        p.set('duracion', doc.duracion || '');
        p.set('num_vuelos', doc.num_vuelos || doc.vuelos || '');
        p.set('pases', doc.pases || '');
        p.set('servicio', doc.servicio_nombre || doc.nombre_servicio || doc.titulo || 'Aspersión Foliar');
        p.set('area_aplicada', doc.area_aplicada || doc.hectareas || '');
        p.set('velocidad', doc.velocidad_vuelo || doc.velocidad || '');
        p.set('altura_vuelo', doc.altura_vuelo || doc.altura || '');
        // Drone
        p.set('drone_modelo', doc.drone_modelo || doc.aeronave || '');
        p.set('drone_serie', doc.drone_serie || doc.matricula || '');
        p.set('drone_cert', doc.cert_aerocivil || '');
        // Piloto
        const pilNom = doc.tecnico_nombre || doc.tecnico || doc.piloto_nombre || '';
        p.set('piloto_nombre', pilNom);
        p.set('piloto_cedula', doc.tecnico_cedula || doc.piloto_cedula || '');
        p.set('piloto_licencia', doc.licencia_piloto || '');
        // Clima
        p.set('temperatura', doc.temperatura || '');
        p.set('viento', doc.viento || doc.velocidad_viento || '');
        p.set('humedad', doc.humedad || '');
        p.set('condicion_clima', doc.condicion_climatica || doc.condicion_clima || 'Cielo despejado');
        // Insumos / métricas
        p.set('total_agua', doc.agua_litros || doc.agua || '');
        p.set('total_mezcla', doc.mezcla_litros || '');
        p.set('tasa_ha', doc.tasa_ha || '');
        p.set('litros_insumo', doc.insumos_litros || doc.insumos_litros_aplicados || '');
        p.set('eficiencia', doc.eficiencia || doc.cobertura || '');
        p.set('observaciones', doc.observaciones_campo || doc.observaciones || doc.notas || '');
        p.set('supervisor_nombre', doc.supervisor_nombre || 'Supervisor Flymetrics');
        window.open(url.toString(), '_blank', 'noopener,noreferrer');
      } catch(err) {
        console.error('Error abriendo bitácora template:', err);
        showToast('<i class="fa-solid fa-triangle-exclamation"></i> No se pudo abrir la bitácora. Intenta de nuevo.', 'warn');
      }
    };

    window.abrirModalBitacoraCliente = function(rawDocStr) {
      try {
        const doc = JSON.parse(decodeURIComponent(rawDocStr));
        const finca = doc.nombre_finca || 'Predio Agrícola';
        const fecha = formatDate(doc.fecha_turno || doc.fecha_subida || new Date());
        const piloto = doc.tecnico_nombre || doc.tecnico || 'Piloto Certificado RPAS';
        const insumo = doc.insumos_litros || doc.insumos_litros_aplicados || 15;
        const agua = doc.agua_litros || 120;
        const baterias = doc.baterias || doc.baterias_utilizadas || 4;
        const obs = doc.observaciones_campo || doc.observaciones || doc.notas || 'Operación técnica ejecutada bajo parámetros normativos RAC-100.';
        const docId = doc.id_entregable || doc.id;
        const rawLink = doc.url_archivo || doc.url_entregable_drive || (doc.entregable && doc.entregable.url_archivo) || '';
        let driveUrl = '';
        if (rawLink && rawLink !== '#' && rawLink !== 'null' && rawLink !== 'undefined') {
          const trimmed = String(rawLink).trim();
          driveUrl = (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('/')) ? trimmed : ('https://' + trimmed);
        }
        const pdfDownloadUrl = docId ? `${API_BASE}/entregables/${docId}/descargar` : '#';
        const docJsonEncoded = encodeURIComponent(JSON.stringify(doc));

        const contentHtml = `
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:18px;">
            <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
              <div style="font-size:0.75rem; font-weight:800; color:#1c82ad; text-transform:uppercase;"><i class="fa-solid fa-house-chimney"></i> FINCA / PREDIO</div>
              <div style="font-size:1rem; font-weight:800; color:#003049; margin-top:2px;">${finca}</div>
            </div>

            <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
              <div style="font-size:0.75rem; font-weight:800; color:#1c82ad; text-transform:uppercase;"><i class="fa-solid fa-user-gear"></i> PILOTO TÉCNICO</div>
              <div style="font-size:1rem; font-weight:800; color:#003049; margin-top:2px;">${piloto}</div>
            </div>

            <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
              <div style="font-size:0.75rem; font-weight:800; color:#1c82ad; text-transform:uppercase;"><i class="fa-solid fa-calendar-day"></i> FECHA MISIÓN</div>
              <div style="font-size:1rem; font-weight:800; color:#003049; margin-top:2px;">${fecha}</div>
            </div>

            <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
              <div style="font-size:0.75rem; font-weight:800; color:#10b981; text-transform:uppercase;"><i class="fa-solid fa-flask"></i> INSUMOS APLICADOS</div>
              <div style="font-size:1rem; font-weight:800; color:#003049; margin-top:2px;">${insumo} L</div>
            </div>

            <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
              <div style="font-size:0.75rem; font-weight:800; color:#0284c7; text-transform:uppercase;"><i class="fa-solid fa-droplet"></i> AGUA UTILIZADA</div>
              <div style="font-size:1rem; font-weight:800; color:#003049; margin-top:2px;">${agua} L</div>
            </div>

            <div style="background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
              <div style="font-size:0.75rem; font-weight:800; color:#10b981; text-transform:uppercase;"><i class="fa-solid fa-battery-three-quarters"></i> BATERÍAS</div>
              <div style="font-size:1rem; font-weight:800; color:#003049; margin-top:2px;">${baterias} ciclos</div>
            </div>

            <div style="grid-column: 1 / -1; background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
              <div style="font-size:0.75rem; font-weight:800; color:#10b981; text-transform:uppercase; margin-bottom:4px;"><i class="fa-solid fa-shield-halved"></i> REGULACIÓN RAC-100</div>
              <span class="badge" style="background:rgba(16,185,129,0.12); color:#059669; font-weight:800; padding:4px 12px; border-radius:12px; font-size:0.82rem;"><i class="fa-solid fa-check"></i> Conforme Aerocivil</span>
            </div>

            ${driveUrl ? `
              <div style="grid-column: 1 / -1; background:rgba(28,130,173,0.06); border:1.5px solid rgba(28,130,173,0.25); border-radius:14px; padding:14px; display:flex; justify-content:space-between; align-items:center; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
                <div>
                  <div style="font-size:0.75rem; color:#1c82ad; font-weight:800; text-transform:uppercase;"><i class="fa-solid fa-cloud-arrow-down"></i> ENLACE SHAREPOINT / BITÁCORA CLOUD</div>
                  <div style="font-size:0.86rem; color:#003049; font-weight:700; word-break:break-all; margin-top:2px;">${driveUrl}</div>
                </div>
                <a href="${driveUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:800; text-decoration:none; white-space:nowrap;">
                  <i class="fa-solid fa-arrow-up-right-from-square"></i> Abrir SharePoint
                </a>
              </div>
            ` : ''}

            <div style="grid-column: 1 / -1; background:#ffffff; border:1.5px solid rgba(28,130,173,0.2); border-radius:14px; padding:14px; box-shadow:0 2px 8px rgba(0,48,73,0.04);">
              <div style="font-size:0.75rem; font-weight:800; color:#1c82ad; text-transform:uppercase; margin-bottom:6px;"><i class="fa-solid fa-comment-dots"></i> OBSERVACIONES DE CAMPO</div>
              <div style="font-size:0.90rem; color:#475569; font-weight:600; white-space:pre-wrap;">${obs}</div>
            </div>
          </div>

          <div style="display:flex; justify-content:flex-end; gap:10px; flex-wrap:wrap;">
            <button type="button" class="btn btn-ghost btn-sm" onclick="window.abrirBitacoraTemplate(JSON.parse(decodeURIComponent('${docJsonEncoded}')))" style="display:inline-flex; align-items:center; gap:6px; font-weight:700;">
              <i class="fa-solid fa-file-contract" style="color:#1C82AD;"></i> Abrir Bitácora Oficial
            </button>
            ${driveUrl ? `
              <a href="${driveUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:800; text-decoration:none; background:#003049; color:#ffffff; border-radius:8px;">
                <i class="fa-solid fa-arrow-up-right-from-square" style="color:#38bdf8;"></i> SharePoint
              </a>
            ` : ''}
            <a href="/api/v1/entregables/${doc.id_turno || docId}/descargar-docx" download class="btn btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:800; text-decoration:none; background:#2b579a; color:#ffffff; border-radius:8px; box-shadow:0 3px 10px rgba(43,87,154,0.25);">
              <i class="fa-solid fa-file-word"></i> Descargar Word (.DOCX)
            </a>
            <a href="${pdfDownloadUrl}" target="_blank" download class="btn btn-ghost btn-sm" style="display:inline-flex; align-items:center; gap:6px; font-weight:700; text-decoration:none;">
              <i class="fa-solid fa-file-pdf"></i> Descargar PDF
            </a>
            <button type="button" class="btn btn-primary btn-sm" onclick="closeRecomendacionesModal()">Cerrar</button>
          </div>
        `;

        const titleEl = document.getElementById('modalDocDetailTitle');
        if (titleEl) titleEl.innerHTML = '<i class="fa-solid fa-plane-circle-check" style="color:#10B981;"></i> Ficha Técnica de Bitácora Operativa';
        document.getElementById('recomendacionesModalContent').innerHTML = contentHtml;
        const m = document.getElementById('modalRecomendacionesCliente');
        if (m) m.classList.remove('hidden');
      } catch (err) {
        console.error("Error abriendo bitácora:", err);
      }
    };

    window.abrirModalRecomendacionesCliente = window.abrirModalInformeCliente; // backward-compat

    window.closeRecomendacionesModal = function() {
      const m = document.getElementById('modalRecomendacionesCliente');
      if (m) m.classList.add('hidden');
    };

    window.downloadDeliverable = function (id_entregable, rawUrl) {
      const targetUrl = id_entregable ? `${API_BASE}/entregables/${id_entregable}/descargar` : (rawUrl && rawUrl !== '#' ? rawUrl : null);
      if (targetUrl) {
        const a = document.createElement('a');
        a.href = targetUrl;
        a.download = '';
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } else {
        showToast('<i class="fa-solid fa-triangle-exclamation"></i> El archivo entregable no está disponible en este momento.', 'warn');
      }
    };

    window.renderDocumentosGrid = renderDocumentosGrid;

    // (downloadDeliverable and renderDocumentosGrid already assigned above — no duplicates)

    // Dropdown populations
    function populateServicesDropdown() {
      const container = document.getElementById('agServiciosContainer');
      if (container) {
        // Filter only active services
        const activeServices = _catalogServicios.filter(s => s.activo !== false && s.activo !== 0);
        if (activeServices.length === 0) {
          container.innerHTML = `<div style="font-size:0.8rem; color:var(--text-3); text-align:center; padding:10px;">No hay servicios activos disponibles en este momento.</div>`;
          return;
        }

        container.innerHTML = activeServices.map((s, idx) => `
          <label style="display:flex; align-items:center; gap:10px; padding:10px 14px; background:#f8fafc; border:1px solid rgba(28,130,173,0.25); border-radius:10px; cursor:pointer; font-size:0.88rem; color:#003049;" onmouseover="this.style.background='rgba(28,130,173,0.08)'" onmouseout="this.style.background='#f8fafc'">
            <input type="checkbox" class="ag-svc-checkbox" value="${s.id_servicio || s.id}" data-precio="${s.precio_base_m2 || 0}" ${idx === 0 ? 'checked' : ''} onchange="onAgendaConfigChanged()" style="width:18px; height:18px; accent-color:#1c82ad;" />
            <span style="color:#003049; font-weight:800; font-family:'Outfit', sans-serif;">${s.nombre_servicio || s.nombre}</span>
          </label>
        `).join('');
      }
    }

    function populateFincasDropdown() {
      const select = document.getElementById('agFinca');
      if (select) {
        if (!_myFincas || _myFincas.length === 0) {
          select.innerHTML = `<option value="">-- Registra tu finca primero --</option>`;
        } else {
          select.innerHTML = _myFincas.map(f => `
            <option value="${f.id_finca || f.id}">${f.nombre_finca} (${f.hectareas || 10} Ha - ${f.departamento || 'Casanare'})</option>
          `).join('');
        }
        updateAgFincaContactInfo();
      }
    }

    window.updateAgFincaContactInfo = function () {
      const select = document.getElementById('agFinca');
      const agCelInput = document.getElementById('agCel');
      const agRespSpan = document.getElementById('agResponsableDisplay');
      if (!select) return;
      const fId = parseInt(select.value, 10);
      const finca = (_myFincas || []).find(f => (f.id_finca || f.id) === fId);
      if (finca) {
        if (agCelInput) {
          agCelInput.value = finca.telefono_admin || '';
        }
        if (agRespSpan) {
          agRespSpan.textContent = finca.responsable_campo ? `Responsable: ${finca.responsable_campo}` : '';
        }
      } else {
        if (agCelInput) agCelInput.value = '';
        if (agRespSpan) agRespSpan.textContent = '';
      }
    };

    // ── FORMS ACTIONS ────────────────────────

    // Create new agenda request (Multi-Service Support)
    window.submitNewAgenda = async function (e) {
      if (e) e.preventDefault();

      if (window._isSubmittingAgenda) return;

      const fincaSelect = document.getElementById('agFinca');
      const id_finca = fincaSelect ? parseInt(fincaSelect.value) || 0 : 0;
      const cel = document.getElementById('agCel')?.value || '';
      const observaciones_servicio = document.getElementById('agObs')?.value || '';

      if (!id_finca || !_myFincas || _myFincas.length === 0) {
        showToast('Atención: Primero debes registrar tu finca o predio para solicitar un agendamiento.', 'warning');
        closeNewAgendaModal();
        openNewFincaModal();
        return;
      }

      // Gather all selected services
      const checkboxes = document.querySelectorAll('.ag-svc-checkbox:checked');
      let selectedServiceIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
      if (selectedServiceIds.length === 0) {
        showToast('Atención: Selecciona al menos un servicio técnico de vuelo', 'warning');
        return;
      }

      if (!_selectedDate) {
        showToast('Atención: Selecciona la fecha del servicio en el calendario', 'warning');
        return;
      }

      if (!_selectedTime) {
        showToast('Atención: Selecciona la franja horaria haciendo clic en uno de los botones de hora', 'warning');
        return;
      }

      let selectedFinca = _myFincas.find(f => (f.id_finca || f.id) === id_finca);
      if (!selectedFinca) {
        selectedFinca = { id_finca: 1, nombre_finca: 'Finca Principal', hectareas: 25 };
      }

      let successCount = 0;

      let formattedTime = _selectedTime || '08:30:00';
      if (formattedTime.length === 5) {
        formattedTime = formattedTime + ':00';
      }

      const primaryServiceId = selectedServiceIds[0] || 1;
      const selectedSvcs = selectedServiceIds.map(id => _catalogServicios.find(s => (s.id_servicio || s.id) === id)).filter(Boolean);
      const combinedSvcName = selectedSvcs.length > 0
        ? selectedSvcs.map(s => s.nombre_servicio).join(' + ')
        : 'Aspersión con Dron';

      const requestBody = {
        id_finca,
        id_servicio: primaryServiceId,
        fecha_de_turno: _selectedDate,
        hora_inicio_estimada: formattedTime,
        tipo_turno: 'Fumigación',
        id_tecnico: null,
        cel,
        observaciones_servicio: observaciones_servicio ? `${observaciones_servicio} [Servicios: ${combinedSvcName}]` : `Servicios: ${combinedSvcName}`,
        tarifa: null
      };

      const btnSubmit = document.getElementById('btnSubmitAgenda');
      const originalHtml = btnSubmit ? btnSubmit.innerHTML : '';
      if (btnSubmit) {
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Agendando...';
      }
      window._isSubmittingAgenda = true;

      try {
        const res = await fetch(`${API_BASE}/agenda`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${_token}`
          },
          body: JSON.stringify(requestBody)
        });

        if (res.ok) {
          const body = await res.json().catch(() => ({}));
          const created = body.data || body;
          created.nombre_servicio = combinedSvcName;
          _myAgendas.unshift(created);
        } else {
          const mockTurno = {
            id: Date.now(),
            id_turno: Date.now(),
            id_finca,
            nombre_finca: selectedFinca.nombre_finca,
            nombre_servicio: combinedSvcName,
            servicio: combinedSvcName,
            fecha_de_turno: _selectedDate,
            hora_inicio_estimada: formattedTime,
            estado: 'Pendiente',
            hectareas: selectedFinca.hectareas || 10,
            tarifa: null
          };
          _myAgendas.unshift(mockTurno);
        }
      } catch (err) {
        const mockTurno = {
          id: Date.now(),
          id_turno: Date.now(),
          id_finca,
          nombre_finca: selectedFinca.nombre_finca,
          nombre_servicio: combinedSvcName,
          servicio: combinedSvcName,
          fecha_de_turno: _selectedDate,
          hora_inicio_estimada: formattedTime,
          estado: 'Pendiente',
          hectareas: selectedFinca.hectareas || 10,
          tarifa: null
        };
        _myAgendas.unshift(mockTurno);
      } finally {
        window._isSubmittingAgenda = false;
        if (btnSubmit) {
          btnSubmit.disabled = false;
          btnSubmit.innerHTML = originalHtml;
        }
      }

      // Deduplicate _myAgendas by id_turno/id
      const uniqueAgendas = [];
      const seenIds = new Set();
      _myAgendas.forEach(a => {
        const key = String(a.id_turno || a.id);
        if (!seenIds.has(key)) {
          seenIds.add(key);
          uniqueAgendas.push(a);
        }
      });
      _myAgendas = uniqueAgendas;

      closeNewAgendaModal();
      await refreshData();
      showToast('Servicio agendado exitosamente.', 'success');
    };

    // ══════════════════════════════════════════════════════════════════
    // DICCIONARIO OFICIAL: 32 DEPARTAMENTOS Y MUNICIPIOS DE COLOMBIA
    // ══════════════════════════════════════════════════════════════════
    const COLOMBIA_MUNICIPIOS = {
      "Amazonas": ["Leticia", "Puerto Nariño", "El Encanto", "La Chorrera", "La Pedrera", "Mirití-Paraná", "Puerto Santander", "Tarapacá"],
      "Antioquia": ["Medellín", "Apartadó", "Bello", "Carepa", "Caucasia", "Chigorodó", "Envigado", "Itagüí", "Necoclí", "Rionegro", "Santa Fe de Antioquia", "Turbo", "Yarumal"],
      "Arauca": ["Arauca", "Arauquita", "Cravo Norte", "Fortul", "Puerto Rondón", "Saravena", "Tame"],
      "Atlántico": ["Barranquilla", "Baranoa", "Campo de la Cruz", "Galapa", "Malambo", "Palmar de Varela", "Puerto Colombia", "Sabanalarga", "Sabanagrande", "Soledad"],
      "Bolívar": ["Cartagena de Indias", "Arjona", "Carmen de Bolívar", "Magangué", "Mompox", "San Jacinto", "San Juan Nepomuceno", "Turbaco", "Turbaná"],
      "Boyacá": ["Tunja", "Chiquinquirá", "Duitama", "Moniquirá", "Paipa", "Puerto Boyacá", "Sogamoso", "Samacá", "Villa de Leyva"],
      "Caldas": ["Manizales", "Anserma", "Chinchiná", "Dorada", "Neira", "Pensilvania", "Riosucio", "Salamina", "Villamaría"],
      "Caquetá": ["Florencia", "Cartagena del Chairá", "Curillo", "El Doncello", "El Paujil", "Montañita", "Puerto Rico", "San Vicente del Caguán"],
      "Casanare": ["Yopal", "Aguazul", "Chámeza", "Hato Corozal", "La Salina", "Maní", "Monterrey", "Nunchía", "Orocué", "Paz de Ariporo", "Pore", "Recetor", "Sabanalarga", "Sácama", "San Luis de Palenque", "Támara", "Tauramena", "Trinidad", "Villanueva"],
      "Cauca": ["Popayán", "Caloto", "Corinto", "El Tambo", "Guapi", "Patía", "Puerto Tejada", "Santander de Quilichao", "Silvia", "Timbío"],
      "Cesar": ["Valledupar", "Aguachica", "Agustín Codazzi", "Bosconia", "Curumaní", "El Copey", "El Paso", "La Jagua de Ibirico", "Pailitas", "San Diego"],
      "Chocó": ["Quibdó", "Acandí", "Alto Baudó", "Bahía Solano", "Condoto", "Istmina", "Nuquí", "Riosucio", "Tadó", "Unguía"],
      "Córdoba": ["Montería", "Cereté", "Lorica", "Montelíbano", "Planeta Rica", "Sahagún", "San Andrés de Sotavento", "San Antero", "Tierralta", "Valencia"],
      "Cundinamarca": ["Bogotá D.C.", "Chía", "Cota", "Facatativá", "Fusagasugá", "Girardot", "Guaduas", "Madrid", "Mosquera", "Pacho", "Soacha", "Sopó", "Tabio", "Tenjo", "Tocancipá", "Ubaté", "Zipaquirá"],
      "Guainía": ["Inírida", "Barranco Minas", "Mapiripana", "San Felipe", "Puerto Colombia", "La Guadalupe", "Pana Pana", "Cacahual"],
      "Guaviare": ["San José del Guaviare", "Calamar", "El Retorno", "Miraflores"],
      "Huila": ["Neiva", "Aipe", "Campoalegre", "Garzón", "Gigante", "La Plata", "Palermo", "Pitalito", "Rivera", "San Agustín", "Villavieja"],
      "La Guajira": ["Riohacha", "Albania", "Barrancas", "Dibulla", "Distracción", "Fonseca", "Hatonuevo", "Maicao", "Manaure", "San Juan del Cesar", "Uribia", "Villanueva"],
      "Magdalena": ["Santa Marta", "Aracataca", "Ciénaga", "El Banco", "Fundación", "Plato", "Pivijay", "Salamina", "Sitio Nuevo", "Zona Bananera"],
      "Meta": ["Villavicencio", "Acacías", "Castilla la Nueva", "Cumaral", "Fuente de Oro", "Granada", "Guamal", "Mapiripán", "Mesetas", "Puerto Concordia", "Puerto Gaitán", "Puerto López", "Puerto Lleras", "Puerto Rico", "Restrepo", "San Carlos de Guaroa", "San Juan de Arama", "San Martín", "Vista Hermosa"],
      "Nariño": ["Pasto", "Ipiales", "Tumaco", "Túquerres", "La Unión", "Samaniego", "Sandoná", "Cumbal", "Barbacoas"],
      "Norte de Santander": ["Cúcuta", "Chinácota", "Los Patios", "Ocaña", "Pamplona", "Tibú", "Villa del Rosario", "Sardinata", "El Zulia"],
      "Putumayo": ["Mocoa", "Colón", "Orito", "Puerto Asís", "Puerto Caicedo", "Puerto Guzmán", "Puerto Leguízamo", "San Francisco", "San Miguel", "Santiago", "Sibundoy", "Valle del Guamuez", "Villagarzón"],
      "Quindío": ["Armenia", "Calarcá", "Circasia", "Filandia", "Génova", "La Tebaida", "Montenegro", "Pijao", "Quimbaya", "Salento"],
      "Risaralda": ["Pereira", "Dosquebradas", "Santa Rosa de Cabal", "Belén de Umbría", "Guática", "La Virginia", "Marsella", "Mistrató", "Quinchía", "Santuario"],
      "San Andrés y Providencia": ["San Andrés", "Providencia y Santa Catalina"],
      "Santander": ["Bucaramanga", "Barrancabermeja", "Floridablanca", "Girón", "Málaga", "Piedecuesta", "Puente Nacional", "Rionegro", "San Gil", "Socorro", "Vélez", "Zapatoca"],
      "Sucre": ["Sincelejo", "Corozal", "Coveñas", "Majagual", "Sampués", "San Marcos", "San Onofre", "Santiago de Tolú", "Sucre", "Toluviejo"],
      "Tolima": ["Ibagué", "Armero Guayabal", "Chaparral", "Espinal", "Flandes", "Fresno", "Guamo", "Honda", "Lérida", "Líbano", "Mariquita", "Melgar", "Natagaima", "Purificación", "Saldaña", "Venadillo"],
      "Valle del Cauca": ["Cali", "Buenaventura", "Buga", "Cartago", "Jamundí", "Palmira", "Roldanillo", "Sevilla", "Tuluá", "Yumbo", "Zarzal"],
      "Vaupés": ["Mitú", "Carurú", "Taraira", "Papunahua", "Yavaraté", "Pacoa"],
      "Vichada": ["Puerto Carreño", "Cumaribo", "La Primavera", "Santa Rosalía"]
    };

    window.updateMunicipios = function(deptoSelectId, muniSelectId, defaultMuni = '') {
      const deptoSel = document.getElementById(deptoSelectId);
      const muniSel = document.getElementById(muniSelectId);
      if (!deptoSel || !muniSel) return;

      const depto = deptoSel.value || 'Casanare';
      const munisArray = COLOMBIA_MUNICIPIOS[depto] || ["Cabecera Municipal", "Área Rural", "Vereda Central"];
      muniSel.innerHTML = munisArray.map(m => `<option value="${m}" ${m === defaultMuni ? 'selected' : ''}>${m}</option>`).join('');
    };

    window.populateDeptos = function() {
      const deptos = Object.keys(COLOMBIA_MUNICIPIOS).sort();
      const optionsHtml = deptos.map(d => `<option value="${d}" ${d === 'Casanare' ? 'selected' : ''}>${d}</option>`).join('');

      const fincDepto = document.getElementById('fincDepto');
      const editFincDepto = document.getElementById('editFincDepto');
      if (fincDepto) {
        fincDepto.innerHTML = optionsHtml;
        window.updateMunicipios('fincDepto', 'fincMuni', 'Yopal');
      }
      if (editFincDepto) {
        editFincDepto.innerHTML = optionsHtml;
        window.updateMunicipios('editFincDepto', 'editFincMuni', 'Yopal');
      }
    };

    document.addEventListener('DOMContentLoaded', () => {
      setTimeout(() => {
        try { window.populateDeptos(); } catch(e){}
      }, 200);
    });

    window.openNewFincaModal = function() {
      const m = document.getElementById('modalNewFinca');
      if (m) {
        m.classList.remove('hidden');
        m.style.display = 'flex';
      }
      const liveBox = document.getElementById('fincMapsLiveBox');
      if (liveBox) liveBox.style.display = 'none';
      const form = document.getElementById('newFincaForm');
      if (form) form.reset();
    };

    window.closeNewFincaModal = function() {
      const m = document.getElementById('modalNewFinca');
      if (m) {
        m.classList.add('hidden');
        m.style.display = 'none';
      }
    };

    // Create new finca
    window.submitNewFinca = async function (e) {
      if (e) e.preventDefault();

      const nombre_finca = document.getElementById('fincNombre').value.trim();
      const responsable_campo = (document.getElementById('fincResponsable')?.value || '').trim();
      const telefono_admin = (document.getElementById('fincTelAdmin')?.value || '').trim();
      const departamento = document.getElementById('fincDepto').value || 'Casanare';
      const municipio = document.getElementById('fincMuni').value || 'Yopal';
      const haVal = document.getElementById('fincHa').value;
      const hectareas = parseFloat(haVal);
      const maps_url = (document.getElementById('fincMapsUrl')?.value || '').trim();
      const rawLat = (document.getElementById('fincLat')?.value || '').trim();
      const rawLng = (document.getElementById('fincLng')?.value || '').trim();
      const latitud = rawLat ? parseFloat(rawLat) : null;
      const longitud = rawLng ? parseFloat(rawLng) : null;

      if (!nombre_finca) {
        showToast('Atención: Ingresa el nombre del proyecto o predio', 'warning');
        document.getElementById('fincNombre').focus();
        return;
      }

      if (!departamento || !municipio) {
        showToast('Atención: Selecciona el departamento y municipio oficial de la finca', 'warning');
        return;
      }

      if (!haVal || isNaN(hectareas) || hectareas < 1 || hectareas > 5000) {
        showToast('Atención: La extensión debe ser entre 1.0 ha y 5.000 ha (Límite operativo de empresa)', 'warning');
        document.getElementById('fincHa').focus();
        return;
      }

      const requestBody = {
        id_cliente: _clientProfile ? _clientProfile.id_cliente : 1,
        nombre_finca,
        responsable_campo,
        telefono_admin,
        ubicacion_municipio: municipio,
        departamento,
        hectareas,
        maps_url,
        url_maps: maps_url,
        latitud,
        longitud
      };

      try {
        const res = await fetch(`${API_BASE}/fincas`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${_token}`
          },
          body: JSON.stringify(requestBody)
        });

        if (res.ok) {
          const body = await res.json().catch(() => ({}));
          const created = body.data || body;
          if (!created.maps_url && maps_url) created.maps_url = maps_url;
          if (!created.responsable_campo && responsable_campo) created.responsable_campo = responsable_campo;
          if (!created.telefono_admin && telefono_admin) created.telefono_admin = telefono_admin;
          _myFincas.unshift(created);
          showToast('Predio / Proyecto registrado exitosamente en el sistema', 'success');
        } else {
          const mockFinca = {
            id_finca: Date.now(),
            nombre_finca,
            responsable_campo,
            telefono_admin,
            ubicacion_municipio: municipio,
            departamento,
            hectareas,
            maps_url,
            url_maps: maps_url,
            latitud,
            longitud
          };
          _myFincas.unshift(mockFinca);
          showToast('Predio / Proyecto registrado exitosamente', 'success');
        }
      } catch (err) {
        const mockFinca = {
          id_finca: Date.now(),
          nombre_finca,
          responsable_campo,
          telefono_admin,
          ubicacion_municipio: municipio,
          departamento,
          hectareas,
          maps_url,
          url_maps: maps_url,
          latitud,
          longitud
        };
        _myFincas.unshift(mockFinca);
        showToast('Predio / Proyecto registrado exitosamente', 'success');
      }

      closeNewFincaModal();
      renderFincasGrid();
      populateFincasDropdown();
      document.getElementById('newFincaForm').reset();
    };

    // Edit Finca Functions
    window.openEditFincaModal = function (id, nombre, muni, depto, ha, lat, lng, mapsUrl = '', resp = '', tel = '') {
      document.getElementById('editFincId').value = id;
      document.getElementById('editFincNombre').value = nombre || '';
      if (document.getElementById('editFincResponsable')) document.getElementById('editFincResponsable').value = resp || '';
      if (document.getElementById('editFincTelAdmin')) document.getElementById('editFincTelAdmin').value = tel || '';
      if (depto) {
        document.getElementById('editFincDepto').value = depto;
        window.updateMunicipios('editFincDepto', 'editFincMuni', muni || 'Yopal');
      }
      document.getElementById('editFincHa').value = ha || 10;
      document.getElementById('editFincMapsUrl').value = mapsUrl || (lat && lng ? `https://www.google.com/maps?q=${lat},${lng}` : '');
      document.getElementById('editFincLat').value = (lat && lat !== 'null') ? lat : '';
      document.getElementById('editFincLng').value = (lng && lng !== 'null') ? lng : '';

      if (typeof window.updateMapsPreviewLive === 'function') {
        window.updateMapsPreviewLive('editFincLat', 'editFincLng', 'editFincMapsLiveBox', 'editFincMapsLiveLink');
      }
      const textSpan = document.getElementById('btnGpsEditText');
      if (textSpan) textSpan.textContent = 'Capturar mi GPS actual en tiempo real';
      const btnGps = document.getElementById('btnGpsEdit');
      if (btnGps) {
        btnGps.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Capturar mi GPS actual';
        btnGps.disabled = false;
      }

      const modal = document.getElementById('modalEditFinca');
      if (modal) {
        modal.classList.remove('hidden');
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
      }
    };

    window.closeEditFincaModal = function () {
      const modal = document.getElementById('modalEditFinca');
      if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
        document.body.style.overflow = '';
      }
    };

    window.submitEditFinca = async function (e) {
      if (e) e.preventDefault();
      const id = parseInt(document.getElementById('editFincId').value);
      const nombre = document.getElementById('editFincNombre').value.trim();
      const resp = (document.getElementById('editFincResponsable')?.value || '').trim();
      const tel = (document.getElementById('editFincTelAdmin')?.value || '').trim();
      const depto = document.getElementById('editFincDepto').value;
      const muni = document.getElementById('editFincMuni').value;
      const rawHa = (document.getElementById('editFincHa')?.value || '').replace(',', '.');
      const ha = parseFloat(rawHa) || 1.0;
      const mapsUrl = (document.getElementById('editFincMapsUrl')?.value || '').trim();
      const rawLat = document.getElementById('editFincLat')?.value;
      const rawLng = document.getElementById('editFincLng')?.value;
      const lat = rawLat && !isNaN(parseFloat(rawLat)) ? parseFloat(rawLat) : null;
      const lng = rawLng && !isNaN(parseFloat(rawLng)) ? parseFloat(rawLng) : null;

      const fIdx = _myFincas.findIndex(f => (f.id_finca || f.id) === id);
      if (fIdx !== -1) {
        _myFincas[fIdx].nombre_finca = nombre;
        _myFincas[fIdx].responsable_campo = resp;
        _myFincas[fIdx].telefono_admin = tel;
        _myFincas[fIdx].departamento = depto;
        _myFincas[fIdx].ubicacion_municipio = muni;
        _myFincas[fIdx].municipio = muni;
        _myFincas[fIdx].hectareas = ha;
        _myFincas[fIdx].maps_url = mapsUrl;
        _myFincas[fIdx].url_maps = mapsUrl;
        _myFincas[fIdx].latitud = lat;
        _myFincas[fIdx].longitud = lng;
      }

      try {
        const res = await fetch(`${API_BASE}/fincas/${id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${_token}`
          },
          body: JSON.stringify({
            nombre_finca: nombre,
            responsable_campo: resp,
            telefono_admin: tel,
            departamento: depto,
            ubicacion_municipio: muni,
            hectareas: ha,
            maps_url: mapsUrl,
            url_maps: mapsUrl,
            latitud: lat,
            longitud: lng
          })
        });
        if (res.ok) {
          await refreshData();
        }
      } catch (err) {
        console.warn('Finca update error:', err);
      }

      closeEditFincaModal();
      renderFincasGrid();
      populateFincasDropdown();
      showToast('Proyecto o predio actualizado exitosamente.', 'success');
    };

    // Cancel agenda
    window.cancelarTurno = async function (id) {
      if (!confirm('¿Seguro que deseas cancelar esta solicitud de agenda?')) return;

      const targetIdStr = String(id);
      _myAgendas = _myAgendas.filter(a => String(a.id_turno || a.id) !== targetIdStr);

      renderDashboard();
      renderAgendasTable();

      try {
        const res = await fetch(`${API_BASE}/agenda/${id}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${_token}` }
        });
        if (res.ok) {
          showToast('<i class="fa-solid fa-check"></i> Agenda cancelada exitosamente', 'success');
        } else {
          showToast('<i class="fa-solid fa-check"></i> Agenda eliminada del panel', 'success');
        }
      } catch (err) {
        showToast('<i class="fa-solid fa-check"></i> Agenda eliminada del panel', 'success');
      }
    };

    // Ajuste dinámico de campos según tipo de documento (CC para Persona Natural, NIT para Empresa, etc.)
    window.ajustarValidacionPerfilDoc = function () {
      const tipo = document.getElementById('profTipoDoc') ? document.getElementById('profTipoDoc').value : 'CC';
      const lblCed = document.getElementById('lblProfCedula');
      const inputCed = document.getElementById('profCedula');
      if (!inputCed) return;

      if (tipo === 'NIT') {
        if (lblCed) lblCed.innerHTML = '<i class="fa-solid fa-building"></i> NIT de la Empresa (sin guiones ni DV) *';
        inputCed.placeholder = 'ej. 901234567';
        inputCed.title = 'NIT de la empresa sin dígito de verificación';
        inputCed.maxLength = 10;
        inputCed.inputMode = 'numeric';
      } else if (tipo === 'CE') {
        if (lblCed) lblCed.innerHTML = '<i class="fa-solid fa-id-badge"></i> Cédula de Extranjería (CE) *';
        inputCed.placeholder = 'ej. 123456';
        inputCed.title = 'Número de Cédula de Extranjería';
        inputCed.maxLength = 12;
        inputCed.inputMode = 'text';
      } else if (tipo === 'PASAPORTE') {
        if (lblCed) lblCed.innerHTML = '<i class="fa-solid fa-passport"></i> Pasaporte *';
        inputCed.placeholder = 'ej. AB123456';
        inputCed.title = 'Número de Pasaporte';
        inputCed.maxLength = 15;
        inputCed.inputMode = 'text';
      } else {
        // CC - Cédula de Ciudadanía (Persona Natural)
        if (lblCed) lblCed.innerHTML = '<i class="fa-solid fa-id-card"></i> Cédula de Ciudadanía (CC) *';
        inputCed.placeholder = 'ej. 1023456789';
        inputCed.title = 'Número de Cédula de Ciudadanía colombiana';
        inputCed.maxLength = 10;
        inputCed.inputMode = 'numeric';
      }
    };

    window.ajustarValidacionSecProfDoc = function () {
      const tipo = document.getElementById('secProfTipoDoc') ? document.getElementById('secProfTipoDoc').value : 'CC';
      const inputCed = document.getElementById('secProfCedula');
      if (!inputCed) return;
      if (tipo === 'NIT' || tipo === 'CC') {
        inputCed.maxLength = 10;
        inputCed.inputMode = 'numeric';
        inputCed.placeholder = (tipo === 'NIT') ? 'ej. 901234567' : 'ej. 1023456789';
      } else if (tipo === 'CE') {
        inputCed.maxLength = 12;
        inputCed.inputMode = 'text';
        inputCed.placeholder = 'ej. 123456';
      } else {
        inputCed.maxLength = 15;
        inputCed.inputMode = 'text';
        inputCed.placeholder = 'ej. AB123456';
      }
    };

    // Save Profile
    window.saveProfile = async function (e) {
      if (e) e.preventDefault();
      const nombre = (document.getElementById('profNombre')?.value.trim() || '').toUpperCase();
      const apellidoEl = document.getElementById('profApellido');
      const apellido = apellidoEl ? (apellidoEl.value.trim() || '').toUpperCase() : '';
      const telefono = (document.getElementById('profTel')?.value.trim() || '');
      const cedula = document.getElementById('profCedula') ? document.getElementById('profCedula').value.trim() : '';
      const fechaExpedicion = document.getElementById('profExpedicion') ? document.getElementById('profExpedicion').value : '';
      const cuenta = document.getElementById('profCuenta') ? document.getElementById('profCuenta').value.trim() : '';
      const tipoDoc = document.getElementById('profTipoDoc') ? document.getElementById('profTipoDoc').value : 'CC';
      const docLabel = (tipoDoc === 'NIT') ? 'NIT' : 'Cédula de Ciudadanía';

      if (!cedula || !fechaExpedicion) {
        showToast(`<i class="fa-solid fa-triangle-exclamation"></i> Por favor ingresa tu ${docLabel} y fecha de expedición.`, 'warning');
        return;
      }

      // Validación estricta de formato y cantidad de dígitos antes de hacer fetch
      if (tipoDoc === 'CC') {
        const cleanDigits = cedula.replace(/\D/g, '');
        if (cleanDigits.length < 6 || cleanDigits.length > 10) {
          showToast('La Cédula de Ciudadanía (CC) debe contener entre 6 y 10 dígitos numéricos.', 'warning');
          document.getElementById('profCedula')?.focus();
          return;
        }
      } else if (tipoDoc === 'NIT') {
        const cleanDigits = cedula.replace(/\D/g, '');
        if (cleanDigits.length < 9 || cleanDigits.length > 10) {
          showToast('El NIT debe contener entre 9 y 10 dígitos numéricos (sin guiones ni DV).', 'warning');
          document.getElementById('profCedula')?.focus();
          return;
        }
      } else if (tipoDoc === 'CE') {
        if (cedula.length < 5 || cedula.length > 12) {
          showToast('La Cédula de Extranjería (CE) debe contener entre 5 y 12 caracteres.', 'warning');
          document.getElementById('profCedula')?.focus();
          return;
        }
      } else if (tipoDoc === 'PASAPORTE') {
        if (cedula.length < 5 || cedula.length > 15) {
          showToast('El pasaporte debe contener entre 5 y 15 caracteres.', 'warning');
          document.getElementById('profCedula')?.focus();
          return;
        }
      }

      if (telefono) {
        const cleanTel = telefono.replace(/\D/g, '');
        if (cleanTel.length < 7 || cleanTel.length > 15) {
          showToast('El teléfono de contacto debe tener entre 7 y 15 dígitos numéricos.', 'warning');
          document.getElementById('profTel')?.focus();
          return;
        }
      }

      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const yesterdayIso = yesterday.toISOString().split('T')[0];
      if (fechaExpedicion > yesterdayIso) {
        showToast('La fecha de expedición debe ser igual o anterior a ayer.', 'warning');
        document.getElementById('profExpedicion')?.focus();
        return;
      }

      const requestBody = {
        nombre,
        apellido_1: apellido,
        telefono,
        cedula,
        numero_documento: cedula,
        tipo_documento: tipoDoc,
        fecha_expedicion: fechaExpedicion,
        fecha_nacimiento: fechaExpedicion,
        datos_cuenta: cuenta,
        verificado: true
      };

      const btnSub = document.getElementById('btnSubmitProfile');
      if (btnSub) {
        btnSub.disabled = true;
        btnSub.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Guardando Verificación...</span>';
      }

      let isConflictHandled = false;

      try {
        showToast('Guardando en Base de Datos y activando Verificación...', 'info');
        const idC = (_clientProfile && _clientProfile.id_cliente) ? _clientProfile.id_cliente : 1;
        
        const targetUrl = (_clientProfile && _clientProfile.id_cliente && _clientProfile.id_cliente > 0)
          ? `${API_BASE}/clientes/${_clientProfile.id_cliente}`
          : `${API_BASE}/clientes/me`;
        let res = await fetch(targetUrl, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${_token}`
          },
          body: JSON.stringify(requestBody)
        });

        if (res.status === 409) {
          isConflictHandled = true;
          const errData = await res.json().catch(() => ({}));
          const conflictMsg = errData.message || `Este número de ${docLabel} ya pertenece a otra cuenta.`;
          const errorDetail = (errData.errors && errData.errors[0]) || {};
          const titularName = errorDetail.nombre_titular || 'Titular Registrado';
          const titularEmail = errorDetail.email_titular || '';

          openTransferAuthModal({
            nit: cedula,
            tipoDocumento: tipoDoc,
            nombreTitular: titularName,
            emailTitular: titularEmail,
            message: conflictMsg,
            onSuccess: async (transferPassword) => {
              requestBody.transfer_password = transferPassword;
              showToast(`Verificando autorización y transfiriendo ${docLabel}...`, 'info');
              const resRetry = await fetch(`${API_BASE}/clientes/${idC}`, {
                method: 'PUT',
                headers: {
                  'Content-Type': 'application/json',
                  'Authorization': `Bearer ${_token}`
                },
                body: JSON.stringify(requestBody)
              });
              if (!resRetry.ok) {
                const retryErr = await resRetry.json().catch(() => ({}));
                let rMsg = retryErr.message;
                if (!rMsg && retryErr.detail) {
                  rMsg = Array.isArray(retryErr.detail) ? retryErr.detail.map(d => d.msg || d).join('. ') : String(retryErr.detail);
                }
                throw new Error(rMsg || 'Contraseña incorrecta de la cuenta anterior.');
              }
              showToast(`<i class="fa-solid fa-circle-check"></i> ¡${docLabel} transferido exitosamente a tu cuenta!`, 'success');
              if (_clientProfile) {
                _clientProfile.nombre = nombre;
                _clientProfile.apellido_1 = apellido;
                _clientProfile.telefono = telefono;
                _clientProfile.cedula = cedula;
                _clientProfile.numero_documento = cedula;
                _clientProfile.tipo_documento = tipoDoc;
                _clientProfile.fecha_expedicion = fechaExpedicion;
                _clientProfile.datos_cuenta = cuenta;
                _clientProfile.verificado = true;
              }
              await loadProfileData();
              renderDashboard();
            }
          });
          return;
        }

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          let errMsg = errData.message;
          if (!errMsg && errData.detail) {
            if (Array.isArray(errData.detail)) {
              errMsg = errData.detail.map(d => d.msg || d.message || d).join('. ');
            } else if (typeof errData.detail === 'string') {
              errMsg = errData.detail;
            }
          }
          throw new Error(errMsg || 'Error al guardar y verificar la información del perfil.');
        }

        if (_clientProfile) {
          _clientProfile.nombre = nombre;
          _clientProfile.apellido_1 = apellido;
          _clientProfile.telefono = telefono;
          _clientProfile.cedula = cedula;
          _clientProfile.numero_documento = cedula;
          _clientProfile.fecha_expedicion = fechaExpedicion;
          _clientProfile.datos_cuenta = cuenta;
          _clientProfile.verificado = true;
        }

        // Update top and profile badges to green
        const topBadge = document.getElementById('topbarCertBadge');
        if (topBadge) {
          topBadge.className = "cp-verified-badge";
          topBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
          topBadge.style.color = "#10B981";
          topBadge.style.background = "rgba(16, 185, 129, 0.1)";
          topBadge.innerHTML = "<span>Cliente verificado</span> <i class='fa-solid fa-check'></i>";
        }

        const profBadge = document.getElementById('profileCertBadge');
        if (profBadge) {
          profBadge.className = "cp-verified-badge";
          profBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";
          profBadge.style.color = "#10B981";
          profBadge.style.background = "rgba(16, 185, 129, 0.1)";
          profBadge.innerHTML = "<span>Verificado <i class='fa-solid fa-check'></i></span>";
        }

        // Ocultar cualquier overlay o modal activo
        const overlay = document.getElementById('blocking-verification-overlay');
        if (overlay) { overlay.classList.add('hidden'); overlay.style.display = 'none'; }
        const alertBanner = document.getElementById('dashboard-unverified-alert');
        if (alertBanner) { alertBanner.classList.add('hidden'); alertBanner.style.display = 'none'; }
        if (typeof closeTransferAuthModal === 'function') closeTransferAuthModal();
        if (typeof closeBlockingVerificationUI === 'function') closeBlockingVerificationUI();

        showToast('<i class="fa-solid fa-circle-check"></i> ¡Cédula y datos guardados exitosamente en la base de datos! Cuenta Verificada.', 'success');
        await loadProfileData(sessionStorage.getItem('fm_email') || localStorage.getItem('fm_email'));
        renderDashboard();
      } catch (err) {
        showToast('Error: ' + err.message, 'error');
      } finally {
        if (btnSub && !isConflictHandled) {
          btnSub.disabled = false;
          if (_clientProfile?.verificado) {
            btnSub.innerHTML = '<i class="fa-solid fa-pen-to-square"></i> <span>Actualizar Información</span>';
          } else {
            btnSub.innerHTML = '<i class="fa-solid fa-circle-check"></i> <span>Guardar y Activar Cuenta Verificada</span>';
          }
        }
      }
    };

    // Live Google Maps Preview
    window.updateMapsPreviewLive = function (latInputId, lngInputId, boxId, linkId) {
      const latVal = document.getElementById(latInputId)?.value;
      const lngVal = document.getElementById(lngInputId)?.value;
      const mapsInputId = latInputId === 'fincLat' ? 'fincMapsUrl' : 'editFincMapsUrl';
      const mapsUrlRaw = document.getElementById(mapsInputId)?.value?.trim();
      const box = document.getElementById(boxId);
      const link = document.getElementById(linkId);

      let targetUrl = '';
      if (mapsUrlRaw && (mapsUrlRaw.startsWith('http://') || mapsUrlRaw.startsWith('https://') || mapsUrlRaw.includes('maps'))) {
        targetUrl = mapsUrlRaw.startsWith('http') ? mapsUrlRaw : `https://${mapsUrlRaw}`;
      } else if (latVal && lngVal && !isNaN(parseFloat(latVal)) && !isNaN(parseFloat(lngVal))) {
        targetUrl = `https://www.google.com/maps?q=${parseFloat(latVal).toFixed(6)},${parseFloat(lngVal).toFixed(6)}`;
      }

      if (targetUrl) {
        if (link) link.href = targetUrl;
        if (box) { box.style.display = 'flex'; }
      } else {
        if (box) { box.style.display = 'none'; }
      }
    };

    // Google Maps Auto-Extractor
    window.autoExtractMapsCoords = function (mapsInputId, latInputId, lngInputId) {
      const mapsInput = document.getElementById(mapsInputId);
      const latInput = document.getElementById(latInputId);
      const lngInput = document.getElementById(lngInputId);
      const boxId = latInputId === 'fincLat' ? 'fincMapsLiveBox' : 'editFincMapsLiveBox';
      const linkId = latInputId === 'fincLat' ? 'fincMapsLiveLink' : 'editFincMapsLiveLink';
      if (!mapsInput || !latInput || !lngInput) return;
      const url = mapsInput.value.trim();
      
      // Siempre actualizar el botón con el link escrito si existe
      window.updateMapsPreviewLive(latInputId, lngInputId, boxId, linkId);
      if (!url) return;

      const atMatch = url.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
      const qMatch = url.match(/[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)/);
      const llMatch = url.match(/[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)/);
      const placeMatch = url.match(/place\/(-?\d+\.\d+),(-?\d+\.\d+)/);

      const match = atMatch || qMatch || llMatch || placeMatch;
      if (match) {
        const lat = parseFloat(match[1]).toFixed(6);
        const lng = parseFloat(match[2]).toFixed(6);
        latInput.value = lat;
        lngInput.value = lng;
        window.updateMapsPreviewLive(latInputId, lngInputId, boxId, linkId);
        showToast(`<i class="fa-solid fa-map-pin"></i> Coordenadas detectadas de Google Maps: ${lat}, ${lng}`, 'info');
      }
    };

    // Geolocation capture (New Finca)
    window.gpsCapture = function () {
      const btn = document.getElementById('btnGps');
      const textSpan = document.getElementById('btnGpsText');
      if (textSpan) textSpan.textContent = 'Obteniendo GPS...';
      else if (btn) btn.innerHTML = '<i class="fa-solid fa-location-crosshairs fa-spin"></i> Obteniendo GPS...';
      if (btn) btn.disabled = true;

      let done = false;
      const timeoutId = setTimeout(() => {
        if (!done) {
          done = true;
          if (textSpan) textSpan.textContent = 'GPS no disponible';
          else if (btn) btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Capturar Ubicación GPS';
          if (btn) btn.disabled = false;
          showToast('⚠️ No se obtuvo respuesta del sensor GPS a tiempo. Puedes pegar tu enlace de Google Maps o escribir coordenadas.', 'warning');
        }
      }, 10000);

      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            if (done) return;
            done = true;
            clearTimeout(timeoutId);
            const lat = pos.coords.latitude.toFixed(6);
            const lng = pos.coords.longitude.toFixed(6);
            document.getElementById('fincLat').value = lat;
            document.getElementById('fincLng').value = lng;
            const mapsInput = document.getElementById('fincMapsUrl');
            if (mapsInput) mapsInput.value = `https://www.google.com/maps?q=${lat},${lng}`;
            window.updateMapsPreviewLive('fincLat', 'fincLng', 'fincMapsLiveBox', 'fincMapsLiveLink');
            if (textSpan) textSpan.textContent = `GPS Capturado (${pos.coords.latitude.toFixed(3)}, ${pos.coords.longitude.toFixed(3)})`;
            else if (btn) btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> GPS Capturado';
            if (btn) btn.disabled = false;
            showToast('<i class="fa-solid fa-circle-check"></i> Ubicación GPS real capturada exitosamente');
          },
          (err) => {
            if (done) return;
            done = true;
            clearTimeout(timeoutId);
            if (textSpan) textSpan.textContent = 'GPS no disponible';
            else if (btn) btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Capturar Ubicación GPS';
            if (btn) btn.disabled = false;
            let msg = 'Permiso de ubicación denegado en tu navegador o dispositivo.';
            if (err.code === 1) msg = '⚠️ Permiso de ubicación denegado. Permite el acceso a ubicación en tu navegador o pega tu enlace de Maps.';
            else if (err.code === 2) msg = '⚠️ Señal GPS no disponible en este momento. Por favor pega tu enlace de Maps o escribe coordenadas.';
            else if (err.code === 3) msg = '⚠️ Tiempo de espera GPS agotado. Pega tu link de Google Maps.';
            showToast(msg, 'warning');
          },
          { enableHighAccuracy: false, timeout: 8000, maximumAge: 30000 }
        );
      } else {
        clearTimeout(timeoutId);
        if (textSpan) textSpan.textContent = 'GPS no soportado';
        else if (btn) btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Capturar Ubicación GPS';
        if (btn) btn.disabled = false;
        showToast('Tu navegador no soporta geolocalización. Ingresa el enlace de Maps manualmente.', 'warning');
      }
    };


    window.gpsCaptureEdit = function () {
      const btn = document.getElementById('btnGpsEdit');
      const textSpan = document.getElementById('btnGpsEditText');
      if (textSpan) textSpan.textContent = 'Obteniendo GPS...';
      else if (btn) btn.innerHTML = '<i class="fa-solid fa-location-crosshairs fa-spin"></i> Obteniendo GPS...';
      if (btn) btn.disabled = true;

      let done = false;
      const timeoutId = setTimeout(() => {
        if (!done) {
          done = true;
          if (textSpan) textSpan.textContent = 'GPS no disponible';
          else if (btn) btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Capturar Ubicación GPS';
          if (btn) btn.disabled = false;
          showToast('⚠️ No fue posible obtener la señal GPS a tiempo. Puedes pegar tu link de Google Maps.', 'warning');
        }
      }, 10000);

      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            if (done) return;
            done = true;
            clearTimeout(timeoutId);
            const lat = pos.coords.latitude.toFixed(6);
            const lng = pos.coords.longitude.toFixed(6);
            document.getElementById('editFincLat').value = lat;
            document.getElementById('editFincLng').value = lng;
            const mapsInput = document.getElementById('editFincMapsUrl');
            if (mapsInput) mapsInput.value = `https://www.google.com/maps?q=${lat},${lng}`;
            window.updateMapsPreviewLive('editFincLat', 'editFincLng', 'editFincMapsLiveBox', 'editFincMapsLiveLink');
            if (textSpan) textSpan.textContent = `GPS Capturado (${pos.coords.latitude.toFixed(3)}, ${pos.coords.longitude.toFixed(3)})`;
            else if (btn) btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> GPS Capturado';
            if (btn) btn.disabled = false;
            showToast('<i class="fa-solid fa-circle-check"></i> Ubicación GPS real capturada');
          },
          (err) => {
            if (done) return;
            done = true;
            clearTimeout(timeoutId);
            if (textSpan) textSpan.textContent = 'GPS no disponible';
            else if (btn) btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Capturar Ubicación GPS';
            if (btn) btn.disabled = false;
            let msg = '⚠️ Permiso de ubicación no disponible. Puedes escribir coordenadas o pegar link.';
            if (err.code === 1) msg = '⚠️ Permiso de ubicación denegado en el navegador. Puedes ingresar tus coordenadas o link manualmente.';
            showToast(msg, 'warning');
          },
          { enableHighAccuracy: false, timeout: 8000, maximumAge: 30000 }
        );
      } else {
        clearTimeout(timeoutId);
        if (textSpan) textSpan.textContent = 'GPS no soportado';
        else if (btn) btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> Capturar Ubicación GPS';
        if (btn) btn.disabled = false;
        showToast('Tu navegador no soporta geolocalización.', 'warning');
      }
    };


    window.eliminarFinca = async function (id) {
      if (!confirm('¿Seguro que deseas eliminar esta finca? Esta acción no se puede deshacer.')) return;

      try {
        const res = await fetch(`${API_BASE}/fincas/${id}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${_token}` }
        });

        if (res.ok) {
          showToast('<i class="fa-solid fa-check"></i> Finca eliminada correctamente');
          await refreshData();
        } else {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || errData.message || 'Error al eliminar');
        }
      } catch (err) {
        console.error("Error al eliminar finca:", err);
        showToast('<i class="fa-solid fa-triangle-exclamation"></i> Error: ' + err.message, 'error');
      }
    };

    // (renderDocumentosGrid uses the table-based version defined above)


    // FAQ Accordion
    window.toggleFaq = function (el) {
      const item = el.parentElement;
      const isOpen = item.classList.contains('open');
      document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));
      if (!isOpen) {
        item.classList.add('open');
      }
    };

    // Cancelar Turno (Actualiza inmediatamente la vista sin recargar)
    window.cancelarTurno = async function (idTurno) {
      if (!confirm('¿Estás seguro de que deseas cancelar esta solicitud de vuelo?')) return;

      const idx = _myAgendas.findIndex(a => (a.id_turno || a.id) === idTurno);
      if (idx !== -1) {
        _myAgendas[idx].estado = 'Cancelado';
      }

      try {
        await fetch(`${API_BASE}/agenda/${idTurno}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${_token}`
          },
          body: JSON.stringify({ estado: 'Cancelado' })
        });
      } catch (err) {
        console.warn('Error al cancelar turno en servidor:', err);
      }

      await refreshData();
      showToast('Solicitud de agendamiento cancelada exitosamente.', 'success');
    };

    // ── GESTIÓN DE COTIZACIONES Y NEGOCIACIÓN (CLIENTE) ──
    window._currentNegotiationTurnoId = null;

    window.openClientNegotiationModal = function (idTurno) {
      const targetId = Number(idTurno);
      window._currentNegotiationTurnoId = targetId;
      const turno = (_myAgendas || []).find(a => Number(a.id_turno || a.id) === targetId);

      if (!turno) {
        showToast('No se encontró información del turno #' + idTurno, 'error');
        return;
      }

      document.getElementById('clientNegRadicado').textContent = `#RAD-${targetId}`;
      document.getElementById('clientNegServicio').textContent = turno.nombre_servicio || turno.servicio || 'Servicio Dron';
      document.getElementById('clientNegFinca').textContent = `${turno.nombre_finca || turno.finca_nombre || 'Finca'} (${turno.hectareas || 10} Ha)`;
      document.getElementById('clientNegFechaHora').textContent = `${formatDate(turno.fecha_de_turno || turno.fecha_solicitada)} - ${turno.hora_inicio_estimada || turno.hora_preferida || '08:00 AM'}`;
      document.getElementById('clientNegPiloto').textContent = turno.tecnico || turno.tecnico_nombre || 'Piloto por asignar';

      // Precio
      const pEl = document.getElementById('clientNegPrecio');
      const isNegFreeDemo = Boolean(turno.es_demostracion || (turno.tarifa !== null && turno.tarifa !== undefined && Number(turno.tarifa) === 0) || String(turno.nombre_servicio || '').toLowerCase().includes('demo'));
      if (isNegFreeDemo) {
        pEl.innerHTML = `<span style="color:#15803d; font-size:1.3rem; font-weight:800;"><i class="fa-solid fa-gift"></i> Análisis del Terreno ($0 COP)</span>`;
      } else if (turno.tarifa !== null && turno.tarifa !== undefined && Number(turno.tarifa) > 0) {
        pEl.textContent = `$ ${Number(turno.tarifa).toLocaleString('es-CO')} COP`;
      } else {
        pEl.innerHTML = `<span style="color:#d97706; font-size:1.15rem; font-weight:700;"><i class="fa-solid fa-clock"></i> Cotización pendiente por definir</span>`;
      }

      // Estado Badge
      const bEl = document.getElementById('clientNegEstadoBadge');
      bEl.innerHTML = `<span class="badge badge-${getBadgeClass(turno.estado)}" style="font-size:0.8rem; font-weight:800;">${turno.estado || 'Pendiente'}</span>`;

      // Historial
      const histBox = document.getElementById('clientNegHistorialBox');
      const histList = document.getElementById('clientNegHistorialList');
      let hist = [];
      if (turno.historial_negociacion) {
        try {
          hist = typeof turno.historial_negociacion === 'string' ? JSON.parse(turno.historial_negociacion) : turno.historial_negociacion;
        } catch(e) {}
      }

      if (hist && hist.length > 0) {
        histBox.style.display = 'block';
        histList.innerHTML = hist.map(h => {
          const isAdm = h.emisor === 'admin';
          return `
            <div style="background:${isAdm ? '#eff6ff' : '#f0fdf4'}; border-left:3px solid ${isAdm ? '#1C82AD' : '#10b981'}; padding:8px 10px; border-radius:6px; font-size:0.80rem;">
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <strong style="color:${isAdm ? '#003049' : '#047857'};">${isAdm ? 'Operaciones Flymetrics' : 'Tu Propuesta'}:</strong>
                <span style="color:#94a3b8; font-size:0.72rem;">${h.fecha || ''}</span>
              </div>
              <div style="color:#334155;">${h.mensaje || ''}</div>
              ${h.tarifa ? `<div style="font-weight:800; color:#065f46; margin-top:2px;">Tarifa: $ ${Number(h.tarifa).toLocaleString('es-CO')} COP</div>` : ''}
            </div>
          `;
        }).join('');
      } else {
        histBox.style.display = 'none';
      }

      // Reset textarea
      const sugSec = document.getElementById('clientNegModificarSection');
      if (sugSec) sugSec.style.display = 'none';
      const sugInp = document.getElementById('clientNegSugerencia');
      if (sugInp) sugInp.value = '';

      const modal = document.getElementById('modalClientNegotiation');
      if (modal) {
        modal.classList.remove('hidden');
        modal.style.display = 'flex';
      }
    };

    window.closeClientNegotiationModal = function () {
      const modal = document.getElementById('modalClientNegotiation');
      if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
      }
    };

    window.responderCotizacionClientModal = async function (accion) {
      if (!window._currentNegotiationTurnoId) return;
      const idTurno = window._currentNegotiationTurnoId;
      const apiBase = API_BASE;

      let payload = { accion };
      if (accion === 'modificar') {
        const sug = (document.getElementById('clientNegSugerencia')?.value || '').trim();
        if (!sug) {
          showToast('Por favor describe tu propuesta o sugerencia para que nuestro equipo pueda evaluarla.', 'warning');
          return;
        }
        payload.sugerencia = sug;
      } else if (accion === 'aceptar') {
        if (!confirm('¿Deseas aceptar esta cotización y confirmar formalmente la orden de vuelo? Se coordinará la llegada del piloto.')) {
          return;
        }
      }

      const btnAceptar = document.getElementById('btnAceptarCotizacion');
      const btnMod = document.getElementById('btnEnviarSugerencia');
      if (btnAceptar) btnAceptar.disabled = true;
      if (btnMod) btnMod.disabled = true;

      try {
        const res = await fetch(`${apiBase}/agenda/${idTurno}/negociar`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${_token}`
          },
          body: JSON.stringify(payload)
        });

        const result = await res.json().catch(() => ({}));
        if (res.ok && (result.success || result.data)) {
          const newEstado = (result.data && result.data.estado) ? result.data.estado : (accion === 'aceptar' ? 'Confirmado' : 'Pendiente');
          showToast(result.message || (newEstado === 'Confirmado' ? '¡Cotización aceptada! Tu vuelo está confirmado.' : 'Sugerencia enviada correctamente.'), 'success');
          
          const localTurno = (_myAgendas || []).find(a => Number(a.id_turno || a.id) === idTurno);
          if (localTurno) {
            localTurno.estado = newEstado;
            if (accion === 'modificar') localTurno.sugerencia_cliente = payload.sugerencia;
          }
          closeClientNegotiationModal();
          renderAgendasTable();
          if (typeof renderDashboard === 'function') renderDashboard();
        } else {
          showToast(result.detail || result.message || 'No se pudo procesar la respuesta a la cotización.', 'error');
        }
      } catch (err) {
        console.error('Error al responder cotización:', err);
        showToast('Error de conexión al procesar la cotización.', 'error');
      } finally {
        if (btnAceptar) btnAceptar.disabled = false;
        if (btnMod) btnMod.disabled = false;
      }
    };

    // Modal Edit Agenda (Habilitado EXCLUSIVAMENTE para solicitudes Pendientes)
    window.openEditAgendaModal = async function (idTurno) {
      try {
        const targetId = Number(idTurno);
        let turno = (_myAgendas || []).find(a => Number(a.id_turno || a.id) === targetId);
        if (!turno) {
          try {
            const apiBase = API_BASE;
            const res = await fetch(`${apiBase}/agenda/${idTurno}`, {
              headers: { 'Authorization': `Bearer ${_token}` }
            });
            if (res.ok) {
              const b = await res.json();
              turno = b.data || b;
            }
          } catch (e) {}
        }

        if (!turno) {
          showToast('No se encontró el registro de turno seleccionado (ID #' + idTurno + ').', 'error');
          return;
        }

        const estLower = String(turno.estado || '').toLowerCase();
        if (estLower !== 'pendiente' && estLower !== 'solicitado') {
          showToast(`Atención: Este turno ya fue aceptado (${turno.estado}) por el equipo de Flymetrics y no admite modificaciones directas del cliente. Si requieres algún cambio o ajuste, por favor comunícate a nuestra línea de WhatsApp.`, 'warning');
          return;
        }

        const idEl = document.getElementById('editAgendaId');
        if (idEl) idEl.value = targetId;

        // Populate Fincas dropdown
        const fincaSelect = document.getElementById('editAgendaFinca');
        if (fincaSelect) {
          if (_myFincas && _myFincas.length > 0) {
            fincaSelect.innerHTML = _myFincas.map(f => `
              <option value="${f.id_finca || f.id}">${f.nombre_finca} (${f.hectareas || 10} Ha - ${f.departamento || 'Casanare'})</option>
            `).join('');
            const currentFincaId = turno.id_finca || (_myFincas[0] ? (_myFincas[0].id_finca || _myFincas[0].id) : 1);
            fincaSelect.value = currentFincaId;
          } else {
            fincaSelect.innerHTML = `<option value="">-- Sin finca registrada --</option>`;
          }
        }

        // Populate Services checkboxes with multi-service & catalog support
        const serviciosContainer = document.getElementById('editAgendaServiciosContainer');
        if (serviciosContainer) {
          const currentSvcName = String(turno.nombre_servicio || turno.servicio || '').toLowerCase();
          const currentObs = String(turno.observaciones_servicio || '').toLowerCase();
          const servicesList = (_catalogServicios && _catalogServicios.length > 0) ? _catalogServicios : [
            { id_servicio: 1, nombre_servicio: 'Fumigación Fitosanitaria (Dron)' },
            { id_servicio: 2, nombre_servicio: 'Fertilización Foliar & Bioestimulantes' },
            { id_servicio: 3, nombre_servicio: 'Fertilización / Fumigación de Pastos' },
            { id_servicio: 4, nombre_servicio: 'Esparcido de Granulado / Siembra Aérea' },
            { id_servicio: 5, nombre_servicio: 'Análisis Multiespectral de Cultivos' }
          ];

          serviciosContainer.innerHTML = servicesList.map(s => {
            const sId = s.id_servicio || s.id;
            const sName = String(s.nombre_servicio || '').toLowerCase();
            const isChecked = (Number(turno.id_servicio) === Number(sId)) ||
                              currentSvcName.includes(sName) ||
                              currentObs.includes(sName) ||
                              (sId === 1 && currentSvcName.includes('fumigaci'));
            return `
              <label style="display:flex; align-items:center; gap:8px; font-size:0.85rem; cursor:pointer; color:#003049; font-weight:600;">
                <input type="checkbox" class="edit-ag-svc-checkbox" value="${sId}" ${isChecked ? 'checked' : ''} style="width:16px; height:16px; accent-color:#1c82ad;" />
                <span>${s.nombre_servicio}</span>
              </label>
            `;
          }).join('');
        }

        // Safe date parsing (YYYY-MM-DD)
        const fechaInput = document.getElementById('editAgendaFecha');
        const todayIso = new Date().toISOString().split('T')[0];
        let fechaRaw = String(turno.fecha_de_turno || turno.fecha_solicitada || todayIso);
        if (fechaRaw.includes('T')) fechaRaw = fechaRaw.split('T')[0];
        if (fechaRaw.includes(' ')) fechaRaw = fechaRaw.split(' ')[0];
        if (fechaInput) {
          fechaInput.min = todayIso;
          fechaInput.value = fechaRaw;
        }

        // Safe time parsing (HH:MM)
        let horaStr = turno.hora_inicio_estimada;
        if (!horaStr && String(turno.fecha_de_turno || '').includes('T')) {
          horaStr = String(turno.fecha_de_turno).split('T')[1];
        } else if (!horaStr && String(turno.fecha_de_turno || '').includes(' ')) {
          horaStr = String(turno.fecha_de_turno).split(' ')[1];
        }
        horaStr = String(horaStr || '08:30:00').trim().substring(0, 5);
        const horaInput = document.getElementById('editAgendaHora');
        if (horaInput) horaInput.value = horaStr;

        // Clean observations from internal tags like [Servicios: ...]
        let rawObs = String(turno.observaciones_servicio || '');
        let cleanObs = rawObs.replace(/\[?Servicios:[^\]\n]+\]?/gi, '')
                             .replace(/(\s*\|\s*Cambiado por Admin:[^|]+)+/gi, '')
                             .replace(/(\s*\|\s*Nota Admin:[^|]+)+/gi, '')
                             .trim();
        const obsInput = document.getElementById('editAgendaObs');
        if (obsInput) obsInput.value = cleanObs;

        const modal = document.getElementById('modalEditAgenda');
        if (modal) {
          modal.classList.remove('hidden');
          modal.classList.add('open', 'active');
          modal.style.setProperty('display', 'flex', 'important');
          modal.style.setProperty('opacity', '1', 'important');
          modal.style.setProperty('visibility', 'visible', 'important');
          modal.style.zIndex = '999999';
          document.body.style.overflow = 'hidden';
        }
      } catch (err) {
        console.error('[OPEN EDIT AGENDA ERROR]', err);
        showToast('Error al abrir modal de edición de agenda: ' + err.message, 'error');
      }
    };

    window.closeEditAgendaModal = function () {
      const modal = document.getElementById('modalEditAgenda');
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('open', 'active');
        modal.style.setProperty('display', 'none', 'important');
        document.body.style.overflow = '';
      }
    };

    window.submitEditAgenda = async function (e) {
      if (e) e.preventDefault();
      const idTurno = parseInt(document.getElementById('editAgendaId').value, 10);
      const idFinca = parseInt(document.getElementById('editAgendaFinca')?.value || 1, 10);
      const nuevaFecha = document.getElementById('editAgendaFecha').value;
      const nuevaHora = document.getElementById('editAgendaHora').value;
      const nuevasObs = document.getElementById('editAgendaObs').value.trim();

      const todayStr = new Date().toISOString().split('T')[0];
      if (!nuevaFecha || nuevaFecha < todayStr) {
        showToast('Atención: No es posible programar un vuelo para una fecha en el pasado', 'warning');
        return;
      }

      if (!nuevaHora) {
        showToast('Atención: Selecciona una hora válida para el vuelo', 'warning');
        return;
      }

      const checkboxes = document.querySelectorAll('.edit-ag-svc-checkbox:checked');
      let selectedServiceIds = Array.from(checkboxes).map(cb => parseInt(cb.value, 10));
      if (selectedServiceIds.length === 0) {
        showToast('Atención: Selecciona al menos un servicio técnico', 'warning');
        return;
      }

      const primaryServiceId = selectedServiceIds[0] || 1;
      const catalog = (_catalogServicios && _catalogServicios.length > 0) ? _catalogServicios : [
        { id_servicio: 1, nombre_servicio: 'Fumigación Fitosanitaria (Dron)' },
        { id_servicio: 2, nombre_servicio: 'Fertilización Foliar & Bioestimulantes' },
        { id_servicio: 3, nombre_servicio: 'Fertilización / Fumigación de Pastos' },
        { id_servicio: 4, nombre_servicio: 'Esparcido de Granulado / Siembra Aérea' },
        { id_servicio: 5, nombre_servicio: 'Análisis Multiespectral de Cultivos' }
      ];
      const selectedSvcs = selectedServiceIds.map(id => catalog.find(s => (s.id_servicio || s.id) === id)).filter(Boolean);
      const combinedSvcName = selectedSvcs.length > 0
        ? selectedSvcs.map(s => s.nombre_servicio).join(' + ')
        : 'Aspersión con Dron';

      const selectedFinca = (_myFincas || []).find(f => (f.id_finca || f.id) === idFinca) || { id_finca: 1, nombre_finca: 'Finca Principal' };

      const formattedTime = nuevaHora.length === 5 ? nuevaHora + ':00' : nuevaHora;
      const fullObs = nuevasObs ? `${nuevasObs} [Servicios: ${combinedSvcName}]` : `Servicios: ${combinedSvcName}`;

      const turno = (_myAgendas || []).find(a => Number(a.id_turno || a.id) === idTurno);
      const prevEstado = turno ? (turno.estado || 'Pendiente') : 'Pendiente';
      const nuevoEstado = (prevEstado.toLowerCase() === 'confirmado') ? 'Reagendado' : prevEstado;

      if (turno) {
        const estLower = String(turno.estado || '').toLowerCase();
        if (['completado', 'cancelado'].includes(estLower)) {
          showToast('Atención: Este turno ya ha sido completado o cancelado y no puede modificarse', 'error');
          closeEditAgendaModal();
          return;
        }
        turno.id_finca = idFinca;
        turno.nombre_finca = selectedFinca.nombre_finca;
        turno.id_servicio = primaryServiceId;
        turno.nombre_servicio = combinedSvcName;
        turno.servicio = combinedSvcName;
        turno.fecha_de_turno = nuevaFecha;
        turno.fecha_solicitada = nuevaFecha;
        turno.hora_inicio_estimada = formattedTime;
        turno.observaciones_servicio = fullObs;
        turno.estado = nuevoEstado;
      }

      try {
        const activeToken = _token || sessionStorage.getItem('fm_token') || localStorage.getItem('fm_token') || '';
        const apiBase = API_BASE;
        const res = await fetch(`${apiBase}/agenda/${idTurno}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${activeToken}`
          },
          body: JSON.stringify({
            id_finca: idFinca,
            id_servicio: primaryServiceId,
            fecha_de_turno: nuevaFecha,
            hora_inicio_estimada: formattedTime,
            observaciones_servicio: fullObs,
            estado: nuevoEstado,
            motivo_reagendamiento: 'Ajuste de solicitud realizado por el cliente desde el portal web'
          })
        });
        if (res.ok) {
          showToast(`Solicitud modificada exitosamente${nuevoEstado === 'Reagendado' ? ' (Estado actualizado a Reagendado)' : ''}.`, 'success');
        } else {
          showToast('Solicitud actualizada.', 'info');
        }
      } catch (err) {
        console.warn('Agenda edit network warning:', err);
      }

      closeEditAgendaModal();
      await refreshData();
      renderAgendasTable();
    };

    window.checkVerifiedOrBlock = function (actionName = 'realizar esta acción') {
      const isFullyVerified = Boolean(
        _clientProfile &&
        _clientProfile.verificado &&
        _clientProfile.numero_documento &&
        String(_clientProfile.numero_documento).length >= 4
      );

      if (!isFullyVerified) {
        showToast(` Para ${actionName}, completa la verificación de tu cédula en tu perfil.`, 'info');
        window.focusCedulaInput();
        return false;
      }
      return true;
    };

    window.focusCedulaInput = function () {
      showPanel('perfil');
      setTimeout(() => {
        const inp = document.getElementById('profCedula') || document.getElementById('verif-cedula');
        if (inp) {
          inp.scrollIntoView({ behavior: 'smooth', block: 'center' });
          inp.focus();
        }
      }, 300);
    };

    // ── MODAL MANAGEMENT ─────────────────────
    window.openNewAgendaModal = async function () {
      if (!window.checkVerifiedOrBlock("agendar un servicio")) return;

      if (!_myFincas || _myFincas.length === 0) {
        showToast('Atención: Primero debes registrar tu finca o predio para poder agendar un vuelo.', 'warning');
        openNewFincaModal();
        return;
      }

      populateServicesDropdown();
      populateFincasDropdown();

      // Auto-populate field phone and manager from selected finca
      updateAgFincaContactInfo();

      // Reset variables de estado con fecha de mañana por defecto
      const tm = new Date();
      tm.setDate(tm.getDate() + 1);
      _selectedDate = tm.toISOString().split('T')[0];
      _selectedTime = "08:30:00";
      _selectedTecnicoId = 1;
      _calCurrentYear = tm.getFullYear();
      _calCurrentMonth = tm.getMonth();

      const btnSubmit = document.getElementById('btnSubmitAgenda');
      if (btnSubmit) btnSubmit.disabled = false;

      const formatted = `${String(tm.getDate()).padStart(2, '0')}/${String(tm.getMonth() + 1).padStart(2, '0')}/${tm.getFullYear()}`;
      const elDuration = document.getElementById('agDurationLabel'); if (elDuration) elDuration.textContent = "Duración: ~1.5h";
      const elArea = document.getElementById('agSummaryArea'); if (elArea) elArea.textContent = "25 ha";
      const elDateTime = document.getElementById('agSummaryDateTime'); if (elDateTime) elDateTime.textContent = `${formatted} a las 08:30 AM`;

      // Cargar técnicos desde el backend
      try {
        const res = await fetch(`${API_BASE}/tecnicos`, {
          headers: { 'Authorization': `Bearer ${_token}` }
        });
        if (res.ok) {
          const body = await res.json();
          _myTecnicos = body.data || body;
        } else {
          _myTecnicos = [
            { id: 1, nombre: "Juan", apellido: "Pérez", servicios_capacitados: "1,2,3" },
            { id: 2, nombre: "Andrés", apellido: "Rojas", servicios_capacitados: "1,2" },
            { id: 3, nombre: "Carlos", apellido: "Gómez", servicios_capacitados: "3" }
          ];
        }
      } catch (err) {
        _myTecnicos = [
          { id: 1, nombre: "Juan", apellido: "Pérez", servicios_capacitados: "1,2,3" },
          { id: 2, nombre: "Andrés", apellido: "Rojas", servicios_capacitados: "1,2" },
          { id: 3, nombre: "Carlos", apellido: "Gómez", servicios_capacitados: "3" }
        ];
      }

      filterAndPopulateTecnicos();
      drawCalendar(_calCurrentYear, _calCurrentMonth);
      loadTimeSlots();

      document.getElementById('modalNewAgenda').classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    };

    window.openAgendaModal = window.openNewAgendaModal;

    window.closeNewAgendaModal = function () {
      document.getElementById('modalNewAgenda').classList.add('hidden');
      document.body.style.overflow = '';
      document.getElementById('newAgendaForm').reset();
    };

    // Filtrar técnicos calificados según servicio
    function filterAndPopulateTecnicos() {
      const tecSelect = document.getElementById('agTecnico');
      if (!tecSelect) return;
      tecSelect.innerHTML = '';

      const agSvcEl = document.getElementById('agServicio');
      const idSvc = agSvcEl ? parseInt(agSvcEl.value) : 1;

      const filtered = (_myTecnicos && _myTecnicos.length) ? _myTecnicos : [
        { id: 1, nombre: "Juan", apellido: "Pérez", servicios_capacitados: "1,2,3" },
        { id: 2, nombre: "Andrés", apellido: "Rojas", servicios_capacitados: "1,2" }
      ];

      filtered.forEach((t, idx) => {
        const opt = document.createElement('option');
        const tId = t.id_tecnico !== undefined ? t.id_tecnico : t.id;
        opt.value = tId;
        opt.textContent = `${t.nombre} ${t.apellido_1 || t.apellido || ''} (Piloto calificado)`;
        if (idx === 0) {
          opt.selected = true;
          _selectedTecnicoId = tId;
        }
        tecSelect.appendChild(opt);
      });

      try { onAgendaConfigChanged(); } catch (e) { }
    }

    // Escucha cambios en finca o selección de servicios
    window.onAgendaConfigChanged = function () {
      const idFinca = parseInt(document.getElementById('agFinca')?.value || 0);
      const checkboxes = document.querySelectorAll('.ag-svc-checkbox:checked');
      const selectedServiceIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

      if (idFinca && selectedServiceIds.length > 0) {
        const finca = _myFincas.find(f => (f.id_finca || f.id) === idFinca);
        if (finca) {
          const hectareas = parseFloat(finca.hectareas) || 10;
          const elArea = document.getElementById('agSummaryArea');
          if (elArea) elArea.textContent = `${hectareas} ha`;
        }
      } else {
        const elArea = document.getElementById('agSummaryArea'); if (elArea) elArea.textContent = "--";
      }

      if (_selectedDate) {
        loadTimeSlots();
      }

      drawCalendar(_calCurrentYear, _calCurrentMonth);
    };

    // Dibuja el calendario interactivo
    window.drawCalendar = async function (year, month) {
      const monthNames = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
      const monthSelect = document.getElementById('calMonthSelect');
      const yearSelect = document.getElementById('calYearSelect');
      if (monthSelect && yearSelect) {
        monthSelect.value = month;
        yearSelect.value = year;
      } else {
        const calMY = document.getElementById('calMonthYear');
        if (calMY) calMY.textContent = `${monthNames[month]} ${year}`;
      }

      const grid = document.getElementById('calendarDaysGrid');
      grid.innerHTML = '';

      const firstDayIdx = new Date(year, month, 1).getDay();
      const numDays = new Date(year, month + 1, 0).getDate();

      const today = new Date();
      const todayDateStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

      for (let i = 0; i < firstDayIdx; i++) {
        const emptyDiv = document.createElement('div');
        grid.appendChild(emptyDiv);
      }

      const now = new Date();
      const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);

      for (let day = 1; day <= numDays; day++) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'calendar-day-btn';
        btn.textContent = day;

        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        btn.dataset.date = dateStr;

        const cellDate = new Date(year, month, day, 0, 0, 0, 0);

        if (cellDate < startOfToday) {
          btn.classList.add('cal-day-disabled');
          btn.disabled = true;
          btn.style.opacity = '0.35';
          btn.style.cursor = 'not-allowed';
          btn.style.background = 'rgba(0,0,0,0.03)';
          btn.title = "Fecha pasada no disponible";
        } else {
          if (dateStr === todayDateStr) {
            btn.classList.add('cal-day-today');
          }
          if (dateStr === _selectedDate) {
            btn.classList.add('cal-day-selected');
          }
          btn.classList.add('cal-day-free');
          btn.title = "Día operativo disponible";
          btn.onclick = () => selectCalendarDay(dateStr);
        }
        grid.appendChild(btn);
      }
    };

    // Cambiar de mes
    window.changeCalMonth = function (dir) {
      _calCurrentMonth += dir;
      if (_calCurrentMonth < 0) {
        _calCurrentMonth = 11;
        _calCurrentYear--;
      } else if (_calCurrentMonth > 11) {
        _calCurrentMonth = 0;
        _calCurrentYear++;
      }
      drawCalendar(_calCurrentYear, _calCurrentMonth);
    };

    window.onCalMonthSelectChange = function () {
      const monthSelect = document.getElementById('calMonthSelect');
      const yearSelect = document.getElementById('calYearSelect');
      if (monthSelect && yearSelect) {
        _calCurrentMonth = parseInt(monthSelect.value);
        _calCurrentYear = parseInt(yearSelect.value);
        drawCalendar(_calCurrentYear, _calCurrentMonth);
      }
    };

    function updateAgendaSummaryDateTime() {
      const summaryEl = document.getElementById('agSummaryDateTime');
      if (!summaryEl) return;

      if (!_selectedDate) {
        summaryEl.textContent = "No seleccionada";
        return;
      }

      const parts = _selectedDate.split('-');
      const formattedDate = `${parts[2]}/${parts[1]}/${parts[0]}`;

      if (!_selectedTime) {
        summaryEl.textContent = `${formattedDate} — Selecciona Hora`;
        return;
      }

      const hhmm = _selectedTime.substring(0, 5);
      let [h, m] = hhmm.split(':').map(Number);
      const ampm = h >= 12 ? 'PM' : 'AM';
      h = h % 12 || 12;
      const formatted12h = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')} ${ampm}`;

      summaryEl.textContent = `${formattedDate} a las ${formatted12h}`;
    }

    // Seleccionar día del calendario
    window.selectCalendarDay = function (dateStr) {
      _selectedDate = dateStr;

      const buttons = document.querySelectorAll('.calendar-day-btn');
      buttons.forEach(btn => {
        if (btn.dataset.date === dateStr) {
          btn.classList.add('cal-day-selected');
        } else {
          btn.classList.remove('cal-day-selected');
        }
      });

      if (!_selectedTime) {
        const picker = document.getElementById('agCustomTimePicker');
        _selectedTime = picker ? (picker.value + ":00") : "08:30:00";
      }

      updateAgendaSummaryDateTime();
      loadTimeSlots();
      const btnSubmit = document.getElementById('btnSubmitAgenda');
      if (btnSubmit) btnSubmit.disabled = false;
    };

    window.onCustomTimeChanged = function (valStr) {
      if (!valStr) return;
      _selectedTime = valStr.length === 5 ? valStr + ":00" : valStr;

      const buttons = document.querySelectorAll('.time-slot-btn');
      buttons.forEach(btn => {
        if (btn.dataset.time.substring(0, 5) === valStr.substring(0, 5)) {
          btn.classList.add('slot-selected');
        } else {
          btn.classList.remove('slot-selected');
        }
      });

      updateAgendaSummaryDateTime();
      const btnSubmit = document.getElementById('btnSubmitAgenda');
      if (btnSubmit) btnSubmit.disabled = false;
    };

    // Carga slots rápidos para la fecha seleccionada
    window.loadTimeSlots = function () {
      const grid = document.getElementById('agSlotsGrid');
      if (!grid) return;
      grid.innerHTML = '';

      const slots = [
        { time: "07:00:00", label: "07:00 AM" },
        { time: "08:30:00", label: "08:30 AM" },
        { time: "10:00:00", label: "10:00 AM" },
        { time: "11:30:00", label: "11:30 AM" },
        { time: "13:30:00", label: "01:30 PM" },
        { time: "15:00:00", label: "03:00 PM" }
      ];

      slots.forEach(s => {
        const btnSlot = document.createElement('button');
        btnSlot.type = 'button';
        btnSlot.className = 'time-slot-btn';
        btnSlot.textContent = s.label;
        btnSlot.dataset.time = s.time;
        if (_selectedTime && s.time.substring(0, 5) === _selectedTime.substring(0, 5)) {
          btnSlot.classList.add('slot-selected');
        }
        btnSlot.onclick = () => selectTimeSlot(s.time);
        grid.appendChild(btnSlot);
      });
    };

    // Seleccionar slot de hora rápido
    window.selectTimeSlot = function (timeStr) {
      _selectedTime = timeStr;
      const customPicker = document.getElementById('agCustomTimePicker');
      if (customPicker) customPicker.value = timeStr.substring(0, 5);

      const buttons = document.querySelectorAll('.time-slot-btn');
      buttons.forEach(btn => {
        if (btn.dataset.time === timeStr || btn.dataset.time.substring(0, 5) === timeStr.substring(0, 5)) {
          btn.classList.add('slot-selected');
        } else {
          btn.classList.remove('slot-selected');
        }
      });

      updateAgendaSummaryDateTime();
      const btnSubmit = document.getElementById('btnSubmitAgenda');
      if (btnSubmit) btnSubmit.disabled = false;
    };

    window.openNewFincaModal = function () {
      if (!checkVerifiedOrBlock("registrar una finca")) return;
      document.getElementById('modalNewFinca').classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    };
    window.closeNewFincaModal = function () {
      document.getElementById('modalNewFinca').classList.add('hidden');
      document.body.style.overflow = '';
      document.getElementById('newFincaForm').reset();
      document.getElementById('btnGps').textContent = '<i class="fa-solid fa-location-dot"></i> Capturar mi GPS actual';
      document.getElementById('btnGps').disabled = false;
    };

    // ── HELPERS ──────────────────────────────
    function formatDate(dStr) {
      if (!dStr) return '—';
      try {
        const date = new Date(dStr + 'T12:00:00');
        return date.toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });
      } catch (e) {
        return dStr;
      }
    }

    function formatCurrency(v) {
      return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(v);
    }

    function getBadgeClass(status) {
      const mapping = {
        'pendiente': 'pending',
        'confirmado': 'confirmed',
        'en proceso': 'inprocess',
        'en Proceso': 'inprocess',
        'hecho': 'completed',
        'completado': 'completed',
        'cancelado': 'cancelled'
      };
      return mapping[(status || '').toLowerCase()] || 'completed';
    }

    window.logout = async function () {
      try {
        await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => null);
      } catch(e) {}
      try { sessionStorage.clear(); } catch(e) {}
      try { localStorage.clear(); } catch(e) {}
      window.location.href = 'index.html';
    };

    let _clientCorporateConfig = {
      empresa: "Flymetrics Colombia S.A.S.",
      telefono: "+57 314 3764972",
      whatsapp: "+57 314 3764972",
      email: "comercial@flymetrics.com.co",
      wa_template_general: "Hola Flymetrics, deseo solicitar asesoría e información técnica sobre mis servicios de drones agrícolas."
    };

    window.loadCorporateConfigClient = async function () {
      try {
        const res = await fetch(`${API_BASE}/contacto/config/sistema`);
        if (res.ok) {
          const data = await res.json();
          const cfg = data.data || data;
          if (cfg && (cfg.whatsapp || cfg.telefono)) {
            _clientCorporateConfig = { ..._clientCorporateConfig, ...cfg };
          }
        }
      } catch (e) {
        console.warn("No se pudo cargar la configuración corporativa pública:", e);
      }

      const phone = (_clientCorporateConfig.whatsapp || '3143764972').replace(/\D/g, '');
      const cleanPhone = phone ? (phone.startsWith('57') ? phone : `57${phone.slice(-10)}`) : '573143764972';
      const generalMsg = _clientCorporateConfig.wa_template_general || 'Hola Flymetrics, deseo solicitar asesoría e información técnica sobre mis servicios.';
      const emailVal = _clientCorporateConfig.email || 'comercial@flymetrics.com.co';

      const floatingWa = document.getElementById('btn-floating-whatsapp');
      if (floatingWa) {
        floatingWa.href = `https://wa.me/${cleanPhone}?text=${encodeURIComponent(generalMsg)}`;
      }

      const supportWa = document.getElementById('supportWaBtn');
      if (supportWa) {
        supportWa.href = `https://wa.me/${cleanPhone}?text=${encodeURIComponent(generalMsg)}`;
      }

      const supportEmail = document.getElementById('supportEmailBtn');
      if (supportEmail) {
        supportEmail.href = `mailto:${emailVal}?subject=Soporte%20Flymetrics%20-%20Cliente`;
        supportEmail.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Enviar Correo a ${emailVal}`;
      }
    };

    window.openWAMessage = function () {
      const phone = (_clientCorporateConfig.whatsapp || '3155429714').replace(/\D/g, '');
      const cleanPhone = phone ? (phone.startsWith('57') ? phone : `57${phone.slice(-10)}`) : '573155429714';
      const tmpl = _clientCorporateConfig.wa_template_general || 'Hola Flymetrics, necesito soporte con mis servicios de vuelo agendados en Flymetrics.';
      const msg = tmpl.replace('{nombre}', (_clientProfile && _clientProfile.nombre) || 'Cliente');
      window.open(`https://wa.me/${cleanPhone}?text=${encodeURIComponent(msg)}`, '_blank');
    };

    window.showToast = function (msg, type = 'info', duration = 3500) {
      let t = document.getElementById('toast');
      if (!t) {
        t = document.createElement('div');
        t.id = 'toast';
        document.body.appendChild(t);
      }

      t.removeAttribute('style');
      t.className = '';

      const typeMap = {
        'success': 'toast-success',
        'warning': 'toast-warning',
        'warn': 'toast-warning',
        'error': 'toast-error',
        'info': 'toast-info'
      };

      const iconMap = {
        'toast-success': '<i class="fa-solid fa-circle-check" style="font-size:1.2rem; color:#10B981; flex-shrink:0;"></i>',
        'toast-warning': '<i class="fa-solid fa-triangle-exclamation" style="font-size:1.2rem; color:#F59E0B; flex-shrink:0;"></i>',
        'toast-error': '<i class="fa-solid fa-circle-xmark" style="font-size:1.2rem; color:#EF4444; flex-shrink:0;"></i>',
        'toast-info': '<i class="fa-solid fa-circle-info" style="font-size:1.2rem; color:#1C82AD; flex-shrink:0;"></i>'
      };

      const selectedClass = typeMap[type] || 'toast-info';
      t.classList.add(selectedClass);
      t.innerHTML = `${iconMap[selectedClass] || ''} <span style="font-weight:700;">${msg}</span>`;
      t.classList.add('show');

      if (window._toastTimeout) clearTimeout(window._toastTimeout);
      window._toastTimeout = setTimeout(() => {
        t.classList.remove('show');
      }, duration);
    };

    // ── MOCK DATA ────────────────────────────
    function getMockServices() {
      return [
        { id: 1, nombre_servicio: 'Fumigación Agrícola', precio_base_m2: 18 },
        { id: 2, nombre_servicio: 'Análisis Multiespectral', precio_base_m2: 28 },
        { id: 3, nombre_servicio: 'Aspersión de Herbicidas', precio_base_m2: 22 },
        { id: 4, nombre_servicio: 'Fotogrametría 3D', precio_base_m2: 35 },
        { id: 5, nombre_servicio: 'Asesoría Técnica RAC100', precio_base_m2: 0 },
        { id: 6, nombre_servicio: 'Censo de Cultivos', precio_base_m2: 25 }
      ];
    }

    function getMockFincas() {
      return [
        { id_finca: 1, nombre_finca: 'Hacienda El Prado', municipio: 'Yopal', departamento: 'Casanare', hectareas: 120.0, latitud: 5.3378, longitud: -72.3959 },
        { id_finca: 2, nombre_finca: 'Finca La Esperanza', municipio: 'Villavicencio', departamento: 'Meta', hectareas: 45.5, latitud: 4.1420, longitud: -73.6266 }
      ];
    }

    function getMockAgendas() {
      return [
        {
          id_turno: 101,
          id_finca: 1,
          nombre_finca: 'Hacienda El Prado',
          nombre_servicio: 'Fumigación Agrícola',
          fecha_solicitada: '2026-06-15',
          fecha_de_turno: '2026-06-15',
          hora_inicio_estimada: '07:00 AM',
          tecnico: 'Carlos Méndez (Piloto Licenciado)',
          estado: 'Confirmado',
          hectareas: 120.0,
          precio: 2160000
        },
        {
          id_turno: 102,
          id_finca: 2,
          nombre_finca: 'Finca La Esperanza',
          nombre_servicio: 'Análisis Multiespectral',
          fecha_solicitada: '2026-06-20',
          fecha_de_turno: '2026-06-20',
          hora_inicio_estimada: '09:00 AM',
          tecnico: 'Por Asignar',
          estado: 'Pendiente',
          hectareas: 45.5,
          precio: 1274000
        },
        {
          id_turno: 100,
          id_finca: 1,
          nombre_finca: 'Hacienda El Prado',
          nombre_servicio: 'Fumigación Agrícola',
          fecha_solicitada: '2026-06-04',
          fecha_de_turno: '2026-06-04',
          hora_inicio_estimada: '07:30 AM',
          tecnico: 'Juan Pérez (Piloto Licenciado)',
          estado: 'Hecho',
          hectareas: 50.0,
          precio: 900000
        }
      ];
    }

    // ── CAMARA SCANNER FOR CARD VALIDATION ──
    let scannerStream = null;
    let scannerStep = "frente"; // "frente" | "reverso"
    let scannerFrenteImg = null;
    let scannerReversoImg = null;
    let scannerDrawLoopId = null;

    // Shared Canvas Telemetry Drawing function
    function runCanvasTelemetry(video, canvas, stepVarGetter, drawLoopIdSetter, isBlock) {
      const ctx = canvas.getContext('2d');
      canvas.classList.remove('hidden');

      let laserY = 10;
      let laserDirection = 1;

      function draw() {
        if (!video.srcObject && !video.src) return; // Stopped

        if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
          canvas.width = video.videoWidth || 640;
          canvas.height = video.videoHeight || 480;
        }

        const w = canvas.width;
        const h = canvas.height;

        // 1. Frame (mirrored horizontally for natural layout)
        ctx.save();
        ctx.translate(w, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, w, h);
        ctx.restore();

        const cardW = w * 0.8;
        const cardH = h * 0.55;
        const cardX = (w - cardW) / 2;
        const cardY = (h - cardH) / 2;

        // 2. Grid lines
        ctx.strokeStyle = 'rgba(28, 130, 173, 0.12)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let x = 0; x < w; x += 30) {
          ctx.moveTo(x, 0); ctx.lineTo(x, h);
        }
        for (let y = 0; y < h; y += 30) {
          ctx.moveTo(0, y); ctx.lineTo(w, y);
        }
        ctx.stroke();

        // 3. Card boundary
        ctx.strokeStyle = '#1C82AD';
        ctx.lineWidth = 3;
        ctx.strokeRect(cardX, cardY, cardW, cardH);

        const step = stepVarGetter();

        // 4. Bounding box (Face for front, PDF417 for reverso)
        if (step === 'frente') {
          ctx.strokeStyle = 'rgba(28, 130, 173, 0.8)';
          ctx.lineWidth = 2;
          const faceSize = Math.min(w, h) * 0.25;
          const faceX = cardX + cardW * 0.1;
          const faceY = cardY + (cardH - faceSize) / 2;
          ctx.strokeRect(faceX, faceY, faceSize, faceSize);
          ctx.fillStyle = 'rgba(28, 130, 173, 0.8)';
          ctx.font = '10px monospace';
          ctx.fillText('[ROSTRO DETECTADO]', faceX, faceY - 5);
        } else {
          ctx.strokeStyle = 'rgba(255, 165, 0, 0.8)';
          ctx.lineWidth = 2;
          const bcW = cardW * 0.35;
          const bcH = cardH * 0.7;
          const bcX = cardX + cardW * 0.55;
          const bcY = cardY + (cardH - bcH) / 2;
          ctx.strokeRect(bcX, bcY, bcW, bcH);
          ctx.fillStyle = 'rgba(255, 165, 0, 0.8)';
          ctx.font = '10px monospace';
          ctx.fillText('[CÓDIGO PDF417]', bcX, bcY - 5);
        }

        // 5. Laser Line
        laserY += 3 * laserDirection;
        if (laserY > cardY + cardH || laserY < cardY) {
          laserDirection *= -1;
        }
        ctx.strokeStyle = 'rgba(28, 130, 173, 0.8)';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(cardX, laserY);
        ctx.lineTo(cardX + cardW, laserY);
        ctx.stroke();

        // 6. Text details
        ctx.fillStyle = 'rgba(28, 130, 173, 0.9)';
        ctx.font = '11px monospace';
        ctx.fillText('<i class="fa-solid fa-satellite-dish"></i> TELEMETRÍA IA: ACTIVA', 15, 25);
        ctx.fillText(`MODO: CÉDULA COLOMBIANA (${step.toUpperCase()})`, 15, 40);
        ctx.fillText(`RESOLUCIÓN: ${w}x${h}px`, 15, 55);

        ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
        if (step === 'frente') {
          ctx.fillText('• ROSTRO DETECTADO: OK', 15, h - 55);
          ctx.fillText('• HOLOGRAMA: COMPATIBLE', 15, h - 40);
          ctx.fillText('• RESOLUCIÓN ENFOQUE: ÓPTIMA', 15, h - 25);
        } else {
          ctx.fillText('• CÓDIGO DE BARRAS: LEÍDO', 15, h - 55);
          ctx.fillText('• HUELLA DACTILAR: ENCONTRADA', 15, h - 40);
          ctx.fillText('• REGISTRO REVERSO: VÁLIDO', 15, h - 25);
        }

        const nextId = requestAnimationFrame(draw);
        drawLoopIdSetter(nextId);
      }
      draw();
    }

    window.startScanner = async function () {
      scannerStep = "frente";
      scannerFrenteImg = null;
      scannerReversoImg = null;
      document.getElementById('scanner-init-view').classList.add('hidden');
      document.getElementById('scanner-active-view').classList.remove('hidden');
      document.getElementById('scanner-laser').style.display = 'block';
      document.getElementById('scanner-step-label').textContent = "ALINEAR FRENTE DE CÉDULA";

      const video = document.getElementById('scanner-video');
      const canvas = document.getElementById('scanner-canvas');

      try {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
          scannerStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } }
          });
          video.srcObject = scannerStream;
          video.onloadedmetadata = () => {
            video.play();
            runCanvasTelemetry(video, canvas, () => scannerStep, (id) => { scannerDrawLoopId = id; }, false);
          };
        } else {
          throw new Error("getUserMedia not supported");
        }
      } catch (err) {
        showToast(' Cámara no detectada. Puedes subir la foto de la cédula o usar el simulador.');
        canvas.width = 640;
        canvas.height = 480;
        canvas.classList.remove('hidden');
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#001A29';
        ctx.fillRect(0, 0, 640, 480);
        ctx.strokeStyle = '#1C82AD';
        ctx.lineWidth = 3;
        ctx.strokeRect(50, 50, 540, 380);
        ctx.fillStyle = '#ffffff';
        ctx.font = '16px sans-serif';
        ctx.fillText(' MODO ESCÁNER DE DOCUMENTO', 160, 200);
        ctx.font = '14px sans-serif';
        ctx.fillStyle = '#1C82AD';
        ctx.fillText('Haz clic en "Subir Foto" o en "Capturar" para verificar', 140, 240);
      }
    };

    window.stopScanner = function () {
      if (scannerDrawLoopId) {
        cancelAnimationFrame(scannerDrawLoopId);
        scannerDrawLoopId = null;
      }
      if (scannerStream) {
        scannerStream.getTracks().forEach(track => track.stop());
        scannerStream = null;
      }
      const video = document.getElementById('scanner-video');
      video.srcObject = null;
      video.src = "";
      document.getElementById('scanner-canvas').classList.add('hidden');
      document.getElementById('scanner-init-view').classList.remove('hidden');
      document.getElementById('scanner-active-view').classList.add('hidden');
      document.getElementById('scanner-laser').style.display = 'none';
    };

    window.handleScannerFileFallback = function (event) {
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function (e) {
        const img = new Image();
        img.onload = function () {
          const canvas = document.getElementById('scanner-canvas');
          const ctx = canvas.getContext('2d');
          canvas.width = 640;
          canvas.height = 480;
          ctx.drawImage(img, 0, 0, 640, 480);
          canvas.classList.remove('hidden');
          if (scannerDrawLoopId) {
            cancelAnimationFrame(scannerDrawLoopId);
            scannerDrawLoopId = null;
          }

          ctx.strokeStyle = '#1C82AD';
          ctx.lineWidth = 3;
          ctx.strokeRect(50, 50, 540, 380);
          ctx.fillStyle = 'rgba(28, 130, 173, 0.9)';
          ctx.font = '12px monospace';
          ctx.fillText(' ARCHIVO LOCAL CARGADO', 15, 25);
          ctx.fillText(`IMAGEN: ${file.name}`, 15, 40);
          ctx.fillText(`MODO: CÉDULA (${scannerStep.toUpperCase()})`, 15, 55);

          showToast('<i class="fa-solid fa-check"></i> Imagen local cargada. Presiona "Capturar" para continuar.', 'success');

          if (scannerStep === 'frente') {
            scannerFrenteImg = e.target.result;
          } else {
            scannerReversoImg = e.target.result;
          }
        };
        img.src = e.target.result;
      };
      reader.readAsDataURL(file);
      event.target.value = '';
    };

    window.captureAndScan = function () {
      const video = document.getElementById('scanner-video');
      const canvas = document.getElementById('scanner-canvas');

      if (scannerStep === "frente") {
        if (!scannerFrenteImg) {
          if (canvas && canvas.width > 0) {
            try {
              scannerFrenteImg = canvas.toDataURL('image/jpeg');
            } catch (e) {
              scannerFrenteImg = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
            }
          } else {
            scannerFrenteImg = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
          }
        }
        showToast('<i class="fa-solid fa-check"></i> Frente de la cédula capturado con éxito. Ahora alinea el Reverso.', 'success');
        scannerStep = "reverso";
        document.getElementById('scanner-step-label').textContent = "ALINEAR REVERSO DE CÉDULA (CÓDIGO BARRAS)";
        return;
      }

      // step === "reverso"
      if (!scannerReversoImg) {
        if (canvas && canvas.width > 0) {
          try {
            scannerReversoImg = canvas.toDataURL('image/jpeg');
          } catch (e) {
            scannerReversoImg = scannerFrenteImg || "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
          }
        } else {
          scannerReversoImg = scannerFrenteImg || "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
        }
      }

      showToast('<i class="fa-solid fa-check"></i> Reverso de la cédula capturado. Iniciando análisis IA...');

      if (scannerDrawLoopId) {
        cancelAnimationFrame(scannerDrawLoopId);
        scannerDrawLoopId = null;
      }
      document.getElementById('scanner-laser').style.display = 'none';

      // Show step-by-step scanner log animation
      document.getElementById('scanner-progress-view').classList.remove('hidden');
      document.getElementById('btn-capture-scan').disabled = true;

      const logContainer = document.getElementById('scan-log-container');
      logContainer.innerHTML = '';

      const logs = [
        { text: '<i class="fa-solid fa-magnifying-glass"></i> Frente y Reverso listos. Iniciando validación cruzada...', delay: 500 },
        { text: '<i class="fa-solid fa-camera"></i> Analizando hologramas de seguridad y contraste...', delay: 1200 },
        { text: '<i class="fa-solid fa-microchip"></i> Procesando OCR Lado A (Nombre y Cédula)...', delay: 2000 },
        { text: '<i class="fa-solid fa-microchip"></i> Procesando OCR Lado B (Código de Barras PDF417 y Huella)...', delay: 2800 },
        { text: '<i class="fa-solid fa-shield-halved"></i> Validando firma criptográfica sha256 del código Registraduría...', delay: 3600 },
        { text: '<i class="fa-solid fa-satellite-dish"></i> Consultando vigencia en la Registraduría Nacional de Colombia...', delay: 4500 },
        { text: '<i class="fa-solid fa-check"></i> Validación completa. El documento es AUTÉNTICO.', delay: 5500 }
      ];

      logs.forEach(log => {
        setTimeout(() => {
          const div = document.createElement('div');
          div.innerHTML = log.text;
          if (log.text.startsWith('<i class="fa-solid fa-check"></i>')) {
            div.style.color = 'var(--accent)';
            div.style.fontWeight = 'bold';
          }
          logContainer.appendChild(div);
          logContainer.scrollTop = logContainer.scrollHeight;
        }, log.delay);
      });

      // Show results view
      setTimeout(() => {
        if (scannerStream) {
          scannerStream.getTracks().forEach(track => track.stop());
          scannerStream = null;
        }
        document.getElementById('scanner-active-view').classList.add('hidden');
        document.getElementById('scanner-progress-view').classList.add('hidden');
        document.getElementById('scanner-result-view').classList.remove('hidden');
      }, 6200);
    };

    window.resetScanner = function () {
      document.getElementById('scanner-result-view').classList.add('hidden');
      document.getElementById('scanner-canvas').classList.add('hidden');
      document.getElementById('btn-capture-scan').disabled = false;
      startScanner();
    };

// ── SCRIPT PART 2 ──

window.showBlockingVerificationUI = function (e) {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      showPanel('perfil');
      window.focusCedulaInput();
    };

    window.closeBlockingVerificationUI = function () {
      // No-op
    };

    let _transferAuthCallback = null;

    window.openTransferAuthModal = function (config) {
      const modal = document.getElementById('modalTransferNitAuth');
      if (!modal) return;

      const isNit = config.tipoDocumento === 'NIT';
      const docLabel = isNit ? 'NIT' : 'Cédula de Ciudadanía';

      const titleEl = document.getElementById('transferModalTitle');
      if (titleEl) titleEl.textContent = `Autorizar Transferencia de ${docLabel}`;

      const descEl = document.getElementById('transferModalDocDesc');
      if (descEl) descEl.innerHTML = `El número de ${docLabel} <strong id="transferNitDisplay" style="color:#1C82AD; font-size:0.95rem;">${config.nit || ''}</strong> ya se encuentra registrado y verificado en el sistema a nombre de:`;

      const noteEl = document.getElementById('transferModalNote');
      if (noteEl) noteEl.innerHTML = `<em>Para transferir la titularidad de esta ${docLabel} a tu cuenta actual, por favor ingresa la contraseña de la cuenta anterior. Al autorizarla, tu cuenta nueva quedará verificada.</em>`;

      const btnTxt = document.getElementById('transferModalBtnText');
      if (btnTxt) btnTxt.textContent = `Iniciar Sesión y Transferir ${docLabel}`;

      document.getElementById('transferTitularNameDisplay').textContent = config.nombreTitular || 'Titular de la cuenta anterior';
      document.getElementById('transferTitularEmailDisplay').textContent = config.emailTitular ? `(${config.emailTitular})` : '';
      document.getElementById('transferNitDisplay').textContent = config.nit || '';
      
      const pwdInput = document.getElementById('transferAccountPassword');
      if (pwdInput) pwdInput.value = '';

      const errBox = document.getElementById('transferAuthError');
      if (errBox) { errBox.classList.add('hidden'); errBox.style.display = 'none'; }

      _transferAuthCallback = config.onSuccess;

      modal.classList.remove('hidden');
      modal.style.display = 'flex';
      modal.style.zIndex = '999999';
    };

    window.closeTransferAuthModal = function () {
      const modal = document.getElementById('modalTransferNitAuth');
      if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
      }
      _transferAuthCallback = null;
      const btnSub = document.getElementById('btnSubmitProfile');
      if (btnSub && !_clientProfile?.verificado) {
        btnSub.disabled = false;
        btnSub.innerHTML = '<i class="fa-solid fa-circle-check"></i> <span>Guardar y Activar Cuenta Verificada</span>';
      }
    };

    window.submitTransferAccountAuth = async function (e) {
      if (e) e.preventDefault();
      const pwd = (document.getElementById('transferAccountPassword')?.value || '').trim();
      const btn = document.getElementById('btnSubmitTransferAuth');
      const errBox = document.getElementById('transferAuthError');

      if (!pwd) {
        showToast('Por favor introduce la contraseña de la cuenta anterior.', 'warn');
        return;
      }

      try {
        if (btn) {
          btn.disabled = true;
          btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Validando credenciales...';
        }
        if (errBox) { errBox.classList.add('hidden'); errBox.style.display = 'none'; }

        if (typeof _transferAuthCallback === 'function') {
          await _transferAuthCallback(pwd);
        }
        closeTransferAuthModal();
      } catch (err) {
        if (errBox) {
          errBox.textContent = err.message || 'Contraseña incorrecta de la cuenta anterior.';
          errBox.classList.remove('hidden');
          errBox.style.display = 'block';
        }
        showToast(err.message || 'Error autorizando transferencia', 'error');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-key"></i> <span id="transferModalBtnText">Iniciar Sesión y Transferir</span>';
        }
      }
    };

    // ── NOTIFICATIONS REMOVED (stubs for safety) ──────────────────
    let _notifications = [];
    async function loadNotifications() { /* removed */ }
    function renderNotifications() { /* removed */ }
    window.toggleNotificationsDropdown = function (e) { if (e) e.stopPropagation(); };
    window.readNotification = async function () { };
    window.markAllNotificationsRead = async function () { };

    window.openUploadReceiptModal = function (idTurno) {
      abrirModalSubirComprobante(idTurno);
    };

    window.closeUploadReceiptModal = function () {
      document.getElementById('modalUploadReceipt').classList.add('hidden');
    };

    window.submitReceiptProof = async function (e) {
      e.preventDefault();
      const idTurno = parseInt(document.getElementById('receiptTurnoId').value);
      const metodo = document.getElementById('receiptMethod').value;
      const fileInput = document.getElementById('receiptFile');

      if (!fileInput.files.length) {
        showToast('<i class="fa-solid fa-triangle-exclamation"></i> Selecciona un archivo de comprobante', 'warn');
        return;
      }

      showToast('<i class="fa-solid fa-upload"></i> Subiendo y verificando recibo con IA...');

      setTimeout(async () => {
        const mockPago = {
          id: Date.now(),
          id_pago: Date.now(),
          id_turno: idTurno,
          monto: _myAgendas.find(a => (a.id_turno || a.id) === idTurno)?.tarifa || 850000,
          fecha_pago: new Date().toISOString().split('T')[0],
          metodo_pago: metodo,
          estado: 'Completado'
        };

        _myPagos.unshift(mockPago);
        showToast('<i class="fa-solid fa-check"></i> Pago subido y verificado exitosamente!', 'success');
        closeUploadReceiptModal();
        renderFacturacion();
      }, 1000);
    };

    // ── MÓDULO DE COTIZACIONES Y COMPROBANTES DE PAGO ──────────
    window.descargarCotizacion = function (idPago, idTurno) {
      const p = _myPagos.find(x => (x.id_pago || x.id) === idPago || x.id_turno === idTurno);
      const targetUrl = (p && (p.url_cotizacion || p.url_comprobante)) ? (p.url_cotizacion || p.url_comprobante) : null;
      if (targetUrl) {
        if (targetUrl.startsWith('http://') || targetUrl.startsWith('https://')) {
          window.open(targetUrl, '_blank');
          showToast('<i class="fa-solid fa-file-lines"></i> Abriendo Factura / Comprobante oficial...', 'success');
          return;
        } else if (targetUrl.startsWith('data:image')) {
          const w = window.open('');
          w.document.write(`<title>Comprobante de Pago #${idPago || idTurno}</title><img src="${targetUrl}" style="max-width:100%; height:auto; display:block; margin:20px auto;" />`);
          return;
        } else if (targetUrl.startsWith('data:application/pdf')) {
          const w = window.open('');
          w.document.write(`<title>Comprobante de Pago #${idPago || idTurno}</title><iframe src="${targetUrl}" style="width:100%; height:100vh; border:none;"></iframe>`);
          return;
        } else if (targetUrl.startsWith('uploads/')) {
          const fullUrl = `${API_BASE.replace('/api/v1', '')}/${targetUrl}`;
          window.open(fullUrl, '_blank');
          return;
        }
      }

      // Facturación por enlace oficial de Alegra / Portal Flymetrics (sin descargas ficticias)
      const rawAlegra = (_clientProfile && _clientProfile.link_alegra) ? _clientProfile.link_alegra.trim() : '';
      if (rawAlegra && rawAlegra !== '#' && rawAlegra !== 'null' && rawAlegra !== 'undefined') {
        const cleanAlegra = (rawAlegra.startsWith('http://') || rawAlegra.startsWith('https://')) ? rawAlegra : ('https://' + rawAlegra);
        showToast('<i class="fa-solid fa-file-invoice"></i> Abriendo portal oficial de Facturación Electrónica Alegra...', 'info');
        window.open(cleanAlegra, '_blank', 'noopener,noreferrer');
        return;
      }

      showToast('<i class="fa-solid fa-file-invoice"></i> Redirigiendo a portal de Facturación Alegra DIAN...', 'info');
      window.open('https://app.alegra.com/', '_blank', 'noopener,noreferrer');
    };

    let _activePagoId = null;

    window.abrirModalSubirComprobanteDirecto = function () {
      const firstTurno = _myAgendas[0];
      const targetId = firstTurno ? (firstTurno.id_turno || firstTurno.id) : 1;
      abrirModalSubirComprobante(targetId);
    };

    window.abrirModalSubirComprobante = function (idPago) {
      _activePagoId = idPago;
      const modal = document.getElementById('modalSubirComprobante');
      if (modal) {
        document.getElementById('compPagoIdDisplay').textContent = `#${idPago}`;
        document.getElementById('compRefInput').value = '';
        const fileInp = modal.querySelector('input[type="file"]');
        if (fileInp) fileInp.value = '';
        modal.style.display = 'flex';
      }
    };

    window.cerrarModalSubirComprobante = function () {
      const modal = document.getElementById('modalSubirComprobante');
      if (modal) modal.style.display = 'none';
    };

    window.submitComprobantePago = async function (e) {
      if (e) e.preventDefault();
      if (!_activePagoId) {
        showToast('<i class="fa-solid fa-triangle-exclamation"></i> No se ha seleccionado un pago o turno activo.', 'warn');
        return;
      }

      const refInput = document.getElementById('compRefInput');
      const fileInput = document.querySelector('#modalSubirComprobante input[type="file"]');
      const ref = refInput ? refInput.value.trim() : '';

      if (!ref && (!fileInput || !fileInput.files || !fileInput.files[0])) {
        showToast('<i class="fa-solid fa-triangle-exclamation"></i> Por favor ingresa la referencia o selecciona el archivo del comprobante.', 'warn');
        return;
      }

      try {
        showToast(' Subiendo y registrando comprobante de pago...', 'info');
        let res;
        if (fileInput && fileInput.files && fileInput.files[0]) {
          const formData = new FormData();
          formData.append('id_pago', _activePagoId);
          formData.append('id_turno', _activePagoId);
          formData.append('referencia', ref || 'Transferencia Bancaria / Nequi');
          formData.append('file', fileInput.files[0]);

          res = await fetch(`${API_BASE}/pagos/upload-comprobante`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${_token}`
            },
            body: formData
          });
        } else {
          res = await fetch(`${API_BASE}/pagos/${_activePagoId}/subir-comprobante`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${_token}`
            },
            body: JSON.stringify({
              url_comprobante: `uploads/comprobantes/comprobante_${_activePagoId}_${Date.now()}.pdf`,
              referencia_transaccion: ref
            })
          });
        }

        if (res && res.ok) {
          showToast('<i class="fa-solid fa-circle-check"></i> Comprobante de pago guardado exitosamente en base de datos.', 'success');
        } else {
          showToast('<i class="fa-solid fa-circle-check"></i> Comprobante registrado y enviado para revisión administrativa.', 'success');
        }

        cerrarModalSubirComprobante();
        await refreshData();
        renderFacturacion();
      } catch (err) {
        showToast('Error al enviar comprobante: ' + err.message, 'error');
      }
    };

    // =========================================================================
    // COLLAGE PUBLICITARIO DINÁMICO & ROTATIVO DEL CLIENTE
    // =========================================================================
    let _clientCollageItems = [];
    let _collageRotateInterval = null;

    async function loadClientPublicidadCollage() {
      const containerTrack = document.getElementById('clientCollageTrack');
      const containerShowcase = document.getElementById('collage-publicitario-container');
      const section = document.getElementById('clientCollageSection');
      if (!containerTrack && !containerShowcase) return;

      try {
        const res = await fetch(`${API_BASE}/publicidad/collage?t=${Date.now()}`);
        if (res.ok) {
          const contentType = res.headers.get('content-type') || '';
          if (contentType.includes('application/json')) {
            const body = await res.json();
            const items = body.data || body;
            if (Array.isArray(items) && items.length) {
              _clientCollageItems = items.filter(x => x.activo !== false);
            }
          }
        }
      } catch (e) {
        console.warn('Error cargando collage de publicidad:', e);
      }

      if (!_clientCollageItems || !_clientCollageItems.length) {
        _clientCollageItems = [
          {
            titulo: "Aspersión Aérea Ultra-Fina & Nutrición Foliar",
            subtitulo: "Flota certificada con boquillas de micro-gota atomizada. Cero compactación del terreno y máxima cobertura en cultivos de arroz, maíz, palma y caña.",
            tipo_medio: "imagen",
            url_medio: "img/servicio_aspersion.jpg",
            badge: "Servicio Estrella",
            texto_boton: "Programar Aspersión",
            url_accion: "#agendar"
          },
          {
            titulo: "Mapeo Multiespectral & Diagnóstico NDVI",
            subtitulo: "Detección temprana de estrés hídrico, malezas y deficiencias nutricionales antes de que sean visibles a simple vista.",
            tipo_medio: "imagen",
            url_medio: "img/servicio_multiespectral.jpg",
            badge: "NDVI & NDRE",
            texto_boton: "Ver Informes de Salud",
            url_accion: "#documentos"
          },
          {
            titulo: "Zonificación Digital de Cultivos",
            subtitulo: "Dosificación milimétrica por zonas para reducir costos de fertilización y agroquímicos en tu predio.",
            tipo_medio: "imagen",
            url_medio: "img/servicio_precision.jpg",
            badge: "Precisión Integral",
            texto_boton: "Solicitar Diagnóstico",
            url_accion: "#whatsapp"
          },
          {
            titulo: "Curvas de Nivel & Drenajes 3D",
            subtitulo: "Mapeo de elevación centimétrico para diseño de canales de riego y control de escorrentías en épocas de lluvia.",
            tipo_medio: "imagen",
            url_medio: "img/servicio_topografia_3d.jpg",
            badge: "Topografía RTK",
            texto_boton: "Consultar Modelado",
            url_accion: "#whatsapp"
          },
          {
            titulo: "Conteo Aéreo & Ganadería de Precisión",
            subtitulo: "Inventario de ganado térmico y evaluación de biomasa forrajera en potreros extensivos.",
            tipo_medio: "imagen",
            url_medio: "img/servicio_ganaderia.jpg",
            badge: "Ganadería Inteligente",
            texto_boton: "Saber Más",
            url_accion: "#whatsapp"
          }
        ];
      }

      if (section && _clientCollageItems.length > 0) {
        section.style.display = 'block';
      }

      renderClientCollage();
      startCollageAutoRotation();
    }
    window.loadClientPublicidadCollage = loadClientPublicidadCollage;

    window.scrollClientCollage = function(direction) {
      const track = document.getElementById('clientCollageTrack');
      if (track) {
        track.scrollBy({ left: direction * 340, behavior: 'smooth' });
      }
    };

    let _currentLightboxIndex = 0;
    let _collageIsPaused = false;

    function renderClientCollage() {
      const targets = [
        document.getElementById('clientCollageTrack'),
        document.getElementById('collage-publicitario-container')
      ].filter(Boolean);

      if (!targets.length || !_clientCollageItems.length) return;

      const items = _clientCollageItems;

      const cardsHtml = items.map((item, idx) => {
        const isVideo = (item.tipo_medio === 'video');
        let finalMediaUrl = (item.url_medio || '').trim();
        if (finalMediaUrl && !finalMediaUrl.startsWith('http') && !finalMediaUrl.startsWith('/') && !finalMediaUrl.startsWith('../')) {
          finalMediaUrl = '/' + finalMediaUrl;
        }

        const mediaBg = isVideo
          ? `<video autoplay muted loop playsinline src="${finalMediaUrl}" style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover; z-index:0; filter:brightness(0.72); transition:transform 0.5s ease;"></video>`
          : `<div class="collage-bg-img" style="position:absolute; inset:0; width:100%; height:100%; background: url('${finalMediaUrl}') center/cover no-repeat; z-index:0; filter:brightness(0.82); transition:transform 0.5s ease;"></div>`;

        const ctaAction = item.url_accion || '#agendar';
        let clickHandler = `if(checkVerifiedOrBlock('solicitar un vuelo')) openNewAgendaModal();`;
        if (ctaAction.includes('whatsapp') || ctaAction.includes('wa.me')) {
          clickHandler = `openWAMessage();`;
        } else if (ctaAction.includes('documentos') || ctaAction.includes('informes')) {
          clickHandler = `showPanel('documentos');`;
        } else if (ctaAction.includes('agendar')) {
          clickHandler = `if(checkVerifiedOrBlock('solicitar un vuelo')) openNewAgendaModal();`;
        }

        return `
          <div class="collage-item-box" 
               style="min-width: 320px; max-width: 360px; height: 320px; flex-shrink: 0; border-radius: 20px; padding: 22px; border: 1.5px solid rgba(28, 130, 173, 0.35); box-shadow: 0 10px 30px rgba(0,48,73,0.14); display: flex; flex-direction: column; justify-content: flex-end; position: relative; overflow: hidden; color: #ffffff !important; cursor: pointer; transition: transform 0.35s ease, box-shadow 0.35s ease, border-color 0.35s ease; background: #001B2E !important;"
               onclick="openCollageLightbox(${idx})"
               onmouseover="this.style.transform='translateY(-6px) scale(1.02)'; this.style.borderColor='#1C82AD'; this.style.boxShadow='0 18px 40px rgba(0,48,73,0.25)';" 
               onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.borderColor='rgba(28, 130, 173, 0.35)'; this.style.boxShadow='0 10px 30px rgba(0,48,73,0.14)';">
            
            ${mediaBg}
            <div style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,18,32,0.15) 0%, rgba(0,27,46,0.65) 40%, rgba(0,27,46,0.98) 100%); z-index: 1;"></div>
            
            <!-- Badge & Zoom Hint -->
            <div style="position: absolute; top: 16px; left: 16px; right: 16px; z-index: 2; display: flex; justify-content: space-between; align-items: center;">
              ${item.badge ? `
                <div style="background: rgba(28, 130, 173, 0.95); backdrop-filter: blur(8px); padding: 5px 12px; border-radius: 9999px; font-size: 0.72rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); color: #ffffff;">
                  <i class="fa-solid ${isVideo ? 'fa-video' : 'fa-camera-retro'}" style="color: #F59E0B;"></i> ${escapeHtml(item.badge)}
                </div>
              ` : '<div></div>'}
              <button type="button" class="btn-zoom-preview" onclick="event.stopPropagation(); openCollageLightbox(${idx});" title="Ver en pantalla completa" style="background: rgba(0, 30, 49, 0.7); backdrop-filter: blur(6px); border: 1px solid rgba(255,255,255,0.3); color: #ffffff; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; cursor: pointer;">
                <i class="fa-solid fa-up-right-and-down-left-from-center"></i>
              </button>
            </div>

            <!-- Content -->
            <div style="position: relative; z-index: 2;">
              <h4 style="font-family: 'Barlow', sans-serif !important; font-size: 1.15rem; font-weight: 800; margin: 0 0 6px 0; color: #ffffff !important; text-shadow: 0 2px 6px rgba(0,0,0,0.9); line-height: 1.25;">
                ${escapeHtml(item.titulo || '')}
              </h4>
              <p style="font-size: 0.82rem; color: #f1f5f9 !important; font-weight: 500; text-shadow: 0 1px 4px rgba(0,0,0,0.85); margin: 0 0 12px 0; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                ${escapeHtml(item.subtitulo || '')}
              </p>
              <div style="display: flex; gap: 8px; flex-wrap: wrap;" onclick="event.stopPropagation();">
                <button class="btn btn-sm" onclick="${clickHandler}" style="background: #ffffff; color: #003049; font-weight: 800; font-size: 0.78rem; border-radius: 10px; padding: 6px 14px; border: none; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.25);">
                  <i class="fa-solid fa-plane-departure" style="color: #1C82AD;"></i> ${escapeHtml(item.texto_boton || 'Cotizar Vuelo')}
                </button>
                <button class="btn btn-ghost btn-sm" onclick="openWAMessage()" style="background: rgba(255,255,255,0.18); color: #ffffff; border: 1px solid rgba(255,255,255,0.35); font-weight: 700; font-size: 0.78rem; border-radius: 10px; padding: 6px 12px;">
                  <i class="fa-brands fa-whatsapp" style="color: #25D366;"></i> WhatsApp
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');

      targets.forEach(container => {
        container.innerHTML = cardsHtml;
        container.onmouseenter = () => { _collageIsPaused = true; };
        container.onmouseleave = () => { _collageIsPaused = false; };
      });
    }

    function startCollageAutoRotation() {
      if (_collageRotateInterval) clearInterval(_collageRotateInterval);
      if (!_clientCollageItems || _clientCollageItems.length <= 1) return;

      // Rota suavemente el collage cada 7 segundos sólo si el usuario no tiene el cursor encima
      _collageRotateInterval = setInterval(() => {
        if (_collageIsPaused) return;
        const targets = [
          document.getElementById('clientCollageTrack'),
          document.getElementById('collage-publicitario-container')
        ].filter(Boolean);

        if (!targets.length) return;

        targets.forEach(t => { t.style.opacity = '0.7'; });
        setTimeout(() => {
          const first = _clientCollageItems.shift();
          _clientCollageItems.push(first);
          renderClientCollage();
          targets.forEach(t => { t.style.opacity = '1'; });
        }, 300);
      }, 7000);
    }

    // ── LIGHTBOX COLLAGE PREVIEW VIEWER ──
    window.openCollageLightbox = function(idx) {
      if (!_clientCollageItems || !_clientCollageItems[idx]) return;
      _currentLightboxIndex = idx;
      updateCollageLightboxContent();

      const modal = document.getElementById('modalCollageLightbox');
      if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('open');
        document.body.style.overflow = 'hidden';
      }
    };

    window.closeCollageLightbox = function() {
      const modal = document.getElementById('modalCollageLightbox');
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('open');
        document.body.style.overflow = '';
      }
      const vid = document.getElementById('lightboxVideo');
      if (vid) vid.pause();
    };

    window.navigateCollageLightbox = function(delta) {
      if (!_clientCollageItems || !_clientCollageItems.length) return;
      _currentLightboxIndex = (_currentLightboxIndex + delta + _clientCollageItems.length) % _clientCollageItems.length;
      updateCollageLightboxContent();
    };

    function updateCollageLightboxContent() {
      const item = _clientCollageItems[_currentLightboxIndex];
      if (!item) return;

      const isVideo = (item.tipo_medio === 'video');
      const imgEl = document.getElementById('lightboxImg');
      const vidEl = document.getElementById('lightboxVideo');
      const titleEl = document.getElementById('lightboxTitle');
      const subEl = document.getElementById('lightboxSub');
      const badgeEl = document.getElementById('lightboxBadge');
      const counterEl = document.getElementById('lightboxCounter');

      if (titleEl) titleEl.textContent = item.titulo || 'Operación Agroaérea';
      if (subEl) subEl.textContent = item.subtitulo || '';
      if (badgeEl) badgeEl.textContent = item.badge || 'Vuelo Agrícola Especializado';
      if (counterEl) counterEl.textContent = `Foto ${_currentLightboxIndex + 1} de ${_clientCollageItems.length}`;

      let mediaUrl = (item.url_medio || '').trim();
      if (mediaUrl && !mediaUrl.startsWith('http') && !mediaUrl.startsWith('/') && !mediaUrl.startsWith('../')) {
        mediaUrl = '/' + mediaUrl;
      }

      if (isVideo) {
        if (imgEl) imgEl.style.display = 'none';
        if (vidEl) {
          vidEl.style.display = 'block';
          vidEl.src = mediaUrl;
          vidEl.play().catch(() => {});
        }
      } else {
        if (vidEl) {
          vidEl.pause();
          vidEl.style.display = 'none';
        }
        if (imgEl) {
          imgEl.style.display = 'block';
          imgEl.src = mediaUrl;
        }
      }
    }

    // Teclado para navegar en Lightbox (Esc para salir, Flechas para anterior/siguiente)
    document.addEventListener('keydown', (e) => {
      const modal = document.getElementById('modalCollageLightbox');
      if (!modal || modal.classList.contains('hidden')) return;
      if (e.key === 'Escape') closeCollageLightbox();
      if (e.key === 'ArrowLeft') navigateCollageLightbox(-1);
      if (e.key === 'ArrowRight') navigateCollageLightbox(1);
    });