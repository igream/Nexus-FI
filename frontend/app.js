// =============================================================================
// SESIÓN DEL USUARIO (Anexo B del Avance 3)
// Sin token se va a /login. Cada petición a la API lleva el token; si la API
// responde 401 (sesión vencida o cerrada), se borra y se regresa a /login.
// =============================================================================
const TOKEN_KEY = 'nexus_token';
const CARRERA_KEY = 'nexus_carrera';

function getToken() {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

function borrarSesion() {
    try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(CARRERA_KEY);
    } catch { /* sin almacenamiento */ }
}

function irALogin() {
    borrarSesion();
    location.replace('/login');
}

if (!getToken()) {
    location.replace('/login');
    throw new Error('Sin sesión: redirigiendo a /login');
}

function getSecurityHeaders() {
    const headers = { "Content-Type": "application/json" };
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
}

async function cerrarSesion() {
    try {
        await fetch('/api/auth/logout', { method: 'POST', headers: getSecurityHeaders() });
    } catch { /* aunque falle, la sesión local se borra */ }
    irALogin();
}

const $ = s => document.querySelector(s);

/* ========================================
MODO OSCURO — NEXUS FI
Guarda la preferencia entre páginas
======================================== */

const THEME_STORAGE_KEY = 'nexusfi-theme';

function applyTheme(theme) {
const selectedTheme = theme === 'dark' ? 'dark' : 'light';


document.documentElement.dataset.theme = selectedTheme;

document.querySelectorAll('.theme-toggle').forEach(button => {
    const isDark = selectedTheme === 'dark';

    // Ícono + texto; en celular el CSS oculta el texto (.tt-label)
    button.innerHTML = isDark
        ? '<span aria-hidden="true">☀️</span><span class="tt-label">Modo claro</span>'
        : '<span aria-hidden="true">🌙</span><span class="tt-label">Modo oscuro</span>';
    button.setAttribute('aria-pressed', String(isDark));
    button.setAttribute(
        'aria-label',
        isDark ? 'Activar modo claro' : 'Activar modo oscuro'
    );
});

// Aviso para que las gráficas del tablero se redibujen con los colores del tema
document.dispatchEvent(new CustomEvent('nexus-theme', { detail: selectedTheme }));

}

function initializeTheme() {
let savedTheme = 'light';


try {
    savedTheme = localStorage.getItem(THEME_STORAGE_KEY) || 'light';
} catch (error) {
    console.warn('No fue posible leer la preferencia de tema.', error);
}

applyTheme(savedTheme);

document.querySelectorAll('.theme-toggle').forEach(button => {
    button.addEventListener('click', () => {
        const currentTheme =
            document.documentElement.dataset.theme || 'light';

        const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';

        applyTheme(nextTheme);

        try {
            localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
        } catch (error) {
            console.warn('No fue posible guardar la preferencia de tema.', error);
        }
    });
});


}

initializeTheme();

// Datos del usuario en sesión (nombre y carrera) e insignia de cuota
function iniciales(nombre) {
    const conectores = ['de', 'del', 'la', 'las', 'los', 'y'];
    const partes = (nombre || '').trim().split(/\s+/).filter(p => p && !conectores.includes(p.toLowerCase()));
    return ((partes[0]?.[0] || '') + (partes[1]?.[0] || '')).toUpperCase() || 'FI';
}

// Opciones de administrador en el menú lateral: usuarios registrados y reinicio de registro
function montarHerramientasAdmin() {
    const side = document.getElementById('sidebar');
    const abajo = side?.querySelector('.sidebottom');
    if (!side || !abajo || document.getElementById('admin-tools')) return;

    const caja = document.createElement('div');
    caja.id = 'admin-tools';
    caja.className = 'admin-tools';
    caja.setAttribute('data-admin-only', '');
    caja.innerHTML = '<p class="label">ADMINISTRACIÓN</p>' +
        '<button type="button" class="nav" id="btn-usuarios">👥 Usuarios registrados</button>';
    side.insertBefore(caja, abajo);

    const dlg = document.createElement('dialog');
    dlg.className = 'modal modal-usuarios';
    dlg.setAttribute('aria-labelledby', 'usuarios-titulo');
    dlg.innerHTML = `
      <div class="modal-body">
        <div class="modal-head">
          <h2 id="usuarios-titulo">Usuarios registrados</h2>
          <button type="button" class="side-close" id="usuarios-cerrar" aria-label="Cerrar">✕</button>
        </div>
        <p>Cuentas que ya crearon su contraseña. Si alguien se registró con una cuenta que no es suya, reinicia el registro: la contraseña se borra, sus sesiones se cierran y el dueño puede registrarse de nuevo.</p>
        <label for="usuarios-buscar">Buscar por número de cuenta o nombre</label>
        <input id="usuarios-buscar" type="search" autocomplete="off" placeholder="Escribe para filtrar">
        <div id="usuarios-msg" class="auth-msg" role="status" hidden></div>
        <ul id="usuarios-lista" class="user-list" aria-live="polite"></ul>
      </div>`;
    document.body.appendChild(dlg);

    const buscar = dlg.querySelector('#usuarios-buscar');
    const lista = dlg.querySelector('#usuarios-lista');
    const msg = dlg.querySelector('#usuarios-msg');
    let usuarios = [];

    const aviso = (t, tipo = 'ok') => { msg.textContent = t; msg.className = 'auth-msg ' + tipo; msg.hidden = !t; };
    const fecha = iso => {
        const d = new Date(iso);
        return isNaN(d) ? '' : d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' });
    };

    function pintarLista() {
        const q = buscar.value.trim().toLowerCase();
        const visibles = usuarios.filter(u => !q || u.numero_cuenta.includes(q) || u.nombre.toLowerCase().includes(q));
        lista.replaceChildren();
        if (!visibles.length) {
            const li = document.createElement('li');
            li.className = 'user-empty';
            li.textContent = usuarios.length ? 'Ninguna cuenta registrada coincide con la búsqueda.' : 'Todavía no hay cuentas registradas.';
            lista.append(li);
            return;
        }
        for (const u of visibles) {
            const li = document.createElement('li');
            li.className = 'user-row';

            const datos = document.createElement('div');
            datos.className = 'user-data';
            const nombre = document.createElement('b');
            nombre.textContent = u.nombre || 'Sin nombre';
            const det = document.createElement('small');
            det.textContent = `${u.numero_cuenta} · ${u.rol === 'admin' ? 'Admin' : 'Alumno'} · registrado ${fecha(u.registrado_en)}`;
            datos.append(nombre, det);

            const acciones = document.createElement('div');
            acciones.className = 'user-actions';
            if (u.es_tu_cuenta) {
                const tag = document.createElement('span');
                tag.className = 'tag';
                tag.textContent = 'Tu cuenta';
                acciones.append(tag);
            } else {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'btn-sec';
                btn.textContent = 'Reiniciar';
                btn.addEventListener('click', () => pedirConfirmacion(acciones, u));
                acciones.append(btn);
            }
            li.append(datos, acciones);
            lista.append(li);
        }
    }

    // Confirmación dentro de la misma fila (sin ventanas del navegador)
    function pedirConfirmacion(acciones, u) {
        acciones.replaceChildren();
        const no = document.createElement('button');
        no.type = 'button';
        no.className = 'btn-sec';
        no.textContent = 'Cancelar';
        no.addEventListener('click', pintarLista);
        const si = document.createElement('button');
        si.type = 'button';
        si.className = 'btn-danger';
        si.textContent = 'Sí, reiniciar';
        si.addEventListener('click', () => reiniciar(u, si));
        acciones.append(no, si);
        si.focus();
    }

    async function reiniciar(u, boton) {
        boton.disabled = true;
        boton.textContent = 'Reiniciando…';
        try {
            const r = await fetch('/api/auth/admin/reiniciar-registro', {
                method: 'POST', headers: getSecurityHeaders(), body: JSON.stringify({ numero_cuenta: u.numero_cuenta })
            });
            if (r.status === 401) return irALogin();
            const data = await r.json().catch(() => ({}));
            if (r.ok && data.reiniciado) {
                usuarios = usuarios.filter(x => x.numero_cuenta !== u.numero_cuenta);
                aviso(`Registro de ${u.nombre || u.numero_cuenta} reiniciado. Ya puede registrarse de nuevo.`, 'ok');
            } else {
                aviso(typeof data.detail === 'string' ? data.detail : 'No se pudo reiniciar el registro.', 'error');
                await cargar();
            }
        } catch {
            aviso('No hay conexión con el servidor.', 'error');
        }
        pintarLista();
        buscar.focus();
    }

    async function cargar() {
        lista.innerHTML = '<li class="user-empty">Cargando…</li>';
        try {
            const r = await fetch('/api/auth/admin/usuarios', { headers: getSecurityHeaders() });
            if (r.status === 401) return irALogin();
            const data = await r.json();
            usuarios = Array.isArray(data.usuarios) ? data.usuarios : [];
        } catch {
            usuarios = [];
            aviso('No hay conexión con el servidor.', 'error');
        }
        pintarLista();
    }

    buscar.addEventListener('input', pintarLista);
    dlg.querySelector('#usuarios-cerrar').addEventListener('click', () => dlg.close());
    dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
    // Al cerrar, la lista descifrada no se queda en la página
    dlg.addEventListener('close', () => { usuarios = []; lista.replaceChildren(); });
    document.getElementById('btn-usuarios').addEventListener('click', () => {
        buscar.value = '';
        aviso('');
        setMenu(false);
        dlg.showModal();
        buscar.focus();
        cargar();
    });
}

function pintarUsuario(usuario) {
    if (!usuario) return;
    const esAdmin = usuario.rol === 'admin';
    document.documentElement.classList.toggle('es-admin', esAdmin);
    if (esAdmin) montarHerramientasAdmin();
    // El panel admin solo es para administradores
    if (!esAdmin && /admin-metrics/.test(location.pathname)) { location.replace('/'); return; }
    document.querySelectorAll('[data-user-name]').forEach(el => { el.textContent = usuario.nombre || 'Usuario'; });
    document.querySelectorAll('[data-user-career]').forEach(el => { el.textContent = usuario.carrera_nombre || usuario.carrera || ''; });
    document.querySelectorAll('[data-user-initials]').forEach(el => {
        el.textContent = iniciales(usuario.nombre);
        el.title = usuario.nombre || '';
    });
}

document.querySelectorAll('[data-logout]').forEach(b => b.addEventListener('click', cerrarSesion));

// ---------------------------------------------------------------------------
// Selector de modelo (F3): recuerda la última elección y desactiva un modelo sin cuota
// ---------------------------------------------------------------------------
const MODELO_KEY = 'nexus_modelo';
const modeloSelect = document.getElementById('modelo');
let sesionInfo = null;

function modeloElegido() {
    return modeloSelect?.value || 'gpt-4o-mini';
}

function pintarSelectorModelos(s) {
    if (!modeloSelect || !s.quotas) return;
    let guardado = null;
    try { guardado = localStorage.getItem(MODELO_KEY); } catch { }
    const previo = modeloSelect.value || guardado;
    modeloSelect.innerHTML = '';
    for (const [id, q] of Object.entries(s.quotas)) {
        const opt = document.createElement('option');
        opt.value = id;
        const corto = (q.label || id).split(' (')[0];
        const agotado = s.rate_limit_enabled && !q.allowed;
        opt.textContent = agotado ? `${corto} (agotado)` : (q.available ? corto : `${corto} (no disponible)`);
        opt.title = q.label || id;
        opt.disabled = !q.available || agotado;
        modeloSelect.appendChild(opt);
    }
    // Conserva la elección si sigue disponible; si no, el modelo por defecto
    const preferido = [previo, guardado, s.default_model].find(
        id => id && s.quotas[id] && !modeloSelect.querySelector(`option[value="${CSS.escape(id)}"]`).disabled
    );
    if (preferido) modeloSelect.value = preferido;
}

function pintarCuota() {
    const quota = document.getElementById('rate-limit-badge');
    const s = sesionInfo;
    if (!quota || !s) return;
    if (!s.rate_limit_enabled) {
        quota.textContent = '⏱️ Sin límite';
        return;
    }
    const q = (s.quotas && s.quotas[modeloElegido()]) || s.quota;
    if (!q) {
        quota.textContent = '⏱️ Sin sesión';
        return;
    }
    const corto = (q.label || '').split(' (')[0];
    quota.textContent = `⏱️ ${corto ? corto + ' ' : ''}${q.hourly_remaining}/${q.hourly_limit}/h`;
    quota.title = `${q.label || 'Modelo'}: te quedan ${q.hourly_remaining} de ${q.hourly_limit} consultas en la última hora`
        + (q.daily_limit ? ` y ${q.daily_remaining} de ${q.daily_limit} en el día` : '');
}

modeloSelect?.addEventListener('change', () => {
    try { localStorage.setItem(MODELO_KEY, modeloSelect.value); } catch { }
    pintarCuota();
});

async function refreshSecurityBadges() {
    const quota = document.getElementById('rate-limit-badge');
    try {
        const r = await fetch('/api/session/info', { headers: getSecurityHeaders() });
        const s = await r.json();
        if (!s.authenticated) { irALogin(); return; }
        sesionInfo = s;
        pintarUsuario(s.usuario);
        pintarSelectorModelos(s);
        pintarCuota();
    } catch (error) {
        if (quota) quota.textContent = '⚠️ Servidor sin conexión';
    }
}

refreshSecurityBadges();


// Registro de Service Worker PWA
if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
    addEventListener('load', () => navigator.serviceWorker.register('./service-worker.js').catch(() => {}));
}

// Control del menú lateral (desplegable en celular y tablet) y cortina
const side = $('#sidebar'), shade = $('#shade'), menuBtn = $('#menu');

function setMenu(open) {
    side?.classList.toggle('open', open);
    shade?.classList.toggle('show', open);
    document.body.classList.toggle('no-scroll', open);
    menuBtn?.setAttribute('aria-expanded', String(open));
}

menuBtn?.addEventListener('click', () => setMenu(true));
shade?.addEventListener('click', () => setMenu(false));
$('.side-close')?.addEventListener('click', () => setMenu(false));
document.addEventListener('keydown', e => { if (e.key === 'Escape') setMenu(false); });
// Al elegir una opción del menú en celular, se cierra
side?.querySelectorAll('.nav, #new').forEach(el => el.addEventListener('click', () => setMenu(false)));
// Si la pantalla crece a escritorio con el menú abierto, se limpia el estado
window.matchMedia('(min-width: 961px)').addEventListener('change', e => { if (e.matches) setMenu(false); });

// Elementos principales de la interfaz
const input = $('#input'),
      form = $('#form'),
      messages = $('#messages'),
      welcome = $('#welcome'),
      count = $('#count');

// =============================================================================
// HISTORIAL DE CONVERSACIONES (fase F1 del plan de implementación)
// La barra lateral se llena desde /api/conversaciones. La conversación abierta
// se identifica con conversacionActual; "Nueva consulta" la reinicia.
// =============================================================================
const historyList = $('#history-list');
let conversacionActual = null;

function mensajeHistorial(texto) {
    if (!historyList) return;
    historyList.innerHTML = '';
    const p = document.createElement('p');
    p.className = 'history-empty';
    p.textContent = texto;
    historyList.append(p);
}

function marcarConversacionActiva() {
    historyList?.querySelectorAll('.history-item').forEach(el => {
        const activa = el.dataset.id === conversacionActual;
        el.classList.toggle('active', activa);
        el.querySelector('.history')?.toggleAttribute('aria-current', activa);
    });
}

async function cargarHistorial() {
    if (!historyList) return;
    try {
        const r = await fetch('/api/conversaciones', { headers: getSecurityHeaders() });
        if (r.status === 401) { irALogin(); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const { conversaciones } = await r.json();
        if (!conversaciones.length) { mensajeHistorial('Aún no tienes consultas guardadas.'); return; }

        historyList.innerHTML = '';
        conversaciones.forEach(c => {
            const item = document.createElement('div');
            item.className = 'history-item';
            item.dataset.id = c.id;

            const abrir = document.createElement('button');
            abrir.type = 'button';
            abrir.className = 'history';
            abrir.textContent = `⌕ ${c.titulo}`;
            abrir.title = c.titulo;
            abrir.addEventListener('click', () => { setMenu(false); abrirConversacion(c.id); });

            const borrar = document.createElement('button');
            borrar.type = 'button';
            borrar.className = 'history-del';
            borrar.textContent = '✕';
            borrar.setAttribute('aria-label', `Borrar la conversación "${c.titulo}"`);
            borrar.addEventListener('click', () => borrarConversacion(c.id, c.titulo));

            item.append(abrir, borrar);
            historyList.append(item);
        });
        marcarConversacionActiva();
    } catch (err) {
        console.warn('No se pudo cargar el historial:', err);
        mensajeHistorial('No se pudo cargar el historial.');
    }
}

function limpiarChat() {
    conversacionActual = null;
    if (messages) messages.innerHTML = '';
    if (welcome) welcome.style.display = '';
    if (input) input.value = '';
    if (count) count.textContent = '0 / 500';
    marcarConversacionActiva();
}

async function abrirConversacion(id) {
    try {
        const r = await fetch(`/api/conversaciones/${encodeURIComponent(id)}`, { headers: getSecurityHeaders() });
        if (r.status === 401) { irALogin(); return; }
        if (r.status === 404) { limpiarChat(); cargarHistorial(); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const conv = await r.json();
        limpiarChat();
        conversacionActual = conv.id;
        if (welcome) welcome.style.display = 'none';
        conv.mensajes.forEach(m => {
            const tel = m.rol === 'assistant' ? { total_latency_ms: m.latencia_ms, model: m.modelo } : null;
            add(m.contenido, m.rol, m.citas || [], tel);
        });
        marcarConversacionActiva();
    } catch (err) {
        console.warn('No se pudo abrir la conversación:', err);
    }
}

async function borrarConversacion(id, titulo) {
    if (!confirm(`¿Borrar la conversación "${titulo}"?`)) return;
    try {
        const r = await fetch(`/api/conversaciones/${encodeURIComponent(id)}`, {
            method: 'DELETE', headers: getSecurityHeaders(),
        });
        if (r.status === 401) { irALogin(); return; }
    } catch (err) {
        console.warn('No se pudo borrar la conversación:', err);
    }
    if (id === conversacionActual) limpiarChat();
    cargarHistorial();
}

cargarHistorial();

// El Markdown seguro (escaparHTML, markdownEnLinea, renderMarkdown) vive en markdown.js

// ---------------------------------------------------------------------------
// Fuentes consultables: cada cita abre su documento dentro de la app
// ---------------------------------------------------------------------------
function paginaCitada(c) {
    const n = parseInt(String(c.pagina || '').split('-')[0], 10);
    return Number.isFinite(n) && n > 0 ? n : null;
}

async function abrirFuente(c, item) {
    // La pestaña se abre en el clic (antes de esperar al servidor) para que el navegador no la bloquee
    const ventana = window.open('about:blank', '_blank');
    try {
        const r = await fetch(`/api/documentos/${encodeURIComponent(c.doc_id)}/enlace`, {
            method: 'POST', headers: getSecurityHeaders()
        });
        if (r.status === 401) { ventana?.close(); irALogin(); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const e = await r.json();
        const pag = paginaCitada(c);
        let url = e.url;
        if (e.tipo === 'pdf' && pag) url += `#page=${pag}`;
        if (ventana) { ventana.opener = null; ventana.location.href = url; }
        else window.location.href = url;
    } catch (err) {
        ventana?.close();
        console.warn('No se pudo abrir el documento:', err);
        if (item && !item.querySelector('.cite-error')) {
            const aviso = document.createElement('span');
            aviso.className = 'cite-error';
            aviso.textContent = ' No se pudo abrir el documento; intenta de nuevo.';
            item.appendChild(aviso);
        }
    }
}

// Renderizado de burbujas en el feed de mensajes
function add(t, who, citations = [], telemetry = null) {
    let row = document.createElement('div');
    row.className = 'message ' + who;

    let av = document.createElement('div');
    av.className = 'msglogo';
    av.textContent = who === 'user' ? 'TÚ' : 'N';

    let b = document.createElement('div');
    b.className = 'bubble';
    if (who === 'assistant') {
        // Respuesta del asistente: Markdown con el HTML escapado de antemano
        b.classList.add('md');
        b.innerHTML = renderMarkdown(t);
    } else {
        b.textContent = t;
    }

    // Si existen citas oficiales verificadas (RF09), agregarlas en un bloque institucional
    if (who === 'assistant' && citations && citations.length > 0) {
        let citeBox = document.createElement('div');
        citeBox.className = 'cites';

        let citeTitle = document.createElement('strong');
        citeTitle.textContent = 'Fuentes oficiales consultadas (RF09):';
        citeBox.appendChild(citeTitle);

        citations.forEach(c => {
            let item = document.createElement('div');
            item.className = 'cite';
            let simPercent = Math.round(c.similarity * 100);
            const pag = paginaCitada(c);
            // La fuente se abre desde la app: el PDF original en la página citada o su texto
            let doc;
            if (c.doc_id) {
                doc = document.createElement('button');
                doc.type = 'button';
                doc.className = 'cite-link';
                doc.title = 'Abrir el documento' + (pag ? ` en la página ${pag}` : '');
                doc.textContent = c.documento;
                doc.addEventListener('click', () => abrirFuente(c, item));
            } else {
                doc = document.createElement('b');
                doc.textContent = c.documento;
            }
            let rel = document.createElement('span');
            rel.className = 'rel';
            rel.textContent = `(${simPercent}% relevancia)`;
            const extra = [c.articulo, pag ? `pág. ${pag}` : ''].filter(Boolean).join(' · ');
            item.append('• ', doc, ` [${c.categoria}] ${extra ? '· ' + extra : ''} `, rel);
            citeBox.appendChild(item);
        });

        if (telemetry && telemetry.total_latency_ms) {
            let telDiv = document.createElement('div');
            telDiv.className = 'cite-tel';
            telDiv.textContent = ` Latencia RAG: ${telemetry.total_latency_ms} ms · Modelo: ${telemetry.model || 'LanceDB + GPT'}`;
            if (telemetry.history_turns) {
                telDiv.textContent += ` · Contexto: ${telemetry.history_turns} turno(s) previo(s)`;
            }
            citeBox.appendChild(telDiv);
            // F2: la búsqueda se hizo con la pregunta reescrita a partir del historial
            if (telemetry.rewritten_query) {
                let rwDiv = document.createElement('div');
                rwDiv.className = 'cite-tel';
                rwDiv.textContent = ` Búsqueda interpretada como: «${telemetry.rewritten_query}»`;
                citeBox.appendChild(rwDiv);
            }
        }

        b.appendChild(citeBox);
    }

    if (who === 'user') {
        row.append(b, av);
    } else {
        row.append(av, b);
    }

    messages.append(row);
    row.scrollIntoView({ block: 'end', behavior: 'smooth' });
    return row;
}

// Respuesta de respaldo local en caso de que el backend no esté encendido
function answerFallback(q) {
    q = q.toLowerCase();
    if (q.includes('social')) {
        return 'Para comenzar tu servicio social, consulta la convocatoria y los requisitos vigentes en la Coordinación de ICO o en los canales oficiales de la Facultad. (Modo de demostración offline)';
    }
    if (q.includes('titul')) {
        return 'Consulta las 8 opciones de titulación y la normativa vigente del Reglamento de Estudios Profesionales en la Subdirección Académica de la Facultad. (Modo de demostración offline)';
    }
    if (q.includes('cultur') || q.includes('activ')) {
        return 'Revisa las convocatorias de actividades culturales y deportivas en el Edificio B de la Facultad de Ingeniería. (Modo de demostración offline)';
    }
    return 'Nexus FI está diseñado para orientarte sobre qué hacer, dónde consultar y con quién comunicarte en la Facultad de Ingeniería (UAEMéx). Enciende el servidor backend para consultar los 211 documentos y 3,977 vectores oficiales.';
}

// Contador de caracteres y auto-ajuste de altura
input?.addEventListener('input', () => {
    count.textContent = input.value.length + ' / 500';
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
});

// Envío y consulta con el backend RAG
form?.addEventListener('submit', async e => {
    e.preventDefault();
    let q = input.value.trim();
    if (!q) return;

    if (welcome) welcome.style.display = 'none';
    add(q, 'user');
    input.value = '';
    if (count) count.textContent = '0 / 500';
    input.style.height = '';

    // Burbuja temporal de carga
    let loadingRow = add('Consultando acervo institucional oficial de la FI UAEMéx...', 'assistant');

    try {
        const consultar = () => fetch('/api/chat', {
            method: 'POST',
            headers: getSecurityHeaders(),
            body: JSON.stringify({
                query: q, top_k: 4, use_llm: true, conversation_id: conversacionActual, model: modeloElegido()
            })
        });
        let response = await consultar();

        // La conversación se borró en otra pestaña o equipo: la pregunta inicia una nueva
        if (response.status === 404 && conversacionActual) {
            conversacionActual = null;
            response = await consultar();
        }

        if (response.status === 401) {
            irALogin();
            return;
        }

        // F3: la cuota es por modelo; el servidor dice cuál se agotó y cuándo se libera
        if (response.status === 429 || response.status === 503) {
            loadingRow.remove();
            let detalle = '';
            try { detalle = (await response.json()).detail || ''; } catch { }
            add(`⚠️ ${detalle || 'Alcanzaste la cuota de consultas. Espera unos minutos antes de preguntar de nuevo.'}`, 'assistant');
            refreshSecurityBadges();
            return;
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        loadingRow.remove();
        add(data.answer, 'assistant', data.citations, data.telemetry);
        if (data.conversation_id) {
            const nueva = data.conversation_id !== conversacionActual;
            conversacionActual = data.conversation_id;
            // El orden de la lista cambia con cada consulta (la más reciente arriba)
            cargarHistorial();
            if (nueva) marcarConversacionActiva();
        }
        refreshSecurityBadges();
    } catch (err) {
        console.warn('Backend RAG no disponible o error en petición, activando fallback local:', err);
        loadingRow.remove();
        add(answerFallback(q), 'assistant');
    }
});

// Clics en sugerencias rápidas
document.querySelectorAll('[data-q]').forEach(b => {
    b.addEventListener('click', () => {
        input.value = b.dataset.q;
        form.requestSubmit();
    });
});

// Botón Nueva consulta: limpia el chat y la próxima pregunta abre otra conversación
$('#new')?.addEventListener('click', limpiarChat);
