/**
 * Zustand global store for Gnosis UI.
 *
 * Manages:
 * - Currently active note ID
 * - Sidebar collapsed state
 * - Search query and mode
 * - Editor mode (edit/preview/split)
 * - AI chat session
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChatMessage, NoteListItem } from '../types';

type EditorMode = 'edit' | 'preview' | 'split';
type SearchMode = 'hybrid' | 'semantic' | 'fulltext';
type RAGMode = 'hybrid' | 'local' | 'global';

interface AppState {
  // Navigation
  activeNoteId: string | null;
  setActiveNoteId: (id: string | null) => void;

  // Sidebar
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (v: boolean) => void;
  toggleSidebar: () => void;

  // Editor
  editorMode: EditorMode;
  setEditorMode: (mode: EditorMode) => void;

  // Search
  searchQuery: string;
  searchMode: SearchMode;
  setSearchQuery: (q: string) => void;
  setSearchMode: (mode: SearchMode) => void;

  // Selected folder filter
  activeFolder: string | null;
  setActiveFolder: (folder: string | null) => void;

  // AI Chat
  chatMessages: ChatMessage[];
  ragMode: RAGMode;
  sessionId: string | null;
  appendChatMessage: (msg: ChatMessage) => void;
  clearChat: () => void;
  setRagMode: (mode: RAGMode) => void;

  // Recently viewed
  recentNotes: NoteListItem[];
  addRecentNote: (note: NoteListItem) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Navigation
      activeNoteId: null,
      setActiveNoteId: (id) => set({ activeNoteId: id }),

      // Sidebar
      sidebarCollapsed: false,
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

      // Editor
      editorMode: 'split',
      setEditorMode: (mode) => set({ editorMode: mode }),

      // Search
      searchQuery: '',
      searchMode: 'hybrid',
      setSearchQuery: (q) => set({ searchQuery: q }),
      setSearchMode: (mode) => set({ searchMode: mode }),

      // Folder filter
      activeFolder: null,
      setActiveFolder: (folder) => set({ activeFolder: folder }),

      // AI Chat
      chatMessages: [],
      ragMode: 'hybrid',
      sessionId: null,
      appendChatMessage: (msg) =>
        set((s) => ({ chatMessages: [...s.chatMessages, msg] })),
      clearChat: () => set({ chatMessages: [], sessionId: null }),
      setRagMode: (mode) => set({ ragMode: mode }),

      // Recently viewed
      recentNotes: [],
      addRecentNote: (note) =>
        set((s) => ({
          recentNotes: [
            note,
            ...s.recentNotes.filter((n) => n.id !== note.id),
          ].slice(0, 10),
        })),
    }),
    {
      name: 'gnosis-app-store',
      partialize: (s) => ({
        sidebarCollapsed: s.sidebarCollapsed,
        editorMode: s.editorMode,
        searchMode: s.searchMode,
        recentNotes: s.recentNotes,
        ragMode: s.ragMode,
      }),
    }
  )
);
