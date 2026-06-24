import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => vi.fn(),
}));

import NoteCard from '@/components/NoteCard';
import type { Note } from '@/types';

const BASE: Note = {
  note_id:    'n1',
  id:         'n1',
  title:      'My Note',
  body:       '',
  slug:       'my-note',
  note_type:  'permanent',
  status:     'evergreen',
  folder:     '',
  tags:       ['alpha', 'beta'],
  word_count: 42,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
  modified_at:'2026-06-01T00:00:00Z',
};

function wrap(node: React.ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

describe('NoteCard', () => {
  it('renders title', () => {
    wrap(<NoteCard note={BASE} />);
    expect(screen.getByText('My Note')).toBeTruthy();
  });
});
