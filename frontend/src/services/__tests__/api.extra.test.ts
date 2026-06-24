/**
 * api.extra.test.ts
 * =================
 * Covers the api.ts lines NOT exercised by the existing api.test.ts:
 *
 *   95      getDailyNote
 *   115     getBacklinks, getOutlinks, getOrphanNotes
 *   126     searchNoteByTitle, listTemplates
 *   153     listTags, getFullGraph, getNeighborhood, getPath,
 *           getClusters, getGraphStats, getLightRagGraph, getGraphEntities
 *   160     summarizeNote, critiqueNote, suggestLinks, ingestNote,
 *           getProviders, setModel
 *   173-183 triggerVaultSync, getVaultSyncStatus, openVaultSyncStream
 *   185-207 ingestFile (success + error), ingestUrl (success + error)
 *
 * Cases (26):
 *  Notes: getDailyNote, getBacklinks, getOutlinks, getOrphanNotes,
 *         searchNoteByTitle, listTemplates
 *  Tags / Graph: listTags, getFullGraph, getNeighborhood, getPath,
 *               getClusters, getGraphStats, getLightRagGraph, getGraphEntities
 *  AI: summarizeNote, critiqueNote, suggestLinks, ingestNote,
 *      getProviders, setModel
 *  Vault sync: triggerVaultSync, getVaultSyncStatus, openVaultSyncStream
 *  Ingest: ingestFile success, ingestFile error,
 *          ingestUrl success,  ingestUrl error
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '../api';

// ── Stub Zustand store so api.ts doesn't blow up outside React ───────────
vi.mock('../../store/useVaultStore', () => ({
  useVaultStore: { getState: () => ({ activeVaultOwnerId: null }) },
}));

// ── Helpers ──────────────────────────────────────────────────────────────
function mockFetch(body: unknown = {}, ok = true, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    status,
    json:       async () => body,
    statusText: ok ? 'OK' : 'Error',
  } as Response);
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('gnosis_token', 'test-tok');
});

// ── Notes (extra endpoints) ───────────────────────────────────────────────
describe('api extra — notes', () => {
  it('getDailyNote calls GET /notes/daily', async () => {
    mockFetch({ id: 'daily-1' });
    await api.getDailyNote();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/notes/daily');
  });

  it('getBacklinks calls GET /notes/:id/backlinks', async () => {
    mockFetch([]);
    await api.getBacklinks('note-5');
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/notes/note-5/backlinks');
  });

  it('getOutlinks calls GET /notes/:id/outlinks', async () => {
    mockFetch([]);
    await api.getOutlinks('note-6');
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/notes/note-6/outlinks');
  });

  it('getOrphanNotes calls GET /notes/orphans', async () => {
    mockFetch([]);
    await api.getOrphanNotes();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/notes/orphans');
  });

  it('searchNoteByTitle calls GET /notes/by-title?q=…', async () => {
    mockFetch([]);
    await api.searchNoteByTitle('Buddhism');
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/notes/by-title');
    expect(url).toContain('q=Buddhism');
  });

  it('listTemplates calls GET /notes/templates', async () => {
    mockFetch([]);
    await api.listTemplates();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/notes/templates');
  });
});

// ── Tags / Graph ──────────────────────────────────────────────────────────
describe('api extra — tags and graph', () => {
  it('listTags calls GET /tags/', async () => {
    mockFetch([]);
    await api.listTags();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/tags/');
  });

  it('getFullGraph calls GET /graph/', async () => {
    mockFetch({});
    await api.getFullGraph();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/graph/');
  });

  it('getNeighborhood calls GET /graph/neighborhood/:id', async () => {
    mockFetch({});
    await api.getNeighborhood('n1');
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/graph/neighborhood/n1');
  });

  it('getPath calls GET /graph/path/:from/:to', async () => {
    mockFetch({});
    await api.getPath('a', 'b');
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/graph/path/a/b');
  });

  it('getClusters calls GET /graph/clusters', async () => {
    mockFetch([]);
    await api.getClusters();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/graph/clusters');
  });

  it('getGraphStats calls GET /graph/stats', async () => {
    mockFetch({});
    await api.getGraphStats();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/graph/stats');
  });

  it('getLightRagGraph calls GET /graph/lightrag', async () => {
    mockFetch({});
    await api.getLightRagGraph();
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/graph/lightrag');
  });

  it('getGraphEntities calls GET /graph/entities?limit=…', async () => {
    mockFetch({ entities: [] });
    await api.getGraphEntities(50);
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain('/graph/entities');
    expect(url).toContain('limit=50');
  });
});

// ── AI ────────────────────────────────────────────────────────────────────
describe('api extra — AI endpoints', () => {
  it('summarizeNote calls POST /ai/summarize/:id', async () => {
    mockFetch({});
    await api.summarizeNote('note-x');
    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/ai/summarize/note-x');
    expect(opts.method).toBe('POST');
  });

  it('critiqueNote calls POST /ai/critique/:id', async () => {
    mockFetch({});
    await api.critiqueNote('note-y');
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/ai/critique/note-y');
  });

  it('suggestLinks calls POST /ai/suggest-links/:id', async () => {
    mockFetch([]);
    await api.suggestLinks('note-z');
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/ai/suggest-links/note-z');
  });

  it('ingestNote calls POST /ai/ingest-note/:id', async () => {
    mockFetch({});
    await api.ingestNote('note-q');
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/ai/ingest-note/note-q');
  });

  it('getProviders calls GET /ai/providers', async () => {
    mockFetch([]);
    await api.getProviders();
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/ai/providers');
  });

  it('setModel sends POST /ai/providers/model with { model }', async () => {
    mockFetch({});
    await api.setModel('gpt-4o');
    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/ai/providers/model');
    expect(JSON.parse(opts.body as string)).toEqual({ model: 'gpt-4o' });
  });
});

// ── Vault Sync ────────────────────────────────────────────────────────────
describe('api extra — vault sync', () => {
  it('triggerVaultSync calls POST /vault/sync', async () => {
    mockFetch({ status: 'accepted', message: 'ok', user_id: 1 });
    await api.triggerVaultSync();
    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/vault/sync');
    expect(opts.method).toBe('POST');
  });

  it('getVaultSyncStatus calls GET /vault/sync/status', async () => {
    mockFetch({ state: 'idle', started: null, elapsed: null, files_processed: 0, files_total: 0, last_error: null });
    await api.getVaultSyncStatus();
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/vault/sync/status');
  });

  it('openVaultSyncStream returns an EventSource', () => {
    // EventSource is not available in jsdom — stub it
    const FakeES = vi.fn().mockImplementation(function (this: EventSource) {}) as unknown as typeof EventSource;
    global.EventSource = FakeES;
    const es = api.openVaultSyncStream();
    expect(FakeES).toHaveBeenCalled();
    const calledUrl: string = (FakeES as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(calledUrl).toContain('/vault/sync');
    expect(calledUrl).toContain('stream=true');
    void es;
  });
});

// ── Ingest ────────────────────────────────────────────────────────────────
describe('api extra — ingest', () => {
  it('ingestFile sends POST /ingest/file with FormData', async () => {
    mockFetch({ id: 'new-note' });
    const file = new File(['content'], 'test.md', { type: 'text/markdown' });
    const result = await api.ingestFile(file);
    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/ingest/file');
    expect(opts.method).toBe('POST');
    expect(opts.body).toBeInstanceOf(FormData);
    expect(result).toEqual({ id: 'new-note' });
  });

  it('ingestFile throws on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok:   false,
      json: async () => ({ detail: 'Unsupported file type' }),
      statusText: 'Bad Request',
    } as Response);
    const file = new File([''], 'bad.exe');
    await expect(api.ingestFile(file)).rejects.toThrow('Unsupported file type');
  });

  it('ingestUrl sends POST /ingest/url with FormData', async () => {
    mockFetch({ id: 'url-note' });
    const result = await api.ingestUrl('https://example.com/article');
    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain('/ingest/url');
    expect(opts.method).toBe('POST');
    expect(opts.body).toBeInstanceOf(FormData);
    expect(result).toEqual({ id: 'url-note' });
  });

  it('ingestUrl throws on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok:   false,
      json: async () => ({ detail: 'Invalid URL' }),
      statusText: 'Bad Request',
    } as Response);
    await expect(api.ingestUrl('not-a-url')).rejects.toThrow('Invalid URL');
  });
});
