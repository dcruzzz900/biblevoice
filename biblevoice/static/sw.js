// Caches the app shell so the UI loads with no internet (the API runs on your own local server).
const C='bv2';self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(['/','/index.html']))));
self.addEventListener('fetch',e=>{if(e.request.url.includes('/api/'))return;e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)))});
