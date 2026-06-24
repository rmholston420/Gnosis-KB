/**
 * DailyNotePage.test.tsx
 * ======================
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DailyNotePage from '../DailyNotePage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockGetDailyNote = vi.fn();
vi.mock('../../services/api', () => ({
  default: {
    getDailyNote: (...args: unknown[]) => mockGetDailyNote(...args),
  },
}));

const dailyNote = {
  id:         'dn-1',
  title:      'Daily Note 2026-06-24',
  slug:       'daily-2026-06-24',
  body:       '',
  note_type:  'journal',
  tags:       [],
  folder:     null,
  created_at: '2026-06-24T00:00:00Z',
  updated_at: '2026-06-24T00:00:00Z',
};

function renderPage() {
  return render(<MemoryRouter><DailyNotePage /></MemoryRouter>);
}

beforeEach(() => {
  mockGetDailyNote.mockReset();
  mockNavigate.mockReset();
  mockGetDailyNote.mockResolvedValue(dailyNote);
});

describe('DailyNotePage', () => {
  it('renders without crashing', () => {
    renderPage();
    expect(document.body).toBeInTheDocument();
  });

  it('calls getDailyNote on mount', async () => {
    renderPage();
    await waitFor(() => expect(mockGetDailyNote).toHaveBeenCalled());
  });

  it('navigates to the daily note after loading', async () => {
    renderPage();
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('dn-1'), expect.anything())
    );
  });

  it('shows loading indicator initially', () => {
    mockGetDailyNote.mockReturnValue(new Promise(() => {}));
    renderPage();
    const spinner = document.querySelector('.animate-spin, [data-testid="loading"]');
    const loadingText = screen.queryByText(/loading|please wait/i);
    expect(spinner || loadingText).toBeTruthy();
  });
});
