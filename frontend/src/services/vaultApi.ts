/**
 * Typed API wrappers for vault / sharing endpoints.
 *
 * All functions read the JWT from localStorage under the key used by the
 * existing auth flow ("gnosis_token").
 *
 * NOTE: These calls intentionally bypass the main api.ts request() wrapper
 * because they are used to bootstrap the vault context itself (circular
 * dependency if they went through it). They do NOT inject X-Vault-Owner-Id
 * because vault-management endpoints always operate on the caller's own
 * account regardless of which vault they're browsing.
 */

export interface VaultGrant {
  /** The user-id that owns this vault (== current user for own vault). */
  ownerId: number;
  /** Human-readable name shown in the switcher. */
  label: string;
  /** 'owner' | 'read' | 'write' */
  permission: 'owner' | 'read' | 'write';
  /** Grant row id from shared_vaults table; null for own vault. */
  grantId: number | null;
  /** True when the invite has not yet been accepted. */
  pending: boolean;
}

const BASE = '/api/v1';

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('gnosis_token') ?? '';
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
}

/** Fetch the authenticated user's own profile. */
export async function fetchMe(): Promise<{
  id: number;
  vault_display_name: string | null;
  email: string;
}> {
  const res = await fetch(`${BASE}/users/me`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`fetchMe: ${res.status}`);
  return res.json();
}

/** Fetch all shared-vault grants for the current user (received invitations). */
export async function fetchMyVaultGrants(): Promise<VaultGrant[]> {
  const [me, grantsRes] = await Promise.all([
    fetchMe(),
    fetch(`${BASE}/users/me/vaults`, { headers: authHeaders() }),
  ]);

  const rawGrants: Array<{
    id: number;
    owner_id: number;
    owner_display_name: string;
    permission: 'read' | 'write';
    accepted_at: string | null;
  }> = grantsRes.ok ? await grantsRes.json() : [];

  const ownEntry: VaultGrant = {
    ownerId: me.id,
    label: me.vault_display_name ?? me.email ?? 'My Vault',
    permission: 'owner',
    grantId: null,
    pending: false,
  };

  const sharedEntries: VaultGrant[] = rawGrants.map((g) => ({
    ownerId: g.owner_id,
    label: g.owner_display_name,
    permission: g.permission,
    grantId: g.id,
    pending: g.accepted_at === null,
  }));

  return [ownEntry, ...sharedEntries];
}

/** Accept a pending vault invitation. */
export async function acceptVaultGrant(grantId: number): Promise<void> {
  const res = await fetch(`${BASE}/users/me/vaults/${grantId}/accept`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`acceptVaultGrant: ${res.status}`);
}
