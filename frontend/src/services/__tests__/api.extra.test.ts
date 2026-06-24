/**
 * api.extra.test.ts
 * Tests for additional API service methods:
 *   - streamQuery (SSE)
 *   - getLightRagNode
 *   - getLightRagGraph
 *   - getGraph
 *   - getNote (full)
 *   - updateNote / deleteNote
 *   - ingestNote
 *   - listTags / listFolders
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---- mock fetch globally -------------------------------------------------------
const mockFetch = vi.fn();
global.fetch = mockFetch;

function makeJsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
    headers: new Headers({ 'content-type': 'application/json' }),
  } as Response);
}

import api from '../api';

// ---- helpers -------------------------------------------------------------------
beforeEach(() => {
  mockFetch.mockReset();
});

// ================================================================================
// getGraph
// ================================================================================
describe('api.getGraph', () => {
  it('returns graph data', async () => {
    const data = { nodes: [], edges: [] };
    mockFetch.mockReturnValue(makeJsonResponse(data));
    const result = await api.getGraph() as { nodes: unknown[]; edges: unknown[] };
    expect(result.nodes).toBeDefined();
  });

  it('throws on non-ok response', async () => {
    mockFetch.mockReturnValue(makeJsonResponse({ detail: 'Not found' }, 404));
    await expect(api.getGraph()).rejects.toThrow();
  });
});

// ================================================================================
// getNote (full note)
// ================================================================================
describe('api.getNote', () => {
  const NOTE = {
    id: 'n1', title: 'Test', slug: 'test', body: 'body', note_type: 'permanent',
    status: 'evergreen', tags: [], folder: '', word_count: 1,
    created_at: '2026-01-01T00:00:00Z', modified_at: '2026-06-01T00:00:00Z',
    incoming_links: [], outgoing_links: [], frontmatter: {},
    body_html: '', is_deleted: false, vector_indexed: false, graph_indexed: false,
  };

  it('returns note data', async () => {
    mockFetch.mockReturnValue(makeJsonResponse(NOTE));
    const result = await api.getNote('n1') as { id: string };
    expect(result.id).toBe('n1');
  });

  it('throws on non-ok response', async () => {
    mockFetch.mockReturnValue(makeJsonResponse({ detail: 'Not found' }, 404));
    await expect(api.getNote('missing')).rejects.toThrow();
  });
});

// ================================================================================
// updateNote
// ================================================================================
describe('api.updateNote', () => {
  const UPDATED = {
    id: 'n1', title: 'Updated', slug: 'updated', body: 'new body',
    note_type: 'permanent', status: 'evergreen', tags: [], folder: '',
    word_count: 2, created_at: '2026-01-01T00:00:00Z',
    modified_at: '2026-06-24T00:00:00Z',
    incoming_links: [], outgoing_links: [], frontmatter: {},
    body_html: '', is_deleted: false, vector_indexed: false, graph_indexed: false,
  };

  it('sends PUT and returns updated note', async () => {
    mockFetch.mockReturnValue(makeJsonResponse(UPDATED));
    const result = await api.updateNote('n1', { title: 'Updated' }) as { title: string };
    expect(result.title).toBe('Updated');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('n1'),
      expect.objectContaining({ method: 'PUT' })
    );
  });
});

// ================================================================================
// deleteNote
// ================================================================================
describe('api.deleteNote', () => {
  it('sends DELETE request', async () => {
    mockFetch.mockReturnValue(makeJsonResponse({}, 204));
    await api.deleteNote('n1');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('n1'),
      expect.objectContaining({ method: 'DELETE' })
    );
  });
});

// ================================================================================
// listTags
// ================================================================================
describe('api.listTags', () => {
  it('returns array of tags', async () => {
    mockFetch.mockReturnValue(makeJsonResponse(['buddhism', 'madhyamaka']));
    const result = await api.listTags() as string[];
    expect(Array.isArray(result)).toBe(true);
  });
});

// ================================================================================
// listFolders
// ================================================================================
describe('api.listFolders', () => {
  it('returns array of folders', async () => {
    mockFetch.mockReturnValue(makeJsonResponse(['inbox', 'archive']));
    const result = await api.listFolders() as string[];
    expect(Array.isArray(result)).toBe(true);
  });
});

// ================================================================================
// ingestNote
// ================================================================================
describe('api.ingestNote', () => {
  it('sends POST and returns result', async () => {
    mockFetch.mockReturnValue(makeJsonResponse({ ok: true }));
    const result = await api.ingestNote('n1');
    expect(result).toBeDefined();
  });
});

// ================================================================================
// getLightRagNode
// ================================================================================
describe('api.getLightRagNode', () => {
  it('returns entity and relations', async () => {
    const data = { entity: { id: 'e1', name: 'Emptiness', type: 'concept' }, relations: [] };
    mockFetch.mockReturnValue(makeJsonResponse(data));
    const result = await api.getLightRagNode('e1') as { entity: { id: string } };
    expect(result.entity).toBeDefined();
  });
});

// ================================================================================
// getLightRagGraph
// ================================================================================
describe('api.getLightRagGraph', () => {
  it('returns graph data', async () => {
    const data = { nodes: [], edges: [] };
    mockFetch.mockReturnValue(makeJsonResponse(data));
    const result = await api.getLightRagGraph();
    expect(result).toBeDefined();
  });
});

// ================================================================================
// streamQuery (SSE via EventSource)
// ================================================================================
describe('api.streamQuery', () => {
  const origEventSource = global.EventSource;

  afterEach(() => {
    global.EventSource = origEventSource;
  });

  it('creates an EventSource with the correct URL', () => {
    const FakeES = vi.fn().mockImplementation(function (this: EventSource) {}) as unknown as typeof EventSource;
    global.EventSource = FakeES;

    api.streamQuery('SELECT * FROM notes', vi.fn(), vi.fn());

    expect(FakeES).toHaveBeenCalledTimes(1);
    const calledUrl: string = (FakeES as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(calledUrl).toContain('stream');
  });

  it('calls onChunk for each message event', () => {
    const mockInstance = {
      onmessage: null as ((e: MessageEvent) => void) | null,
      onerror:   null as ((e: Event) => void) | null,
      close:     vi.fn(),
    };
    const FakeES = vi.fn().mockImplementation(() => mockInstance) as unknown as typeof EventSource;
    global.EventSource = FakeES;

    const onChunk = vi.fn();
    api.streamQuery('SELECT * FROM notes', onChunk, vi.fn());

    mockInstance.onmessage?.({ data: 'token1' } as MessageEvent);
    mockInstance.onmessage?.({ data: 'token2' } as MessageEvent);
    expect(onChunk).toHaveBeenCalledTimes(2);
  });

  it('calls onDone when [DONE] sentinel received', () => {
    const mockInstance = {
      onmessage: null as ((e: MessageEvent) => void) | null,
      onerror:   null as ((e: Event) => void) | null,
      close:     vi.fn(),
    };
    const FakeES = vi.fn().mockImplementation(() => mockInstance) as unknown as typeof EventSource;
    global.EventSource = FakeES;

    const onDone = vi.fn();
    api.streamQuery('SELECT * FROM notes', vi.fn(), onDone);

    mockInstance.onmessage?.({ data: '[DONE]' } as MessageEvent);
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(mockInstance.close).toHaveBeenCalledTimes(1);
  });
});
