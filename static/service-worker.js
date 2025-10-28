const CACHE_NAME = 'gimmie-v1.1.1-cache-busting';
const urlsToCache = [
  '/',
  '/static/images/gimmie-icon.png',
  '/manifest.json'
  // CSS and JS files are handled with version-based cache busting
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', event => {
  if (event.request.url.includes('/api/') || 
      event.request.url.includes('/login') || 
      event.request.url.includes('/logout') ||
      event.request.url.includes('/static/js/') ||
      event.request.url.includes('/static/css/') ||
      event.request.url.includes('?v=')) {
    // Always fetch fresh for API calls, auth, versioned assets
    return fetch(event.request);
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }

        const fetchRequest = event.request.clone();

        return fetch(fetchRequest).then(response => {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }

          const responseToCache = response.clone();

          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });

          return response;
        });
      })
  );
});

self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];

  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});