/**
 * Service Worker for Gnosis PWA.
 * Strategy: Cache-first for static assets, Network-first for API calls.
 * Uses the Workbox-compatible manual strategy for zero build-tool dependency.
 */

const CACHE_NAME = 'gnosis-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
];

// Install: pre-cache shell
self.addEventListener('install', (event: ExtendableEvent) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)),
  );
  (self as unknown as ServiceWorkerGlobalScope).skipWaiting();
});

// Activate: prune old caches
self.addEventListener('activate', (event: ExtendableEvent) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
    ),
  );
  (self as unknown as ServiceWorkerGlobalScope).clients.claim();
});

// Fetch: network-first for API, cache-first for static
self.addEventListener('fetch', (event: FetchEvent) => {
  const url = new URL(event.request.url);

  // API calls: network first, no cache
  if (url.pathname.startsWith('/api/')) {
    return; // fall through to network
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        // Cache successful GET responses for same-origin static assets
        if (
          response.ok &&
          event.request.method === 'GET' &&
          url.origin === self.location.origin
        ) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      });
    }),
  );
});

export {}; // Make TypeScript treat this as a module
