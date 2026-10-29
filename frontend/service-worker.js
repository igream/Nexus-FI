// Service Worker de Nexus FI: red primero, caché solo como respaldo sin conexión.
// Así cada actualización del servidor llega al navegador sin borrar datos a mano.
const CACHE = 'nexus-fi-v2';
const FILES = ['./', './index.html', './dashboard.html', './admin-metrics.html', './styles.css',
               './app.js', './manifest.webmanifest', './assets/nexus-icon.svg'];

self.addEventListener('install', e => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).catch(() => {}).then(() => self.skipWaiting()));
});

// Elimina cachés de versiones anteriores (p. ej. nexus-fi-demo-v1)
self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys()
            .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);
    // La API nunca se guarda en caché; otros orígenes (CDN) pasan directo
    if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
    e.respondWith(
        fetch(e.request)
            .then(resp => {
                if (resp.ok) {
                    const copy = resp.clone();
                    caches.open(CACHE).then(c => c.put(e.request, copy));
                }
                return resp;
            })
            .catch(() => caches.match(e.request).then(r => r || caches.match('./index.html')))
    );
});
