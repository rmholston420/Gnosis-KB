import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../../services/api', () => ({
  default: {
    summarizeNote: vi.fn().mockResolvedValue({ summary: 'A summary.' }),
    critiqueNote: vi.fn().mockResolvedValue({ overall: 'Good note.' }),
    suggestLinks: vi.fn().mockResolvedValue({ suggestions: [] }),
    ingestNote: vi.fn().mockResolvedValue({}),
  },
}));

import NoteDetailPanel from '../NoteDetailPanel';
import type { Note } from '../../types';

const baseNote: Note = {
  id: 'note-abc',
  title: 'Śūnyatā',
  slug: 'sunyata',
  body: '## Emptiness\n\nAll phenomena lack inherent existence. See also [[Dependent Origination]].',
  note_type: 'permanent',
  status: 'evergreen',
  tags: ['buddhism', 'madhyamaka'],
  folder: '',
  created_at: '2025-01-01T00:00:00Z',
  modified_at: '2025-06-01T00:00:00Z',
  incoming_links: [],
  outgoing_links: [],
  frontmatter: {},
  word_count: 12,
};

const onClose = vi.fn();

function renderPanel(note: Note = baseNote, onWikilinkClick?: (t: string) => void) {
  return render(
    <MemoryRouter>
      <NoteDetailPanel note={note} onClose={onClose} onWikilinkClick={onWikilinkClick} />
    </MemoryRouter>
  );
}

beforeEach(() => {
  onClose.mockReset();
  mockNavigate.mockReset();
});

describe('NoteDetailPanel', () => {
  it('renders note title', () => {
    renderPanel();
    expect(screen.getByText('Śūnyatā')).toBeTruthy();
  });
});
