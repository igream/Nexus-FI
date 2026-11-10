// Markdown seguro compartido por el chat (app.js) y el visor de documentos (documento.js).
// Se carga antes que esos scripts.
// =============================================================================
// MARKDOWN SEGURO PARA LAS RESPUESTAS DEL ASISTENTE
// Primero se escapa todo el HTML; después solo se convierten los elementos
// permitidos (títulos, negritas, cursivas, listas, citas, código, separadores
// y enlaces http/https). Así el texto del modelo no puede inyectar código.
// =============================================================================
function escaparHTML(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function markdownEnLinea(s) {
    const codigos = [];
    s = s.replace(/`([^`]+)`/g, (_, c) => `\u0000${codigos.push(c) - 1}\u0000`);
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        (_, texto, url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${texto}</a>`);
    s = s.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/__([^_]+?)__/g, '<strong>$1</strong>');
    // Cursiva solo con asterisco: el guion bajo aparece en nombres de archivo (Guia_Tramites.pdf)
    s = s.replace(/(^|[^*\w])\*(?!\s)([^*\n]+?)\*(?!\w)/g, '$1<em>$2</em>');
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codigos[i]}</code>`);
}

function renderMarkdown(texto) {
    const lineas = escaparHTML(String(texto || '').replace(/\r\n?/g, '\n')).split('\n');
    const html = [];
    let parrafo = [], lista = null, cita = [], bloque = null;

    const cerrarParrafo = () => {
        if (parrafo.length) html.push(`<p>${parrafo.map(markdownEnLinea).join('<br>')}</p>`);
        parrafo = [];
    };
    const cerrarLista = () => {
        if (!lista) return;
        const inicio = lista.tipo === 'ol' && lista.inicio !== 1 ? ` start="${lista.inicio}"` : '';
        html.push(`<${lista.tipo}${inicio}>${lista.items.map(i => `<li>${markdownEnLinea(i)}</li>`).join('')}</${lista.tipo}>`);
        lista = null;
    };
    const cerrarCita = () => {
        if (cita.length) html.push(`<blockquote>${cita.map(markdownEnLinea).join('<br>')}</blockquote>`);
        cita = [];
    };
    // Tablas Markdown (| a | b |): encabezado, fila separadora |---|:---:| y filas de datos
    let tabla = [];
    const celdas = fila => fila.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
    const esSeparador = fila => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(fila);
    const cerrarTabla = () => {
        if (!tabla.length) return;
        if (tabla.length >= 2 && esSeparador(tabla[1])) {
            const alineacion = celdas(tabla[1]).map(c =>
                c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : '');
            const fila = (linea, etiqueta) => '<tr>' + celdas(linea).map((c, i) => {
                const a = alineacion[i] ? ` style="text-align:${alineacion[i]}"` : '';
                return `<${etiqueta}${a}>${markdownEnLinea(c)}</${etiqueta}>`;
            }).join('') + '</tr>';
            const cuerpo = tabla.slice(2).map(l => fila(l, 'td')).join('');
            html.push(`<div class="tabla-md"><table><thead>${fila(tabla[0], 'th')}</thead><tbody>${cuerpo}</tbody></table></div>`);
        } else {
            // Sin fila separadora no es una tabla: se muestra como texto
            html.push(`<p>${tabla.map(markdownEnLinea).join('<br>')}</p>`);
        }
        tabla = [];
    };
    const cerrarTodo = () => { cerrarParrafo(); cerrarLista(); cerrarCita(); cerrarTabla(); };

    for (const linea of lineas) {
        if (bloque) {
            if (/^\s*```/.test(linea)) { html.push(`<pre><code>${bloque.join('\n')}</code></pre>`); bloque = null; }
            else bloque.push(linea);
            continue;
        }
        if (/^\s*```/.test(linea)) { cerrarTodo(); bloque = []; continue; }
        if (!linea.trim()) { cerrarTodo(); continue; }
        if (/^\s*\|.*\|\s*$/.test(linea)) { cerrarParrafo(); cerrarLista(); cerrarCita(); tabla.push(linea); continue; }
        cerrarTabla();

        let m;
        if ((m = linea.match(/^\s*(#{1,6})\s+(.*)$/))) {
            cerrarTodo();
            const nivel = Math.min(m[1].length + 2, 6);   // # → h3 … para no competir con el título de la página
            html.push(`<h${nivel}>${markdownEnLinea(m[2])}</h${nivel}>`);
        } else if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(linea)) {
            cerrarTodo();
            html.push('<hr>');
        } else if ((m = linea.match(/^\s*[-*+•]\s+(.*)$/))) {
            cerrarParrafo(); cerrarCita();
            if (!lista || lista.tipo !== 'ul') { cerrarLista(); lista = { tipo: 'ul', items: [] }; }
            lista.items.push(m[1]);
        } else if ((m = linea.match(/^\s*(\d+)[.)]\s+(.*)$/))) {
            cerrarParrafo(); cerrarCita();
            if (!lista || lista.tipo !== 'ol') { cerrarLista(); lista = { tipo: 'ol', inicio: Number(m[1]), items: [] }; }
            lista.items.push(m[2]);
        } else if ((m = linea.match(/^\s*&gt;\s?(.*)$/))) {
            cerrarParrafo(); cerrarLista();
            cita.push(m[1]);
        } else if (lista && /^\s{2,}\S/.test(linea)) {
            // Continuación de un elemento de la lista
            lista.items[lista.items.length - 1] += ' ' + linea.trim();
        } else {
            cerrarLista(); cerrarCita();
            parrafo.push(linea.trim());
        }
    }
    if (bloque) html.push(`<pre><code>${bloque.join('\n')}</code></pre>`);
    cerrarTodo();
    return html.join('');
}
