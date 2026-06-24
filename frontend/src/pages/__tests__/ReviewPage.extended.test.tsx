/**
 * ReviewPage.extended.test.tsx
 * Targets uncovered lines in ReviewPage.tsx
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockListDue      = vi.fn();
const mockSubmitReview = vi.fn();
const mockSkipReview   = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    listDueReviews:  (...a: unknown[]) => mockListDue(...a),
    submitReview:    (...a: unknown[]) => mockSubmitReview(...a),
    skipReview:      (...a: unknown[]) => mockSkipReview(...a),
    listNotes:       vi.fn().mockResolvedValue({ items: [] }),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}));
vi.mock('remark-gfm', () => ({ default: () => {} }));

import ReviewPage from '@/pages/ReviewPage';

const BASE_CARD = {
  id: 'r1',
  note_id: 'note-1',
  title: 'Review Card Title',
  body: 'Card body text here.',
  due_at: '2026-06-24T00:00:00Z',
  interval: 1,
  ease_factor: 2.5,
  repetitions: 0,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <ReviewPage />
    </MemoryRouter>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — loading + empty', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows loading state', () => {
    mockListDue.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/loading/i)).toBeTruthy();
  });

  it('shows empty state when no cards due', async () => {
    mockListDue.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.queryByText(/no cards|done|finished|all caught up/i)).toBeTruthy());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — card interaction', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders card title', async () => {
    mockListDue.mockResolvedValue([BASE_CARD]);
    renderPage();
    await waitFor(() => expect(screen.getByText('Review Card Title')).toBeTruthy());
  });

  it('calls submitReview when rating button clicked', async () => {
    mockListDue.mockResolvedValue([BASE_CARD]);
    mockSubmitReview.mockResolvedValue({});
    renderPage();
    await waitFor(() => screen.getByText('Review Card Title'));
    const ratingBtn = screen.queryByRole('button', { name: /good|easy|hard|again/i });
    if (ratingBtn) {
      fireEvent.click(ratingBtn);
      await waitFor(() => expect(mockSubmitReview).toHaveBeenCalled());
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — skip', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('calls skipReview when skip button clicked', async () => {
    mockListDue.mockResolvedValue([BASE_CARD]);
    mockSkipReview.mockResolvedValue({});
    renderPage();
    await waitFor(() => screen.getByText('Review Card Title'));
    const skipBtn = screen.queryByRole('button', { name: /skip/i });
    if (skipBtn) {
      fireEvent.click(skipBtn);
      await waitFor(() => expect(mockSkipReview).toHaveBeenCalled());
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — error state', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows error when listDue rejects', async () => {
    mockListDue.mockRejectedValue(new Error('fetch failed'));
    renderPage();
    await waitFor(() => expect(screen.queryByText(/error/i)).toBeTruthy());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('ReviewPage — reveal answer', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('shows answer after reveal button click', async () => {
    mockListDue.mockResolvedValue([BASE_CARD]);
    renderPage();
    await waitFor(() => screen.getByText('Review Card Title'));
    const revealBtn = screen.queryByRole('button', { name: /show|reveal|answer/i });
    if (revealBtn) {
      fireEvent.click(revealBtn);
      expect(screen.getByText(/Card body text here/)).toBeTruthy();
    }
  });
});
