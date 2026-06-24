/**
 * useVaultStore — vault switching & grant management
 *
 * Mocks vaultApi so no HTTP calls are made. Tests the store logic:
 *  - switchVault dispatches the gnosis:vault-changed CustomEvent
 *  - resetToOwnVault falls back to the first grant label (or 'My Vault')
 *  - fetchGrants resets to own vault when active vault is no longer in the list
 *  - acceptInvite calls acceptVaultGrant then re-fetches grants
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useVaultStore } from '../useVaultStore';

// Mock the vaultApi module — we don't want real HTTP in store tests
vi.mock('../../services/vaultApi', () => ({
  fetchMyVaultGrants: vi.fn(),
  acceptVaultGrant:   vi.fn(),
}));

import { fetchMyVaultGrants, acceptVaultGrant } from '../../services/vaultApi';

const mockFetchGrants = fetchMyVaultGrants as ReturnType<typeof vi.fn>;
const mockAcceptGrant = acceptVaultGrant   as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  // Reset store to clean state (bypass persist middleware)
  useVaultStore.setState({
    activeVaultOwnerId: null,
    activeVaultLabel:   'My Vault',
    grants:             [],
    loading:            false,
  });
});

describe('switchVault', () => {
  it('updates activeVaultOwnerId and label', () => {
    useVaultStore.getState().switchVault(7, "Alice's Vault");
    expect(useVaultStore.getState().activeVaultOwnerId).toBe(7);
    expect(useVaultStore.getState().activeVaultLabel).toBe("Alice's Vault");
  });

  it('dispatches gnosis:vault-changed CustomEvent with ownerId', () => {
    const listener = vi.fn();
    window.addEventListener('gnosis:vault-changed', listener);

    useVaultStore.getState().switchVault(7, "Alice's Vault");
    expect(listener).toHaveBeenCalledOnce();
    const event = listener.mock.calls[0][0] as CustomEvent;
    expect(event.detail).toMatchObject({ ownerId: 7 });

    window.removeEventListener('gnosis:vault-changed', listener);
  });
});

describe('resetToOwnVault', () => {
  it('sets activeVaultOwnerId to null', () => {
    useVaultStore.setState({ activeVaultOwnerId: 7, activeVaultLabel: "Alice's Vault" });
    useVaultStore.getState().resetToOwnVault();
    expect(useVaultStore.getState().activeVaultOwnerId).toBeNull();
  });

  it('uses the first grant label when grants are loaded', () => {
    useVaultStore.setState({
      grants: [{ id: 1, ownerId: 1, label: 'My Personal Vault', pending: false }],
    });
    useVaultStore.getState().resetToOwnVault();
    expect(useVaultStore.getState().activeVaultLabel).toBe('My Personal Vault');
  });

  it('falls back to "My Vault" when grants list is empty', () => {
    useVaultStore.setState({ grants: [] });
    useVaultStore.getState().resetToOwnVault();
    expect(useVaultStore.getState().activeVaultLabel).toBe('My Vault');
  });

  it('dispatches gnosis:vault-changed with ownerId null', () => {
    const listener = vi.fn();
    window.addEventListener('gnosis:vault-changed', listener);

    useVaultStore.getState().resetToOwnVault();
    const event = listener.mock.calls[0][0] as CustomEvent;
    expect(event.detail.ownerId).toBeNull();

    window.removeEventListener('gnosis:vault-changed', listener);
  });
});

describe('fetchGrants', () => {
  it('sets loading true during fetch then false when done', async () => {
    let resolveGrants!: (v: unknown) => void;
    mockFetchGrants.mockReturnValueOnce(new Promise((r) => { resolveGrants = r; }));

    const fetchPromise = useVaultStore.getState().fetchGrants();
    expect(useVaultStore.getState().loading).toBe(true);

    resolveGrants([]);
    await fetchPromise;
    expect(useVaultStore.getState().loading).toBe(false);
  });

  it('stores the returned grants', async () => {
    const grants = [
      { id: 1, ownerId: 1, label: 'My Vault',      pending: false },
      { id: 2, ownerId: 5, label: "Bob's Vault",   pending: false },
    ];
    mockFetchGrants.mockResolvedValueOnce(grants);
    await useVaultStore.getState().fetchGrants();
    expect(useVaultStore.getState().grants).toEqual(grants);
  });

  it('resets to own vault when active vault is no longer in the grant list', async () => {
    useVaultStore.setState({ activeVaultOwnerId: 99, activeVaultLabel: 'Gone Vault' });
    mockFetchGrants.mockResolvedValueOnce([
      { id: 1, ownerId: 1, label: 'My Vault', pending: false },
    ]);
    await useVaultStore.getState().fetchGrants();
    expect(useVaultStore.getState().activeVaultOwnerId).toBeNull();
  });

  it('sets loading false on fetch error', async () => {
    mockFetchGrants.mockRejectedValueOnce(new Error('network error'));
    await useVaultStore.getState().fetchGrants();
    expect(useVaultStore.getState().loading).toBe(false);
  });
});

describe('acceptInvite', () => {
  it('calls acceptVaultGrant with the grant id then re-fetches grants', async () => {
    mockAcceptGrant.mockResolvedValueOnce(undefined);
    mockFetchGrants.mockResolvedValueOnce([]);

    await useVaultStore.getState().acceptInvite(42);

    expect(mockAcceptGrant).toHaveBeenCalledWith(42);
    expect(mockFetchGrants).toHaveBeenCalledOnce();
  });
});
