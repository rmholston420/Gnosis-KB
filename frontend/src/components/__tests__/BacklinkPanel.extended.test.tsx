/**
 * BacklinkPanel.extended.test.tsx
 * Targets uncovered lines:
 *   34  — lookupTitle with Map (map instanceof Map branch)
 *   70  — LinkChip onClick → navigate
 *   126-132 — outgoing section expand / "This note has no outgoing links" empty state
 */
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
  { source_id: 'note-a', target_id: 'note-1', link_text: 'Note A' },
];
const OUT: import('@/types').LinkRef[] = [
  { source_id: 'note-1', target_id: 'note-b', link_text: 'Note B' },
];

function wrap(props: React.ComponentProps<typeof BacklinkPanel>) {
  return render(
    <MemoryRouter>
      <BacklinkPanel {...props} />
    </MemoryRouter>
  );
}

describe('BacklinkPanel — empty state', () => {
  it('renders "No links" when both arrays are empty', () => {
    wrap({ noteId: 'note-1', incomingLinks: [], outgoingLinks: [] });
    expect(screen.getByText('No links')).toBeTruthy();
  });
});

describe('BacklinkPanel — lookupTitle with Map (line 34)', () => {
  it('resolves title from a Map', () => {
    const titleMap = new Map([['note-a', 'Alpha Note'], ['note-b', 'Beta Note']]);
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: [], noteTitlesById: titleMap });
    expect(screen.getByText('Alpha Note')).toBeTruthy();
  });

  it('resolves title from a plain Record', () => {
    const titleMap = { 'note-a': 'Alpha Note', 'note-b': 'Beta Note' };
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: [], noteTitlesById: titleMap });
    expect(screen.getByText('Alpha Note')).toBeTruthy();
  });

  it('falls back to id when map has no entry', () => {
    const titleMap = new Map<string, string>();
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: [], noteTitlesById: titleMap });
    expect(screen.getByText('note-a')).toBeTruthy();
  });

  it('falls back to id when noteTitlesById is undefined', () => {
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: [] });
    expect(screen.getByText('note-a')).toBeTruthy();
  });
});

describe('BacklinkPanel — LinkChip onClick (line 70)', () => {
  it('clicking an incoming link navigates to source note', () => {
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: [] });
    const chip = screen.getByRole('button', { name: /note-a/i });
    fireEvent.click(chip);
    expect(mockNavigate).toHaveBeenCalledWith('/notes/note-a');
  });

  it('clicking an outgoing link navigates to target note', () => {
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: OUT });
    // Expand outgoing section first
    const outgoingBtn = screen.getByText(/Links out/i).closest('button')!;
    fireEvent.click(outgoingBtn);
    const chip = screen.getByRole('button', { name: /note-b/i });
    fireEvent.click(chip);
    expect(mockNavigate).toHaveBeenCalledWith('/notes/note-b');
  });
});

describe('BacklinkPanel — outgoing section (lines 126-132)', () => {
  it('outgoing section is collapsed by default', () => {
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: OUT });
    // note-b chip should not be visible until expanded
    expect(screen.queryByText('note-b')).toBeNull();
  });

  it('clicking "Links out" header expands outgoing links', () => {
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: OUT });
    const outgoingBtn = screen.getByText(/Links out/i).closest('button')!;
    fireEvent.click(outgoingBtn);
    expect(screen.getByRole('button', { name: /note-b/i })).toBeTruthy();
  });

  it('shows empty message when outgoing is expanded but empty', () => {
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: [] });
    const outgoingBtn = screen.getByText(/Links out/i).closest('button')!;
    fireEvent.click(outgoingBtn);
    expect(screen.getByText(/This note has no outgoing links/i)).toBeTruthy();
  });

  it('top-level panel toggle collapses everything', () => {
    wrap({ noteId: 'note-1', incomingLinks: INC, outgoingLinks: OUT });
    // The top toggle shows "Links X"
    const topBtn = screen.getByText(/^Links \d+$/).closest('button')!;
    fireEvent.click(topBtn); // collapse
    expect(screen.queryByText('note-a')).toBeNull();
    fireEvent.click(topBtn); // re-expand
    expect(screen.getByRole('button', { name: /note-a/i })).toBeTruthy();
  });
});
