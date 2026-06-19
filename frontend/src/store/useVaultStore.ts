/**
 * Vault context store.
 *
 * Tracks which vault the user is currently "viewing". When the active vault
 * is the user's own, all API calls proceed normally. When it is a shared
 * vault, a header X-Vault-Owner-Id is expected to be injected by the API
 * layer (see services/api.ts) so the backend returns notes scoped to that
 * owner.
 *
 * The store fires a CustomEvent 'gnosis:vault-changed' on window whenever
 * the active vault changes so data-fetching hooks can invalidate/refetch
 * without prop drilling.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { VaultGrant } from '../services/vaultApi';
import { fetchMyVaultGrants, acceptVaultGrant } from '../services/vaultApi';

interface VaultState {
  /** User-id of the vault currently being browsed. null = own vault. */
  activeVaultOwnerId: number | null;
  /** Display label for the active vault (shown in the context banner). */
  activeVaultLabel: string;
  /** All grants fetched from the server (own vault always index 0). */
  grants: VaultGrant[];
  /** Whether the grant list is being loaded. */
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
          // If the currently active vault is no longer in the grant list
          // (e.g. grant was revoked), fall back to own vault.
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
        // Refresh the grant list so the accepted invite becomes active
        await get().fetchGrants();
      },
    }),
    {
      name: 'gnosis-vault-store',
      // Only persist the active selection — grants are always re-fetched on load
      partialize: (s) => ({
        activeVaultOwnerId: s.activeVaultOwnerId,
        activeVaultLabel: s.activeVaultLabel,
      }),
    }
  )
);
