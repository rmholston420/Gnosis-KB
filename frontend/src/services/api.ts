/**
 * services/api.ts — canonical API client.
 *
 * This is the single source of truth consumed by all tests, hooks, and pages.
 * Key contract:
 *   - updateNote uses PUT (not PATCH)
 *   - createNote posts to /api/notes/ (trailing slash)
 *   - getNote passes explicit method: 'GET'
 *   - setActiveVaultPath is a named export
 *   - listNotes, getGraph, listTags, listFolders, ingestNote, getLightRagNode,
 *     streamQuery, chat, search, listTemplates are all present
 *   - summarizeNote, critiqueNote, suggestLinks, getDailyNote,
 *     ingestFile, ingestUrl, getLightRagGraph, post are all present
 */
import { useVaultStore } from '../store/useVaultStore';

const BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ?? '/api';

let _activeVaultPath: string | null = null;

export function setActiveVaultPath(path: string | null): void {
  _activeVaultPath = path;
}

function authHeaders(): Record<string, string> {
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('gnosis_token') : null;
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  try {
    const ownerId = useVaultStore.getState().activeVaultOwnerId;
    if (_activeVaultPath) headers['X-Vault-Path'] = _activeVaultPath;
    if (ownerId !== null && ownerId !== undefined) {
      headers['X-Vault-Owner-Id'] = String(ownerId);
    }
  } catch {
    // skip outside React tree
  }
  return headers;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${method} ${path} → ${res.status}: ${text}`);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

const api = {
  get:  <T>(path: string)                => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put:  <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  del:  <T>(path: string)                => request<T>('DELETE', path),

  listNotes(params: Record<string, unknown> = {}) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) qs.set(k, String(v));
    }
    const q = qs.toString();
    return request<unknown[]>('GET', `/notes/${q ? `?${q}` : ''}`);
  },

  getNote(noteId: string) {
    return request<unknown>('GET', `/notes/${noteId}`);
  },

  createNote(payload: unknown) {
    return request<unknown>('POST', '/notes/', payload);
  },

  updateNote(noteId: string, payload: unknown) {
    return request<unknown>('PUT', `/notes/${noteId}`, payload);
  },

  deleteNote(noteId: string) {
    return request<void>('DELETE', `/notes/${noteId}`);
  },

  listTags() {
    return request<string[]>('GET', '/notes/tags');
  },

  listFolders() {
    return request<string[]>('GET', '/notes/folders');
  },

  listTemplates() {
    return request<string[]>('GET', '/notes/templates');
  },

  ingestNote(path: string) {
    return request<{ job_id: string }>('POST', '/notes/ingest', { path });
  },

  getDailyNote(dateStr?: string) {
    const path = dateStr ? `/notes/daily?date=${dateStr}` : '/notes/daily';
    return request<unknown>('GET', path);
  },

  ingestFile(payload: { file_path: string; note_type?: string }) {
    return request<{ job_id: string }>('POST', '/ingest/file', payload);
  },

  ingestUrl(payload: { url: string; note_type?: string }) {
    return request<{ job_id: string }>('POST', '/ingest/url', payload);
  },

  getGraph() {
    return request<unknown>('GET', '/graph');
  },

  getLightRagGraph() {
    return request<unknown>('GET', '/graph/lightrag');
  },

  getLightRagNode(nodeId: string) {
    return request<unknown>('GET', `/graph/lightrag/node/${nodeId}`);
  },

  getGraphEntities(query?: string) {
    const qs = query ? `?q=${encodeURIComponent(query)}` : '';
    return request<unknown[]>('GET', `/graph/entities${qs}`);
  },

  getFullGraph() {
    return request<unknown>('GET', '/graph/full');
  },

  search(
    q: string,
    mode: 'hybrid' | 'semantic' | 'fulltext' | 'keyword' = 'hybrid',
    limit = 20,
  ) {
    const qs = new URLSearchParams({ q, mode, limit: String(limit) });
    return request<unknown[]>('GET', `/search?${qs.toString()}`);
  },

  chat(
    message: string,
    mode: 'hybrid' | 'local' | 'global' = 'hybrid',
    sessionId?: string,
  ) {
    return request<unknown>('POST', '/ai/chat', { message, mode, session_id: sessionId });
  },

  streamQuery(
    query: string,
    onChunk?: (token: string) => void,
    onDone?: () => void,
  ): EventSource {
    const qs = new URLSearchParams({ query });
    const url = `${BASE}/ai/stream?${qs.toString()}`;
    const es = new EventSource(url);
    if (onChunk) {
      es.addEventListener('message', (e) => onChunk((e as MessageEvent).data));
    }
    if (onDone) {
      es.addEventListener('done', () => { onDone(); es.close(); });
    }
    return es;
  },

  summarizeNote(noteId: string) {
    return request<unknown>('POST', `/ai/summarize/${noteId}`, {});
  },

  critiqueNote(noteId: string) {
    return request<unknown>('POST', `/ai/critique/${noteId}`, {});
  },

  suggestLinks(noteId: string) {
    return request<unknown[]>('POST', `/ai/suggest-links/${noteId}`, {});
  },

  suggestTags(noteId: string) {
    return request<unknown[]>('POST', `/ai/suggest-tags/${noteId}`, {});
  },

  triggerVaultSync() {
    return request<void>('POST', '/vault/sync', {});
  },

  getBacklinks(noteId: string) {
    return request<unknown>('GET', `/notes/${noteId}/backlinks`);
  },
};

export default api;
export const { triggerVaultSync } = api;
export type { GraphEntitySummary } from '../types';
