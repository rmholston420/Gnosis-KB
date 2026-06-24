/**
 * editorStore — Zustand slice for active note editor state.
 * Tracks the currently open note, dirty flag, and autosave status.
 */
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { Note } from '../types';

interface EditorState {
  /** Currently open note, or null if none. */
  activeNote:   Note | null;
  /** True if the editor has unsaved changes. */
  isDirty:      boolean;
  /** Milliseconds since last save (null = never saved this session). */
  lastSavedAt:  number | null;
  /** True while an autosave request is in-flight. */
  isSaving:     boolean;
  /** The raw editor content (markdown string). */
  editorContent: string;

  // ---- Actions ----
  setActiveNote:    (note: Note | null) => void;
  setEditorContent: (content: string) => void;
  markDirty:        () => void;
  markClean:        () => void;
  setSaving:        (saving: boolean) => void;
  markSaved:        () => void;
  reset:            () => void;
}

export const useEditorStore = create<EditorState>()(immer((set) => ({
  activeNote:    null,
  isDirty:       false,
  lastSavedAt:   null,
  isSaving:      false,
  editorContent: '',

  setActiveNote: (note) => set((s) => {
    s.activeNote    = note;
    s.editorContent = note?.body ?? '';
    s.isDirty       = false;
    s.isSaving      = false;
  }),

  setEditorContent: (content) => set((s) => {
    s.editorContent = content;
    s.isDirty       = content !== (s.activeNote?.body ?? '');
  }),

  markDirty:  () => set((s) => { s.isDirty = true; }),
  markClean:  () => set((s) => { s.isDirty = false; }),
  setSaving:  (saving) => set((s) => { s.isSaving = saving; }),
  markSaved:  () => set((s) => {
    s.isDirty     = false;
    s.isSaving    = false;
    s.lastSavedAt = Date.now();
  }),

  reset: () => set((s) => {
    s.activeNote    = null;
    s.isDirty       = false;
    s.lastSavedAt   = null;
    s.isSaving      = false;
    s.editorContent = '';
  }),
})));
