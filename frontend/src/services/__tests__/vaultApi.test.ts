/**
 * vaultApi.ts — fetch-based vault/sharing API wrappers
 *
 * Strategy: replace globalThis.fetch with a vi.fn() mock; restore after each test.
 * Tests assert correct URL, method, headers, and response shape.
 *
 * What we test:
 *  fetchMe:
 *    1. GET /api/v1/users/me with Bearer token
 *    2. Throws on non-ok response
 *
 *  fetchMyVaultGrants:
 *    3. Returns own-vault entry at index 0
 *    4. Maps raw grant rows into VaultGrant shape
 *    5. Marks accepted_at=null grants as pending=true
 *    6. Falls back gracefully when /me/vaults returns non-ok (empty shared list)
 *
 *  acceptVaultGrant:
 *    7. POST /api/v1/users/me/vaults/:id/accept with correct method
 *    8. Throws on non-ok response
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchMe, fetchMyVaultGrants, acceptVaultGrant } from '../vaultApi';

function mockFetch(responses: Array<{ ok: boolean; status?: number; body: unknown }>) {
  let call = 0;
  return vi.fn().mockImplementation(() => {
    const r = responses[call++] ?? { ok: true, body: {} };
    return Promise.resolve({
      ok: r.ok,
      status: r.status ?? (r.ok ? 200 : 400),
      json: () => Promise.resolve(r.body),
    });
  });
}

beforeEach(() => {
  localStorage.setItem('gnosis_token', 'test-jwt');
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('fetchMe', () => {
  it('calls GET /api/v1/users/me with Bearer token', async () => {
    const fetchSpy = mockFetch([{ ok: true, body: { id: 1, email: 'a@b.com', vault_display_name: null } }]);
    vi.stubGlobal('fetch', fetchSpy);

    const result = await fetchMe();

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, opts] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/users/me');
    expect((opts.headers as Record<string, string>)['Authorization']).toBe('Bearer test-jwt');
    expect(result.id).toBe(1);
  });

  it('throws when response is not ok', async () => {
    vi.stubGlobal('fetch', mockFetch([{ ok: false, status: 401, body: {} }]));
    await expect(fetchMe()).rejects.toThrow('fetchMe: 401');
  });
});

describe('fetchMyVaultGrants', () => {
  const meBody = { id: 5, email: 'user@gnosis.app', vault_display_name: 'My Notes' };
  const rawGrant = {
    id: 10,
    owner_id: 9,
    owner_display_name: "Alice's Vault",
    permission: 'read',
    accepted_at: '2025-01-01T00:00:00Z',
  };
  const pendingGrant = { ...rawGrant, id: 11, accepted_at: null };

  it('places own-vault entry at index 0 with permission=owner', async () => {
    vi.stubGlobal('fetch', mockFetch([
      { ok: true, body: meBody },
      { ok: true, body: [] },
    ]));
    const grants = await fetchMyVaultGrants();
    expect(grants[0].permission).toBe('owner');
    expect(grants[0].ownerId).toBe(5);
    expect(grants[0].label).toBe('My Notes');
    expect(grants[0].grantId).toBeNull();
  });

  it('maps raw grant rows into VaultGrant shape', async () => {
    vi.stubGlobal('fetch', mockFetch([
      { ok: true, body: meBody },
      { ok: true, body: [rawGrant] },
    ]));
    const grants = await fetchMyVaultGrants();
    expect(grants).toHaveLength(2);
    expect(grants[1].ownerId).toBe(9);
    expect(grants[1].label).toBe("Alice's Vault");
    expect(grants[1].permission).toBe('read');
    expect(grants[1].grantId).toBe(10);
    expect(grants[1].pending).toBe(false);
  });

  it('marks accepted_at=null grants as pending=true', async () => {
    vi.stubGlobal('fetch', mockFetch([
      { ok: true, body: meBody },
      { ok: true, body: [pendingGrant] },
    ]));
    const grants = await fetchMyVaultGrants();
    expect(grants[1].pending).toBe(true);
  });

  it('returns only own-vault when /me/vaults is non-ok', async () => {
    vi.stubGlobal('fetch', mockFetch([
      { ok: true, body: meBody },
      { ok: false, status: 403, body: {} },
    ]));
    const grants = await fetchMyVaultGrants();
    expect(grants).toHaveLength(1);
    expect(grants[0].permission).toBe('owner');
  });

  it('uses email as label fallback when vault_display_name is null', async () => {
    vi.stubGlobal('fetch', mockFetch([
      { ok: true, body: { id: 3, email: 'fallback@test.com', vault_display_name: null } },
      { ok: true, body: [] },
    ]));
    const grants = await fetchMyVaultGrants();
    expect(grants[0].label).toBe('fallback@test.com');
  });
});

describe('acceptVaultGrant', () => {
  it('sends POST to /api/v1/users/me/vaults/:id/accept', async () => {
    const fetchSpy = mockFetch([{ ok: true, body: {} }]);
    vi.stubGlobal('fetch', fetchSpy);

    await acceptVaultGrant(42);

    const [url, opts] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/users/me/vaults/42/accept');
    expect(opts.method).toBe('POST');
    expect((opts.headers as Record<string, string>)['Authorization']).toBe('Bearer test-jwt');
  });

  it('throws when response is not ok', async () => {
    vi.stubGlobal('fetch', mockFetch([{ ok: false, status: 404, body: {} }]));
    await expect(acceptVaultGrant(99)).rejects.toThrow('acceptVaultGrant: 404');
  });
});
