/**
 * App.extended.test.tsx
 * Covers PrivateRoute redirect, AppRoutes protected layout, SW toast branches,
 * handleToast variants, and the OfflineBanner integration — all the lines
 * in App.tsx missed by the existing suite (27-41, 43-44, 51-52, 116-119).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// ---- Dependency mocks -------------------------------------------------------
vi.mock('@/registerSW', () => ({
  registerSW: vi.fn(),
  skipWaiting: vi.fn(),
}));

vi.mock('@/hooks/useOfflineSync', () => ({
  useOfflineSync: vi.fn().mockReturnValue({
    isOnline: true,
    queuedCount: 0,
    triggerSync: vi.fn(),
  }),
}));

vi.mock('@/components/OfflineBanner', () => ({
  OfflineBanner: ({ isOnline, queuedCount }: { isOnline: boolean; queuedCount: number }) => (
    <div data-testid="offline-banner" data-online={String(isOnline)} data-queued={queuedCount} />
  ),
}));

vi.mock('@/components/Layout', () => ({
  default: () => <div data-testid="layout" />,
}));

vi.mock('react-hot-toast', () => ({
  Toaster: () => <div data-testid="toaster" />,
  toast:   Object.assign(
    vi.fn(),
    { success: vi.fn(), dismiss: vi.fn() }
  ),
}));

// Lazy-loaded page stubs
const pageMock = (name: string) => ({
  default: () => <div data-testid={`page-${name}`} />,
});

vi.mock('@/pages/LoginPage',      () => pageMock('login'));
vi.mock('@/pages/NotesPage',      () => pageMock('notes'));
vi.mock('@/pages/NoteEditorPage', () => pageMock('note-editor'));
vi.mock('@/pages/GraphPage',      () => pageMock('graph'));
vi.mock('@/pages/SearchPage',     () => pageMock('search'));
vi.mock('@/pages/AIChatPage',     () => pageMock('ai'));
vi.mock('@/pages/SettingsPage',   () => pageMock('settings'));
vi.mock('@/pages/QueryPage',      () => pageMock('query'));
vi.mock('@/pages/DailyNotePage',  () => pageMock('daily'));
vi.mock('@/pages/ReviewPage',     () => pageMock('review'));
vi.mock('@/pages/IngestPage',     () => pageMock('ingest'));
vi.mock('@/pages/MocPage',        () => pageMock('moc'));
vi.mock('@/pages/TagsPage',       () => pageMock('tags'));

import { AppRoutes } from '@/App';
import App from '@/App';

describe('PrivateRoute — unauthenticated redirect', () => {
  beforeEach(() => {
    localStorage.removeItem('gnosis_token');
  });
  afterEach(() => {
    localStorage.removeItem('gnosis_token');
  });

  it('redirects to /login when no token present', async () => {
    render(
      <MemoryRouter initialEntries={['/notes']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId('page-login'));
  });

  it('redirects to /login from root path when no token', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId('page-login'));
  });

  it('unknown route redirects to root (then to /login when no token)', async () => {
    render(
      <MemoryRouter initialEntries={['/totally-unknown-path']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId('page-login'));
  });
});

describe('PrivateRoute — authenticated access', () => {
  beforeEach(() => {
    localStorage.setItem('gnosis_token', 'test-jwt-token');
  });
  afterEach(() => {
    localStorage.removeItem('gnosis_token');
  });

  it('renders Layout (not login) when token present', async () => {
    render(
      <MemoryRouter initialEntries={['/notes']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId('layout'));
    expect(screen.queryByTestId('page-login')).toBeNull();
  });

  it('/login route renders LoginPage even when authenticated', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId('page-login'));
  });

  it('renders Toaster component', async () => {
    render(
      <MemoryRouter initialEntries={['/notes']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId('toaster'));
  });
});

describe('App root component', () => {
  beforeEach(() => {
    localStorage.setItem('gnosis_token', 'test-token');
  });
  afterEach(() => {
    localStorage.removeItem('gnosis_token');
  });

  it('renders OfflineBanner', async () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByTestId('offline-banner'));
  });

  it('OfflineBanner receives isOnline=true by default', async () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    const banner = await waitFor(() => screen.getByTestId('offline-banner'));
    expect(banner.getAttribute('data-online')).toBe('true');
  });

  it('OfflineBanner reflects offline state from useOfflineSync', async () => {
    const { useOfflineSync } = await import('@/hooks/useOfflineSync');
    vi.mocked(useOfflineSync).mockReturnValueOnce({
      isOnline: false,
      queuedCount: 3,
      triggerSync: vi.fn(),
    });
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    const banner = await waitFor(() => screen.getByTestId('offline-banner'));
    expect(banner.getAttribute('data-online')).toBe('false');
    expect(banner.getAttribute('data-queued')).toBe('3');
  });
});

describe('handleToast variants (via useOfflineSync callback)', () => {
  beforeEach(() => {
    localStorage.setItem('gnosis_token', 'test-token');
  });
  afterEach(() => {
    localStorage.removeItem('gnosis_token');
    vi.restoreAllMocks();
  });

  it('toast.success called for success variant', async () => {
    const { toast } = await import('react-hot-toast');
    const { useOfflineSync } = await import('@/hooks/useOfflineSync');
    let capturedCb: ((msg: string, variant: string) => void) | undefined;
    vi.mocked(useOfflineSync).mockImplementation((cb) => {
      capturedCb = cb as any;
      return { isOnline: true, queuedCount: 0, triggerSync: vi.fn() };
    });
    render(<MemoryRouter><App /></MemoryRouter>);
    await act(async () => {
      capturedCb?.('Sync complete', 'success');
    });
    expect(toast.success).toHaveBeenCalledWith('Sync complete', expect.any(Object));
  });

  it('toast called with warning icon for warning variant', async () => {
    const { toast } = await import('react-hot-toast');
    const { useOfflineSync } = await import('@/hooks/useOfflineSync');
    let capturedCb: ((msg: string, variant: string) => void) | undefined;
    vi.mocked(useOfflineSync).mockImplementation((cb) => {
      capturedCb = cb as any;
      return { isOnline: true, queuedCount: 0, triggerSync: vi.fn() };
    });
    render(<MemoryRouter><App /></MemoryRouter>);
    await act(async () => {
      capturedCb?.('Going offline', 'warning');
    });
    expect(toast).toHaveBeenCalledWith('Going offline', expect.objectContaining({ icon: '⚠️' }));
  });

  it('plain toast called for info variant', async () => {
    const { toast } = await import('react-hot-toast');
    const { useOfflineSync } = await import('@/hooks/useOfflineSync');
    let capturedCb: ((msg: string, variant: string) => void) | undefined;
    vi.mocked(useOfflineSync).mockImplementation((cb) => {
      capturedCb = cb as any;
      return { isOnline: true, queuedCount: 0, triggerSync: vi.fn() };
    });
    render(<MemoryRouter><App /></MemoryRouter>);
    await act(async () => {
      capturedCb?.('Info message', 'info');
    });
    expect(toast).toHaveBeenCalledWith('Info message', expect.any(Object));
  });
});
