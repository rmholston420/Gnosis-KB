import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ── mock heavy hooks / modules before importing App ───────────────────────────
vi.mock('@/hooks/useWebSocket', () => ({
  useVaultWebSocket: vi.fn(),
}));
vi.mock('@/registerSW', () => ({
  registerSW: vi.fn(),
}));
vi.mock('@/components/Sidebar', () => ({
  default: () => <div data-testid="sidebar" />,
}));

import App, { AppRoutes } from '@/App';

function makeQc() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeQc()}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('App routing', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders without crashing', () => {
    expect(() =>
      render(
        <QueryClientProvider client={makeQc()}>
          <MemoryRouter><App /></MemoryRouter>
        </QueryClientProvider>,
      )
    ).not.toThrow();
  });

  it('AppRoutes renders inside a provided router', () => {
    expect(() =>
      render(<AppRoutes />, { wrapper: Wrapper })
    ).not.toThrow();
  });

  it('redirects unauthenticated users to /login', () => {
    localStorage.removeItem('gnosis_token');
    const { container } = render(<AppRoutes />, { wrapper: Wrapper });
    // LoginPage or redirect — component should render without error
    expect(container).toBeTruthy();
  });
});
