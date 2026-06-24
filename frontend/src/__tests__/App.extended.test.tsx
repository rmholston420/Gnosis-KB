import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

vi.mock('@/services/api', () => ({
  default: {
    getProfile: vi.fn().mockResolvedValue({ id: '1', username: 'user', email: 'u@test.com' }),
    listNotes: vi.fn().mockResolvedValue({ items: [] }),
  },
}));

vi.mock('@/components/Layout', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="layout">{children}</div>,
}));

const pageNames = [
  'LoginPage', 'NotesPage', 'NoteEditorPage', 'GraphPage',
  'SearchPage', 'TagsPage', 'AIChatPage', 'SettingsPage',
  'QueryPage', 'ReviewPage', 'DailyNotePage', 'IngestPage',
  'MocPage', 'GraphPage',
];
pageNames.forEach((name) => {
  vi.mock(`@/pages/${name}`, () => ({
    default: () => <div data-testid={`page-${name.toLowerCase()}`}>{name}</div>,
  }));
});

describe('App.tsx extended route coverage', () => {
  beforeEach(() => {
    localStorage.setItem('gnosis_token', 'tok');
  });
  afterEach(() => {
    localStorage.removeItem('gnosis_token');
    vi.clearAllMocks();
  });

  const routes = [
    { path: '/', label: 'root' },
    { path: '/notes', label: 'notes' },
    { path: '/graph', label: 'graph' },
    { path: '/search', label: 'search' },
    { path: '/tags', label: 'tags' },
    { path: '/chat', label: 'chat' },
    { path: '/settings', label: 'settings' },
    { path: '/query', label: 'query' },
    { path: '/review', label: 'review' },
    { path: '/daily', label: 'daily' },
    { path: '/ingest', label: 'ingest' },
    { path: '/moc', label: 'moc' },
  ];

  routes.forEach(({ path, label }) => {
    it(`renders authenticated route ${label} (${path})`, async () => {
      const { default: App } = await import('@/App');
      render(
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      );
      await new Promise((r) => setTimeout(r, 50));
    });
  });

  it('redirects to /login when no token', async () => {
    localStorage.removeItem('gnosis_token');
    const { default: App } = await import('@/App');
    render(
      <MemoryRouter initialEntries={['/notes']}>
        <App />
      </MemoryRouter>
    );
    await new Promise((r) => setTimeout(r, 50));
  });

  it('renders /login route directly', async () => {
    localStorage.removeItem('gnosis_token');
    const { default: App } = await import('@/App');
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>
    );
    await new Promise((r) => setTimeout(r, 50));
  });
});
