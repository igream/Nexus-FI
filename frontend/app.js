// =============================================================================
// CABECERAS DE LAS PETICIONES A LA API
// El límite de consultas es por usuario registrado (SC-001). Cuando exista el
// inicio de sesión (Avance 3), aquí se agregará el token de la sesión.
// =============================================================================
function getSecurityHeaders() {
    return {
        "Content-Type": "application/json"
    };
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

// Insignia de cuota: consultas restantes del usuario en sesión
async function refreshSecurityBadges() {
    const quota = document.getElementById('rate-limit-badge');
    if (!quota) return;
    try {
        const r = await fetch('/api/session/info', { headers: getSecurityHeaders() });
        const s = await r.json();
        if (!s.rate_limit_enabled) {
            quota.textContent = '⏱️ Sin límite';
        } else if (!s.quota) {
            quota.textContent = '⏱️ Sin sesión';
        } else {
            quota.textContent = `⏱️ ${s.quota.hourly_remaining}/${s.quota.hourly_limit} por hora`;
        }
    } catch (error) {
        quota.textContent = '⚠️ Servidor sin conexión';
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
side?.querySelectorAll('.nav, .history, #new').forEach(el => el.addEventListener('click', () => setMenu(false)));
// Si la pantalla crece a escritorio con el menú abierto, se limpia el estado
window.matchMedia('(min-width: 961px)').addEventListener('change', e => { if (e.matches) setMenu(false); });

// Elementos principales de la interfaz
const input = $('#input'),
      form = $('#form'),
      messages = $('#messages'),
      welcome = $('#welcome'),
      count = $('#count');

// Renderizado de burbujas en el feed de mensajes
function add(t, who, citations = [], telemetry = null) {
    let row = document.createElement('div');
    row.className = 'message ' + who;

    let av = document.createElement('div');
    av.className = 'msglogo';
    av.textContent = who === 'user' ? 'TÚ' : 'N';

    let b = document.createElement('div');
    b.className = 'bubble';
    b.textContent = t;

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
            let doc = document.createElement('b');
            doc.textContent = c.documento;
            let rel = document.createElement('span');
            rel.className = 'rel';
            rel.textContent = `(${simPercent}% relevancia)`;
            item.append('• ', doc, ` [${c.categoria}] ${c.articulo ? '· ' + c.articulo : ''} `, rel);
            citeBox.appendChild(item);
        });

        if (telemetry && telemetry.total_latency_ms) {
            let telDiv = document.createElement('div');
            telDiv.className = 'cite-tel';
            telDiv.textContent = ` Latencia RAG: ${telemetry.total_latency_ms} ms · Modelo: ${telemetry.model || 'LanceDB + GPT'}`;
            citeBox.appendChild(telDiv);
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
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: getSecurityHeaders(),
            body: JSON.stringify({ query: q, top_k: 4, use_llm: true })
        });

        if (response.status === 429) {
            loadingRow.remove();
            add(`⚠️ Límite de consultas excedido (HTTP 429): Alcanzaste la cuota de tu cuenta (20 consultas por hora o 60 por día). Por favor espera unos momentos antes de realizar otra pregunta.`, 'assistant');
            return;
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        loadingRow.remove();
        add(data.answer, 'assistant', data.citations, data.telemetry);
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

// Clics en historial
document.querySelectorAll('.history').forEach(h => {
    h.addEventListener('click', () => {
        let text = h.textContent.replace('⌕', '').trim();
        input.value = `Información sobre: ${text}`;
        form.requestSubmit();
    });
});

// Botón Nueva consulta
$('#new')?.addEventListener('click', () => {
    if (messages) messages.innerHTML = '';
    if (welcome) welcome.style.display = '';
    if (input) input.value = '';
    if (count) count.textContent = '0 / 500';
});
