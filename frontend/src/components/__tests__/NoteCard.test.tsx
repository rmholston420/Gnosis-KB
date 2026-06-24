import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { createElement } from 'react';
import NoteCard from '../NoteCard';
import { makeNote } from '../../test/factories';

function wrap(props: React.ComponentProps<typeof NoteCard>) {
  return render(createElement(MemoryRouter, null, createElement(NoteCard, props)));
}

describe('NoteCard', () => {
  it('renders title', () => {
    wrap({ note: makeNote({ title: 'The Dharma of Code' }) });
    expect(screen.getByText('The Dharma of Code')).toBeInTheDocument();
  });

  it('renders note type badge', () => {
    wrap({ note: makeNote({ note_type: 'literature' }) });
    expect(screen.getByText(/literature/i)).toBeInTheDocument();
  });

  it('renders tags when present', () => {
    wrap({ note: makeNote({ tags: ['buddhism', 'practice'] }) });
    expect(screen.getByText('buddhism')).toBeInTheDocument();
    expect(screen.getByText('practice')).toBeInTheDocument();
  });

  it('links to note detail page', () => {
    wrap({ note: makeNote({ note_id: 'abc-123' }) });
    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).toContain('abc-123');
  });
});
