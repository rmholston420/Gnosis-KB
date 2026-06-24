import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';

import WikilinkPopup, { type PopupState } from '@/components/WikilinkPopup';
import type { NoteListItem } from '@/types';

function makeNote(overrides: Partial<NoteListItem & { body?: string }> = {}): NoteListItem & { body?: string } {
  return {
    note_id:    overrides.note_id    ?? 'n1',
    id:         overrides.id         ?? 'n1',
    title:      overrides.title      ?? 'Test Note',
    slug:       overrides.slug       ?? 'test-note',
    note_type:  overrides.note_type  ?? 'permanent',
    status:     overrides.status     ?? 'evergreen',
    folder:     overrides.folder     ?? '',
    word_count: overrides.word_count ?? 100,
    created_at: overrides.created_at ?? '2024-01-01T00:00:00Z',
    updated_at: overrides.updated_at ?? '2024-01-01T00:00:00Z',
    modified_at:overrides.modified_at ?? '2024-01-01T00:00:00Z',
    tags:       overrides.tags       ?? [],
    body:       overrides.body       ?? 'Body',
  };
}

describe('WikilinkPopup', () => {
  it('renders note title', () => {
    const state: PopupState = { note: makeNote(), anchorRect: new DOMRect(10, 10, 0, 0) };
    render(
      <MemoryRouter>
        <WikilinkPopup state={state} onClose={() => {}} />
      </MemoryRouter>
    );
    expect(screen.getByText('Test Note')).toBeTruthy();
  });

  it('renders nothing when state is null', () => {
    const { container } = render(
      <MemoryRouter>
        <WikilinkPopup state={null} onClose={() => {}} />
      </MemoryRouter>
    );
    expect(container.firstChild).toBeNull();
  });
});
