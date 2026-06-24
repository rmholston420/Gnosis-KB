/**
 * Vitest global setup — runs before every test file.
 *
 * Responsibilities:
 *  1. Extend expect() with @testing-library/jest-dom matchers
 *     (toBeInTheDocument, toHaveTextContent, etc.)
 *  2. Stub browser APIs that jsdom doesn't implement:
 *     - window.matchMedia  (used by some UI libs)
 *     - ResizeObserver     (used by CodeMirror / cmdk / graph canvas)
 *     - IntersectionObserver
 *     - EventSource        (stubbed per-test; global fallback here)
 *  3. Silence React act() warnings for async state updates in tests
 *  4. Clean up after each test (DOM + Zustand stores reset)
 */

import '@testing-library/jest-dom';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Browser API stubs
// ---------------------------------------------------------------------------

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

// ResizeObserver — used by cmdk, CodeMirror, and canvas-based graph components.
// Must be a proper constructor that returns an object with observe/unobserve/disconnect.
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe:    vi.fn(),
  unobserve:  vi.fn(),
  disconnect: vi.fn(),
})) as unknown as typeof ResizeObserver;

global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe:      vi.fn(),
  unobserve:    vi.fn(),
  disconnect:   vi.fn(),
  root:         null,
  rootMargin:   '',
  thresholds:   [],
  takeRecords:  () => [],
})) as unknown as typeof IntersectionObserver;

// EventSource — global fallback stub; individual tests replace this as needed.
class _EventSourceStub {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  readyState = 0;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror:   ((e: Event) => void) | null = null;
  onopen:    ((e: Event) => void) | null = null;
  constructor(public url: string) {}
  close() { this.readyState = _EventSourceStub.CLOSED; }
  addEventListener    = vi.fn();
  removeEventListener = vi.fn();
  dispatchEvent       = vi.fn();
}
global.EventSource = _EventSourceStub as unknown as typeof EventSource;

// Stub localStorage so api/client.ts interceptors don't crash in jsdom
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem:    (k: string) => store[k] ?? null,
    setItem:    (k: string, v: string) => { store[k] = v; },
    removeItem: (k: string) => { delete store[k]; },
    clear:      () => { store = {}; },
    get length() { return Object.keys(store).length; },
    key:        (i: number) => Object.keys(store)[i] ?? null,
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Prevent jsdom from complaining about window.location.href assignments
Object.defineProperty(window, 'location', {
  writable: true,
  value: { ...window.location, href: 'http://localhost/', origin: 'http://localhost' },
});

// ---------------------------------------------------------------------------
// Auto-cleanup
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
  localStorageMock.clear();
  vi.clearAllMocks();
});
