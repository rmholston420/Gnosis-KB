/**
 * store/vaultStore.ts — Zustand store for vault / sync state.
 */
import { create } from 'zustand';

export interface VaultState {
  /** Absolute path to the active vault on disk. */
  activeVaultPath: string | null;
  isSyncing:       boolean;
  lastSyncedAt:    string | null;
  syncError:       string | null;

  setActiveVaultPath: (path: string | null) => void;
  setIsSyncing:       (v: boolean) => void;
  setLastSyncedAt:    (ts: string | null) => void;
  setSyncError:       (err: string | null) => void;
}

export const useVaultStore = create<VaultState>((set) => ({
  activeVaultPath: null,
  isSyncing:       false,
  lastSyncedAt:    null,
  syncError:       null,

  setActiveVaultPath: (path) => set({ activeVaultPath: path }),
  setIsSyncing:       (v)    => set({ isSyncing: v }),
  setLastSyncedAt:    (ts)   => set({ lastSyncedAt: ts }),
  setSyncError:       (err)  => set({ syncError: err }),
}));

export default useVaultStore;
