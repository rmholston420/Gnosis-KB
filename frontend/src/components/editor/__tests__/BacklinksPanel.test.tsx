/**
 * BacklinksPanel.test.tsx
 * Spy on `getBacklinks` (the real named export from api/notes).
 *
 * getBacklinks returns BacklinksResponse: { backlinks: Note[], count: number }
 * The mock must match that envelope shape.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import * as notesApi from '../../../api/notes';
import { BacklinksPanel } from '../BacklinksPanel';

const backlinkNotes = [
  {
    note_id: 'bl-1',
    title: 'Dependent Origination',
    body: '',
    tags: [],
    note_type: 'permanent',
    status: 'active',
    created_at: '',
    updated_at: '',
    folder: '',
    source_url: null,
  },
  {
    note_id: 'bl-2',
    title: 'Emptiness',
    body: '',
    tags: [],
    note_type: 'permanent',
    status: 'active',
    created_at: '',
    updated_at: '',
    folder: '',
    source_url: null,
  },
];

// BacklinksResponse envelope expected by the component
const backlinkFixture = { backlinks: backlinkNotes, count: 2 };

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('BacklinksPanel', () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it('shows empty state when noteId is null', () => {
    render(<Wrapper><BacklinksPanel noteId={null} /></Wrapper>);
    expect(screen.getByText(/no notes link to this one yet/i)).toBeInTheDocument();
  });

  it('renders backlink titles after load', async () => {
    vi.spyOn(notesApi, 'getBacklinks').mockResolvedValue(backlinkFixture as never);
    render(<Wrapper><BacklinksPanel noteId="xyz" /></Wrapper>);
    await waitFor(() => screen.getByText('Dependent Origination'));
    expect(screen.getByText('Emptiness')).toBeInTheDocument();
  });

  it('shows empty state when backlinks array is empty', async () => {
    vi.spyOn(notesApi, 'getBacklinks').mockResolvedValue({ backlinks: [], count: 0 } as never);
    render(<Wrapper><BacklinksPanel noteId="xyz" /></Wrapper>);
    await waitFor(() => screen.getByText(/no notes link to this one yet/i));
    expect(screen.getByText(/no notes link to this one yet/i)).toBeInTheDocument();
  });
});
