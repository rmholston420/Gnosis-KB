import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import BacklinkPanel from '@/components/BacklinkPanel';

const INC: import('@/types').LinkRef[] = [
  { source_id: 'note-a', target_id: 'note-1', link_text: 'Note A', link_type: 'wiki' },
];
const OUT: import('@/types').LinkRef[] = [
  { source_id: 'note-1', target_id: 'note-b', link_text: 'Note B', link_type: 'wiki' },
];

function wrap(props: React.ComponentProps<typeof BacklinkPanel>) {
  return render(
    <MemoryRouter>
      <BacklinkPanel {...props} />
    </MemoryRouter>
  );
}

describe('BacklinkPanel', () => {
  it('renders empty state', () => {
    wrap({ noteId: 'note-1', incomingLinks: [], outgoingLinks: [] });
    expect(screen.getByText('No links')).toBeTruthy();
  });

  it('resolves title from a Map', () => {
    const titleMap = new Map([['note-a', 'Alpha Note']]);
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: [], noteTitlesById: titleMap });
    expect(screen.getByText('Alpha Note')).toBeTruthy();
  });

  it('clicking an incoming link navigates', () => {
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: [] });
    fireEvent.click(screen.getByRole('button', { name: /note-a/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/notes/note-a');
  });

  it('shows outgoing empty message when expanded', () => {
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: [] });
    fireEvent.click(screen.getByText(/Links out/i).closest('button')!);
    expect(screen.getByText(/This note has no outgoing links/i)).toBeTruthy();
  });
});
