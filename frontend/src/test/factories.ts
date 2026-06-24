/**
 * test/factories.ts — Test data factories.
 */
import type {
  Note,
  NoteListItem,
  SearchResult,
  NoteType,
  NoteStatus,
} from '../types';

export function makeNote(overrides: Partial<Note> = {}): Note {
  const note_id = overrides.note_id ?? overrides.id ?? 'note-001';
  return {
    note_id,
    id:         note_id,
    title:      'Test Note',
    body:       '# Test\n\nBody text.',
    note_type:  'permanent' as NoteType,
    status:     'active'   as NoteStatus,
    tags:       [],
    folder:     'inbox',
    word_count: 4,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    modified_at:'2025-01-01T00:00:00Z',
    ...overrides,
    note_id,       // always equal to resolved note_id
    id: note_id,   // always keep alias in sync
  };
}

export function makeNoteListItem(overrides: Partial<NoteListItem> = {}): NoteListItem {
  const note_id = overrides.note_id ?? overrides.id ?? 'note-001';
  return {
    note_id,
    id:        note_id,
    title:     'Test Note',
    note_type: 'permanent' as NoteType,
    status:    'active'    as NoteStatus,
    tags:      [],
    folder:    'inbox',
    word_count: 4,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    ...overrides,
    note_id,
    id: note_id,
  };
}

export function makeSearchResult(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    note_id:  'note-001',
    title:    'Test Result',
    excerpt:  'Test excerpt body.',
    snippet:  'Test excerpt body.',
    score:    0.9,
    folder:   'inbox',
    tags:     [],
    note_type:'permanent' as NoteType,
    ...overrides,
  };
}
