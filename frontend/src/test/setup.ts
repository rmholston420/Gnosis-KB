import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeAll } from 'vitest';

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// scrollIntoView polyfill
// jsdom does not implement scrollIntoView; cmdk and other scroll-aware libs
// call it during keyboard navigation, which causes crashes in tests.
// ---------------------------------------------------------------------------
beforeAll(() => {
  if (typeof window !== 'undefined') {
    window.HTMLElement.prototype.scrollIntoView = function () { /* no-op */ };
    // Also patch Element for non-HTMLElement cases
    if (!Element.prototype.scrollIntoView) {
      Element.prototype.scrollIntoView = function () { /* no-op */ };
    }
  }
});

// ---------------------------------------------------------------------------
// matchMedia stub — jsdom ships without this; many UI libs depend on it.
// ---------------------------------------------------------------------------
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// ---------------------------------------------------------------------------
// ResizeObserver stub — used by several layout-aware components.
// ---------------------------------------------------------------------------
if (typeof window.ResizeObserver === 'undefined') {
  window.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
