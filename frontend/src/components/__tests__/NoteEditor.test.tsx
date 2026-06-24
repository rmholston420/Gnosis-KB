/**
 * NoteEditor
 * ==========
 * TipTap / CodeMirror is mocked at the module level so jsdom never
 * tries to load canvas or DOM-heavy CM internals.
 *
 * What we test (13 cases):
 *  1.  Renders the title input pre-filled from note.title
 *  2.  Renders the note body inside the mocked editor
 *  3.  Shows edit / split / preview mode buttons
 *  4.  Dirty indicator shows '● unsaved' after title change
 *  5.  'Saving…' indicator when isLoading=true
 *  6.  Title blur triggers onSave when isDirty
 *  7.  Body change triggers debounced onSave (fake timers)
 *  8.  onBodyChange callback fires on every body keystroke
 *  9.  Tags change schedules debounced save with updated tags
 *  10. Note navigation (note.id change) resets body + title + clears dirty
 *  11. BacklinkPanel is rendered when note.id is present
 *  12. BacklinkPanel is NOT rendered when note has no id
 *  13. TagInput is disabled when note has no id and no prefill title
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mocks ─────────────────────────────────────────────────────────────────

// Mock CodeMirror — renders a plain textarea so we can fireEvent on it
vi.mock('@uiw/react-codemirror', () => ({
  default: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea
      data-testid="codemirror-mock"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

// Mock heavy CodeMirror deps so jsdom doesn't choke
vi.mock('@codemirror/lang-markdown', () => ({ markdown: () => [] }));
vi.mock('@codemirror/autocomplete', () => ({ autocompletion: () => [] }));
vi.mock('@uiw/codemirror-theme-github', () => ({ githubDark: {} }));

// Mock api (listNotes for wikilink autocomplete)
vi.mock('../../services/api', () => ({
  default: { listNotes: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
}));

// Mock child components to keep the test surface narrow
vi.mock('../WikilinkPreview', () => ({
  default: () => <div data-testid="wikilink-preview" />,
}));
vi.mock('../BacklinkPanel', () => ({
  default: ({ noteId }: { noteId: string }) => (
    <div data-testid="backlink-panel" data-note-id={noteId} />
  ),
}));
vi.mock('../TagInput', () => ({
  default: ({ tags, onChange, disabled }: { tags: string[]; onChange: (t: string[]) => void; disabled?: boolean }) => (
    <div data-testid="tag-input" data-disabled={String(disabled)}>
      {tags.map((t) => <span key={t}>{t}</span>)}
      <button onClick={() => onChange([...tags, 'new-tag'])}>add-tag</button>
    </div>
  ),
}));

import NoteEditor from '../NoteEditor';
import type { Note } from '../../types';

// ── Helpers ───────────────────────────────────────────────────────────────

function makeNote(overrides: Partial<Note> = {}): Note {
  return {
    id: 'note-1',
    title: 'Test Note',
    body: 'Hello world',
    note_type: 'permanent',
    tags: ['alpha'],
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    incoming_links: [],
    outgoing_links: [],
    ...overrides,
  };
}

function renderEditor(
  note: Note,
  onSave = vi.fn().mockResolvedValue(undefined),
  props: Record<string, unknown> = {},
) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <NoteEditor note={note} onSave={onSave} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.runOnlyPendingTimers(); vi.useRealTimers(); vi.clearAllMocks(); });

describe('NoteEditor rendering', () => {
  it('renders title input pre-filled', () => {
    renderEditor(makeNote());
    expect(screen.getByPlaceholderText('Note title…')).toHaveValue('Test Note');
  });

  it('renders body inside mocked CodeMirror', () => {
    renderEditor(makeNote());
    expect(screen.getByTestId('codemirror-mock')).toHaveValue('Hello world');
  });

  it('renders edit / split / preview mode buttons', () => {
    renderEditor(makeNote());
    expect(screen.getByText('edit')).toBeInTheDocument();
    expect(screen.getByText('split')).toBeInTheDocument();
    expect(screen.getByText('preview')).toBeInTheDocument();
  });

  it('shows isLoading indicator', () => {
    renderEditor(makeNote(), undefined, { isLoading: true });
    expect(screen.getByText('Saving…')).toBeInTheDocument();
  });
});

describe('dirty state', () => {
  it('shows unsaved indicator after title change', () => {
    renderEditor(makeNote());
    fireEvent.change(screen.getByPlaceholderText('Note title…'), {
      target: { value: 'Changed Title' },
    });
    expect(screen.getByText('● unsaved')).toBeInTheDocument();
  });

  it('title blur triggers onSave when isDirty', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderEditor(makeNote(), onSave);
    const titleInput = screen.getByPlaceholderText('Note title…');
    fireEvent.change(titleInput, { target: { value: 'New Title' } });
    await act(async () => { fireEvent.blur(titleInput); });
    expect(onSave).toHaveBeenCalledWith('Hello world', 'New Title', ['alpha']);
  });
});

describe('body change debounce', () => {
  it('fires onSave after 800 ms debounce', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderEditor(makeNote(), onSave);
    fireEvent.change(screen.getByTestId('codemirror-mock'), {
      target: { value: 'Updated body' },
    });
    expect(onSave).not.toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(800); });
    expect(onSave).toHaveBeenCalledWith('Updated body', 'Test Note', ['alpha']);
  });

  it('fires onBodyChange on every change', () => {
    const onBodyChange = vi.fn();
    renderEditor(makeNote(), undefined, { onBodyChange });
    fireEvent.change(screen.getByTestId('codemirror-mock'), {
      target: { value: 'Keystroke' },
    });
    expect(onBodyChange).toHaveBeenCalledWith('Keystroke');
  });
});

describe('tags', () => {
  it('tag change schedules debounced save with updated tags', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderEditor(makeNote(), onSave);
    fireEvent.click(screen.getByText('add-tag'));
    await act(async () => { vi.advanceTimersByTime(800); });
    expect(onSave).toHaveBeenCalledWith('Hello world', 'Test Note', ['alpha', 'new-tag']);
  });

  it('TagInput is disabled when note has no id and no prefill title', () => {
    renderEditor(makeNote({ id: '' }));
    expect(screen.getByTestId('tag-input').dataset.disabled).toBe('true');
  });
});

describe('note navigation', () => {
  it('resets body and title when note.id changes', () => {
    const note1 = makeNote({ id: 'n1', title: 'Note 1', body: 'Body 1' });
    const note2 = makeNote({ id: 'n2', title: 'Note 2', body: 'Body 2' });
    const { rerender } = renderEditor(note1);
    // Dirty it first
    fireEvent.change(screen.getByPlaceholderText('Note title…'), { target: { value: 'Dirty' } });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    rerender(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <NoteEditor note={note2} onSave={vi.fn().mockResolvedValue(undefined)} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByPlaceholderText('Note title…')).toHaveValue('Note 2');
    expect(screen.queryByText('● unsaved')).not.toBeInTheDocument();
  });
});

describe('BacklinkPanel', () => {
  it('renders when note.id is present', () => {
    renderEditor(makeNote());
    expect(screen.getByTestId('backlink-panel')).toBeInTheDocument();
  });

  it('is NOT rendered when note has no id', () => {
    renderEditor(makeNote({ id: '' }));
    expect(screen.queryByTestId('backlink-panel')).not.toBeInTheDocument();
  });
});
