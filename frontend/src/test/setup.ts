/**
 * Vitest global setup — runs before every test file.
 *
 * Responsibilities:
 *  1. Extend expect() with @testing-library/jest-dom matchers
 *     (toBeInTheDocument, toHaveTextContent, etc.)
 *  2. Stub browser APIs that jsdom doesn't implement:
 *     - window.matchMedia  (used by some UI libs)
 *     - ResizeObserver     (used by CodeMirror / graph canvas)
 *     - IntersectionObserver
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

global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
})) as unknown as typeof ResizeObserver;

global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
  root: null,
  rootMargin: '',
  thresholds: [],
  takeRecords: () => [],
})) as unknown as typeof IntersectionObserver;

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
  value: { ...window.location, href: 'http://localhost/' },
});

// ---------------------------------------------------------------------------
// Auto-cleanup
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
  localStorageMock.clear();
  vi.clearAllMocks();
});
