/**
 * api.ts — Gnosis-KB frontend API client
 *
 * All requests go through the `request()` helper which:
 *  - Prepends BASE_URL
 *  - Attaches the active-vault header
 *  - Throws on non-2xx responses with the server's detail message
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

// ---------------------------------------------------------------------------
// Active vault state (shared with VaultSwitcher)
// ---------------------------------------------------------------------------
let _activeVaultPath: string | null = null;

export function setActiveVaultPath(p: string | null) {
  _activeVaultPath = p;
}
export function getActiveVaultPath(): string | null {
  return _activeVaultPath;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
function buildCommonHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  if (_activeVaultPath) h['X-Vault-Path'] = _activeVaultPath;
  return h;
}

async function request(method: string, path: string, body?: unknown): Promise<unknown> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...buildCommonHeaders(),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  if (res.status === 204) return {};
  return res.json();
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------
const api = {
  // -- Notes -----------------------------------------------------------------
  listNotes: (params: Record<string, string | number>) =>
    request(
      'GET',
      '/notes/?' +
        Object.entries(params)
          .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
          .join('&'),
    ),

  getNote: (id: string) => request('GET', `/notes/${id}`),

  createNote: (data: unknown) => request('POST', '/notes/', data),

  updateNote: (id: string, data: unknown) => request('PUT', `/notes/${id}`, data),

  deleteNote: (id: string) => request('DELETE', `/notes/${id}`),

  getDailyNote: () => request('GET', '/notes/daily'),

  getBacklinks: (id: string) => request('GET', `/notes/${id}/backlinks`),

  getOutlinks: (id: string) => request('GET', `/notes/${id}/outlinks`),

  getOrphanNotes: () => request('GET', '/notes/orphans'),

  searchNoteByTitle: (q: string) =>
    request('GET', `/notes/search-by-title?q=${encodeURIComponent(q)}`),

  listTemplates: () => request('GET', '/notes/templates'),

  search: (q: string, params: Record<string, string | number> = {}) =>
    request(
      'GET',
      '/search/?' +
        Object.entries({ q, ...params })
          .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
          .join('&'),
    ),

  listTags: () => request('GET', '/tags/'),

  // -- Graph -----------------------------------------------------------------
  getFullGraph: () => request('GET', '/graph/'),

  getNeighborhood: (id: string) => request('GET', `/graph/neighborhood/${id}`),

  getPath: (fromId: string, toId: string) =>
    request('GET', `/graph/path?from=${fromId}&to=${toId}`),

  getClusters: () => request('GET', '/graph/clusters'),

  getGraphStats: () => request('GET', '/graph/stats'),

  getLightRagGraph: () => request('GET', '/graph/lightrag'),

  getGraphEntities: (limit = 100) =>
    request('GET', `/graph/entities?limit=${limit}`),

  // -- AI --------------------------------------------------------------------
  chat: (message: string, mode = 'hybrid', sessionId?: string) =>
    request('POST', '/ai/chat', { message, mode, session_id: sessionId }),

  summarizeNote: (id: string) => request('POST', `/ai/summarize/${id}`),

  critiqueNote: (id: string) => request('POST', `/ai/critique/${id}`),

  suggestLinks: (id: string) => request('POST', `/ai/suggest-links/${id}`),

  /** Trigger on-demand LightRAG ingestion of a single note (backfill). */
  ingestNote: (id: string) => request('POST', `/ai/ingest-note/${id}`),

  getProviders: () => request('GET', '/ai/providers'),

  setModel: (model: string) => request('POST', '/ai/providers/model', { model }),

  // -- Vault sync ------------------------------------------------------------
  triggerVaultSync: () =>
    request('POST', '/vault/sync'),

  getVaultSyncStatus: () =>
    request('GET', '/vault/sync/status'),

  listVaults: () => request('GET', '/vault/vaults'),

  openVaultSyncStream: (): EventSource => {
    const url = `${BASE_URL}/vault/sync/stream`;
    return new EventSource(url);
  },

  // -- Ingest ----------------------------------------------------------------
  // NOTE: these two methods build FormData manually so they do NOT use
  // build headers manually via buildCommonHeaders() (no Content-Type override).
  ingestFile: (file: File, folder = '70-sources') => {
    const form = new FormData();
    form.append('file', file);
    form.append('folder', folder);
    return fetch(`${BASE_URL}/ingest/file`, {
      method: 'POST',
      headers: buildCommonHeaders(),
      body: form,
    }).then(async (res) => {
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
      return res.json();
    });
  },

  ingestUrl: (url: string, folder = '70-sources') => {
    const form = new FormData();
    form.append('url', url);
    form.append('folder', folder);
    return fetch(`${BASE_URL}/ingest/url`, {
      method: 'POST',
      headers: buildCommonHeaders(),
      body: form,
    }).then(async (res) => {
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
      return res.json();
    });
  },

  // -- New methods (graph + query) -------------------------------------------

  /** Fetch the full knowledge graph (nodes + edges). */
  getGraph: () => request('GET', '/graph/'),

  /** Fetch a single LightRAG entity node with its relations. */
  getLightRagNode: (nodeId: string) =>
    request('GET', `/graph/lightrag/node/${encodeURIComponent(nodeId)}`),

  /** List all vault folders. */
  listFolders: () => request('GET', '/notes/folders'),

  /** Stream a query response via SSE. Returns the EventSource for cleanup. */
  streamQuery: (
    query: string,
    onChunk: (token: string) => void,
    onDone: () => void,
  ): EventSource => {
    const url = `${BASE_URL}/query/stream?q=${encodeURIComponent(query)}`;
    const es = new EventSource(url);
    es.onmessage = (e: MessageEvent) => {
      if (e.data === '[DONE]') {
        onDone();
        es.close();
      } else {
        onChunk(e.data as string);
      }
    };
    es.onerror = () => { es.close(); };
    return es;
  },
};

// --- Shared types used by api methods above --------------------------------

export interface VaultSyncStatus {
  state: 'idle' | 'running' | 'done' | 'error';
  started: number | null;
  elapsed: number | null;
  files_processed: number;
  files_total: number;
  last_error: string | null;
}

export interface GraphEntitySummary {
  id: string;
  label: string;
  description?: string;
  cluster?: number;
  source_note_ids?: string[];
}

export default api;
