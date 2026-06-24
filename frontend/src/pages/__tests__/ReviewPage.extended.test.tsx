/**
 * ReviewPage.extended.test.tsx
 *
 * ReviewPage.tsx calls native fetch() directly.
 * Fix: vi.stubGlobal('fetch', ...) in beforeEach.
 *
 * Critical: all waitFor callbacks use expect().toBeTruthy() so waitFor
 * retries on failure. queryByText/queryByRole return null (no throw)
 * and would exit waitFor immediately without the assertion wrapper.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('@/services/api', () => ({
  default: {
    listNotes: vi.fn().mockResolvedValue({ items: [] }),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import ReviewPage from '@/pages/ReviewPage';

const DUE_CARDS = [
  {
    note_id: 'note-1',
    note_title: 'What is Sunyata?',
    note_body: 'Sunyata refers to the absence of inherent existence.',
    note_folder: '10-zettelkasten',
    note_tags: ['buddhism', 'madhyamaka'],
    easiness: 2.5,
    interval: 1,
    repetitions: 0,
    due_date: '2026-01-01T00:00:00Z',
    last_quality: null,
  },
];

const STATS = {
  due_today: 1,
  due_this_week: 3,
  total_enrolled: 10,
  new_today: 0,
  reviewed_today: 0,
};

function makeFetchMock(queue: unknown[], stats = STATS) {
  return vi.fn().mockImplementation((url: string) => {
    const u = String(url);
    if (u.includes('/review/queue')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(queue) });
    }
    if (u.includes('/review/stats')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(stats) });
    }
    // POST rating — matches /review/{id}
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter>
        <ReviewPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('fetch', makeFetchMock(DUE_CARDS));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('ReviewPage — loading + empty', () => {
  it('shows loading state initially', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    renderPage();
    // Loading spinner renders synchronously before fetch resolves
    expect(document.body.textContent).toMatch(/loading queue/i);
  });

  it('shows "Nothing due today" when queue is empty', async () => {
    vi.stubGlobal('fetch', makeFetchMock([]));
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText(/nothing due today/i)).toBeTruthy()
    );
  });
});

describe('ReviewPage — card interaction', () => {
  it('renders card title after queue loads', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('What is Sunyata?')).toBeTruthy()
    );
  });

  it('reveals rating buttons after clicking Rate recall', async () => {
    renderPage();
    // Wait for queue to load and card title to appear
    await waitFor(() =>
      expect(screen.queryByText('What is Sunyata?')).toBeTruthy()
    );
    fireEvent.click(screen.getByRole('button', { name: /rate recall/i }));
    await waitFor(() =>
      expect(screen.queryByText('Perfect')).toBeTruthy()
    );
  });

  it('calls fetch POST when rating button clicked', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('What is Sunyata?')).toBeTruthy()
    );
    fireEvent.click(screen.getByRole('button', { name: /rate recall/i }));
    await waitFor(() =>
      expect(screen.queryByText('Perfect')).toBeTruthy()
    );
    const ratingBtns = screen.queryAllByRole('button');
    const perfectBtn = ratingBtns.find((b) => b.textContent?.includes('Perfect'));
    if (perfectBtn) {
      fireEvent.click(perfectBtn);
      await waitFor(() =>
        expect(vi.mocked(fetch)).toHaveBeenCalledWith(
          expect.stringContaining('/review/note-1'),
          expect.objectContaining({ method: 'POST' })
        )
      );
    }
  });
});

describe('ReviewPage — skip', () => {
  it('skip button advances to session complete when only 1 card', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('What is Sunyata?')).toBeTruthy()
    );
    fireEvent.click(screen.getByRole('button', { name: /rate recall/i }));
    await waitFor(() =>
      expect(screen.queryByText('Skip')).toBeTruthy()
    );
    fireEvent.click(screen.getByText('Skip'));
    await waitFor(() =>
      expect(screen.queryByText(/session complete|nothing due/i)).toBeTruthy()
    );
  });
});

describe('ReviewPage — error state', () => {
  it('shows "Failed to load review queue" when fetch rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText(/failed to load review queue/i)).toBeTruthy()
    );
  });
});
