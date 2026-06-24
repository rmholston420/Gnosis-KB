import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import WikilinkPreview from '@/components/WikilinkPreview';
import type { NoteListItem } from '@/types';

function makeNote(overrides: Partial<NoteListItem> = {}): NoteListItem {
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
    ...overrides,
  };
}

describe('WikilinkPreview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders title', () => {
    render(<WikilinkPreview note={makeNote()} />);
    expect(screen.getByText('Test Note')).toBeTruthy();
  });
});
