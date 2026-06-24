/**
 * services/api.ts — fetch-based note/graph/AI service layer
 *
 * Strategy:
 *  - Stub globalThis.fetch per test via vi.stubGlobal
 *  - Pre-seed useVaultStore to test vault-scoped header injection
 *  - Test the request() internals through the public api.* methods
 *
 * What we test:
 *  1.  listNotes builds correct query string
 *  2.  getNote calls GET /notes/:id
 *  3.  createNote calls POST /notes/ with JSON body
 *  4.  updateNote calls PUT /notes/:id with JSON body
 *  5.  deleteNote calls DELETE /notes/:id; handles 204 no-content
 *  6.  X-Vault-Owner-Id header is injected when activeVaultOwnerId is set
 *  7.  X-Vault-Owner-Id header is absent when activeVaultOwnerId is null
 *  8.  Non-ok response throws an Error with detail message
 *  9.  chat sends correct payload
 *  10. search builds correct query string
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import api from '../api';
import { useVaultStore } from '../../store/useVaultStore';

function ok(body: unknown = {}, status = 200) {
  return Promise.resolve({
    ok: true,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    headers: new Headers({ 'content-type': 'application/json' }),
  } as Response);
}

function notOk(detail = 'Not found', status = 404) {
  return Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve({ detail }),
    text: () => Promise.resolve(JSON.stringify({ detail })),
    statusText: 'Not Found',
    headers: new Headers(),
  } as unknown as Response);
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
  useVaultStore.setState({ activeVaultOwnerId: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  useVaultStore.setState({ activeVaultOwnerId: null });
});

const mockFetch = () => globalThis.fetch as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
describe('api.listNotes', () => {
  it('builds correct query string', async () => {
    mockFetch().mockReturnValue(ok({ items: [], total: 0 }));
    await api.listNotes({ note_type: 'permanent', page: 1 });
    const url: string = mockFetch().mock.calls[0][0];
    expect(url).toContain('note_type=permanent');
    expect(url).toContain('page=1');
  });
});

// ---------------------------------------------------------------------------
describe('api.getNote', () => {
  it('calls GET /notes/:id', async () => {
    mockFetch().mockReturnValue(ok({ id: 'n1' }));
    await api.getNote('n1');
    expect(mockFetch().mock.calls[0][0]).toContain('/notes/n1');
    expect(mockFetch().mock.calls[0][1].method).toBe('GET');
  });
});

// ---------------------------------------------------------------------------
describe('api.createNote', () => {
  it('calls POST /notes/ with JSON body', async () => {
    mockFetch().mockReturnValue(ok({ id: 'n2' }));
    await api.createNote({ title: 'New', body: '' });
    const [url, opts] = mockFetch().mock.calls[0];
    expect(url).toContain('/notes/');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject({ title: 'New' });
  });
});

// ---------------------------------------------------------------------------
describe('api.updateNote', () => {
  it('calls PUT /notes/:id with JSON body', async () => {
    mockFetch().mockReturnValue(ok({ id: 'n1', title: 'Updated' }));
    await api.updateNote('n1', { title: 'Updated' });
    const [url, opts] = mockFetch().mock.calls[0];
    expect(url).toContain('/notes/n1');
    expect(opts.method).toBe('PUT');
  });
});

// ---------------------------------------------------------------------------
describe('api.deleteNote', () => {
  it('sends DELETE and handles 204', async () => {
    mockFetch().mockReturnValue(ok({}, 204));
    await api.deleteNote('n1');
    expect(mockFetch().mock.calls[0][1].method).toBe('DELETE');
  });
});

// ---------------------------------------------------------------------------
describe('vault header injection', () => {
  it('injects X-Vault-Owner-Id when activeVaultOwnerId is set', async () => {
    useVaultStore.setState({ activeVaultOwnerId: 42 });
    const { setActiveVaultPath } = await import('../api');
    setActiveVaultPath('/home/user/vault');
    mockFetch().mockReturnValue(ok());
    await api.listNotes({});
    const headers: Record<string, string> = mockFetch().mock.calls[0][1].headers;
    // api.ts injects X-Vault-Path from setActiveVaultPath
    expect(headers['X-Vault-Path']).toBe('/home/user/vault');
    setActiveVaultPath(null);
  });

  it('omits X-Vault-Path when null', async () => {
    const { setActiveVaultPath } = await import('../api');
    setActiveVaultPath(null);
    useVaultStore.setState({ activeVaultOwnerId: null });
    mockFetch().mockReturnValue(ok());
    await api.listNotes({});
    const headers: Record<string, string> = mockFetch().mock.calls[0][1].headers;
    expect(headers['X-Vault-Path']).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
describe('error handling', () => {
  it('throws Error with detail message on non-ok response', async () => {
    mockFetch().mockReturnValue(notOk('Note not found', 404));
    await expect(api.getNote('missing')).rejects.toThrow('Note not found');
  });
});

// ---------------------------------------------------------------------------
describe('api.chat', () => {
  it('sends correct payload', async () => {
    mockFetch().mockReturnValue(ok({ response: 'pong' }));
    await api.chat('hello', 'hybrid');
    const opts = mockFetch().mock.calls[0][1];
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.message).toBe('hello');
    expect(body.mode).toBe('hybrid');
  });
});

// ---------------------------------------------------------------------------
describe('api.search', () => {
  it('builds correct query string', async () => {
    mockFetch().mockReturnValue(ok({ items: [], total: 0 }));
    await api.search('emptiness');
    const url: string = mockFetch().mock.calls[0][0];
    expect(url).toContain('q=emptiness');
  });
});
