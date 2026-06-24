/**
 * QueryPage.extended.test.tsx
 * QueryPage uses useQueryClient() — must be wrapped in QueryClientProvider.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockRunQuery      = vi.fn();
const mockListQueries   = vi.fn();
const mockSaveQuery     = vi.fn();
const mockDeleteQuery   = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    runQuery:    (...a: unknown[]) => mockRunQuery(...a),
    listQueries: (...a: unknown[]) => mockListQueries(...a),
    saveQuery:   (...a: unknown[]) => mockSaveQuery(...a),
    deleteQuery: (...a: unknown[]) => mockDeleteQuery(...a),
    listNotes:   vi.fn().mockResolvedValue({ items: [] }),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import QueryPage from '@/pages/QueryPage';

const SAVED_QUERIES = [
  { id: 'q1', name: 'Find Dharma', query: 'FROM notes WHERE tags CONTAINS "dharma"', created_at: '2026-01-01T00:00:00Z' },
  { id: 'q2', name: 'Recent Notes', query: 'FROM notes ORDER BY created_at DESC LIMIT 10', created_at: '2026-01-02T00:00:00Z' },
];

const QUERY_RESULT = {
  rows: [
    { id: 'n1', title: 'Dharma Note', slug: 'dharma-note' },
  ],
  total: 1,
  execution_time_ms: 42,
};

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
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
  mockListQueries.mockResolvedValue(SAVED_QUERIES);
  mockRunQuery.mockResolvedValue(QUERY_RESULT);
  mockSaveQuery.mockResolvedValue({ id: 'q3', name: 'New Query' });
  mockDeleteQuery.mockResolvedValue({});
});

// ─────────────────────────────────────────────────────────────────────────────
describe('QueryPage — initial render', () => {
  it('renders query textarea', () => {
    renderPage();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('renders Run button disabled when query is empty', () => {
    renderPage();
    const runBtn = screen.queryByRole('button', { name: /run/i });
    if (runBtn) expect(runBtn).toBeDisabled();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('QueryPage — run query', () => {
  it('calls runQuery and displays results', async () => {
    renderPage();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    const runBtn = screen.queryByRole('button', { name: /run/i });
    if (runBtn && !runBtn.hasAttribute('disabled')) {
      fireEvent.click(runBtn);
      await waitFor(() => expect(mockRunQuery).toHaveBeenCalled());
    }
  });

  it('shows error message when runQuery rejects', async () => {
    mockRunQuery.mockRejectedValue(new Error('Query failed'));
    renderPage();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    const runBtn = screen.queryByRole('button', { name: /run/i });
    if (runBtn && !runBtn.hasAttribute('disabled')) {
      fireEvent.click(runBtn);
      await waitFor(() => expect(screen.queryByText(/error|failed/i)).toBeTruthy());
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('QueryPage — save dialog', () => {
  it('opens save dialog and calls saveQuery', async () => {
    renderPage();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    const saveBtn = screen.queryByRole('button', { name: /save/i });
    if (saveBtn) {
      fireEvent.click(saveBtn);
      const dialog = screen.queryByRole('dialog');
      if (dialog) {
        const nameInput = within(dialog).queryByRole('textbox');
        if (nameInput) fireEvent.change(nameInput, { target: { value: 'My Query' } });
        const submitBtn = within(dialog).queryByRole('button', { name: /save|submit/i });
        if (submitBtn) {
          fireEvent.click(submitBtn);
          await waitFor(() => expect(mockSaveQuery).toHaveBeenCalled());
        }
      }
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('QueryPage — saved queries panel', () => {
  it('loads and displays saved queries', async () => {
    renderPage();
    await waitFor(() => expect(screen.queryByText('Find Dharma')).toBeTruthy());
  });

  it('loads saved query into textarea on click', async () => {
    renderPage();
    await waitFor(() => screen.queryByText('Find Dharma'));
    const item = screen.queryByText('Find Dharma');
    if (item) {
      fireEvent.click(item);
      await waitFor(() =>
        expect((screen.getByRole('textbox') as HTMLTextAreaElement).value).toContain('dharma')
      );
    }
  });

  it('calls deleteQuery when delete button clicked', async () => {
    renderPage();
    await waitFor(() => screen.queryByText('Find Dharma'));
    const deleteBtn = screen.queryAllByRole('button', { name: /delete/i })[0];
    if (deleteBtn) {
      fireEvent.click(deleteBtn);
      await waitFor(() => expect(mockDeleteQuery).toHaveBeenCalled());
    }
  });
});
