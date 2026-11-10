// Visor de documentos del acervo: muestra el texto de una fuente citada en el chat.
// Requiere sesión (el mismo token que usa el chat) y solo acepta ids del catálogo del servidor.
(function () {
    try {
        const tema = localStorage.getItem('nexusfi-theme');
        if (tema === 'dark') document.documentElement.dataset.theme = 'dark';
    } catch { }

    const titulo = document.getElementById('doc-titulo');
    const sub = document.getElementById('doc-sub');
    const cuerpo = document.getElementById('doc-cuerpo');

    let token = null;
    try { token = localStorage.getItem('nexus_token'); } catch { }
    const id = new URLSearchParams(location.search).get('id');

    function error(texto) {
        titulo.textContent = 'No se pudo abrir el documento';
        cuerpo.textContent = texto;
    }

    if (!token) { location.replace('/login'); return; }
    if (!id) { error('Falta el identificador del documento.'); return; }

    fetch(`/api/documentos/${encodeURIComponent(id)}/texto`, { headers: { Authorization: `Bearer ${token}` } })
        .then(async r => {
            if (r.status === 401) { location.replace('/login'); return null; }
            if (r.status === 404) { error('El documento no existe en el acervo.'); return null; }
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then(d => {
            if (!d) return;
            document.title = `Nexus FI - ${d.titulo}`;
            titulo.textContent = d.titulo;
            sub.textContent = `${d.documento}${d.categoria ? ' · ' + d.categoria : ''} · texto del acervo de Nexus FI`;
            cuerpo.innerHTML = renderMarkdown(d.markdown);
        })
        .catch(e => error(`Error al cargar el documento (${e.message}).`));
})();
