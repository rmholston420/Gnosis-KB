/**
 * Test factories — create fully-typed domain objects for use in tests.
 * All required fields are present; callers can override with Partial<T>.
 */
import type { Note, NoteListItem, SearchResult, NoteType, NoteStatus } from '../types';

export function makeNote(overrides: Partial<Note> = {}): Note {
  const id = overrides.note_id ?? overrides.id ?? 'note-001';
  return {
    note_id:        id,
    id,
    title:          'Test Note',
    slug:           'test-note',
    body:           '# Test\n\nBody content.',
    body_html:      '<h1>Test</h1><p>Body content.</p>',
    note_type:      'permanent' as NoteType,
    status:         'evergreen' as NoteStatus,
    folder:         'inbox',
    word_count:     10,
    is_deleted:     false,
    vector_indexed: false,
    graph_indexed:  false,
    frontmatter:    {},
    tags:           [],
    outgoing_links: [],
    incoming_links: [],
    ...overrides,
  };
}

export function makeListItem(overrides: Partial<NoteListItem> = {}): NoteListItem {
  const id = overrides.note_id ?? overrides.id ?? 'note-001';
  return {
    note_id:   id,
    id,
    title:     'Test Note',
    slug:      'test-note',
    note_type: 'permanent' as NoteType,
    status:    'evergreen' as NoteStatus,
    folder:    'inbox',
    word_count: 10,
    tags:      [],
    ...overrides,
  };
}

export function makeSearchResult(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    note_id:  'note-001',
    title:    'Test Result',
    slug:     'test-result',
    folder:   'inbox',
    ...overrides,
  };
}
