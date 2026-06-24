import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/services/vaultApi', () => ({
  fetchMyVaultGrants: vi.fn().mockResolvedValue([]),
  acceptVaultGrant: vi.fn().mockResolvedValue(undefined),
}));

describe('useVaultStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sets loading false on fetch error', async () => {
    const { useVaultStore } = await import('@/store/useVaultStore');
    const { fetchMyVaultGrants } = await import('@/services/vaultApi');
    vi.mocked(fetchMyVaultGrants).mockRejectedValueOnce(new Error('network fail'));
    await useVaultStore.getState().fetchGrants();
    expect(useVaultStore.getState().loading).toBe(false);
  });

  it('revoked grant resets to own vault', async () => {
    const { useVaultStore } = await import('@/store/useVaultStore');
    const { fetchMyVaultGrants } = await import('@/services/vaultApi');
    useVaultStore.setState({ activeVaultOwnerId: 42, activeVaultLabel: 'Gone Vault' });
    vi.mocked(fetchMyVaultGrants).mockResolvedValueOnce([
      { ownerId: 1, label: 'My Vault', permission: 'owner', grantId: null, pending: false },
    ]);
    await useVaultStore.getState().fetchGrants();
    expect(useVaultStore.getState().activeVaultOwnerId).toBeNull();
  });
});
