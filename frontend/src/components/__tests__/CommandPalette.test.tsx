/**
 * CommandPalette.test.tsx
 * Tests for the ⌘K command palette component.
 * Spy on `listNotes` (the real export from api/notes).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import * as apiNotes from '../../api/notes';
import { CommandPalette } from '../CommandPalette';

const mockNotes = [
  { items: [
    { note_id: '1', title: 'Emptiness', body: '', tags: [], note_type: 'permanent', status: 'active', created_at: '', updated_at: '', folder: '', source_url: null },
    { note_id: '2', title: 'Dependent Origination', body: '', tags: [], note_type: 'permanent', status: 'active', created_at: '', updated_at: '', folder: '', source_url: null },
  ], total: 2, page: 1, limit: 200, pages: 1 },
];

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('CommandPalette', () => {
  beforeEach(() => {
    // listNotes is the real export; it returns PaginatedNotes
    vi.spyOn(apiNotes, 'listNotes').mockResolvedValue(mockNotes[0]);
  });

  it('renders nothing when open=false', () => {
    const { container } = render(
      <Wrapper><CommandPalette open={false} onClose={() => {}} /></Wrapper>
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders search input when open=true', async () => {
    render(<Wrapper><CommandPalette open={true} onClose={() => {}} /></Wrapper>);
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('shows all notes initially after load', async () => {
    render(<Wrapper><CommandPalette open={true} onClose={() => {}} /></Wrapper>);
    await waitFor(() => screen.getByText('Emptiness'));
    expect(screen.getByText('Dependent Origination')).toBeInTheDocument();
  });

  it('filters notes by typed query', async () => {
    render(<Wrapper><CommandPalette open={true} onClose={() => {}} /></Wrapper>);
    await waitFor(() => screen.getByText('Emptiness'));
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Dependent' } });
    await waitFor(() => expect(screen.queryByText('Emptiness')).toBeNull());
    expect(screen.getByText('Dependent Origination')).toBeInTheDocument();
  });

  it('calls onClose when Escape is pressed', async () => {
    const onClose = vi.fn();
    render(<Wrapper><CommandPalette open={true} onClose={onClose} /></Wrapper>);
    await waitFor(() => screen.getByRole('combobox'));
    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });
});
