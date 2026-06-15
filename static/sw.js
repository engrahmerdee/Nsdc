/* NSDCP Service Worker — Offline Support + PWA */
const CACHE = 'nsdcp-v1';
const OFFLINE_URL = '/offline';
const STATIC_ASSETS = [
  '/',
  '/static/css/style.css',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);

  // Always go to network for API and auth routes
  if (['/login', '/logout', '/register'].some(p => url.pathname.startsWith(p))) return;
  if (url.pathname.startsWith('/posts/') && e.request.method !== 'GET') return;

  e.respondWith(
    fetch(e.request)
      .then(response => {
        // Cache successful responses for static assets
        if (response.ok && (
          url.pathname.startsWith('/static/') ||
          url.hostname !== location.hostname
        )) {
          const clone = response.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return response;
      })
      .catch(() => {
        // Offline: try cache first
        return caches.match(e.request).then(cached => {
          if (cached) return cached;
          // For navigation requests show offline page
          if (e.request.mode === 'navigate') {
            return new Response(
              `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
              <title>NSDCP — Offline</title>
              <style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Inter,sans-serif;background:#f2f5f3;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;padding:24px;text-align:center}
              .ico{font-size:64px;margin-bottom:20px}.card{background:#fff;border-radius:16px;padding:32px;max-width:400px;box-shadow:0 4px 20px rgba(0,0,0,.1)}
              h1{font-size:22px;color:#111;margin-bottom:8px}p{color:#666;font-size:15px;line-height:1.6;margin-bottom:20px}
              .btn{background:#1a6b3c;color:#fff;padding:12px 24px;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block}
              .sub{font-size:13px;color:#888;margin-top:12px}</style>
              </head><body>
              <div class="card">
                <div class="ico">&#128268;</div>
                <h1>You're Offline</h1>
                <p>No internet connection detected. Please check your network and try again.</p>
                <button class="btn" onclick="window.location.reload()">Try Again</button>
                <p class="sub">NSDCP will reconnect automatically when your internet returns.</p>
              </div></body></html>`,
              { headers: { 'Content-Type': 'text/html' } }
            );
          }
          return new Response('Offline', { status: 503 });
        });
      })
  );
});
