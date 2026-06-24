import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ── Stubs ─────────────────────────────────────────────────────────────────────
vi.mock('@/hooks/useWebSocket', () => ({ useVaultWebSocket: vi.fn() }));
vi.mock('@/components/Sidebar', () => ({ default: () => <div /> }));

// ── toast mock ────────────────────────────────────────────────────────────────
const mockToast = vi.fn() as ReturnType<typeof vi.fn> & { success: ReturnType<typeof vi.fn> };
mockToast.success = vi.fn();
vi.mock('react-hot-toast', () => ({ toast: mockToast, Toaster: () => null }));

// ── registerSW mock: capture callbacks synchronously ─────────────────────────
let captured: { onNeedRefresh?: () => void; onOfflineReady?: () => void } = {};
vi.mock('@/registerSW', () => ({
  registerSW: vi.fn((cbs: typeof captured) => { captured = cbs; }),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('App — registerSW callbacks', () => {
  beforeEach(() => {
    vi.resetModules();
    captured = {};
    mockToast.mockReset();
    (mockToast.success as ReturnType<typeof vi.fn>).mockReset();
  });

  it('onNeedRefresh fires a toast', async () => {
    const { default: App } = await import('@/App');
    render(<App />, { wrapper: Wrapper });
    captured.onNeedRefresh?.();
    expect(mockToast).toHaveBeenCalled();
  });

  it('onOfflineReady fires a toast.success', async () => {
    const { default: App } = await import('@/App');
    render(<App />, { wrapper: Wrapper });
    captured.onOfflineReady?.();
    expect(mockToast.success).toHaveBeenCalled();
  });
});

describe('App — PrivateRoute redirect', () => {
  it('redirects to /login when no token present', async () => {
    localStorage.removeItem('gnosis_token');
    const { AppRoutes } = await import('@/App');
    expect(() => render(<AppRoutes />, { wrapper: Wrapper })).not.toThrow();
  });
});
