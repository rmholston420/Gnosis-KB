/**
 * App.extended.test.tsx
 * Covers the previously-untested lines in App.tsx:
 *   27-41  registerSW callbacks (onNeedRefresh, onOfflineReady toast)
 *   43-44  PrivateRoute — unauthenticated redirect to /login
 *   51-52  PrivateRoute — authenticated pass-through
 *   116-119 App default export — OfflineBanner + AppRoutes rendered
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// ── registerSW stub ────────────────────────────────────────────────────────
const { mockRegisterSW, mockSkipWaiting } = vi.hoisted(() => {
  const mockRegisterSW = vi.fn();
  const mockSkipWaiting = vi.fn();
  return { mockRegisterSW, mockSkipWaiting };
});

vi.mock('@/registerSW', () => ({
  registerSW: mockRegisterSW,
  skipWaiting: mockSkipWaiting,
}));

// ── toast stub ─────────────────────────────────────────────────────────────
const { mockToast } = vi.hoisted(() => {
  const mockToast = vi.fn() as any;
  mockToast.success = vi.fn();
  mockToast.dismiss = vi.fn();
  return { mockToast };
});

vi.mock('react-hot-toast', () => ({
  Toaster: () => <div data-testid="toaster" />,
  toast: mockToast,
}));

// ── useOfflineSync stub ─────────────────────────────────────────────────────
const { mockOfflineSync } = vi.hoisted(() => {
  const mockOfflineSync = vi.fn().mockReturnValue({
    isOnline: true, queuedCount: 0, triggerSync: vi.fn(),
  });
  return { mockOfflineSync };
});
vi.mock('@/hooks/useOfflineSync', () => ({ useOfflineSync: mockOfflineSync }));

// ── OfflineBanner stub ─────────────────────────────────────────────────────
vi.mock('@/components/OfflineBanner', () => ({
  OfflineBanner: ({ isOnline }: { isOnline: boolean }) =>
    <div data-testid="offline-banner" data-online={String(isOnline)} />,
}));

// ── Layout + all lazy page stubs ───────────────────────────────────────────
vi.mock('@/components/Layout', () => ({
  default: () => <div data-testid="layout" />,
}));
vi.mock('@/pages/LoginPage',      () => ({ default: () => <div data-testid="login-page" /> }));
vi.mock('@/pages/NotesPage',      () => ({ default: () => <div data-testid="notes-page" /> }));
vi.mock('@/pages/NoteEditorPage', () => ({ default: () => <div data-testid="editor-page" /> }));
vi.mock('@/pages/GraphPage',      () => ({ default: () => <div data-testid="graph-page" /> }));
vi.mock('@/pages/SearchPage',     () => ({ default: () => <div data-testid="search-page" /> }));
vi.mock('@/pages/AIChatPage',     () => ({ default: () => <div data-testid="ai-page" /> }));
vi.mock('@/pages/SettingsPage',   () => ({ default: () => <div data-testid="settings-page" /> }));
vi.mock('@/pages/QueryPage',      () => ({ default: () => <div data-testid="query-page" /> }));
vi.mock('@/pages/DailyNotePage',  () => ({ default: () => <div data-testid="daily-page" /> }));
vi.mock('@/pages/ReviewPage',     () => ({ default: () => <div data-testid="review-page" /> }));
vi.mock('@/pages/IngestPage',     () => ({ default: () => <div data-testid="ingest-page" /> }));
vi.mock('@/pages/MocPage',        () => ({ default: () => <div data-testid="moc-page" /> }));
vi.mock('@/pages/TagsPage',       () => ({ default: () => <div data-testid="tags-page" /> }));

import App, { AppRoutes } from '@/App';

beforeEach(() => {
  vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
  mockRegisterSW.mockClear();
  mockToast.mockClear();
  mockToast.success.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── registerSW callbacks ───────────────────────────────────────────────────
describe('registerSW callbacks (lines 27-41)', () => {
  it('registerSW is called on module load', () => {
    expect(mockRegisterSW).toHaveBeenCalled();
  });

  it('onNeedRefresh callback fires a toast with Reload button', () => {
    const [[{ onNeedRefresh }]] = mockRegisterSW.mock.calls;
    onNeedRefresh();
    expect(mockToast).toHaveBeenCalled();
    const renderFn = mockToast.mock.calls[0][0];
    if (typeof renderFn === 'function') {
      const el = renderFn({ id: 'sw-update' });
      const { getByText } = render(el);
      const btn = getByText(/reload now/i);
      fireEvent.click(btn);
      expect(mockSkipWaiting).toHaveBeenCalled();
    }
  });

  it('onOfflineReady callback calls toast.success', () => {
    const [[{ onOfflineReady }]] = mockRegisterSW.mock.calls;
    onOfflineReady();
    expect(mockToast.success).toHaveBeenCalledWith(
      expect.stringMatching(/offline/i),
      expect.objectContaining({ id: 'sw-ready' }),
    );
  });
});

// ── PrivateRoute ───────────────────────────────────────────────────────────
describe('PrivateRoute (lines 43-52)', () => {
  it('redirects to /login when no token', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    render(
      <MemoryRouter initialEntries={['/notes']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    );
  });

  it('renders Layout when token is present', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue('some-jwt');
    render(
      <MemoryRouter initialEntries={['/notes']}>
        <AppRoutes />
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(screen.getByTestId('layout')).toBeInTheDocument()
    );
  });
});

// ── App default export (lines 116-119) ────────────────────────────────────
describe('App default export (lines 116-119)', () => {
  it('renders OfflineBanner and AppRoutes', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByTestId('offline-banner')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId('login-page')).toBeInTheDocument()
    );
  });

  it('passes isOnline=false from useOfflineSync to OfflineBanner', () => {
    mockOfflineSync.mockReturnValueOnce({
      isOnline: false, queuedCount: 3, triggerSync: vi.fn(),
    });
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByTestId('offline-banner').getAttribute('data-online')).toBe('false');
  });
});
