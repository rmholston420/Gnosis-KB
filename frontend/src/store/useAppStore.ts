/**
 * useAppStore — lightweight Zustand store for global UI state.
 * RAG mode is the only setting persisted here for now; other
 * settings live in the backend and are fetched via SettingsPage.
 */
import { create } from 'zustand';

export type RagMode = 'hybrid' | 'local' | 'global';

interface AppStore {
  ragMode: RagMode;
  setRagMode: (mode: RagMode) => void;
}

export const useAppStore = create<AppStore>((set) => ({
  ragMode: 'hybrid',
  setRagMode: (mode) => set({ ragMode: mode }),
}));
