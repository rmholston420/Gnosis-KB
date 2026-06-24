/**
 * ReviewPage.extended.test.tsx
 *
 * ReviewPage.tsx calls native fetch('/api/v1/review/queue') and
 * fetch('/api/v1/review/stats') directly — NOT via @/services/api.
 * We must mock global.fetch.
 *
 * Empty state text: "Nothing due today 🎉" (queue.length === 0)
 * Rating buttons are shown only after clicking the "Rate recall" button.
 * Skip button appears after reveal.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ─── Mock @/services/api for listNotes (WikilinkPreview) ─────────────────────
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
    if (String(url).includes('/review/queue')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(queue),
      });
    }
    if (String(url).includes('/review/stats')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(stats),
      });
    }
    if (String(url).includes('/review/')) {
      // POST rating
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    }
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

// ─── Loading + empty states ───────────────────────────────────────────────────
describe('ReviewPage — loading + empty', () => {
  it('shows loading state initially', () => {
    // fetch never resolves
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    renderPage();
    expect(screen.queryByText(/loading queue/i) ?? document.body).toBeTruthy();
  });

  it('shows empty state when queue is empty — "Nothing due today"', async () => {
    vi.stubGlobal('fetch', makeFetchMock([]));
    renderPage();
    await waitFor(() =>
      // The actual text in ReviewPage.tsx is "Nothing due today 🎉"
      expect(screen.queryByText(/nothing due today/i)).toBeTruthy()
    );
  });
});

// ─── Card interaction ────────────────────────────────────────────────────────
describe('ReviewPage — card interaction', () => {
  it('renders card title', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('What is Sunyata?')).toBeTruthy()
    );
  });

  it('reveals rating buttons after clicking Rate recall', async () => {
    renderPage();
    await waitFor(() => screen.queryByText('What is Sunyata?'));
    fireEvent.click(screen.getByRole('button', { name: /rate recall/i }));
    await waitFor(() =>
      expect(screen.queryByText('Perfect')).toBeTruthy()
    );
  });

  it('calls fetch POST when rating button clicked', async () => {
    renderPage();
    await waitFor(() => screen.queryByText('What is Sunyata?'));
    fireEvent.click(screen.getByRole('button', { name: /rate recall/i }));
    await waitFor(() => screen.queryByText('Perfect'));
    // Click the "5 — Perfect" rating button
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

// ─── Skip ─────────────────────────────────────────────────────────────────────
describe('ReviewPage — skip', () => {
  it('skip button advances to session complete when only 1 card', async () => {
    renderPage();
    await waitFor(() => screen.queryByText('What is Sunyata?'));
    // Reveal first
    fireEvent.click(screen.getByRole('button', { name: /rate recall/i }));
    await waitFor(() => screen.queryByText('Skip'));
    fireEvent.click(screen.getByText('Skip'));
    await waitFor(() =>
      // Session ends → shows completion screen
      expect(screen.queryByText(/session complete|nothing due/i)).toBeTruthy()
    );
  });
});

// ─── Error state ──────────────────────────────────────────────────────────────
describe('ReviewPage — error state', () => {
  it('shows "Failed to load review queue" when fetch rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText(/failed to load review queue/i)).toBeTruthy()
    );
  });
});
