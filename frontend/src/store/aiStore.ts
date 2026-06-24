/**
 * aiStore.ts
 * ==========
 * Zustand slice for AI panel state and vault-sync status.
 *
 * Slice:
 *  - activeTab: which AI sidebar tab is open
 *  - summary / linkSuggestions / tagSuggestions / critique results
 *  - vaultSyncStatus + vaultSyncProgress (fed by VaultSyncWatcher)
 */
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { LinkSuggestion } from '../types';

export type AiTab = 'summary' | 'links' | 'tags' | 'critique';
export type SyncStatus = 'idle' | 'syncing' | 'error';

interface AiState {
  activeTab: AiTab;
  summary: string | null;
  summaryLoading: boolean;
  linkSuggestions: LinkSuggestion[];
  tagSuggestions: string[];
  critique: string | null;
  critiqueLoading: boolean;

  // Vault sync status (set by VaultSyncWatcher)
  vaultSyncStatus: SyncStatus;
  vaultSyncProgress: number; // 0-100

  // Actions
  setActiveTab: (tab: AiTab) => void;
  setSummary: (s: string | null) => void;
  setSummaryLoading: (v: boolean) => void;
  setLinkSuggestions: (links: LinkSuggestion[]) => void;
  setTagSuggestions: (tags: string[]) => void;
  setCritique: (c: string | null) => void;
  setCritiqueLoading: (v: boolean) => void;
  setVaultSyncStatus: (s: SyncStatus) => void;
  setVaultSyncProgress: (p: number) => void;
  resetAiPanel: () => void;
}

const INITIAL: Omit<AiState, 'setActiveTab' | 'setSummary' | 'setSummaryLoading' | 'setLinkSuggestions' | 'setTagSuggestions' | 'setCritique' | 'setCritiqueLoading' | 'setVaultSyncStatus' | 'setVaultSyncProgress' | 'resetAiPanel'> = {
  activeTab: 'summary',
  summary: null,
  summaryLoading: false,
  linkSuggestions: [],
  tagSuggestions: [],
  critique: null,
  critiqueLoading: false,
  vaultSyncStatus: 'idle',
  vaultSyncProgress: 0,
};

export const useAiStore = create<AiState>()(immer((set) => ({
  ...INITIAL,

  setActiveTab: (tab)    => set((s) => { s.activeTab = tab; }),
  setSummary:   (sum)    => set((s) => { s.summary = sum; }),
  setSummaryLoading: (v) => set((s) => { s.summaryLoading = v; }),
  setLinkSuggestions: (links) => set((s) => { s.linkSuggestions = links; }),
  setTagSuggestions:  (tags)  => set((s) => { s.tagSuggestions = tags; }),
  setCritique: (c)       => set((s) => { s.critique = c; }),
  setCritiqueLoading: (v) => set((s) => { s.critiqueLoading = v; }),
  setVaultSyncStatus:   (status)   => set((s) => { s.vaultSyncStatus = status; }),
  setVaultSyncProgress: (progress) => set((s) => { s.vaultSyncProgress = progress; }),
  resetAiPanel: () => set((s) => {
    s.summary           = null;
    s.summaryLoading    = false;
    s.linkSuggestions   = [];
    s.tagSuggestions    = [];
    s.critique          = null;
    s.critiqueLoading   = false;
  }),
})));
