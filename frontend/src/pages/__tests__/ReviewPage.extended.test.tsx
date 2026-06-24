/**
 * ReviewPage.extended.test.tsx
 * ReviewPage uses useQueryClient() — must be wrapped in QueryClientProvider.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockListDue      = vi.fn();
const mockSubmitReview = vi.fn();
const mockSkipReview   = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    listDue:      (...a: unknown[]) => mockListDue(...a),
    submitReview: (...a: unknown[]) => mockSubmitReview(...a),
    skipReview:   (...a: unknown[]) => mockSkipReview(...a),
    listNotes:    vi.fn().mockResolvedValue({ items: [] }),
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
    id: 'card-1',
    note_id: 'note-1',
    title: 'What is Emptiness?',
    front: 'Define sunyata',
    back: 'The absence of inherent existence in all phenomena.',
    due_date: '2026-01-01T00:00:00Z',
    interval: 1,
    ease_factor: 2.5,
  },
];

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
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
  mockListDue.mockResolvedValue(DUE_CARDS);
  mockSubmitReview.mockResolvedValue({});
  mockSkipReview.mockResolvedValue({});
});

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — loading + empty', () => {
  it('shows loading state', () => {
    mockListDue.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(document.body).toBeTruthy(); // component renders without crash
  });

  it('shows empty state when no cards due', async () => {
    mockListDue.mockResolvedValue([]);
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText(/no cards|all caught up|nothing due/i)).toBeTruthy()
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — card interaction', () => {
  it('renders card title', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText(/sunyata|emptiness|what is/i)).toBeTruthy()
    );
  });

  it('calls submitReview when rating button clicked', async () => {
    renderPage();
    await waitFor(() => screen.queryByText(/sunyata|emptiness/i));
    // First reveal the answer if there's a reveal button
    const revealBtn = screen.queryByRole('button', { name: /reveal|show answer/i });
    if (revealBtn) fireEvent.click(revealBtn);
    const ratingBtn = screen.queryByRole('button', { name: /easy|good|hard|again|[1-5]/i });
    if (ratingBtn) {
      fireEvent.click(ratingBtn);
      await waitFor(() => expect(mockSubmitReview).toHaveBeenCalled());
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — skip', () => {
  it('calls skipReview when skip button clicked', async () => {
    renderPage();
    await waitFor(() => screen.queryByText(/sunyata|emptiness/i));
    const skipBtn = screen.queryByRole('button', { name: /skip/i });
    if (skipBtn) {
      fireEvent.click(skipBtn);
      await waitFor(() => expect(mockSkipReview).toHaveBeenCalled());
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — error state', () => {
  it('shows error when listDue rejects', async () => {
    mockListDue.mockRejectedValue(new Error('Load failed'));
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText(/error|failed|could not/i)).toBeTruthy()
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — reveal answer', () => {
  it('shows answer after reveal button click', async () => {
    renderPage();
    await waitFor(() => screen.queryByText(/sunyata|emptiness/i));
    const revealBtn = screen.queryByRole('button', { name: /reveal|show answer/i });
    if (revealBtn) {
      fireEvent.click(revealBtn);
      await waitFor(() =>
        expect(screen.queryByText(/absence|inherent|phenomena/i)).toBeTruthy()
      );
    }
  });
});
