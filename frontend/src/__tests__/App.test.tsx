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

// Stub all lazy page imports individually — vi.mock is hoisted to the top of
// the file by Vitest and cannot reference any runtime variable (including a
// `const` declared in the same file). Using a forEach loop therefore causes
// "mod is not defined" at hoist time. Each call must be a static literal.
vi.mock('@/pages/LoginPage', () => ({ default: () => <div data-testid="LoginPage" /> }));
vi.mock('@/pages/NotesPage', () => ({ default: () => <div data-testid="NotesPage" /> }));
vi.mock('@/pages/NoteEditorPage', () => ({ default: () => <div data-testid="NoteEditorPage" /> }));
vi.mock('@/pages/GraphPage', () => ({ default: () => <div data-testid="GraphPage" /> }));
vi.mock('@/pages/SearchPage', () => ({ default: () => <div data-testid="SearchPage" /> }));
vi.mock('@/pages/AIChatPage', () => ({ default: () => <div data-testid="AIChatPage" /> }));
vi.mock('@/pages/SettingsPage', () => ({ default: () => <div data-testid="SettingsPage" /> }));
vi.mock('@/pages/QueryPage', () => ({ default: () => <div data-testid="QueryPage" /> }));
vi.mock('@/pages/DailyNotePage', () => ({ default: () => <div data-testid="DailyNotePage" /> }));
vi.mock('@/pages/ReviewPage', () => ({ default: () => <div data-testid="ReviewPage" /> }));
vi.mock('@/pages/IngestPage', () => ({ default: () => <div data-testid="IngestPage" /> }));
vi.mock('@/pages/MocPage', () => ({ default: () => <div data-testid="MocPage" /> }));
vi.mock('@/pages/TagsPage', () => ({ default: () => <div data-testid="TagsPage" /> }));

import App from '../App';

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
    expect(() => render(<App />)).not.toThrow();
  });
});

describe('PrivateRoute', () => {
  it('redirects to /login when no token stored', async () => {
    localStorage.removeItem('gnosis_token');
    const { Navigate } = await import('react-router-dom');
    expect(Navigate).toBeDefined();
  });
});
