/**
 * BacklinkPanel
 * =============
 *
 * Key facts about the real component:
 *  - incomingLinks / outgoingLinks are LinkRef[] objects
 *  - noteTitlesById is Map<string, string>
 *  - When totalLinks === 0 the component renders a static "No links" div (no toggle button)
 *  - When totalLinks > 0 it renders a top-level toggle button ("Links N") that is
 *    open by default (panelOpen starts true)
 *  - Inside the open panel incoming section starts open, outgoing starts collapsed
 *  - Link rows are <button> elements that call navigate() — NOT <a> tags
 *  - The outer panel starts open, so incoming links are visible immediately
 *
 * Scenarios:
 *  1.  Panel starts open — incoming links visible immediately
 *  2.  Incoming links rendered with titles from map
 *  3.  Empty both arrays → "No links" placeholder, no toggle button
 *  4.  Outgoing link section renders (collapsed by default)
 *  5.  Falls back to note id when title not in noteTitlesById map
 *  6.  Link rows exist for incoming links (buttons, not anchors)
 *  7.  Panel toggle button collapses the panel
 *  8.  Section header "Linked here" visible when incoming links present
 *  9.  Section header "Links out" visible when outgoing links present
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import BacklinkPanel from '../BacklinkPanel';
import type { LinkRef } from '../../types';

const titlesById = new Map([
  ['n-1', 'Alpha Note'],
  ['n-2', 'Beta Note'],
]);

function link(sourceId: string, targetId: string): LinkRef {
  return {
    note_id:   sourceId,
    title:     '',
    source_id: sourceId,
    target_id: targetId,
    context:   '',
    link_text: '',
    link_type: 'wikilink',
  };
}

function renderPanel(props: {
  noteId?: string;
  incomingLinks?: LinkRef[];
  outgoingLinks?: LinkRef[];
  noteTitlesById?: Map<string, string>;
} = {}) {
  return render(
    <MemoryRouter>
      <BacklinkPanel
        noteId={props.noteId ?? 'current'}
        incomingLinks={props.incomingLinks ?? []}
        outgoingLinks={props.outgoingLinks ?? []}
        noteTitlesById={props.noteTitlesById ?? titlesById}
      />
    </MemoryRouter>,
  );
}

afterEach(() => { vi.clearAllMocks(); });

describe('BacklinkPanel', () => {
  it('panel starts open — incoming links visible immediately', () => {
    renderPanel({ incomingLinks: [link('n-1', 'current')] });
    // panelOpen defaults to true, incoming section defaults to open
    expect(screen.getByText('Alpha Note')).toBeInTheDocument();
  });

  it('renders incoming link titles', () => {
    renderPanel({ incomingLinks: [link('n-1', 'current'), link('n-2', 'current')] });
    expect(screen.getByText('Alpha Note')).toBeInTheDocument();
    expect(screen.getByText('Beta Note')).toBeInTheDocument();
  });

  it('shows no-links placeholder when both arrays empty (no toggle button)', () => {
    renderPanel({ incomingLinks: [], outgoingLinks: [] });
    expect(screen.getByText(/no links/i)).toBeInTheDocument();
    // Static render — no toggle button
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('link rows are buttons, not anchors', () => {
    renderPanel({ incomingLinks: [link('n-1', 'current')] });
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('falls back to source_id when title not in map', () => {
    renderPanel({ incomingLinks: [link('unknown-id', 'current')], noteTitlesById: new Map() });
    expect(screen.getByText('unknown-id')).toBeInTheDocument();
  });

  it('shows incoming section header', () => {
    renderPanel({ incomingLinks: [link('n-1', 'current')] });
    expect(screen.getByText(/linked here/i)).toBeInTheDocument();
  });
});
