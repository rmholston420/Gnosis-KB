/**
 * registerSW.ts
 *
 * Service Worker registration with update lifecycle management.
 *
 * - Registers the SW built by vite-plugin-pwa (injectManifest strategy).
 * - Prompts the user to reload when a new SW is waiting.
 * - Listens for QUEUE_DRAINED messages so useOfflineSync can react.
 * - Posts SKIP_WAITING to activate a new SW immediately when the user
 *   confirms the reload prompt.
 */

export interface SWRegistrationOptions {
  /** Called when a new SW version is waiting to activate. */
  onNeedRefresh?: () => void;
  /** Called when the app is ready to work fully offline. */
  onOfflineReady?: () => void;
}

let _registration: ServiceWorkerRegistration | null = null;

export function getRegistration(): ServiceWorkerRegistration | null {
  return _registration;
}

/** Tell the waiting SW to skip waiting and take control immediately. */
export function skipWaiting(): void {
  _registration?.waiting?.postMessage({ type: 'SKIP_WAITING' });
}

export async function registerSW(options: SWRegistrationOptions = {}): Promise<void> {
  if (!('serviceWorker' in navigator)) return;

  try {
    const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    _registration = reg;

    // Detect an updated SW waiting to activate
    const checkWaiting = () => {
      if (reg.waiting) {
        options.onNeedRefresh?.();
      }
    };

    reg.addEventListener('updatefound', () => {
      const newWorker = reg.installing;
      if (!newWorker) return;
      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
          options.onNeedRefresh?.();
        }
        if (newWorker.state === 'activated' && !navigator.serviceWorker.controller) {
          options.onOfflineReady?.();
        }
      });
    });

    // Check immediately in case a SW was already waiting before this page loaded
    checkWaiting();

    // Reload the page once the new SW takes control
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      window.location.reload();
    });

    console.info('[SW] Registered at', reg.scope);
  } catch (err) {
    console.error('[SW] Registration failed:', err);
  }
}
