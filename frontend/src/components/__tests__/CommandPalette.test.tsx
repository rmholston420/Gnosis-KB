import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ── Stub heavy deps ────────────────────────────────────────────────────────────
vi.mock('@/api/notes', () => ({
  fetchNoteStubs: vi.fn().mockResolvedValue([{ note_id: '1', title: 'Alpha' }]),
}));
vi.mock('@/api/search', () => ({
  searchNotes: vi.fn().mockResolvedValue({ results: [] }),
}));

import CommandPalette from '@/components/CommandPalette';

const onClose = vi.fn();

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('CommandPalette', () => {
  beforeEach(() => { onClose.mockReset(); });

  it('renders search input when open=true', () => {
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/search|go to/i)).toBeInTheDocument();
  });

  it('calls onClose when Escape is pressed', () => {
    render(<CommandPalette open onClose={onClose} />, { wrapper: Wrapper });
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('does not render input when open=false', () => {
    render(<CommandPalette open={false} onClose={onClose} />, { wrapper: Wrapper });
    expect(screen.queryByPlaceholderText(/search|go to/i)).toBeNull();
  });
});
