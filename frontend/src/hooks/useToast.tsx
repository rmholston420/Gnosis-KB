/**
 * useToast
 * ========
 * Lightweight, dependency-free toast system for Gnosis KB.
 *
 * Imperative API (works outside React):
 *   import { toast } from './useToast';
 *   toast.success('Note saved');
 *   toast.error('Something went wrong');
 *   toast.info('Syncing 3 offline changes…');
 *
 * React hook:
 *   const toasts = useToast();
 *
 * Mount once near the app root:
 *   <ToastContainer />
 *
 * Internal design: a plain observable store so the imperative API
 * can be called without React context or Zustand.
 *
 * Note: this file intentionally mixes components and non-component exports
 * (toast, useToast, _store, mountToastContainer) to keep the toast system
 * self-contained. Fast-refresh will reload the whole module on changes.
 */
/* eslint-disable react-refresh/only-export-components */

import React from 'react';
import { X } from 'lucide-react';

export type ToastVariant = 'success' | 'error' | 'info' | 'warning';

export interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
  duration: number;
}

type Listener = (toasts: ToastItem[]) => void;

export const _store = {
  toasts: [] as ToastItem[],
  listeners: new Set<Listener>(),

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => { this.listeners.delete(fn); };
  },

  _emit() {
    for (const fn of this.listeners) fn([...this.toasts]);
  },

  add(message: string, variant: ToastVariant, duration = 4000): string {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    this.toasts = [...this.toasts, { id, message, variant, duration }];
    this._emit();
    if (duration > 0) {
      setTimeout(() => this.remove(id), duration);
    }
    return id;
  },

  remove(id: string) {
    this.toasts = this.toasts.filter((t) => t.id !== id);
    this._emit();
  },

  clear() {
    this.toasts = [];
    this.listeners.clear();
  },

  get(id: string): ToastItem | undefined {
    return this.toasts.find((t) => t.id === id);
  },

  size(): number {
    return this.toasts.length;
  },
};

// ---------------------------------------------------------------------------
// Imperative API
// ---------------------------------------------------------------------------

export const toast = {
  success: (message: string, duration?: number): string => _store.add(message, 'success', duration),
  error:   (message: string, duration?: number): string => _store.add(message, 'error',   duration),
  info:    (message: string, duration?: number): string => _store.add(message, 'info',    duration),
  warning: (message: string, duration?: number): string => _store.add(message, 'warning', duration),
  dismiss: (id: string)                                  => _store.remove(id),
};

// ---------------------------------------------------------------------------
// React hook
// ---------------------------------------------------------------------------

export function useToast() {
  const [toasts, setToasts] = React.useState<ToastItem[]>([..._store.toasts]);
  React.useEffect(() => {
    const unsub = _store.subscribe(setToasts);
    return unsub;
  }, []);
  return toasts;
}

const VARIANT_STYLES: Record<ToastVariant, React.CSSProperties> = {
  success: { background: 'var(--color-success-highlight)', color: 'var(--color-success)', border: '1px solid var(--color-success)' },
  error:   { background: 'var(--color-error-highlight)',   color: 'var(--color-error)',   border: '1px solid var(--color-error)' },
  info:    { background: 'var(--color-primary-highlight)', color: 'var(--color-primary)', border: '1px solid var(--color-primary)' },
  warning: { background: 'var(--color-warning-highlight)', color: 'var(--color-warning)', border: '1px solid var(--color-warning)' },
};

function ToastItem({ item, onDismiss }: { item: ToastItem; onDismiss: (id: string) => void }) {
  return (
    <div
      role="alert"
      style={{
        ...VARIANT_STYLES[item.variant],
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '10px 14px',
        borderRadius: '8px',
        fontSize: '13px',
        fontWeight: 500,
        boxShadow: '0 4px 12px oklch(0 0 0 / 0.15)',
        minWidth: '240px',
        maxWidth: '380px',
        pointerEvents: 'auto',
        cursor: 'default',
        animation: 'gnosis-toast-in 200ms ease',
      }}
    >
      <span style={{ flex: 1 }}>{item.message}</span>
      <button
        onClick={() => onDismiss(item.id)}
        style={{ opacity: 0.6, lineHeight: 1, background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const [toasts, setToasts] = React.useState<ToastItem[]>([..._store.toasts]);
  React.useEffect(() => {
    const unsub = _store.subscribe(setToasts);
    return unsub;
  }, []);

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        alignItems: 'flex-end',
        pointerEvents: 'none',
      }}
    >
      <style>{`
        @keyframes gnosis-toast-in {
          from { opacity: 0; transform: translateY(8px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0)   scale(1); }
        }
      `}</style>
      {toasts.map((t) => (
        <ToastItem key={t.id} item={t} onDismiss={_store.remove.bind(_store)} />
      ))}
    </div>
  );
}

export function mountToastContainer() {
  if (typeof document === 'undefined') return;
  const existing = document.getElementById('gnosis-toast-root');
  if (existing) return;
  const root = document.createElement('div');
  root.id = 'gnosis-toast-root';
  document.body.appendChild(root);
  // Dynamic import to avoid circular deps at module init time
  void import('react-dom/client').then(({ createRoot }) => {
    createRoot(root).render(
      React.createElement(ToastContainer)
    );
  });
}
