import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';

import WikilinkPopup, { type PopupState } from '@/components/WikilinkPopup';
import type { NoteListItem } from '@/types';

function makeNote(overrides: Partial<NoteListItem & { body?: string }> = {}): NoteListItem & { body?: string } {
  return {
    id: 'n1',
    title: 'Test Note',
    slug: 'test-note',
    note_type: 'permanent',
    status: 'evergreen',
    folder: overrides.folder ?? '',
    word_count: 100,
    created_at: overrides.created_at ?? '2024-01-01T00:00:00Z',
    modified_at: overrides.modified_at ?? '2024-01-01T00:00:00Z',
    tags: [],
    body: overrides.body ?? 'Body',
    ...overrides,
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
