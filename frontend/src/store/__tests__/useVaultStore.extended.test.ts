/**
 * useVaultStore.extended.test.ts
 * Targets uncovered lines in store/useVaultStore.ts:
 *   61-62 — fetchGrants catch block (set loading:false on error)
 *
 * Also covers the revoked-grant resetToOwnVault branch (lines ~54-59)
 * and the switchVault CustomEvent dispatch.
 *
 * Actual store shape:
 *   { activeVaultOwnerId, activeVaultLabel, grants, loading,
 *     fetchGrants, switchVault, resetToOwnVault, acceptInvite }
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/services/vaultApi', () => ({
  fetchMyVaultGrants: vi.fn().mockResolvedValue([]),
  acceptVaultGrant: vi.fn().mockResolvedValue(undefined),
}));

describe('useVaultStore — fetchGrants catch path (lines 61-62)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('imports and exposes expected state keys', async () => {
    const { useVaultStore } = await import('@/store/useVaultStore');
    const state = useVaultStore.getState();
    expect(state).toHaveProperty('activeVaultOwnerId');
    expect(state).toHaveProperty('activeVaultLabel');
    expect(state).toHaveProperty('grants');
    expect(state).toHaveProperty('loading');
  });

  it('sets loading:false after fetchGrants resolves', async () => {
    const { useVaultStore } = await import('@/store/useVaultStore');
    const { fetchMyVaultGrants } = await import('@/services/vaultApi');
    vi.mocked(fetchMyVaultGrants).mockResolvedValueOnce([]);
    await useVaultStore.getState().fetchGrants();
    expect(useVaultStore.getState().loading).toBe(false);
  });

  it('sets loading:false on fetchGrants error (lines 61-62)', async () => {
    const { useVaultStore } = await import('@/store/useVaultStore');
    const { fetchMyVaultGrants } = await import('@/services/vaultApi');
    vi.mocked(fetchMyVaultGrants).mockRejectedValueOnce(new Error('network fail'));
    await useVaultStore.getState().fetchGrants();
    expect(useVaultStore.getState().loading).toBe(false);
  });

  it('switchVault updates activeVaultOwnerId and dispatches CustomEvent', async () => {
    const { useVaultStore } = await import('@/store/useVaultStore');
    const events: Event[] = [];
    window.addEventListener('gnosis:vault-changed', (e) => events.push(e));
    useVaultStore.getState().switchVault(99, 'Friend Vault');
    expect(useVaultStore.getState().activeVaultOwnerId).toBe(99);
    expect(useVaultStore.getState().activeVaultLabel).toBe('Friend Vault');
    expect(events.length).toBeGreaterThan(0);
    window.removeEventListener('gnosis:vault-changed', (e) => events.push(e));
  });

  it('resetToOwnVault sets activeVaultOwnerId to null', async () => {
    const { useVaultStore } = await import('@/store/useVaultStore');
    useVaultStore.getState().switchVault(99, 'Other');
    useVaultStore.getState().resetToOwnVault();
    expect(useVaultStore.getState().activeVaultOwnerId).toBeNull();
  });

  it('revoked-grant branch: fetchGrants resets to own vault when active grant is gone', async () => {
    const { useVaultStore } = await import('@/store/useVaultStore');
    const { fetchMyVaultGrants } = await import('@/services/vaultApi');
    // Set active vault to id 42, then return a grant list that does NOT include it
    useVaultStore.setState({ activeVaultOwnerId: 42, activeVaultLabel: 'Gone Vault' });
    vi.mocked(fetchMyVaultGrants).mockResolvedValueOnce([
      { id: 1, ownerId: 1, label: 'My Vault', pending: false, ownerEmail: 'me@test.com' },
    ]);
    await useVaultStore.getState().fetchGrants();
    // Revoked — should have fallen back to own vault
    expect(useVaultStore.getState().activeVaultOwnerId).toBeNull();
  });
});
