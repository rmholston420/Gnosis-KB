import '@testing-library/jest-dom';
import { vi } from 'vitest';

// ── ResizeObserver polyfill (required by cmdk and react-force-graph) ──────────
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// ── IntersectionObserver polyfill ─────────────────────────────────────────────
global.IntersectionObserver = class IntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  root = null;
  rootMargin = '';
  thresholds = [];
  takeRecords() { return []; }
} as unknown as typeof IntersectionObserver;

// ── localStorage mock (jsdom blocks localStorage in some sandboxed envs) ──────
const _store: Record<string, string> = {};
const localStorageMock = {
  getItem: (key: string) => _store[key] ?? null,
  setItem: (key: string, value: string) => { _store[key] = value; },
  removeItem: (key: string) => { delete _store[key]; },
  clear: () => { Object.keys(_store).forEach(k => delete _store[k]); },
  get length() { return Object.keys(_store).length; },
  key: (index: number) => Object.keys(_store)[index] ?? null,
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// ── window.matchMedia stub ────────────────────────────────────────────────────
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
