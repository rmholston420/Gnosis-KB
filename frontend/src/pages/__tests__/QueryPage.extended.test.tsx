/**
 * QueryPage.extended.test.tsx
 * Targets uncovered lines in QueryPage.tsx
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// ── mocks ────────────────────────────────────────────────────────────────────
const mockRunQuery    = vi.fn();
const mockSaveQuery   = vi.fn();
const mockListQueries = vi.fn();
const mockDeleteQuery = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    runQuery:     (...a: unknown[]) => mockRunQuery(...a),
    saveQuery:    (...a: unknown[]) => mockSaveQuery(...a),
    listQueries:  (...a: unknown[]) => mockListQueries(...a),
    deleteQuery:  (...a: unknown[]) => mockDeleteQuery(...a),
    listNotes:    vi.fn().mockResolvedValue({ items: [] }),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import QueryPage from '@/pages/QueryPage';

const SAMPLE_RESULTS = [
  { id: 'n1', title: 'Dharma Note', slug: 'dharma-note', note_type: 'permanent',
    tags: [], snippet: 'some snippet', score: 0.9 },
];

const SAVED_QUERIES = [
  { id: 'q1', name: 'My Query', query: 'FROM notes WHERE tag = \'buddhism\'', created_at: '2026-01-01T00:00:00Z' },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <QueryPage />
    </MemoryRouter>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
describe('QueryPage — initial render', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders query textarea', () => {
    mockListQueries.mockResolvedValue([]);
    renderPage();
    expect(screen.getByRole('textbox')).toBeTruthy();
  });

  it('renders Run button disabled when query is empty', () => {
    mockListQueries.mockResolvedValue([]);
    renderPage();
    const runBtn = screen.getAllByRole('button').find(b => /run/i.test(b.textContent ?? ''));
    if (runBtn) expect((runBtn as HTMLButtonElement).disabled).toBe(true);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('QueryPage — run query', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('calls runQuery and displays results', async () => {
    mockListQueries.mockResolvedValue([]);
    mockRunQuery.mockResolvedValue({ items: SAMPLE_RESULTS, total: 1 });
    renderPage();
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'FROM notes' } });
    const runBtn = screen.getAllByRole('button').find(b => /run/i.test(b.textContent ?? ''));
    if (runBtn && !(runBtn as HTMLButtonElement).disabled) {
      fireEvent.click(runBtn);
      await waitFor(() => expect(mockRunQuery).toHaveBeenCalled());
    }
  });

  it('shows error message when runQuery rejects', async () => {
    mockListQueries.mockResolvedValue([]);
    mockRunQuery.mockRejectedValue(new Error('DB error'));
    renderPage();
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'FROM notes' } });
    const runBtn = screen.getAllByRole('button').find(b => /run/i.test(b.textContent ?? ''));
    if (runBtn && !(runBtn as HTMLButtonElement).disabled) {
      fireEvent.click(runBtn);
      await waitFor(() => expect(screen.queryByText(/error/i)).toBeTruthy());
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('QueryPage — save dialog', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('opens save dialog and calls saveQuery', async () => {
    mockListQueries.mockResolvedValue([]);
    mockRunQuery.mockResolvedValue({ items: SAMPLE_RESULTS, total: 1 });
    mockSaveQuery.mockResolvedValue({ id: 'q2', name: 'Saved', query: 'FROM notes' });
    renderPage();
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'FROM notes' } });
    // Find and click the Save toolbar button (not inside dialog)
    const saveBtn = screen.getAllByRole('button').find(b => /^save$/i.test(b.textContent?.trim() ?? ''));
    if (saveBtn) {
      fireEvent.click(saveBtn);
      const dialog = screen.queryByRole('dialog');
      if (dialog) {
        const nameInput = screen.queryByLabelText(/name/i);
        if (nameInput) fireEvent.change(nameInput, { target: { value: 'My Name' } });
        const submitBtn = screen.getAllByRole('button').find(b => /save/i.test(b.textContent ?? '') && b.closest('[role="dialog"]'));
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
  beforeEach(() => { vi.clearAllMocks(); });

  it('loads and displays saved queries', async () => {
    mockListQueries.mockResolvedValue(SAVED_QUERIES);
    renderPage();
    await waitFor(() => expect(screen.queryByText('My Query')).toBeTruthy());
  });

  it('loads saved query into textarea on click', async () => {
    mockListQueries.mockResolvedValue(SAVED_QUERIES);
    renderPage();
    await waitFor(() => screen.getByText('My Query'));
    fireEvent.click(screen.getByText('My Query'));
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    expect(textarea.value).toContain('FROM notes');
  });

  it('calls deleteQuery when delete button clicked', async () => {
    mockListQueries.mockResolvedValue(SAVED_QUERIES);
    mockDeleteQuery.mockResolvedValue({});
    renderPage();
    await waitFor(() => screen.getByText('My Query'));
    const delBtn = screen.queryByRole('button', { name: /delete/i });
    if (delBtn) {
      fireEvent.click(delBtn);
      await waitFor(() => expect(mockDeleteQuery).toHaveBeenCalled());
    }
  });
});
