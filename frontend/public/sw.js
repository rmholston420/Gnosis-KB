/**
 * Gnosis KB — Service Worker
 *
 * Strategy matrix:
 *   App shell (HTML/JS/CSS/fonts) — Cache First, populated at install
 *   GET /api/*                    — Network First, fall back to cache (5 s timeout)
 *   POST/PUT/PATCH/DELETE /api/*  — Queue in IndexedDB, replay on Background Sync
 *   Everything else               — Network First, no cache fallback
 *
 * Cache names are versioned so old caches are purged on activate.
 */

const CACHE_VERSION = 'v1';
const SHELL_CACHE   = `gnosis-shell-${CACHE_VERSION}`;
const API_CACHE     = `gnosis-api-${CACHE_VERSION}`;
const QUEUE_DB      = 'gnosis-offline-queue';
const QUEUE_STORE   = 'mutations';
const SYNC_TAG      = 'gnosis-sync-mutations';

// App-shell assets injected by vite-plugin-pwa at build time.
// The __WB_MANIFEST placeholder is replaced during the build; in dev mode
// we fall back to an empty array so the SW still registers cleanly.
const SHELL_ASSETS = self.__WB_MANIFEST ?? [];

// ---------------------------------------------------------------------------
// Install — pre-cache shell assets
// ---------------------------------------------------------------------------
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => {
      const urls = SHELL_ASSETS.map((entry) =>
        typeof entry === 'string' ? entry : entry.url
      );
      // Cache what we can; ignore individual failures (missing icons etc.)
      return Promise.allSettled(urls.map((url) => cache.add(url)));
    }).then(() => self.skipWaiting())
  );
});

// ---------------------------------------------------------------------------
// Activate — prune stale caches
// ---------------------------------------------------------------------------
self.addEventListener('activate', (event) => {
  const keep = new Set([SHELL_CACHE, API_CACHE]);
  event.waitUntil(
    caches.keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

// ---------------------------------------------------------------------------
// Fetch — route by method + URL pattern
// ---------------------------------------------------------------------------
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET mutations — queue them
  if (!['GET', 'HEAD'].includes(request.method) && url.pathname.startsWith('/api/')) {
    event.respondWith(enqueueMutation(request));
    return;
  }

  // API GET — Network First (5 s timeout), fall back to cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstWithTimeout(request, API_CACHE, 5000));
    return;
  }

  // App shell — Cache First
  if (
    request.destination === 'document' ||
    request.destination === 'script'   ||
    request.destination === 'style'    ||
    request.destination === 'font'
  ) {
    event.respondWith(cacheFirst(request, SHELL_CACHE));
    return;
  }

  // Default — network only (images from API, SSE streams, etc.)
  // Let the browser handle it; no event.respondWith() means default behaviour.
});

// ---------------------------------------------------------------------------
// Background Sync — drain queued mutations when online
// ---------------------------------------------------------------------------
self.addEventListener('sync', (event) => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(drainQueue());
  }
});

// ---------------------------------------------------------------------------
// Message — manual sync trigger from the app
// ---------------------------------------------------------------------------
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (event.data?.type === 'SYNC_NOW') {
    event.waitUntil(drainQueue());
  }
});

// ===========================================================================
// Helpers
// ===========================================================================

/** Cache First: serve from cache, fetch + cache on miss. */
async function cacheFirst(request, cacheName) {
  const cache    = await caches.open(cacheName);
  const cached   = await cache.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    return new Response('Offline', { status: 503 });
  }
}

/** Network First with timeout: try network, fall back to cache. */
async function networkFirstWithTimeout(request, cacheName, timeoutMs) {
  const cache = await caches.open(cacheName);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(request, { signal: controller.signal });
    clearTimeout(timer);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    clearTimeout(timer);
    const cached = await cache.match(request);
    if (cached) return cached;
    return new Response(
      JSON.stringify({ detail: 'You are offline and this response is not cached.' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

/** Enqueue a mutating request in IndexedDB and register a Background Sync. */
async function enqueueMutation(request) {
  try {
    const body = await request.clone().text();
    const entry = {
      id:        crypto.randomUUID(),
      timestamp: Date.now(),
      method:    request.method,
      url:       request.url,
      headers:   Object.fromEntries(request.headers.entries()),
      body,
    };
    await idbSet(QUEUE_DB, QUEUE_STORE, entry);

    // Register Background Sync if supported
    if ('SyncManager' in self) {
      try {
        const reg = await self.registration;
        await reg.sync.register(SYNC_TAG);
      } catch { /* best-effort */ }
    }

    return new Response(
      JSON.stringify({ queued: true, id: entry.id }),
      {
        status:  202,
        headers: { 'Content-Type': 'application/json', 'X-Gnosis-Queued': 'true' },
      }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ detail: `Failed to queue mutation: ${err.message}` }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

/** Replay all queued mutations in order, removing successful ones. */
async function drainQueue() {
  const entries = await idbGetAll(QUEUE_DB, QUEUE_STORE);
  for (const entry of entries) {
    try {
      const response = await fetch(entry.url, {
        method:  entry.method,
        headers: entry.headers,
        body:    entry.body || undefined,
      });
      if (response.ok || response.status === 409) {
        // 409 Conflict = server already has it — safe to dequeue
        await idbDelete(QUEUE_DB, QUEUE_STORE, entry.id);
      }
      // 4xx other than 409 = permanent failure — leave in queue for manual review
      // 5xx = transient, retry on next sync
    } catch {
      // Network still down — stop draining, retry on next sync event
      break;
    }
  }

  // Notify all clients that the queue has been drained
  const clients = await self.clients.matchAll({ includeUncontrolled: true });
  for (const client of clients) {
    client.postMessage({ type: 'QUEUE_DRAINED' });
  }
}

// ===========================================================================
// Minimal IndexedDB helpers (no external deps in SW scope)
// ===========================================================================

function openDB(dbName, storeName) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(dbName, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(storeName)) {
        req.result.createObjectStore(storeName, { keyPath: 'id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror   = () => reject(req.error);
  });
}

async function idbSet(dbName, storeName, value) {
  const db  = await openDB(dbName, storeName);
  return new Promise((resolve, reject) => {
    const tx  = db.transaction(storeName, 'readwrite');
    const req = tx.objectStore(storeName).put(value);
    req.onsuccess = () => resolve();
    req.onerror   = () => reject(req.error);
  });
}

async function idbGetAll(dbName, storeName) {
  const db  = await openDB(dbName, storeName);
  return new Promise((resolve, reject) => {
    const tx  = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).getAll();
    req.onsuccess = () => resolve(req.result.sort((a, b) => a.timestamp - b.timestamp));
    req.onerror   = () => reject(req.error);
  });
}

async function idbDelete(dbName, storeName, id) {
  const db  = await openDB(dbName, storeName);
  return new Promise((resolve, reject) => {
    const tx  = db.transaction(storeName, 'readwrite');
    const req = tx.objectStore(storeName).delete(id);
    req.onsuccess = () => resolve();
    req.onerror   = () => reject(req.error);
  });
}
