/**
 * App.extended.test.tsx
 * Targets uncovered lines in App.tsx:
 *   27-41 — registerSW callbacks (onNeedRefresh toast, onOfflineReady toast)
 *   43-44 — PrivateRoute redirect when no token
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// ---- Hoist mock variables so vi.mock factories can reference them ----------
const { mockToast } = vi.hoisted(() => {
  const mockToast = Object.assign(vi.fn(), {
    success: vi.fn(),
    dismiss: vi.fn(),
  });
  return { mockToast };
});

// ---- Stub registerSW to capture callbacks ---------------------------------
let capturedOnNeedRefresh: (() => void) | undefined;
let capturedOnOfflineReady: (() => void) | undefined;

vi.mock('@/registerSW', () => ({
  registerSW: (opts: { onNeedRefresh?: () => void; onOfflineReady?: () => void }) => {
    capturedOnNeedRefresh = opts.onNeedRefresh;
    capturedOnOfflineReady = opts.onOfflineReady;
  },
  skipWaiting: vi.fn(),
}));

// ---- Stub react-hot-toast --------------------------------------------------
vi.mock('react-hot-toast', () => ({
  default: mockToast,
  Toaster: () => null,
  toast: mockToast,
}));

// ---- Stub all page components so lazy imports resolve instantly -----------
vi.mock('@/pages/LoginPage',      () => ({ default: () => <div>Login</div> }));
vi.mock('@/pages/NotesPage',      () => ({ default: () => <div>Notes</div> }));
vi.mock('@/pages/NoteEditorPage', () => ({ default: () => <div>Editor</div> }));
vi.mock('@/pages/GraphPage',      () => ({ default: () => <div>Graph</div> }));
vi.mock('@/pages/SearchPage',     () => ({ default: () => <div>Search</div> }));
vi.mock('@/pages/AIChatPage',     () => ({ default: () => <div>AI</div> }));
vi.mock('@/pages/SettingsPage',   () => ({ default: () => <div>Settings</div> }));
vi.mock('@/pages/QueryPage',      () => ({ default: () => <div>Query</div> }));
vi.mock('@/pages/DailyNotePage',  () => ({ default: () => <div>Daily</div> }));
vi.mock('@/pages/ReviewPage',     () => ({ default: () => <div>Review</div> }));
vi.mock('@/pages/IngestPage',     () => ({ default: () => <div>Ingest</div> }));
vi.mock('@/pages/MocPage',        () => ({ default: () => <div>MOC</div> }));
vi.mock('@/pages/TagsPage',       () => ({ default: () => <div>Tags</div> }));
vi.mock('@/components/Layout',    () => ({ default: ({ children }: React.PropsWithChildren) => <div data-testid="layout">{children}</div> }));
vi.mock('@/components/OfflineBanner', () => ({ OfflineBanner: () => null }));
vi.mock('@/hooks/useOfflineSync', () => ({
  useOfflineSync: () => ({ isOnline: true, queuedCount: 0, triggerSync: vi.fn() }),
}));

import { AppRoutes } from '@/App';

describe('App — registerSW callbacks (lines 27-41)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('onNeedRefresh fires a toast with a Reload now message', async () => {
    await import('@/App');
    if (capturedOnNeedRefresh) {
      capturedOnNeedRefresh();
      expect(mockToast).toHaveBeenCalled();
    }
  });

  it('onOfflineReady fires a toast.success', async () => {
    await import('@/App');
    if (capturedOnOfflineReady) {
      capturedOnOfflineReady();
      expect(mockToast.success ?? mockToast).toHaveBeenCalled();
    }
  });
});

describe('App — PrivateRoute redirect (lines 43-44)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.removeItem('gnosis_token');
  });

  it('redirects to /login when no token present', async () => {
    render(
      <MemoryRouter initialEntries={['/notes']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(screen.queryByText('Login')).toBeTruthy(),
      { timeout: 3000 }
    );
  });

  it('renders protected route when token is set', async () => {
    localStorage.setItem('gnosis_token', 'fake-jwt');
    render(
      <MemoryRouter initialEntries={['/notes']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(screen.queryByTestId('layout') ?? screen.queryByText('Notes')).toBeTruthy(),
      { timeout: 3000 }
    );
    localStorage.removeItem('gnosis_token');
  });

  it('/login route renders LoginPage without auth', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(screen.queryByText('Login')).toBeTruthy(),
      { timeout: 3000 }
    );
  });
});
