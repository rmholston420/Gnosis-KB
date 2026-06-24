/**
 * editorStore — Zustand slice for active note editor state.
 * Tracks the currently open note, dirty flag, and autosave status.
 *
 * Exports two stores:
 *   useEditorStore       — active note + dirty tracking
 *   useCommandPaletteStore — ⌘K palette open/close
 *
 * The EditorState interface exposes both the canonical API
 * (activeNote, isDirty, editorContent, …) and test-friendly aliases
 * (body, title, mode, pendingChanges, setBody, setTitle, setMode).
 */
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { Note } from '../types';

export type EditorViewMode = 'edit' | 'preview' | 'split';

export interface EditorState {
  /** Currently open note, or null if none. */
  activeNote:   Note | null;
  /** True if the editor has unsaved changes. */
  isDirty:      boolean;
  /** Alias for isDirty — used by unit tests. */
  pendingChanges: boolean;
  /** Milliseconds since last save (null = never saved this session). */
  lastSavedAt:  number | null;
  /** True while an autosave request is in-flight. */
  isSaving:     boolean;
  /** The raw editor content (markdown string). */
  editorContent: string;
  /** Alias for editorContent — used by unit tests. */
  body:  string;
  /** Active note title mirror — used by unit tests. */
  title: string;
  /** Note ID of the active note — used by unit tests. */
  noteId: string | null;
  /** Current view mode. */
  mode:  EditorViewMode;

  // ── Canonical actions ──────────────────────────────────────────────
  setActiveNote:    (note: Note | null) => void;
  setEditorContent: (content: string) => void;
  markDirty:        () => void;
  markClean:        () => void;
  setSaving:        (saving: boolean) => void;
  markSaved:        () => void;
  reset:            () => void;

  // ── Test-friendly alias actions ────────────────────────────────────
  setBody:   (body: string) => void;
  setTitle:  (title: string) => void;
  setMode:   (mode: EditorViewMode) => void;
  setNoteId: (id: string | null) => void;
}

export const useEditorStore = create<EditorState>()(immer((set) => ({
  activeNote:     null,
  isDirty:        false,
  pendingChanges: false,
  lastSavedAt:    null,
  isSaving:       false,
  editorContent:  '',
  body:           '',
  title:          '',
  noteId:         null,
  mode:           'edit',

  setActiveNote: (note) => set((s) => {
    s.activeNote     = note;
    s.editorContent  = note?.body ?? '';
    s.body           = note?.body ?? '';
    s.title          = note?.title ?? '';
    s.noteId         = note?.note_id ?? null;
    s.isDirty        = false;
    s.pendingChanges = false;
    s.isSaving       = false;
  }),

  setEditorContent: (content) => set((s) => {
    s.editorContent  = content;
    s.body           = content;
    s.isDirty        = content !== (s.activeNote?.body ?? '');
    s.pendingChanges = s.isDirty;
  }),

  // Alias — keeps body + pendingChanges in sync
  setBody: (body) => set((s) => {
    s.editorContent  = body;
    s.body           = body;
    s.isDirty        = body !== (s.activeNote?.body ?? '');
    s.pendingChanges = s.isDirty;
  }),

  setTitle: (title) => set((s) => {
    s.title          = title;
    s.isDirty        = true;
    s.pendingChanges = true;
  }),

  setMode: (mode) => set((s) => { s.mode = mode; }),

  setNoteId: (id) => set((s) => { s.noteId = id; }),

  markDirty:  () => set((s) => { s.isDirty = true;  s.pendingChanges = true; }),
  markClean:  () => set((s) => { s.isDirty = false; s.pendingChanges = false; }),
  setSaving:  (saving) => set((s) => { s.isSaving = saving; }),
  markSaved:  () => set((s) => {
    s.isDirty        = false;
    s.pendingChanges = false;
    s.isSaving       = false;
    s.lastSavedAt    = Date.now();
  }),

  reset: () => set((s) => {
    s.activeNote     = null;
    s.isDirty        = false;
    s.pendingChanges = false;
    s.lastSavedAt    = null;
    s.isSaving       = false;
    s.editorContent  = '';
    s.body           = '';
    s.title          = '';
    s.noteId         = null;
    s.mode           = 'edit';
  }),
})));

// ─────────────────────────────────────────────────────────────────────────────
// Command-palette store  (⌘K open/close)
// ─────────────────────────────────────────────────────────────────────────────

interface CommandPaletteState {
  open:           boolean;
  toggle:         () => void;
  openPalette:    () => void;
  closePalette:   () => void;
}

export const useCommandPaletteStore = create<CommandPaletteState>()((set) => ({
  open: false,
  toggle:       () => set((s) => ({ open: !s.open })),
  openPalette:  () => set({ open: true }),
  closePalette: () => set({ open: false }),
}));
