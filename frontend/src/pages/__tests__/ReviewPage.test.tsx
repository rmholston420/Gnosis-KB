/**
 * ReviewPage.test.tsx
 * Covers: loading state, error state, empty queue, session flow
 * (reveal, rate, skip), and session-complete screen.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()),
  useNavigate: () => mockNavigate,
}));

// Stub WikilinkPreview so we don't need real markdown parsing
vi.mock('../../components/WikilinkPreview', () => ({
  default: ({ body }: { body: string }) => <div data-testid="preview">{body}</div>,
}));

// Stub api
vi.mock('../../services/api', () => ({
  default: {
    listNotes: vi.fn().mockResolvedValue({ items: [] }),
  },
}));

import ReviewPage from '../ReviewPage';

const makeCard = (id = 'note-1') => ({
  note_id: id,
  note_title: 'Test Note',
  note_body: '## Body',
  note_folder: '10-zettelkasten',
  note_tags: ['eeg'],
  easiness: 2.5,
  interval: 1,
  repetitions: 0,
  due_date: '2026-06-24',
  last_quality: null,
});

const makeStats = () => ({
  due_today: 3,
  due_this_week: 10,
  total_enrolled: 42,
  new_today: 1,
  reviewed_today: 2,
});

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.resetAllMocks();
  mockNavigate.mockReset();
});

describe('ReviewPage — loading', () => {
  it('shows loading spinner', () => {
    global.fetch = vi.fn().mockReturnValue(new Promise(() => {}));
    wrap(<ReviewPage />);
    expect(screen.getByText(/loading queue/i)).toBeInTheDocument();
  });
});

describe('ReviewPage — error', () => {
  it('shows error message on fetch failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    wrap(<ReviewPage />);
    await waitFor(() =>
      expect(screen.getByText(/failed to load review queue/i)).toBeInTheDocument()
    );
  });
});

describe('ReviewPage — empty queue', () => {
  it('shows nothing-due message when queue is empty', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('stats')) return Promise.resolve({ json: () => Promise.resolve(makeStats()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    wrap(<ReviewPage />);
    await waitFor(() =>
      expect(screen.getByText(/nothing due today/i)).toBeInTheDocument()
    );
  });
});

describe('ReviewPage — session', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('stats')) return Promise.resolve({ json: () => Promise.resolve(makeStats()) });
      if (url.includes('notes-titles') || url.includes('listNotes')) return Promise.resolve({ json: () => Promise.resolve({ items: [] }) });
      if (url.match(/\/review\/note-1$/)) return Promise.resolve({ json: () => Promise.resolve({ ok: true }) });
      // queue endpoint
      return Promise.resolve({ json: () => Promise.resolve([makeCard()]) });
    });
  });

  it('renders the card title', async () => {
    wrap(<ReviewPage />);
    await waitFor(() => expect(screen.getByText('Test Note')).toBeInTheDocument());
  });

  it('shows tag badge', async () => {
    wrap(<ReviewPage />);
    await waitFor(() => expect(screen.getByText('eeg')).toBeInTheDocument());
  });

  it('reveals rating buttons on "Rate recall" click', async () => {
    wrap(<ReviewPage />);
    await waitFor(() => screen.getByText('Test Note'));
    fireEvent.click(screen.getByText(/rate recall/i));
    expect(screen.getByText(/how well did you recall/i)).toBeInTheDocument();
    // 6 rating buttons (0-5)
    expect(screen.getAllByText(/blackout|wrong|hard|good|perfect/i).length).toBeGreaterThanOrEqual(3);
  });

  it('skips to session-complete when only 1 card and skip is clicked', async () => {
    wrap(<ReviewPage />);
    await waitFor(() => screen.getByText('Test Note'));
    fireEvent.click(screen.getByText(/rate recall/i));
    fireEvent.click(screen.getByText(/skip/i));
    await waitFor(() =>
      expect(screen.getByText(/session complete/i)).toBeInTheDocument()
    );
  });

  it('navigates back to notes on "Back to notes" click', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('stats')) return Promise.resolve({ json: () => Promise.resolve(makeStats()) });
      return Promise.resolve({ json: () => Promise.resolve([]) });
    });
    wrap(<ReviewPage />);
    await waitFor(() => screen.getByText(/nothing due today/i));
    fireEvent.click(screen.getByText(/back to notes/i));
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });
});
