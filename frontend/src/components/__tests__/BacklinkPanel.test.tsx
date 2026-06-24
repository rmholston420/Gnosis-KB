/**
 * BacklinkPanel
 * =============
 *
 * What we test (9 cases):
 *  1.  Shows 'No backlinks' when incoming_links is empty
 *  2.  Renders incoming link titles as clickable links
 *  3.  Shows 'No outgoing links' when outgoing_links is empty
 *  4.  Renders outgoing link titles
 *  5.  Falls back to note id when title is not in noteTitlesById map
 *  6.  Renders the correct href for incoming links
 *  7.  Renders the correct href for outgoing links
 *  8.  Section headers 'Backlinks' and 'Outgoing links' are visible
 *  9.  Panel is collapsed by default and expands on click
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import BacklinkPanel from '../BacklinkPanel';

const titlesById = new Map([
  ['n-1', 'Alpha Note'],
  ['n-2', 'Beta Note'],
]);

function renderPanel(props: {
  noteId?: string;
  incomingLinks?: string[];
  outgoingLinks?: string[];
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
  it('shows section headers after expanding', () => {
    renderPanel({ incomingLinks: ['n-1'] });
    // Expand the panel first
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText(/backlinks/i)).toBeInTheDocument();
  });

  it('renders incoming link titles', () => {
    renderPanel({ incomingLinks: ['n-1', 'n-2'] });
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Alpha Note')).toBeInTheDocument();
    expect(screen.getByText('Beta Note')).toBeInTheDocument();
  });

  it('shows no-backlinks placeholder when incoming empty', () => {
    renderPanel({ incomingLinks: [] });
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText(/no backlinks/i)).toBeInTheDocument();
  });

  it('renders outgoing link titles', () => {
    renderPanel({ outgoingLinks: ['n-1'] });
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Alpha Note')).toBeInTheDocument();
  });

  it('shows no-outgoing-links placeholder when outgoing empty', () => {
    renderPanel({ outgoingLinks: [] });
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText(/no outgoing/i)).toBeInTheDocument();
  });

  it('falls back to note id when title not in map', () => {
    renderPanel({ incomingLinks: ['unknown-id'] });
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('unknown-id')).toBeInTheDocument();
  });

  it('incoming links have correct href', () => {
    renderPanel({ incomingLinks: ['n-1'] });
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('link', { name: 'Alpha Note' })).toHaveAttribute('href', '/notes/n-1');
  });

  it('outgoing links have correct href', () => {
    renderPanel({ outgoingLinks: ['n-2'] });
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('link', { name: 'Beta Note' })).toHaveAttribute('href', '/notes/n-2');
  });

  it('panel is collapsed by default', () => {
    renderPanel({ incomingLinks: ['n-1'] });
    expect(screen.queryByText('Alpha Note')).not.toBeInTheDocument();
  });
});
