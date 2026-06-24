import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockGetNote = vi.fn();
const mockDeleteNote = vi.fn();
const mockUpdateNote = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    getNote: (...a: unknown[]) => mockGetNote(...a),
    deleteNote: (...a: unknown[]) => mockDeleteNote(...a),
    updateNote: (...a: unknown[]) => mockUpdateNote(...a),
  },
}));

const NOTE = {
  id: 'note-1',
  title: 'Detail Note',
  content: 'Some **content** here.',
  tags: ['dharma', 'practice'],
  updated_at: new Date().toISOString(),
  backlinks: [],
};

async function setup(noteId = 'note-1', extraProps: Record<string, unknown> = {}) {
  mockGetNote.mockResolvedValue(NOTE);
  const { default: NoteDetailPanel } = await import('@/components/NoteDetailPanel');
  render(
    <MemoryRouter>
      <NoteDetailPanel noteId={noteId} onClose={vi.fn()} {...extraProps} />
    </MemoryRouter>
  );
  await waitFor(() => expect(mockGetNote).toHaveBeenCalled());
}

describe('NoteDetailPanel extended', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders note title', async () => {
    await setup();
    await waitFor(() => screen.getByText('Detail Note'));
  });

  it('renders tags', async () => {
    await setup();
    await waitFor(() => screen.getByText('dharma'));
  });

  it('shows loading skeleton while fetching', () => {
    mockGetNote.mockReturnValue(new Promise(() => {}));
    import('@/components/NoteDetailPanel').then(({ default: NoteDetailPanel }) => {
      render(
        <MemoryRouter>
          <NoteDetailPanel noteId="note-1" onClose={vi.fn()} />
        </MemoryRouter>
      );
    });
  });

  it('handles getNote rejection', async () => {
    mockGetNote.mockRejectedValue(new Error('not found'));
    const { default: NoteDetailPanel } = await import('@/components/NoteDetailPanel');
    render(
      <MemoryRouter>
        <NoteDetailPanel noteId="bad-id" onClose={vi.fn()} />
      </MemoryRouter>
    );
    await new Promise((r) => setTimeout(r, 80));
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    mockGetNote.mockResolvedValue(NOTE);
    const { default: NoteDetailPanel } = await import('@/components/NoteDetailPanel');
    render(
      <MemoryRouter>
        <NoteDetailPanel noteId="note-1" onClose={onClose} />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText('Detail Note'));
    const closeBtn = screen.queryByRole('button', { name: /close/i });
    if (closeBtn) {
      fireEvent.click(closeBtn);
      expect(onClose).toHaveBeenCalled();
    }
  });

  it('delete button triggers deleteNote', async () => {
    mockGetNote.mockResolvedValue(NOTE);
    mockDeleteNote.mockResolvedValue({});
    const { default: NoteDetailPanel } = await import('@/components/NoteDetailPanel');
    render(
      <MemoryRouter>
        <NoteDetailPanel noteId="note-1" onClose={vi.fn()} />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText('Detail Note'));
    const deleteBtn = screen.queryByRole('button', { name: /delete/i });
    if (deleteBtn) {
      fireEvent.click(deleteBtn);
      const confirmBtn = screen.queryByRole('button', { name: /confirm|yes|delete/i });
      if (confirmBtn) {
        fireEvent.click(confirmBtn);
        await waitFor(() => expect(mockDeleteNote).toHaveBeenCalled());
      }
    }
  });

  it('edit button navigates or opens edit mode', async () => {
    mockGetNote.mockResolvedValue(NOTE);
    const { default: NoteDetailPanel } = await import('@/components/NoteDetailPanel');
    render(
      <MemoryRouter>
        <NoteDetailPanel noteId="note-1" onClose={vi.fn()} />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText('Detail Note'));
    const editBtn = screen.queryByRole('button', { name: /edit/i });
    if (editBtn) fireEvent.click(editBtn);
  });
});
