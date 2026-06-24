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

  subscribe(fn: Listener) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  },

  _emit() {
    for (const fn of this.listeners) fn([...this.toasts]);
  },

  add(message: string, variant: ToastVariant, duration = 4000) {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    this.toasts = [...this.toasts, { id, message, variant, duration }];
    this._emit();
    setTimeout(() => this.remove(id), duration);
  },

  remove(id: string) {
    this.toasts = this.toasts.filter((t) => t.id !== id);
    this._emit();
  },
};

/** Imperative API — call anywhere (hooks, service functions, useOfflineSync). */
export const toast = {
  success: (msg: string, duration?: number) => _store.add(msg, 'success', duration),
  error:   (msg: string, duration?: number) => _store.add(msg, 'error', duration),
  info:    (msg: string, duration?: number) => _store.add(msg, 'info', duration),
  warning: (msg: string, duration?: number) => _store.add(msg, 'warning', duration),
};

// ---------------------------------------------------------------------------
// React component
// ---------------------------------------------------------------------------

const VARIANT_STYLES: Record<ToastVariant, { bg: string; icon: string }> = {
  success: { bg: 'var(--color-success)',      icon: '✓' },
  error:   { bg: 'var(--color-error)',         icon: '✕' },
  info:    { bg: 'var(--color-primary)',        icon: 'ℹ' },
  warning: { bg: 'var(--color-warning)',        icon: '⚠' },
};

function ToastItemComponent({ item, onDismiss }: { item: ToastItem; onDismiss: (id: string) => void }) {
  const style = VARIANT_STYLES[item.variant];
  return (
    <div
      role="alert"
      aria-live="assertive"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 'var(--space-3)',
        padding: 'var(--space-3) var(--space-4)',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderLeft: `3px solid ${style.bg}`,
        borderRadius: 'var(--radius-md)',
        boxShadow: 'var(--shadow-md)',
        fontSize: 'var(--text-sm)',
        color: 'var(--color-text)',
        maxWidth: '360px',
        minWidth: '220px',
        animation: 'toast-in 220ms cubic-bezier(0.16,1,0.3,1)',
      }}
    >
      <span
        style={{
          color: style.bg,
          fontWeight: 700,
          flexShrink: 0,
          fontSize: '1rem',
          lineHeight: 1.4,
        }}
        aria-hidden
      >
        {style.icon}
      </span>
      <span style={{ flex: 1, lineHeight: 1.5 }}>{item.message}</span>
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
    return _store.subscribe(setToasts);
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
      <style>{`
        @keyframes toast-in {
          from { opacity: 0; transform: translateY(8px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
      {toasts.map((t) => (
        <div key={t.id} style={{ pointerEvents: 'auto' }}>
          <ToastItemComponent item={t} onDismiss={(id) => _store.remove(id)} />
        </div>
      ))}
    </div>
  );
}

/**
 * mountToastContainer()
 * ---------------------
 * Call once at app startup (e.g. in main.tsx) to inject the ToastContainer
 * into a portal outside the React component tree.  Idempotent.
 */
export function mountToastContainer() {
  if (document.getElementById('gnosis-toast-root')) return;
  const el = document.createElement('div');
  el.id = 'gnosis-toast-root';
  document.body.appendChild(el);
  createRoot(el).render(React.createElement(ToastContainer));
}

export default toast;
