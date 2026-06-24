import '@testing-library/jest-dom';
import { vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock axios globally so the transformRequest function (which contains a
// closure) is never serialized across Vitest worker threads.  Without this
// mock, any test that indirectly imports a module which imports axios triggers
// a DataCloneError when Vitest tries to post the module to its worker.
// ---------------------------------------------------------------------------
vi.mock('axios', () => {
  const mockAxios: Record<string, unknown> = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
    interceptors: {
      request: { use: vi.fn(), eject: vi.fn() },
      response: { use: vi.fn(), eject: vi.fn() },
    },
    defaults: { headers: { common: {} } },
  };
  return { default: mockAxios, ...mockAxios };
});

// Silence noisy console.error output from React during tests
const originalError = console.error.bind(console);
console.error = (...args: unknown[]) => {
  if (
    typeof args[0] === 'string' &&
    (args[0].includes('Warning:') || args[0].includes('ReactDOM.render'))
  ) return;
  originalError(...args);
};
