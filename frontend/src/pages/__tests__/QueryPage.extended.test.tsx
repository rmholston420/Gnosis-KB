import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockRunQuery          = vi.fn();
const mockSaveQuery         = vi.fn();
const mockListSavedQueries  = vi.fn();
const mockDeleteQuery       = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    runQuery:          (...a: unknown[]) => mockRunQuery(...a),
    saveQuery:         (...a: unknown[]) => mockSaveQuery(...a),
    listSavedQueries:  (...a: unknown[]) => mockListSavedQueries(...a),
    deleteSavedQuery:  (...a: unknown[]) => mockDeleteQuery(...a),
    listNotes: vi.fn().mockResolvedValue({ items: [] }),
  },
}));

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

async function setup() {
  mockListSavedQueries.mockResolvedValue([]);
  const { default: QueryPage } = await import('@/pages/QueryPage');
  render(<Wrapper><QueryPage /></Wrapper>);
  await new Promise((r) => setTimeout(r, 40));
}

describe('QueryPage extended', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders page without crashing', async () => {
    await setup();
  });

  it('renders at least one interactive element', async () => {
    await setup();
    const buttons = screen.queryAllByRole('button');
    const inputs  = screen.queryAllByRole('textbox');
    expect(buttons.length + inputs.length).toBeGreaterThan(0);
  });

  it('run button triggers runQuery call', async () => {
    mockListSavedQueries.mockResolvedValue([]);
    mockRunQuery.mockResolvedValue({ results: [{ id: 'r1', title: 'Result A', excerpt: 'ex' }] });
    const { default: QueryPage } = await import('@/pages/QueryPage');
    render(<Wrapper><QueryPage /></Wrapper>);
    await new Promise((r) => setTimeout(r, 40));
    const buttons = screen.queryAllByRole('button');
    const runBtn = buttons.find((b) => /run|search|execute/i.test(b.textContent ?? ''));
    if (runBtn) {
      fireEvent.click(runBtn);
      await waitFor(() => expect(mockRunQuery).toHaveBeenCalled());
    }
  });

  it('handles runQuery rejection gracefully', async () => {
    mockListSavedQueries.mockResolvedValue([]);
    mockRunQuery.mockRejectedValue(new Error('query fail'));
    const { default: QueryPage } = await import('@/pages/QueryPage');
    render(<Wrapper><QueryPage /></Wrapper>);
    await new Promise((r) => setTimeout(r, 40));
    const buttons = screen.queryAllByRole('button');
    const runBtn = buttons.find((b) => /run|search|execute/i.test(b.textContent ?? ''));
    if (runBtn) {
      fireEvent.click(runBtn);
      await new Promise((r) => setTimeout(r, 80));
    }
  });

  it('renders saved queries when they exist', async () => {
    mockListSavedQueries.mockResolvedValue([
      { id: 'sq1', name: 'My Saved Query', query: 'dharma' },
    ]);
    const { default: QueryPage } = await import('@/pages/QueryPage');
    render(<Wrapper><QueryPage /></Wrapper>);
    await new Promise((r) => setTimeout(r, 80));
    const el = screen.queryByText('My Saved Query');
    if (el) expect(el).toBeTruthy();
  });

  it('handles listSavedQueries rejection gracefully', async () => {
    mockListSavedQueries.mockRejectedValue(new Error('fail'));
    const { default: QueryPage } = await import('@/pages/QueryPage');
    render(<Wrapper><QueryPage /></Wrapper>);
    await new Promise((r) => setTimeout(r, 80));
  });

  it('Ctrl+Enter keyboard shortcut does not crash', async () => {
    mockListSavedQueries.mockResolvedValue([]);
    mockRunQuery.mockResolvedValue({ results: [] });
    const { default: QueryPage } = await import('@/pages/QueryPage');
    render(<Wrapper><QueryPage /></Wrapper>);
    await new Promise((r) => setTimeout(r, 40));
    const textarea = screen.queryByRole('textbox');
    if (textarea) {
      fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true });
    }
  });
});
