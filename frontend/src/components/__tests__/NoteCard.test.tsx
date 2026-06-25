/**
 * NoteCard component
 *
 * What we test:
 *  1. Renders the note title
 *  2. Renders the note_type badge
 *  3. Renders word count
 *  4. Renders up to 2 tags with # prefix
 *  5. Does NOT render a tag section when tags is empty
 *  6. Navigates to /notes/:id on click
 *  7. Applies active styling when active=true
 *  8. Applies inactive styling when active=false/omitted
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NoteCard from '../NoteCard';
import { makeNote } from '../../test/factories';

// Capture navigate calls without a real router history
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

beforeEach(() => {
  mockNavigate.mockClear();
});

function renderCard(overrides = {}, active = false) {
  const note = makeNote(overrides);
  render(
    <MemoryRouter>
      <NoteCard note={note} active={active} />
    </MemoryRouter>
  );
  return note;
}

describe('NoteCard rendering', () => {
  it('displays the note title', () => {
    renderCard({ title: 'My Zettel' });
    expect(screen.getByRole('heading', { name: /My Zettel/i })).toBeInTheDocument();
  });

  it('displays the note_type badge', () => {
    renderCard({ note_type: 'literature' });
    expect(screen.getByText('literature')).toBeInTheDocument();
  });

  it('displays word count with trailing w', () => {
    renderCard({ word_count: 123 });
    expect(screen.getByText('123w')).toBeInTheDocument();
  });

  it('renders up to 2 tags with # prefix', () => {
    renderCard({ tags: ['pkm', 'philosophy', 'ignored'] });
    expect(screen.getByText('#pkm #philosophy')).toBeInTheDocument();
  });

  it('does not render tag section when tags is empty', () => {
    renderCard({ tags: [] });
    expect(screen.queryByText(/#/)).toBeNull();
  });
});

describe('NoteCard interaction', () => {
  it('calls navigate with /notes/:id on click', () => {
    const note = renderCard({ id: 'note-xyz' });
    fireEvent.click(screen.getByRole('button'));
    expect(mockNavigate).toHaveBeenCalledWith(`/notes/${note.id}`);
  });
});

describe('NoteCard active styling', () => {
  it('applies active border class when active=true', () => {
    renderCard({}, true);
    const btn = screen.getByRole('button');
    expect(btn.className).toContain('border-accent-blue');
  });

  it('applies inactive border class when active=false', () => {
    renderCard({}, false);
    const btn = screen.getByRole('button');
    expect(btn.className).toContain('border-border-subtle');
  });
});
