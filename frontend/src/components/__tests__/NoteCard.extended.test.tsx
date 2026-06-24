/**
 * NoteCard.extended.test.tsx
 * Targets uncovered lines 50-52 (NoteCard.tsx):
 *   The preview snippet is shown only when the note has a `body` field
 *   and `showPreview` is true.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => vi.fn(),
}));

import NoteCard from '@/components/NoteCard';

const BASE_NOTE = {
  id: 'n1',
  title: 'Test Note',
  tags: ['tag1'],
  updated_at: '2026-01-01T00:00:00Z',
};

describe('NoteCard — preview snippet (lines 50-52)', () => {
  it('renders body preview when body is present and showPreview=true', () => {
    const note = { ...BASE_NOTE, body: 'This is the note body preview text.' };
    render(
      <MemoryRouter>
        <NoteCard note={note as Parameters<typeof NoteCard>[0]['note']} showPreview />
      </MemoryRouter>
    );
    expect(screen.getByText(/This is the note body preview text/i)).toBeTruthy();
  });

  it('does not render body when showPreview is false', () => {
    const note = { ...BASE_NOTE, body: 'Hidden body text.' };
    render(
      <MemoryRouter>
        <NoteCard note={note as Parameters<typeof NoteCard>[0]['note']} showPreview={false} />
      </MemoryRouter>
    );
    expect(screen.queryByText(/Hidden body text/i)).toBeFalsy();
  });

  it('renders without body when note has no body field', () => {
    render(
      <MemoryRouter>
        <NoteCard note={BASE_NOTE as Parameters<typeof NoteCard>[0]['note']} showPreview />
      </MemoryRouter>
    );
    expect(screen.getByText('Test Note')).toBeTruthy();
  });
});
