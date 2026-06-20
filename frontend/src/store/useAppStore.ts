import { create } from 'zustand';

type EditorMode = 'edit' | 'split' | 'preview';
type RagMode = 'hybrid' | 'local' | 'global';

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

  // Sidebar collapsed
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;

  // AI RAG mode (persisted across Settings changes)
  ragMode: RagMode;
  setRagMode: (mode: RagMode) => void;
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

  ragMode: 'hybrid',
  setRagMode: (mode) => set({ ragMode: mode }),
}));
