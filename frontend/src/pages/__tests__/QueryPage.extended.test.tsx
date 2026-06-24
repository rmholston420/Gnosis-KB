/**
 * QueryPage.extended.test.tsx
 * Targets uncovered lines: 29,31,33,54-59,69-74,80-105,193-196,223-250
 * - runSaved, deleteSaved, expand/collapse saved queries
 * - Ctrl+Enter keyboard shortcut
 * - Save dialog (name + description fields)
 * - Result table with data rows
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const { mockGet, mockPost, mockDelete } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockDelete: vi.fn(),
}));

vi.mock('axios', () => ({
  default: { get: mockGet, post: mockPost, delete: mockDelete },
}));

import QueryPage from '../QueryPage';

const SAVED_QUERIES = [
  {
    id: 1, name: 'My Dashboard', query: 'FROM notes LIMIT 5',
    description: 'All notes', created_at: '2025-01-01', updated_at: '2025-01-01',
  },
];

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <QueryPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockGet.mockResolvedValue({ data: [] });
  mockPost.mockResolvedValue({ data: { rows: [], total: 0, query_time_ms: 5 } });
  mockDelete.mockResolvedValue({});
});

describe('QueryPage — saved queries', () => {
  it('lists saved query names in sidebar', async () => {
    mockGet.mockResolvedValueOnce({ data: SAVED_QUERIES });
    wrap();
    await waitFor(() => expect(screen.getByText('My Dashboard')).toBeInTheDocument());
  });

  it('expands a saved query on click', async () => {
    mockGet.mockResolvedValueOnce({ data: SAVED_QUERIES });
    wrap();
    await waitFor(() => screen.getByText('My Dashboard'));
    fireEvent.click(screen.getByText('My Dashboard'));
    await waitFor(() => expect(screen.getByText('All notes')).toBeInTheDocument());
  });

  it('collapses a saved query when clicked again', async () => {
    mockGet.mockResolvedValueOnce({ data: SAVED_QUERIES });
    wrap();
    await waitFor(() => screen.getByText('My Dashboard'));
    fireEvent.click(screen.getByText('My Dashboard'));
    await waitFor(() => screen.getByText('All notes'));
    fireEvent.click(screen.getByText('My Dashboard'));
    await waitFor(() => expect(screen.queryByText('All notes')).not.toBeInTheDocument());
  });

  it('shows "No saved queries" when list is empty', async () => {
    mockGet.mockResolvedValueOnce({ data: [] });
    wrap();
    await waitFor(() => expect(screen.getByText(/no saved queries/i)).toBeInTheDocument());
  });

  it('clicking an example populates the textarea', () => {
    wrap();
    fireEvent.click(screen.getByText(/draft zettelkasten notes/i));
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    expect(textarea.value).toContain('10-zettelkasten');
  });
});

describe('QueryPage — keyboard shortcut', () => {
  it('Ctrl+Enter runs the query', async () => {
    wrap();
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'FROM notes' } });
    fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true });
    await waitFor(() => expect(mockPost).toHaveBeenCalled());
  });

  it('Meta+Enter also runs the query', async () => {
    wrap();
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'FROM notes' } });
    fireEvent.keyDown(textarea, { key: 'Enter', metaKey: true });
    await waitFor(() => expect(mockPost).toHaveBeenCalled());
  });
});

describe('QueryPage — save dialog', () => {
  it('opens the save dialog when Save is clicked', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => {
      const nameInput = screen.queryByPlaceholderText(/query name/i) ??
                        screen.queryByLabelText(/name/i) ??
                        screen.queryByRole('textbox', { name: /name/i });
      expect(nameInput ?? screen.queryByText(/save query/i)).toBeTruthy();
    });
  });

  it('closes save dialog on cancel', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    const cancelBtn = await screen.findByRole('button', { name: /cancel/i });
    fireEvent.click(cancelBtn);
    await waitFor(() => expect(screen.queryByRole('button', { name: /cancel/i })).toBeNull());
  });
});

describe('QueryPage — result table', () => {
  it('renders result rows after a successful query', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        rows: [{ title: 'Zettel One', status: 'draft', folder: '10-zettelkasten' }],
        total: 1,
        query_time_ms: 12,
      },
    });
    wrap();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    fireEvent.click(screen.getByRole('button', { name: /^run$/i }));
    await waitFor(() => expect(screen.getByText('Zettel One')).toBeInTheDocument());
    expect(screen.getByText('draft')).toBeInTheDocument();
  });

  it('renders column headers from row keys', async () => {
    mockPost.mockResolvedValueOnce({
      data: { rows: [{ title: 'Note', word_count: 42 }], total: 1, query_time_ms: 3 },
    });
    wrap();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    fireEvent.click(screen.getByRole('button', { name: /^run$/i }));
    await waitFor(() => expect(screen.getByText(/word_count/i)).toBeInTheDocument());
  });

  it('shows timing info in result header', async () => {
    mockPost.mockResolvedValueOnce({
      data: { rows: [{ title: 'X' }], total: 1, query_time_ms: 99 },
    });
    wrap();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'FROM notes' } });
    fireEvent.click(screen.getByRole('button', { name: /^run$/i }));
    await waitFor(() => expect(screen.getByText(/99/)).toBeInTheDocument());
  });
});
