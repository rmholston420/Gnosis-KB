/**
 * ReviewPage.extended.test.tsx
 * ============================
 * Extended tests for ReviewPage — card interaction, skip, error state.
 *
 * The component fetches from /api/review/queue and /api/review/stats via
 * the global fetch.  We mock global.fetch in each test.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ReviewPage from '../ReviewPage';

// ---- helpers ----------------------------------------------------------------
const makeCard = (id = 'note-1') => ({
  note_id: id,
  note_title: 'What is Sunyata?',
  note_body: 'Emptiness is the nature of all phenomena.',
  note_folder: '20-dharma',
  note_tags: ['buddhism', 'madhyamaka'],
  easiness: 2.5,
  interval: 1,
  repetitions: 0,
  due_date: '2026-06-24',
  last_quality: null,
});

const makeStats = () => ({
  due_today: 1,
  due_this_week: 3,
  total_enrolled: 10,
  new_today: 1,
  reviewed_today: 0,
});

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

function mockFetchWithCard() {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes('stats')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(makeStats()) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve([makeCard()]) });
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ---- empty queue ------------------------------------------------------------
describe('ReviewPage — empty queue', () => {
  it('shows nothing-due message when queue returns []', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('stats')) return Promise.resolve({ ok: true, json: () => Promise.resolve(makeStats()) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText(/nothing due today/i)).toBeTruthy()
    );
  });
});

function renderPage() {
  return wrap(<ReviewPage />);
}

// ---- card interaction -------------------------------------------------------
describe('ReviewPage — card interaction', () => {
  beforeEach(mockFetchWithCard);

  it('renders card title after queue loads', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('What is Sunyata?')).toBeTruthy()
    );
  });

  it('reveals rating buttons after clicking Rate recall', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('What is Sunyata?')).toBeTruthy()
    );
    fireEvent.click(screen.getByRole('button', { name: /rate recall/i }));
    expect(screen.getByText(/how well did you recall/i)).toBeInTheDocument();
  });

  it('calls fetch POST when rating button clicked', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('What is Sunyata?')).toBeTruthy()
    );
    fireEvent.click(screen.getByRole('button', { name: /rate recall/i }));
    // click the first rating button (0 — Blackout)
    const ratingBtns = screen.getAllByRole('button', { name: /blackout|wrong|hard|good|easy|perfect/i });
    fireEvent.click(ratingBtns[0]);
    await waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
      const postCall = calls.find(
        ([url, opts]: [string, RequestInit]) =>
          typeof url === 'string' && url.includes('review') && opts?.method === 'POST'
      );
      expect(postCall).toBeTruthy();
    });
  });
});

// ---- skip -------------------------------------------------------------------
describe('ReviewPage — skip', () => {
  beforeEach(mockFetchWithCard);

  it('skip button advances to session complete when only 1 card', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('What is Sunyata?')).toBeTruthy()
    );
    fireEvent.click(screen.getByRole('button', { name: /rate recall/i }));
    fireEvent.click(screen.getByText(/skip/i));
    await waitFor(() =>
      expect(screen.queryByText(/session complete/i)).toBeTruthy()
    );
  });
});

// ---- error state ------------------------------------------------------------
describe('ReviewPage — error state', () => {
  it('shows "Failed to load review queue" when fetch rejects', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network error'));
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText(/failed to load review queue/i)).toBeTruthy()
    );
  });
});
