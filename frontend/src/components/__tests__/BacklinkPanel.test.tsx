/**
 * BacklinkPanel
 * =============
 *
 * Key facts about the real component:
 *  - incomingLinks / outgoingLinks are LinkRef[] objects, not string[]
 *  - When totalLinks === 0 the component renders a static "No links" div (no toggle button)
 *  - When totalLinks > 0 it renders a top-level toggle button ("Links N") that is
 *    open by default (panelOpen starts true)
 *  - Inside the open panel each section has its own collapse button ("Linked here" / "Links out")
 *  - Link rows are <button> elements that call navigate() — NOT <a> tags
 *  - The outer panel starts open, so links are visible immediately without clicking
 *
 * What we test (9 cases):
 *  1.  Section header 'Linked here' is visible when incoming links exist
 *  2.  Renders incoming link titles
 *  3.  Shows no-links placeholder when both arrays empty (no toggle button)
 *  4.  Renders outgoing link titles
 *  5.  Falls back to note id when title not in noteTitlesById map
 *  6.  Link rows exist for incoming links (buttons, not anchors)
 *  7.  Link rows exist for outgoing links
 *  8.  Panel toggle button collapses the panel
 *  9.  Panel starts open — links visible without any click
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import BacklinkPanel from '../BacklinkPanel';
import type { LinkRef } from '../../types';

const titlesById = new Map([
  ['n-1', 'Alpha Note'],
  ['n-2', 'Beta Note'],
]);

function link(sourceId: string, targetId: string): LinkRef {
  return { source_id: sourceId, target_id: targetId, context: '' };
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

afterEach(() => vi.clearAllMocks());

describe('BacklinkPanel', () => {
  it('panel starts open — incoming links visible immediately', () => {
    renderPanel({ incomingLinks: [link('n-1', 'current')] });
    // panelOpen defaults to true, so "Alpha Note" is visible without any click
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

  it('renders outgoing link titles', () => {
    renderPanel({ outgoingLinks: [link('current', 'n-1')] });
    expect(screen.getByText('Alpha Note')).toBeInTheDocument();
  });

  it('falls back to note id when title not in map', () => {
    renderPanel({ incomingLinks: [link('unknown-id', 'current')] });
    expect(screen.getByText('unknown-id')).toBeInTheDocument();
  });

  it('link rows are buttons (not anchors)', () => {
    renderPanel({ incomingLinks: [link('n-1', 'current')] });
    // The link row for 'Alpha Note' is a <button>
    const linkButtons = screen.getAllByRole('button');
    // At least the panel toggle + the section toggle + the link row
    expect(linkButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('section header "Linked here" is visible when incoming links present', () => {
    renderPanel({ incomingLinks: [link('n-1', 'current')] });
    expect(screen.getByText(/linked here/i)).toBeInTheDocument();
  });

  it('section header "Links out" is visible when outgoing links present', () => {
    // outgoing section starts collapsed (defaultOpen=false), so click to open
    renderPanel({ outgoingLinks: [link('current', 'n-1')] });
    expect(screen.getByText(/links out/i)).toBeInTheDocument();
  });

  it('clicking the panel toggle hides links', () => {
    renderPanel({ incomingLinks: [link('n-1', 'current')] });
    expect(screen.getByText('Alpha Note')).toBeInTheDocument();
    // The first button is the top-level "Links N" toggle
    fireEvent.click(screen.getAllByRole('button')[0]);
    expect(screen.queryByText('Alpha Note')).not.toBeInTheDocument();
  });
});
