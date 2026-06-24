/**
 * useAppStore — Zustand store for global UI state.
 *
 * Exposes every slice consumed by AiChat, Sidebar, TopBar, and other
 * components, plus the full action surface expected by unit tests.
 */
import { create } from 'zustand';
import type { ChatMessage } from '../types';

export type RagMode    = 'hybrid' | 'local' | 'global';
export type EditorMode = 'edit' | 'split' | 'preview';

interface AppStore {
  // ── Note selection ───────────────────────────────────────────────
  activeNoteId:     string | null;
  setActiveNoteId:  (id: string | null) => void;

  // ── Editor layout ────────────────────────────────────────────────
  editorMode:       EditorMode;
  setEditorMode:    (mode: EditorMode) => void;

  // ── Sidebar ──────────────────────────────────────────────────────
  sidebarCollapsed:    boolean;
  setSidebarCollapsed: (v: boolean) => void;
  toggleSidebar:       () => void;
  activeFolder:        string | null;
  setActiveFolder:     (folder: string | null) => void;

  // ── Search ───────────────────────────────────────────────────────
  searchQuery:    string;
  setSearchQuery: (q: string) => void;

  // ── RAG mode (persisted choice) ──────────────────────────────────
  ragMode:    RagMode;
  setRagMode: (mode: RagMode) => void;

  // ── Chat (AiChat streaming panel) ────────────────────────────────
  chatMessages:              ChatMessage[];
  appendChatMessage:         (msg: ChatMessage) => void;
  updateLastAssistantMessage:(content: string) => void;
  clearChat:                 () => void;
  sessionId:                 string | null;
  setSessionId:              (id: string | null) => void;
}

export const useAppStore = create<AppStore>((set) => ({
  // ── Note selection ───────────────────────────────────────────────
  activeNoteId:    null,
  setActiveNoteId: (id) => set({ activeNoteId: id }),

  // ── Editor layout ────────────────────────────────────────────────
  editorMode:    'edit',
  setEditorMode: (mode) => set({ editorMode: mode }),

  // ── Sidebar ──────────────────────────────────────────────────────
  sidebarCollapsed:    false,
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
  toggleSidebar:       () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  activeFolder:        null,
  setActiveFolder:     (folder) => set({ activeFolder: folder }),

  // ── Search ───────────────────────────────────────────────────────
  searchQuery:    '',
  setSearchQuery: (q) => set({ searchQuery: q }),

  // ── RAG mode ─────────────────────────────────────────────────────
  ragMode:    'hybrid',
  setRagMode: (mode) => set({ ragMode: mode }),

  // ── Chat ─────────────────────────────────────────────────────────
  chatMessages: [],
  appendChatMessage: (msg) =>
    set((s) => ({ chatMessages: [...s.chatMessages, msg] })),
  updateLastAssistantMessage: (content) =>
    set((s) => {
      const msgs = [...s.chatMessages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
          msgs[i] = { ...msgs[i], content };
          break;
        }
      }
      return { chatMessages: msgs };
    }),
  clearChat:  () => set({ chatMessages: [], sessionId: null }),
  sessionId:  null,
  setSessionId: (id) => set({ sessionId: id }),
}));
