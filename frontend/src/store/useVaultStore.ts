/**
 * Vault context store.
 *
 * Tracks which vault the user is currently "viewing". When the active vault
 * is the user's own, all API calls proceed normally. When it is a shared
 * vault, a header X-Vault-Owner-Id is expected to be injected by the API
 * layer (see services/api.ts) so the backend returns notes scoped to that
 * owner.
 *
 * STORAGE SAFETY:
 *   The persist middleware writes to localStorage. In sandboxed iframes,
 *   private-browsing mode, or test environments (jsdom) localStorage may be
 *   blocked. We wrap it in a safeStorage adapter that silently no-ops on any
 *   storage error so the store still works — it just won't persist across
 *   page loads in those contexts.
 */

import { create } from 'zustand';
import { persist, type StateStorage } from 'zustand/middleware';
import type { VaultGrant } from '../services/vaultApi';
import { fetchMyVaultGrants, acceptVaultGrant } from '../services/vaultApi';

/** localStorage wrapper that never throws. Falls back to in-memory no-op. */
const safeStorage: StateStorage = {
  getItem(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  setItem(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Sandboxed or private-browsing context — silently ignore
    }
  },
  removeItem(key) {
    try {
      localStorage.removeItem(key);
    } catch {
      // Silently ignore
    }
  },
};

interface VaultState {
  activeVaultOwnerId: number | null;
  activeVaultLabel: string;
  grants: VaultGrant[];
  loading: boolean;

  fetchGrants: () => Promise<void>;
  switchVault: (ownerId: number | null, label: string) => void;
  resetToOwnVault: () => void;
  acceptInvite: (grantId: number) => Promise<void>;
}

export const useVaultStore = create<VaultState>()(
  persist(
    (set, get) => ({
      activeVaultOwnerId: null,
      activeVaultLabel: 'My Vault',
      grants: [],
      loading: false,

      fetchGrants: async () => {
        set({ loading: true });
        try {
          const grants = await fetchMyVaultGrants();
          set({ grants, loading: false });
          const { activeVaultOwnerId, grants: updatedGrants } = get();
          if (
            activeVaultOwnerId !== null &&
            !updatedGrants.some(
              (g) => g.ownerId === activeVaultOwnerId && !g.pending
            )
          ) {
            get().resetToOwnVault();
          }
        } catch {
          set({ loading: false });
        }
      },

      switchVault: (ownerId, label) => {
        set({ activeVaultOwnerId: ownerId, activeVaultLabel: label });
        window.dispatchEvent(
          new CustomEvent('gnosis:vault-changed', { detail: { ownerId, label } })
        );
      },

      resetToOwnVault: () => {
        const own = get().grants[0];
        set({
          activeVaultOwnerId: null,
          activeVaultLabel: own?.label ?? 'My Vault',
        });
        window.dispatchEvent(
          new CustomEvent('gnosis:vault-changed', { detail: { ownerId: null } })
        );
      },

      acceptInvite: async (grantId) => {
        await acceptVaultGrant(grantId);
        await get().fetchGrants();
      },
    }),
    {
      name: 'gnosis-vault-store',
      storage: safeStorage,
      partialize: (s) => ({
        activeVaultOwnerId: s.activeVaultOwnerId,
        activeVaultLabel: s.activeVaultLabel,
      }),
    }
  )
);
