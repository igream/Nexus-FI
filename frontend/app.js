// =============================================================================
// SEGURIDAD Y FINGERPRINTING DE DISPOSITIVO (WBS 1.3.5 / WBS 1.4.2 - Joaquín Ulises)
// =============================================================================
function getOrCreateSessionUUID() {
    const KEY = "nexus_session_uuid";
    let id = localStorage.getItem(KEY);
    if (!id) {
        id = typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID()
            : "sess_" + Math.random().toString(36).substring(2, 15);
        localStorage.setItem(KEY, id);
    }
    return id;
}

function getDeviceFingerprint() {
    const KEY = "nexus_device_fingerprint";
    let fp = localStorage.getItem(KEY);
    if (fp) return fp;

    const signals = [
        screen.width + "x" + screen.height + "x" + screen.colorDepth,
        navigator.userAgent,
        navigator.language || "es",
        Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Mexico_City",
        navigator.hardwareConcurrency || 4
    ];

    let hash = 0;
    const str = signals.join("###");
    for (let i = 0; i < str.length; i++) {
        hash = (hash << 5) - hash + str.charCodeAt(i);
        hash |= 0;
    }
    fp = "fp_" + Math.abs(hash).toString(16).padStart(8, "0");
    localStorage.setItem(KEY, fp);
    return fp;
}

function getSecurityHeaders() {
    return {
        "Content-Type": "application/json",
        "X-Device-Fingerprint": getDeviceFingerprint(),
        "X-Session-ID": getOrCreateSessionUUID()
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

    button.textContent = isDark ? ' Modo claro' : ' Modo oscuro';
    button.setAttribute('aria-pressed', String(isDark));
    button.setAttribute(
        'aria-label',
        isDark ? 'Activar modo claro' : 'Activar modo oscuro'
    );
});


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


// Registro de Service Worker PWA
if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
    addEventListener('load', () => navigator.serviceWorker.register('./service-worker.js').catch(() => {}));
}

// Control del menú lateral y cortina móvil
const side = $('#sidebar'), shade = $('#shade');
$('#menu')?.addEventListener('click', () => {
    side?.classList.add('open');
    shade?.classList.add('show');
});
shade?.addEventListener('click', () => {
    side?.classList.remove('open');
    shade?.classList.remove('show');
});

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
        citeBox.style.marginTop = '10px';
        citeBox.style.paddingTop = '8px';
        citeBox.style.borderTop = '1px dashed #d1e2d7';
        citeBox.style.fontSize = '10px';
        citeBox.style.color = '#42574b';

        let citeTitle = document.createElement('div');
        citeTitle.innerHTML = '<strong> Fuentes oficiales consultadas (RF09):</strong>';
        citeBox.appendChild(citeTitle);

        citations.forEach(c => {
            let item = document.createElement('div');
            item.style.marginTop = '4px';
            item.style.padding = '3px 6px';
            item.style.background = '#f2f8f4';
            item.style.borderRadius = '5px';
            let simPercent = Math.round(c.similarity * 100);
            item.innerHTML = `• <b>${c.documento}</b> [${c.categoria}] ${c.articulo ? '· ' + c.articulo : ''} <span style="color:#006747;font-weight:bold;">(${simPercent}% relevancia)</span>`;
            citeBox.appendChild(item);
        });

        if (telemetry && telemetry.total_latency_ms) {
            let telDiv = document.createElement('div');
            telDiv.style.marginTop = '6px';
            telDiv.style.fontSize = '9px';
            telDiv.style.color = '#8a9890';
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
    messages.scrollTop = messages.scrollHeight;
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

        if (response.status === 403) {
            const errData = await response.json().catch(() => ({}));
            loadingRow.remove();
            add(`🚫 Acceso Denegado (HTTP 403): Conexión fuera del perímetro institucional de la Facultad de Ingeniería (UAEMéx).\n\nSubredes permitidas: 148.215.X.X / 172.17.18.X (Edificios A, B, C y laboratorios FI). Conéctate a la red institucional para consultar.`, 'assistant');
            return;
        }

        if (response.status === 429) {
            loadingRow.remove();
            add(`⚠️ Límite de consultas excedido (HTTP 429): Has alcanzado la cuota máxima permitida (20 consultas/hora o 60 consultas/día por dispositivo). Por favor espera unos momentos antes de realizar otra pregunta.`, 'assistant');
            return;
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        loadingRow.remove();
        add(data.answer, 'assistant', data.citations, data.telemetry);
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
