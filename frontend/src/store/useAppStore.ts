import { create } from 'zustand';
import type { ChatMessage } from '../types';

type EditorMode = 'edit' | 'split' | 'preview';
export type RagMode = 'hybrid' | 'local' | 'global';

interface AppState {
  // Active note
  activeNoteId: string | null;
  setActiveNoteId: (id: string | null) => void;

  // Editor layout mode
  editorMode: EditorMode;
  setEditorMode: (mode: EditorMode) => void;

  // Global search
  searchQuery: string;
  setSearchQuery: (q: string) => void;

  // Sidebar
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;

  // Active PARA folder filter (Notes page)
  activeFolder: string | null;
  setActiveFolder: (id: string | null) => void;

  // AI RAG mode
  ragMode: RagMode;
  setRagMode: (mode: RagMode) => void;

  // AI Chat messages
  chatMessages: ChatMessage[];
  appendChatMessage: (msg: ChatMessage) => void;
  updateLastAssistantMessage: (content: string) => void;
  clearChat: () => void;

  // Chat session ID (for multi-turn context)
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeNoteId: null,
  setActiveNoteId: (id) => set({ activeNoteId: id }),

  editorMode: 'edit',
  setEditorMode: (mode) => set({ editorMode: mode }),

  searchQuery: '',
  setSearchQuery: (q) => set({ searchQuery: q }),

  sidebarCollapsed: false,
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  activeFolder: null,
  setActiveFolder: (id) => set({ activeFolder: id }),

  ragMode: 'hybrid',
  setRagMode: (mode) => set({ ragMode: mode }),

  chatMessages: [],
  appendChatMessage: (msg) =>
    set((s) => ({ chatMessages: [...s.chatMessages, msg] })),
  updateLastAssistantMessage: (content) =>
    set((s) => {
      const msgs = [...s.chatMessages];
      // Find the last assistant bubble and update it
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
          msgs[i] = { ...msgs[i], content };
          break;
        }
      }
      return { chatMessages: msgs };
    }),
  clearChat: () => set({ chatMessages: [], sessionId: null }),

  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),
}));
