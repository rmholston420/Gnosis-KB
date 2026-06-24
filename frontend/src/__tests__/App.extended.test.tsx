import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const { mockToast, captured } = vi.hoisted(() => {
  const mockToast = Object.assign(vi.fn(), {
    success: vi.fn(),
    dismiss: vi.fn(),
  });
  const captured: { onNeedRefresh?: () => void; onOfflineReady?: () => void } = {};
  return { mockToast, captured };
});

vi.mock('@/registerSW', () => ({
  registerSW: (opts: { onNeedRefresh?: () => void; onOfflineReady?: () => void }) => {
    captured.onNeedRefresh = opts.onNeedRefresh;
    captured.onOfflineReady = opts.onOfflineReady;
  },
  skipWaiting: vi.fn(),
}));

vi.mock('react-hot-toast', () => ({
  default: mockToast,
  Toaster: () => null,
  toast: mockToast,
}));

vi.mock('@/pages/LoginPage', () => ({ default: () => <div>Login</div> }));
vi.mock('@/pages/NotesPage', () => ({ default: () => <div>Notes</div> }));
vi.mock('@/pages/NoteEditorPage', () => ({ default: () => <div>Editor</div> }));
vi.mock('@/pages/GraphPage', () => ({ default: () => <div>Graph</div> }));
vi.mock('@/pages/SearchPage', () => ({ default: () => <div>Search</div> }));
vi.mock('@/pages/AIChatPage', () => ({ default: () => <div>AI</div> }));
vi.mock('@/pages/SettingsPage', () => ({ default: () => <div>Settings</div> }));
vi.mock('@/pages/QueryPage', () => ({ default: () => <div>Query</div> }));
vi.mock('@/pages/DailyNotePage', () => ({ default: () => <div>Daily</div> }));
vi.mock('@/pages/ReviewPage', () => ({ default: () => <div>Review</div> }));
vi.mock('@/pages/IngestPage', () => ({ default: () => <div>Ingest</div> }));
vi.mock('@/pages/MocPage', () => ({ default: () => <div>MOC</div> }));
vi.mock('@/pages/TagsPage', () => ({ default: () => <div>Tags</div> }));
vi.mock('@/components/Layout', () => ({ default: ({ children }: React.PropsWithChildren) => <div data-testid="layout">{children}</div> }));
vi.mock('@/components/OfflineBanner', () => ({ OfflineBanner: () => null }));
vi.mock('@/hooks/useOfflineSync', () => ({
  useOfflineSync: () => ({ isOnline: true, queuedCount: 0, triggerSync: vi.fn() }),
}));

import { AppRoutes } from '@/App';

describe('App — registerSW callbacks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('onNeedRefresh fires a toast', async () => {
    await import('@/App');
    captured.onNeedRefresh?.();
    expect(mockToast).toHaveBeenCalled();
  });

  it('onOfflineReady fires a toast.success', async () => {
    await import('@/App');
    captured.onOfflineReady?.();
    expect(mockToast.success).toHaveBeenCalled();
  });
});

describe('App — PrivateRoute redirect', () => {
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
    await waitFor(() => expect(screen.queryByText('Login')).toBeTruthy(), { timeout: 3000 });
  });
});
