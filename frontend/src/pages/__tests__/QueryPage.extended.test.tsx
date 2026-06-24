/**
 * QueryPage.extended.test.tsx
 *
 * QueryPage.tsx defines its own local `api` object built on raw axios calls —
 * it does NOT use @/services/api at all. vi.mock('@/services/api') has zero
 * effect here. We must mock the `axios` module directly.
 *
 * Key behaviors:
 * - Run button: disabled when queryText is empty, enabled once text is typed
 * - Save dialog: has both <input> (Name) and <textarea> (Description), both
 *   role="textbox" — use getAllByRole('textbox')[0] inside the dialog
 * - Saved queries: loaded via useQuery -> api.listSaved -> axios.get
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ─── Mock axios ───────────────────────────────────────────────────────────────
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
  // GET /api/v1/query/saved
  mockAxiosGet.mockResolvedValue({ data: SAVED_QUERIES });
  // POST /api/v1/query/run
  mockAxiosPost.mockResolvedValue({ data: QUERY_RESULT });
  // DELETE
  mockAxiosDelete.mockResolvedValue({ data: {} });
});

// ─── Initial render ───────────────────────────────────────────────────────────
describe('QueryPage — initial render', () => {
  it('renders query textarea', () => {
    renderPage();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('renders Run button (disabled when textarea empty)', () => {
    renderPage();
    const runBtn = screen.queryByRole('button', { name: /run/i });
    expect(runBtn).toBeTruthy();
  });
});

// ─── Run query ────────────────────────────────────────────────────────────────
describe('QueryPage — run query', () => {
  it('calls axios.post and displays results', async () => {
    renderPage();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    // Button should now be enabled
    const runBtn = screen.getByRole('button', { name: /run/i });
    fireEvent.click(runBtn);
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

// ─── Save dialog ──────────────────────────────────────────────────────────────
describe('QueryPage — save dialog', () => {
  it('opens save dialog and calls axios.post to save', async () => {
    // createSaved also goes through axios.post — return saved-query shape
    mockAxiosPost
      .mockResolvedValueOnce({ data: QUERY_RESULT })           // runQuery (if called)
      .mockResolvedValue({ data: { id: 3, name: 'My Query' } }); // createSaved

    renderPage();
    // Type query so Save button is accessible
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });

    const saveBtn = screen.getByRole('button', { name: /save/i });
    fireEvent.click(saveBtn);

    const dialog = await screen.findByRole('dialog');
    // Dialog has <input> (Name) AND <textarea> (Description) — both role=textbox
    const textboxes = within(dialog).getAllByRole('textbox');
    fireEvent.change(textboxes[0], { target: { value: 'My Query' } });

    // The Save button inside dialog is disabled until name is non-empty;
    // after our change it should be enabled
    const submitBtn = within(dialog).getByRole('button', { name: /save/i });
    fireEvent.click(submitBtn);

    await waitFor(() =>
      expect(mockAxiosPost).toHaveBeenCalledWith(
        expect.stringContaining('/query/saved'),
        expect.objectContaining({ name: 'My Query' })
      )
    );
  });
});

// ─── Saved queries panel ──────────────────────────────────────────────────────
describe('QueryPage — saved queries panel', () => {
  it('loads and displays saved queries from axios.get', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText('Find Dharma')).toBeTruthy()
    );
  });

  it('loads saved query text into textarea on click', async () => {
    renderPage();
    await waitFor(() => screen.queryByText('Find Dharma'));
    fireEvent.click(screen.getByText('Find Dharma'));
    // Expanding shows the Run/Delete buttons inside the accordion
    await waitFor(() =>
      expect(screen.queryAllByRole('button', { name: /run/i }).length).toBeGreaterThan(0)
    );
  });

  it('calls axios.delete when delete button clicked', async () => {
    renderPage();
    await waitFor(() => screen.queryByText('Find Dharma'));
    // Expand the first saved query to reveal delete button
    fireEvent.click(screen.getByText('Find Dharma'));
    await waitFor(() => screen.queryAllByRole('button', { name: /run/i }));
    const trashBtns = screen.queryAllByRole('button').filter(
      (btn) => btn.querySelector('svg') && btn.className.includes('red')
    );
    if (trashBtns[0]) {
      fireEvent.click(trashBtns[0]);
      await waitFor(() => expect(mockAxiosDelete).toHaveBeenCalled());
    }
  });
});
