/**
 * services/api.ts — fetch-based note/graph/AI service layer
 *
 * Strategy:
 *  - Stub globalThis.fetch per test via vi.stubGlobal
 *  - Pre-seed useVaultStore to test vault-scoped header injection
 *  - Test the request() internals through the public api.* methods
 *
 * What we test:
 *  1.  listNotes builds correct query string and attaches token
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
import { api } from '../api';
import { useVaultStore } from '../../store/useVaultStore';

function ok(body: unknown = {}, status = 200) {
  return Promise.resolve({
    ok: true,
    status,
    json: () => Promise.resolve(body),
  });
}

function fail(status: number, detail = 'Something went wrong') {
  return Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve({ detail }),
  });
}

beforeEach(() => {
  localStorage.setItem('gnosis_token', 'api-test-token');
  // Reset vault store to own-vault context
  useVaultStore.setState({ activeVaultOwnerId: null });
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('listNotes', () => {
  it('sends GET to /api/v1/notes/ with query params and auth header', async () => {
    const _spy = vi.stubGlobal('fetch', vi.fn(() => ok([{ id: 'n1' }])));
    await api.listNotes({ note_type: 'permanent', limit: 50 });
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/notes/');
    expect(url).toContain('note_type=permanent');
    expect(url).toContain('limit=50');
    expect((opts.headers as Record<string, string>)['Authorization']).toBe('Bearer api-test-token');
  });
});

describe('getNote', () => {
  it('calls GET /api/v1/notes/:id', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ id: 'abc', title: 'Hello' })));
    const note = await api.getNote('abc');
    const [url] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/v1/notes/abc');
    expect((note as { id: string }).id).toBe('abc');
  });
});

describe('createNote', () => {
  it('calls POST /api/v1/notes/ with JSON body', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ id: 'new' })));
    await api.createNote({ title: 'New', content: '...' });
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/v1/notes/');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body as string)).toMatchObject({ title: 'New' });
  });
});

describe('updateNote', () => {
  it('calls PUT /api/v1/notes/:id with JSON body', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ id: 'x1' })));
    await api.updateNote('x1', { title: 'Edited' });
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/v1/notes/x1');
    expect(opts.method).toBe('PUT');
    expect(JSON.parse(opts.body as string)).toMatchObject({ title: 'Edited' });
  });
});

describe('deleteNote', () => {
  it('calls DELETE /api/v1/notes/:id and handles 204 no-content', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, status: 204, json: () => Promise.reject() })));
    const result = await api.deleteNote('del-1');
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/v1/notes/del-1');
    expect(opts.method).toBe('DELETE');
    expect(result).toBeUndefined();
  });
});

describe('vault header injection', () => {
  it('includes X-Vault-Owner-Id when activeVaultOwnerId is set', async () => {
    useVaultStore.setState({ activeVaultOwnerId: 7 });
    vi.stubGlobal('fetch', vi.fn(() => ok([])));
    await api.listNotes({});
    const [, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((opts.headers as Record<string, string>)['X-Vault-Owner-Id']).toBe('7');
  });

  it('omits X-Vault-Owner-Id when activeVaultOwnerId is null', async () => {
    useVaultStore.setState({ activeVaultOwnerId: null });
    vi.stubGlobal('fetch', vi.fn(() => ok([])));
    await api.listNotes({});
    const [, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((opts.headers as Record<string, string>)['X-Vault-Owner-Id']).toBeUndefined();
  });
});

describe('error handling', () => {
  it('throws an Error with the detail message on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn(() => fail(422, 'Validation failed')));
    await expect(api.createNote({})).rejects.toThrow('Validation failed');
  });
});

describe('chat', () => {
  it('sends POST /api/v1/ai/chat with message, mode, and session_id', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ answer: 'ok' })));
    await api.chat('What is a zettelkasten?', 'local', 'sess-1');
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/v1/ai/chat');
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body as string);
    expect(body).toMatchObject({ message: 'What is a zettelkasten?', mode: 'local', session_id: 'sess-1' });
  });
});

describe('search', () => {
  it('builds query string with encoded search term', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok([])));
    await api.search('zettel kasten', { limit: 10 });
    const [url] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/api/v1/search/');
    expect(url).toContain('q=zettel%20kasten');
    expect(url).toContain('limit=10');
  });
});
