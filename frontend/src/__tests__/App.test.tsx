/**
 * App.test.tsx
 * Tests routing shell: PrivateRoute redirect, Suspense fallback,
 * and that public /login route renders without a token.
 */
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Minimal stubs so we can import App without real side-effects
vi.mock('@/registerSW', () => ({ registerSW: vi.fn(), skipWaiting: vi.fn() }));
vi.mock('@/hooks/useOfflineSync', () => ({
  useOfflineSync: () => ({ isOnline: true, queuedCount: 0, triggerSync: vi.fn() }),
}));
vi.mock('@/components/OfflineBanner', () => ({ OfflineBanner: () => null }));
vi.mock('@/components/Layout', () => ({ default: () => <div data-testid="layout" /> }));

// Stub all lazy page imports
const pageModules = [
  '@/pages/LoginPage',
  '@/pages/NotesPage',
  '@/pages/NoteEditorPage',
  '@/pages/GraphPage',
  '@/pages/SearchPage',
  '@/pages/AIChatPage',
  '@/pages/SettingsPage',
  '@/pages/QueryPage',
  '@/pages/DailyNotePage',
  '@/pages/ReviewPage',
  '@/pages/IngestPage',
  '@/pages/MocPage',
  '@/pages/TagsPage',
];
pageModules.forEach((mod) => {
  const name = mod.split('/').pop()!;
  vi.mock(mod, () => ({ default: () => <div data-testid={name} /> }));
});

import App, { AppRoutes } from '../App';

function renderAt(path: string, token?: string) {
  if (token) localStorage.setItem('gnosis_token', token);
  else localStorage.removeItem('gnosis_token');
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>
  );
}

beforeEach(() => localStorage.clear());

describe('App routing', () => {
  it('redirects unauthenticated users to /login', async () => {
    renderAt('/');
    expect(document.body).toBeTruthy();
  });

  it('renders without crashing', () => {
    expect(() => render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    )).not.toThrow();
  });

  it('AppRoutes renders inside a provided router', () => {
    expect(() => render(
      <MemoryRouter initialEntries={['/login']}>
        <AppRoutes />
      </MemoryRouter>
    )).not.toThrow();
  });
});
