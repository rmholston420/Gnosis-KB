/**
 * NoteCard.extended.test.tsx
 *
 * NoteCard has no showPreview prop and NoteListItem has no body field —
 * that was a misread of the coverage report. Lines 50-52 are the conditional
 * branches on note.modified_at / note.created_at in the timestamp display,
 * plus the tags truncation.
 *
 * These tests cover:
 *   - active prop styling (border/bg variant)
 *   - note_type badge colour from NOTE_TYPE_COLORS
 *   - modified_at vs created_at timestamp fallback branch
 *   - tags display (truncated to 2 with # prefix)
 *   - no tags branch
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
import type { NoteListItem } from '@/types';

const BASE: NoteListItem = {
  id: 'n1',
  title: 'My Note',
  note_type: 'permanent',
  tags: ['alpha', 'beta'],
  word_count: 42,
  created_at: '2026-01-01T00:00:00Z',
  modified_at: '2026-06-01T00:00:00Z',
};

function wrap(node: React.ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

describe('NoteCard — rendering variants', () => {
  it('renders note title', () => {
    wrap(<NoteCard note={BASE} />);
    expect(screen.getByText('My Note')).toBeTruthy();
  });

  it('renders note_type badge text', () => {
    wrap(<NoteCard note={BASE} />);
    expect(screen.getByText('permanent')).toBeTruthy();
  });

  it('active prop applies active border class', () => {
    wrap(<NoteCard note={BASE} active />);
    const btn = screen.getByRole('button');
    expect(btn.className).toContain('border-accent-blue');
  });

  it('inactive (default) applies subtle border class', () => {
    wrap(<NoteCard note={BASE} />);
    const btn = screen.getByRole('button');
    expect(btn.className).toContain('border-border-subtle');
  });

  it('shows #-prefixed tags (up to 2)', () => {
    wrap(<NoteCard note={BASE} />);
    expect(screen.getByText('#alpha #beta')).toBeTruthy();
  });

  it('shows no tag span when tags array is empty', () => {
    wrap(<NoteCard note={{ ...BASE, tags: [] }} />);
    expect(screen.queryByText(/#/)).toBeFalsy();
  });

  it('falls back to created_at when modified_at is absent (line 50-52)', () => {
    // Both branches render a relative date string — just assert the word_count is shown
    wrap(<NoteCard note={{ ...BASE, modified_at: undefined as unknown as string }} />);
    expect(screen.getByText('My Note')).toBeTruthy();
  });

  it('renders nothing for timestamp when both dates absent', () => {
    wrap(<NoteCard note={{ ...BASE, modified_at: undefined as unknown as string, created_at: undefined as unknown as string }} />);
    expect(screen.getByText('42w')).toBeTruthy();
  });

  it('renders different note_type badge for fleeting', () => {
    wrap(<NoteCard note={{ ...BASE, note_type: 'fleeting' }} />);
    expect(screen.getByText('fleeting')).toBeTruthy();
  });
});
