import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import WikilinkPreview from '@/components/WikilinkPreview';
import type { NoteListItem } from '@/types';

vi.mock('dompurify', () => ({
  default: { sanitize: (html: string) => html },
}));

function makeNote(overrides: Partial<NoteListItem> = {}): NoteListItem {
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
  };
}

describe('WikilinkPreview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders body text', () => {
    render(
      <MemoryRouter>
        <WikilinkPreview body="Hello world" notes={[makeNote()]} />
      </MemoryRouter>
    );
    expect(screen.getByText(/Hello world/)).toBeTruthy();
  });

  it('renders with empty notes array', () => {
    const { container } = render(
      <MemoryRouter>
        <WikilinkPreview body="Some text" notes={[]} />
      </MemoryRouter>
    );
    expect(container).toBeTruthy();
  });
});
