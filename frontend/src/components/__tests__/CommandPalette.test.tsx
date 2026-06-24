/**
 * CommandPalette tests — legacy path (components/__tests__/)
 * Imports from the barrel re-export at @/components/CommandPalette.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CommandPalette from '@/components/CommandPalette';

// ── Mocks ──────────────────────────────────────────────────────────────────────
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  const mockNavigate = vi.fn();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('@/api/search', () => ({
  searchNotes: vi.fn().mockResolvedValue({ results: [] }),
}));

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

  it('renders nothing when open=false (default)', () => {
    const { container } = render(<CommandPalette />, { wrapper: Wrapper });
    expect(container.firstChild).toBeNull();
  });

  it('renders search input when open=true', () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
  });

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when Cmd+K is pressed while open', () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    fireEvent.keyDown(document, { key: 'k', metaKey: true });
    expect(onClose).toHaveBeenCalled();
  });
});
