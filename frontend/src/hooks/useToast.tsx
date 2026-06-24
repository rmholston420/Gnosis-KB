/**
 * useToast
 * ========
 * Lightweight, dependency-free toast notification system.
 * Renders a fixed portal of toasts in the bottom-right corner.
 *
 * Usage (imperative, anywhere in the app):
 *   import { toast } from '../hooks/useToast';
 *   toast.success('Note saved');
 *   toast.error('Something went wrong');
 *   toast.info('Syncing 3 offline changes…');
 *
 * Usage (in a component, for reactive rendering):
 *   import { useToast, ToastContainer } from '../hooks/useToast';
 *   // render <ToastContainer /> once in your root layout
 *
 * The store is a plain Zustand slice so it works outside React trees.
 */

import { useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import React from 'react';

export type ToastVariant = 'success' | 'error' | 'info' | 'warning';

export interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
  duration: number;
}

// ---------------------------------------------------------------------------
// In-memory store (no Zustand dep needed — just a plain observable)
// ---------------------------------------------------------------------------

type Listener = (toasts: ToastItem[]) => void;

const _store = {
  toasts: [] as ToastItem[],
  listeners: new Set<Listener>(),

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => { this.listeners.delete(fn); };
  },

  _emit() {
    for (const fn of this.listeners) fn([...this.toasts]);
  },

  add(message: string, variant: ToastVariant, duration = 4000) {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    this.toasts = [...this.toasts, { id, message, variant, duration }];
    this._emit();
    if (duration > 0) {
      setTimeout(() => this.remove(id), duration);
    }
  },

  remove(id: string) {
    this.toasts = this.toasts.filter((t) => t.id !== id);
    this._emit();
  },
};

// ---------------------------------------------------------------------------
// Imperative API
// ---------------------------------------------------------------------------

export const toast = {
  success: (message: string, duration?: number) => _store.add(message, 'success', duration),
  error:   (message: string, duration?: number) => _store.add(message, 'error',   duration),
  info:    (message: string, duration?: number) => _store.add(message, 'info',    duration),
  warning: (message: string, duration?: number) => _store.add(message, 'warning', duration),
  dismiss: (id: string)                         => _store.remove(id),
};

// ---------------------------------------------------------------------------
// Hook for reactive components
// ---------------------------------------------------------------------------

export function useToast() {
  const toastRef = useRef<typeof toast>(toast);
  return toastRef.current;
}

// ---------------------------------------------------------------------------
// Single toast item renderer
// ---------------------------------------------------------------------------

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
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-2)',
        padding: 'var(--space-3) var(--space-4)',
        borderRadius: 'var(--radius-md)',
        fontSize: 'var(--text-sm)',
        fontWeight: 500,
        pointerEvents: 'auto',
        minWidth: '240px',
        maxWidth: '420px',
        boxShadow: 'var(--shadow-md)',
        ...VARIANT_STYLES[item.variant],
      }}
    >
      <span style={{ flex: 1 }}>{item.message}</span>
      <button
        onClick={() => onDismiss(item.id)}
        aria-label="Dismiss"
        style={{
          color: 'var(--color-text-faint)',
          fontSize: 'var(--text-sm)',
          padding: '0 var(--space-1)',
          flexShrink: 0,
          lineHeight: 1,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
        }}
      >
        ×
      </button>
    </div>
  );
}

export function ToastContainer() {
  const [toasts, setToasts] = React.useState<ToastItem[]>([..._store.toasts]);

  useEffect(() => {
    const unsub = _store.subscribe(setToasts);
    return () => { unsub(); };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-label="Notifications"
      style={{
        position: 'fixed',
        bottom: 'var(--space-6)',
        right: 'var(--space-6)',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-2)',
        pointerEvents: 'none',
      }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} item={t} onDismiss={_store.remove.bind(_store)} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mount helper — call once at app root if not using ToastContainer directly
// ---------------------------------------------------------------------------

let _mounted = false;
export function mountToastContainer() {
  if (_mounted) return;
  _mounted = true;
  const el = document.createElement('div');
  el.id = 'gnosis-toast-root';
  document.body.appendChild(el);
  createRoot(el).render(<ToastContainer />);
}
