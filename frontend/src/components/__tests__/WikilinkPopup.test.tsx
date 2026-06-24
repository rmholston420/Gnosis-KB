/**
 * WikilinkPopup.test.tsx
 * ======================
 * Tests for the hover popup shown when hovering a resolved [[wikilink]].
 *
 * Cases (10):
 *  1.  Returns null when state is null
 *  2.  Renders the note title
 *  3.  Renders up to 3 tags with # prefix
 *  4.  Renders body snippet (truncated at 160 chars with ellipsis)
 *  5.  Renders "No preview available." when body is absent
 *  6.  Short body renders without ellipsis
 *  7.  Tags section is absent when tags is empty
 *  8.  Clicking the ExternalLink button navigates to /notes/:id
 *  9.  onClose fires when the mouse leaves the popup div
 * 10.  Does not render tags beyond the first 3
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import WikilinkPopup, { type PopupState } from '../WikilinkPopup';
import type { NoteListItem } from '../../types';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

function makeNote(overrides: Partial<NoteListItem & { body?: string }> = {}): NoteListItem & { body?: string } {
  return {
    id:         overrides.id         ?? 'note-1',
    title:      overrides.title      ?? 'Test Note',
    slug:       overrides.slug       ?? 'test-note',
    note_type:  overrides.note_type  ?? 'permanent',
    body:       overrides.body,
    tags:       overrides.tags       ?? [],
    created_at: overrides.created_at ?? '2024-01-01T00:00:00Z',
    updated_at: overrides.updated_at ?? '2024-01-01T00:00:00Z',
    word_count: overrides.word_count ?? 0,
    folder:     overrides.folder     ?? null,
  };
}

function makeRect(overrides: Partial<DOMRect> = {}): DOMRect {
  return {
    top: 100, bottom: 120, left: 50, right: 150,
    width: 100, height: 20, x: 50, y: 100,
    toJSON: () => ({}),
    ...overrides,
  } as DOMRect;
}

function setup(state: PopupState | null, onClose = vi.fn()) {
  return render(
    <MemoryRouter>
      <WikilinkPopup state={state} onClose={onClose} />
    </MemoryRouter>,
  );
}

describe('WikilinkPopup', () => {
  it('renders nothing when state is null', () => {
    const { container } = setup(null);
    expect(container.firstChild).toBeNull();
  });

  it('renders the note title', () => {
    setup({ note: makeNote({ title: 'My Title' }), anchorRect: makeRect() });
    expect(screen.getByText('My Title')).toBeInTheDocument();
  });

  it('renders up to 3 tags with # prefix', () => {
    setup({
      note: makeNote({ tags: ['alpha', 'beta', 'gamma', 'delta'] }),
      anchorRect: makeRect(),
    });
    expect(screen.getByText('#alpha')).toBeInTheDocument();
    expect(screen.getByText('#beta')).toBeInTheDocument();
    expect(screen.getByText('#gamma')).toBeInTheDocument();
    expect(screen.queryByText('#delta')).not.toBeInTheDocument();
  });

  it('renders body snippet truncated at 160 chars with ellipsis', () => {
    const longBody = 'x'.repeat(200);
    setup({ note: makeNote({ body: longBody }), anchorRect: makeRect() });
    // Snippet should be first 160 chars + ellipsis
    expect(screen.getByText(`${'x'.repeat(160)}\u2026`)).toBeInTheDocument();
  });

  it('renders body snippet without ellipsis when body <= 160 chars', () => {
    const shortBody = 'Short body text.';
    setup({ note: makeNote({ body: shortBody }), anchorRect: makeRect() });
    expect(screen.getByText('Short body text.')).toBeInTheDocument();
    // Should not contain ellipsis
    expect(screen.queryByText(/\u2026/)).not.toBeInTheDocument();
  });

  it('renders "No preview available." when body is absent', () => {
    setup({ note: makeNote({ body: undefined }), anchorRect: makeRect() });
    expect(screen.getByText('No preview available.')).toBeInTheDocument();
  });

  it('does not render the tags section when tags is empty', () => {
    setup({ note: makeNote({ tags: [] }), anchorRect: makeRect() });
    // No # prefixed elements should appear
    expect(screen.queryByText(/#/)).toBeNull();
  });

  it('clicking the open-note button navigates to /notes/:id', () => {
    setup({ note: makeNote({ id: 'note-42' }), anchorRect: makeRect() });
    fireEvent.click(screen.getByTitle('Open note'));
    expect(mockNavigate).toHaveBeenCalledWith('/notes/note-42');
  });

  it('onClose fires when the mouse leaves the popup container', () => {
    const onClose = vi.fn();
    setup({ note: makeNote(), anchorRect: makeRect() }, onClose);
    fireEvent.mouseLeave(document.querySelector('.wikilink-popup')!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
