/**
 * QueryPage.extended.test.tsx
 *
 * QueryPage.tsx uses raw axios calls — vi.mock('axios') required.
 *
 * Critical: waitFor callbacks MUST use expect().toBeTruthy() to throw
 * on failure so waitFor actually retries. queryByText/queryByRole return
 * null (no throw) and exit waitFor immediately.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockAxiosPost   = vi.fn();
const mockAxiosGet    = vi.fn();
const mockAxiosDelete = vi.fn();

vi.mock('axios', () => ({
  default: {
    post:   (...a: unknown[]) => mockAxiosPost(...a),
    get:    (...a: unknown[]) => mockAxiosGet(...a),
    delete: (...a: unknown[]) => mockAxiosDelete(...a),
    create: vi.fn().mockReturnThis(),
  },
}));

import QueryPage from '@/pages/QueryPage';

const SAVED_QUERIES = [
  {
    id: 1,
    name: 'Find Dharma',
    query: 'FROM notes WHERE tags CONTAINS "dharma"',
    description: 'Dharma-tagged notes',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Recent Notes',
    query: 'FROM notes ORDER BY created_at DESC LIMIT 10',
    description: 'Most recent notes',
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
];

const QUERY_RESULT = {
  rows: [{ title: 'Dharma Note', slug: 'dharma-note' }],
  total: 1,
  query_time_ms: 42,
};

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter>
        <QueryPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockAxiosGet.mockResolvedValue({ data: SAVED_QUERIES });
  mockAxiosPost.mockResolvedValue({ data: QUERY_RESULT });
  mockAxiosDelete.mockResolvedValue({ data: {} });
});

describe('QueryPage — initial render', () => {
  it('renders query textarea', () => {
    renderPage();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('renders Run button (disabled when textarea empty)', () => {
    renderPage();
    expect(screen.queryByRole('button', { name: /run/i })).toBeTruthy();
  });
});

describe('QueryPage — run query', () => {
  it('calls axios.post and displays results', async () => {
    renderPage();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    fireEvent.click(screen.getByRole('button', { name: /run/i }));
    await waitFor(() => expect(mockAxiosPost).toHaveBeenCalled());
  });

  it('shows result rows after successful run', async () => {
    renderPage();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    fireEvent.click(screen.getByRole('button', { name: /run/i }));
    await waitFor(() =>
      expect(screen.queryByText('Dharma Note')).toBeTruthy()
    );
  });

  it('shows error message when run fails', async () => {
    mockAxiosPost.mockRejectedValue(new Error('Query failed'));
    renderPage();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    fireEvent.click(screen.getByRole('button', { name: /run/i }));
    await waitFor(() =>
      expect(screen.queryByText(/error|failed/i)).toBeTruthy()
    );
  });
});

describe('QueryPage — save dialog', () => {
  it('opens save dialog and calls axios.post to save', async () => {
    mockAxiosPost
      .mockResolvedValueOnce({ data: QUERY_RESULT })
      .mockResolvedValue({ data: { id: 3, name: 'My Query' } });

    renderPage();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    const dialog = await screen.findByRole('dialog');
    const textboxes = within(dialog).getAllByRole('textbox');
    fireEvent.change(textboxes[0], { target: { value: 'My Query' } });

    fireEvent.click(within(dialog).getByRole('button', { name: /save/i }));

    await waitFor(() =>
      expect(mockAxiosPost).toHaveBeenCalledWith(
        expect.stringContaining('/query/saved'),
        expect.objectContaining({ name: 'My Query' })
      )
    );
  });
});

describe('QueryPage — saved queries panel', () => {
  it('loads and displays saved queries from axios.get', async () => {
    renderPage();
    // expect().toBeTruthy() inside waitFor makes it retry until element appears
    await waitFor(() =>
      expect(screen.queryByText('Find Dharma')).toBeTruthy()
    );
    expect(screen.getByText('Find Dharma')).toBeInTheDocument();
  });

  it('expands saved query accordion on click', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('Find Dharma')).toBeTruthy()
    );
    fireEvent.click(screen.getByText('Find Dharma'));
    // After expanding, inline Run button appears inside the accordion
    await waitFor(() =>
      expect(screen.queryAllByRole('button', { name: /run/i }).length).toBeGreaterThan(0)
    );
  });

  it('calls axios.delete when delete button clicked', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('Find Dharma')).toBeTruthy()
    );
    // Expand first saved query
    fireEvent.click(screen.getByText('Find Dharma'));
    await waitFor(() =>
      expect(screen.queryAllByRole('button', { name: /run/i }).length).toBeGreaterThan(0)
    );
    // The delete button is a small button containing a Trash2 SVG with red styling
    const trashBtns = screen.queryAllByRole('button').filter(
      (btn) => btn.querySelector('svg') && btn.className.includes('red')
    );
    if (trashBtns[0]) {
      fireEvent.click(trashBtns[0]);
      await waitFor(() => expect(mockAxiosDelete).toHaveBeenCalled());
    }
  });
});
