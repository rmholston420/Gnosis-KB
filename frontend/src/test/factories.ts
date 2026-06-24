/**
 * Test data factories.
 * Each factory returns a fully-shaped object with sensible defaults;
 * pass overrides as needed in individual tests.
 */

import type { NoteListItem } from '../types';

let _seq = 0;
const seq = () => ++_seq;

export function makeNote(overrides: Partial<NoteListItem> = {}): NoteListItem {
  const n = seq();
  return {
    id:          `note-${n}`,
    title:       `Test Note ${n}`,
    slug:        `test-note-${n}`,
    note_type:   'permanent',
    status:      'draft' as const,
    tags:        [],
    word_count:  42,
    created_at:  '2025-01-01T00:00:00Z',
    modified_at: '2025-06-01T12:00:00Z',
    ...overrides,
  };
}
