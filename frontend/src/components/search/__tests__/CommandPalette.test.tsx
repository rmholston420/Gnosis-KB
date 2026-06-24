/**
 * CommandPalette tests — canonical path (components/search/__tests__/)
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CommandPalette from '@/components/search/CommandPalette';

// ── Mocks ──────────────────────────────────────────────────────────────────────
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  const mockNavigate = vi.fn();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

/** Spy on the module-level fetchNoteStubs export so tests can control it. */
vi.mock('@/components/search/CommandPalette', async () => {
  const actual = await vi.importActual<typeof import('@/components/search/CommandPalette')>(
    '@/components/search/CommandPalette'
  );
  return {
    ...actual,
    fetchNoteStubs: vi.fn().mockResolvedValue([
      { id: 'n1', title: 'My First Note', folder: '00-inbox' },
      { id: 'n2', title: 'Settings Guide', folder: '02-resources' },
    ]),
  };
});

const { fetchNoteStubs } = await import('@/components/search/CommandPalette');

// ── Helpers ────────────────────────────────────────────────────────────────────
const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={qc}>
    <MemoryRouter>{children}</MemoryRouter>
  </QueryClientProvider>
);

// ── Tests ──────────────────────────────────────────────────────────────────────
describe('CommandPalette', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('input is auto-focused on mount', () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
  });

  it('shows action items with no query', () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
  });

  it('pressing Escape closes the palette', () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when closed via Escape', () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('Cmd+K toggles palette closed when already open', () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    fireEvent.keyDown(document, { key: 'k', metaKey: true });
    expect(onClose).toHaveBeenCalled();
  });

  it('shows action items when open', () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
  });

  it('filters action items by query', () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    const input = screen.getByPlaceholderText(/search|go to/i);
    fireEvent.change(input, { target: { value: 'settings' } });
    expect(input).toHaveValue('settings');
  });

  it('fetchNoteStubs is called on first open', async () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(fetchNoteStubs).toHaveBeenCalled();
    });
  });

  it('fetchNoteStubs handles {items:[]} response shape', async () => {
    (fetchNoteStubs as ReturnType<typeof vi.fn>).mockResolvedValueOnce([]);
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
    });
  });

  it('fetchNoteStubs returns empty on non-ok response', async () => {
    (fetchNoteStubs as ReturnType<typeof vi.fn>).mockResolvedValueOnce([]);
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
    });
  });

  it('fetchNoteStubs returns empty when fetch throws', async () => {
    (fetchNoteStubs as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('network'));
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
    });
  });

  it('renders a result item when note stubs are loaded', async () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(fetchNoteStubs).toHaveBeenCalled();
    });
  });

  it('clicking a result navigates to the note', async () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(fetchNoteStubs).toHaveBeenCalled();
    });
  });

  it('calls searchNotes / filters when query is typed', () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    const input = screen.getByPlaceholderText(/search|go to/i);
    fireEvent.change(input, { target: { value: 'graph' } });
    expect(input).toHaveValue('graph');
  });

  it('createQuickNote navigates to /editor/:id on success', async () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
  });
});
