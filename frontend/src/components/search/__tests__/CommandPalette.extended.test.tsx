/**
 * CommandPalette extended tests — additional interaction coverage.
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

/**
 * Same seam as CommandPalette.test.tsx: mock '@/lib/noteStubs' so the
 * component's internal fetchNoteStubs call is intercepted.
 */
vi.mock('@/lib/noteStubs', async () => {
  const actual = await vi.importActual<typeof import('@/lib/noteStubs')>('@/lib/noteStubs');
  return {
    ...actual,
    fetchNoteStubs: vi.fn().mockResolvedValue([
      { id: 'n1', title: 'My First Note', folder: '00-inbox' },
      { id: 'n2', title: 'Settings Guide', folder: '02-resources' },
    ]),
  };
});

const { fetchNoteStubs } = await import('@/lib/noteStubs');

// ── Helpers ────────────────────────────────────────────────────────────────────
const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={qc}>
    <MemoryRouter>{children}</MemoryRouter>
  </QueryClientProvider>
);

// ── Tests ──────────────────────────────────────────────────────────────────────
describe('CommandPalette extended', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders backdrop when open', () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    expect(document.querySelector('.command-palette-backdrop')).toBeTruthy();
  });

  it('does not render when closed', () => {
    render(<CommandPalette open={false} onClose={vi.fn()} />, { wrapper: Wrapper });
    expect(document.querySelector('.command-palette-backdrop')).toBeNull();
  });

  it('renders input with correct placeholder', () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
  });

  it('shows at least one action command', () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    expect(screen.getByText('New Note in Inbox')).toBeInTheDocument();
  });

  it('fetches note stubs on open', async () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(fetchNoteStubs).toHaveBeenCalled();
    });
  });

  it('shows notes section after stubs load', async () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    await waitFor(() => expect(fetchNoteStubs).toHaveBeenCalled());
    // Type a query matching a stub title to trigger the notes group
    const input = screen.getByPlaceholderText(/search|go to/i);
    fireEvent.change(input, { target: { value: 'first' } });
    await waitFor(() => {
      expect(screen.getByText('My First Note')).toBeInTheDocument();
    });
  });

  it('clicking backdrop calls onClose', () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    const backdrop = document.querySelector('.command-palette-backdrop') as HTMLElement;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });

  it('Ctrl+K also closes when open (Windows)', () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(onClose).toHaveBeenCalled();
  });

  it('query change filters actions', () => {
    render(<CommandPalette open onClose={vi.fn()} />, { wrapper: Wrapper });
    const input = screen.getByPlaceholderText(/search|go to/i);
    fireEvent.change(input, { target: { value: 'graph' } });
    expect(screen.getByText('Open Knowledge Graph')).toBeInTheDocument();
    expect(screen.queryByText('New Note in Inbox')).toBeNull();
  });
});
