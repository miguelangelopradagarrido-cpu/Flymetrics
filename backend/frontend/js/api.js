(function(global) {
  'use strict';

  var _loc = global.location || {};
  var _hostname = _loc.hostname || '';
  var _port = _loc.port || '';
  var _protocol = _loc.protocol || '';
  var _origin = _loc.origin || '';

  // Determinar si estamos en dev server local (ej: Live Server en 5500, Vite en 5173, etc.)
  var isDevPort = (_hostname === 'localhost' || _hostname === '127.0.0.1') && _port && _port !== '3000';
  
  // Soporte universal para túneles (ngrok, trycloudflare, locales y producción):
  // Si está en un túnel público o puerto 3000 o servidor de producción, el backend está en el mismo origin.
  // Si está en LiveServer o protocolo file://, apunta a http://localhost:3000
  // Soporte unificado: Si el backend sirve el frontend, _origin es exactamente la API (sin problemas de CORS)
  var isStaticFrontend = _hostname.includes('flymetrics.hostless.site') || _hostname.includes('flymetrics.com.co') || _hostname.includes('github.io');
  var isLocal = (_protocol === 'file:' || isDevPort);
  
  var apiBase = global.API_BASE || (isLocal
    ? 'http://localhost:3000'
    : (isStaticFrontend ? 'https://flymetrics-api.hostless.app' : (_origin || 'https://flymetrics-api.hostless.app')));

  var baseUrl = (apiBase.replace(/\/+$/, '').replace(/\/api\/v1\/?$/, '')) + '/api/v1';

  var API = {
    async login(email, password) {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const res = await fetch(`${baseUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });
      
      if (!res.ok) {
        let errorMsg = 'Credenciales inválidas';
        try {
          const errData = await res.json();
          errorMsg = errData.message || errorMsg;
          if (errData.errors && errData.errors.length > 0) {
            errorMsg = errData.errors.join(', ');
          }
        } catch (e) {}
        throw new Error(errorMsg);
      }
      return await res.json();
    },

    async register(name, email, password, role = 'cliente', phone = null) {
      const parts = (name || '').trim().split(/\s+/);
      let nombre = 'Cliente';
      let apellido_1 = '';

      if (parts.length === 1) {
        nombre = parts[0];
      } else if (parts.length === 2) {
        nombre = parts[0];
        apellido_1 = parts[1];
      } else if (parts.length >= 3) {
        const mid = Math.ceil(parts.length / 2);
        nombre = parts.slice(0, mid).join(' ');
        apellido_1 = parts.slice(mid).join(' ');
      }

      const payload = {
        email: email,
        contraseña: password,
        rol: role,
        nombre: nombre,
        apellido_1: apellido_1
      };
      if (phone) payload.telefono = phone;

      const res = await fetch(`${baseUrl}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) {
        let errorMsg = 'Error al registrar usuario';
        try {
          const errData = await res.json();
          errorMsg = errData.message || errorMsg;
          if (errData.errors && errData.errors.length > 0) {
            errorMsg = errData.errors.join(', ');
          }
        } catch (e) {}
        throw new Error(errorMsg);
      }
      return await res.json();
    },

    async loginGoogle(token) {
      const res = await fetch(`${baseUrl}/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
      });
      
      if (!res.ok) {
        let errorMsg = 'Error al iniciar sesión con Google';
        try {
          const errData = await res.json();
          errorMsg = errData.message || errorMsg;
        } catch (e) {}
        throw new Error(errorMsg);
      }
      return await res.json();
    },

    async completarPerfilGoogle(data, token) {
      const jwt = token || this.getToken();
      const res = await fetch(`${baseUrl}/auth/google-completar-perfil`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${jwt}`
        },
        body: JSON.stringify(data)
      });

      if (!res.ok) {
        let errorMsg = 'Error al completar el perfil';
        try {
          const errData = await res.json();
          errorMsg = errData.message || errorMsg;
        } catch (e) {}
        throw new Error(errorMsg);
      }
      return await res.json();
    },

    async getMe(token) {
      const res = await fetch(`${baseUrl}/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Sesión expirada');
      return await res.json();
    },

    setToken(token) {
      if (token) {
        try { localStorage.setItem('fm_token', token); } catch(e) {}
        try { sessionStorage.setItem('fm_token', token); } catch(e) {}
      } else {
        try { localStorage.removeItem('fm_token'); } catch(e) {}
        try { sessionStorage.removeItem('fm_token'); } catch(e) {}
      }
    },

    getToken() {
      return localStorage.getItem('fm_token') || sessionStorage.getItem('fm_token');
    },

    async logout() {
      try {
        await fetch(`${baseUrl}/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => null);
      } catch(e) {}
      try {
        localStorage.clear();
      } catch(e) {
        try {
          localStorage.removeItem('fm_token');
          localStorage.removeItem('fm_user');
          localStorage.removeItem('fm_role');
          localStorage.removeItem('fm_email');
          localStorage.removeItem('fm_cedula');
          localStorage.removeItem('fm_verified');
        } catch(_) {}
      }
      try {
        sessionStorage.clear();
      } catch(e) {}
      global.location.href = 'index.html';
    }
  };

  // Exposición global segura e incondicional en window
  global.API = API;
  global.API_BASE = apiBase;
  global.BASE_URL = baseUrl;
})(typeof window !== 'undefined' ? window : this);
