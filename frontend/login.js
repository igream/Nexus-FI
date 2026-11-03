// Pantalla de inicio de sesión y registro de Nexus FI (Anexo B del Avance 3)
(() => {
    const TOKEN_KEY = 'nexus_token';
    const CARRERA_KEY = 'nexus_carrera';
    const THEME_KEY = 'nexusfi-theme';

    const leer = k => { try { return localStorage.getItem(k); } catch { return null; } };
    const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };

    // Si ya hay sesión, directo al chat
    if (leer(TOKEN_KEY)) { location.replace('/'); return; }

    // ---- Tema (mismo que el resto de las páginas) ----
    function aplicarTema(tema) {
        const oscuro = tema === 'dark';
        document.documentElement.dataset.theme = oscuro ? 'dark' : 'light';
        document.querySelectorAll('.theme-toggle').forEach(b => {
            b.innerHTML = oscuro
                ? '<span aria-hidden="true">☀️</span><span class="tt-label">Modo claro</span>'
                : '<span aria-hidden="true">🌙</span><span class="tt-label">Modo oscuro</span>';
            b.setAttribute('aria-pressed', String(oscuro));
            b.setAttribute('aria-label', oscuro ? 'Activar modo claro' : 'Activar modo oscuro');
        });
    }
    aplicarTema(leer(THEME_KEY) || 'light');
    document.querySelectorAll('.theme-toggle').forEach(b => b.addEventListener('click', () => {
        const nuevo = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        aplicarTema(nuevo);
        guardar(THEME_KEY, nuevo);
    }));

    // ---- Pestañas ----
    const tabs = { login: document.getElementById('tab-login'), registro: document.getElementById('tab-registro') };
    const forms = { login: document.getElementById('form-login'), registro: document.getElementById('form-registro') };
    const msg = document.getElementById('auth-msg');

    function mostrar(texto, tipo = 'error') {
        msg.textContent = texto;
        msg.className = 'auth-msg ' + tipo;
        msg.hidden = !texto;
    }

    function activar(nombre) {
        for (const k of Object.keys(tabs)) {
            const activa = k === nombre;
            tabs[k].setAttribute('aria-selected', String(activa));
            forms[k].hidden = !activa;
        }
        mostrar('');
        forms[nombre].querySelector('input')?.focus();
    }
    tabs.login.addEventListener('click', () => activar('login'));
    tabs.registro.addEventListener('click', () => activar('registro'));

    // Mostrar / ocultar contraseña
    document.querySelectorAll('.pass-toggle').forEach(b => b.addEventListener('click', () => {
        const input = b.previousElementSibling;
        const ver = input.type === 'password';
        input.type = ver ? 'text' : 'password';
        b.setAttribute('aria-label', ver ? 'Ocultar contraseña' : 'Mostrar contraseña');
    }));

    // Solo dígitos en el número de cuenta
    document.querySelectorAll('input[inputmode="numeric"]').forEach(i =>
        i.addEventListener('input', () => { i.value = i.value.replace(/\D/g, '').slice(0, 7); }));

    async function enviar(url, cuerpo) {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cuerpo)
        });
        let data = {};
        try { data = await r.json(); } catch { /* respuesta sin JSON */ }
        const detalle = typeof data.detail === 'string' ? data.detail : 'Revisa los datos e inténtalo de nuevo.';
        return { status: r.status, data, detalle };
    }

    function ocupado(form, si) {
        const b = form.querySelector('button[type="submit"]');
        b.disabled = si;
        b.dataset.texto ??= b.textContent;
        b.textContent = si ? 'Un momento…' : b.dataset.texto;
    }

    // ---- Iniciar sesión ----
    forms.login.addEventListener('submit', async e => {
        e.preventDefault();
        const numero_cuenta = document.getElementById('login-cuenta').value.trim();
        const password = document.getElementById('login-pass').value;
        if (!/^\d{7}$/.test(numero_cuenta)) return mostrar('El número de cuenta debe tener 7 dígitos.');
        if (!password) return mostrar('Escribe tu contraseña.');

        ocupado(forms.login, true);
        try {
            const r = await enviar('/api/auth/login', { numero_cuenta, password });
            if (r.status === 200 && r.data.token) {
                guardar(TOKEN_KEY, r.data.token);
                guardar(CARRERA_KEY, r.data.carrera || '');
                location.replace('/');
                return;
            }
            mostrar(r.detalle);
        } catch {
            mostrar('No hay conexión con el servidor.');
        } finally {
            ocupado(forms.login, false);
        }
    });

    // ---- Registro ----
    forms.registro.addEventListener('submit', async e => {
        e.preventDefault();
        const carrera = document.getElementById('reg-carrera').value;
        const numero_cuenta = document.getElementById('reg-cuenta').value.trim();
        const password = document.getElementById('reg-pass').value;
        const confirmar = document.getElementById('reg-pass2').value;
        if (!/^\d{7}$/.test(numero_cuenta)) return mostrar('El número de cuenta debe tener 7 dígitos.');
        if (password.length < 8) return mostrar('La contraseña debe tener al menos 8 caracteres.');
        if (password !== confirmar) return mostrar('Las contraseñas no coinciden.');

        ocupado(forms.registro, true);
        try {
            const r = await enviar('/api/auth/registro', { carrera, numero_cuenta, password });
            if (r.status === 201) {
                forms.registro.reset();
                activar('login');
                document.getElementById('login-cuenta').value = numero_cuenta;
                document.getElementById('login-pass').focus();
                mostrar('Registro exitoso, ya puedes iniciar sesión.', 'ok');
                return;
            }
            mostrar(r.detalle);
        } catch {
            mostrar('No hay conexión con el servidor.');
        } finally {
            ocupado(forms.registro, false);
        }
    });
})();
