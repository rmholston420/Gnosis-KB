/**
 * services/api.ts — canonical API client.
 *
 * This is the single source of truth consumed by all tests, hooks, and pages.
 * Key contract (enforced by test suite):
 *   - updateNote uses PUT (not PATCH)
 *   - createNote posts to /api/notes/ (trailing slash)
 *   - getNote passes explicit method: 'GET'
 *   - setActiveVaultPath is a named export
 *   - listNotes, getGraph, listTags, listFolders, ingestNote, getLightRagNode,
 *     streamQuery, chat, search, listTemplates are all present
 */
import { useVaultStore } from '../store/useVaultStore';
import type { GraphEntitySummary } from '../types';

// Re-export so pages can import from one place
export type { GraphEntitySummary };

const BASE = (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ?? '/api';

let _activeVaultPath: string | null = null;

/** Call this when the active vault path changes (e.g. after vault selection). */
export function setActiveVaultPath(path: string | null): void {
  _activeVaultPath = path;
}

function authHeaders(): Record<string, string> {
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('gnosis_token') : null;
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const vaultState = typeof useVaultStore !== 'undefined'
    ? (useVaultStore.getState?.() ?? null)
    : null;
  const ownerId = (vaultState as Record<string, unknown> | null)?.activeVaultOwnerId;
  if (ownerId != null) headers['X-Vault-Owner-Id'] = String(ownerId);
  if (_activeVaultPath) headers['X-Vault-Path'] = _activeVaultPath;
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${msg}`);
  }
  return res.json() as Promise<T>;
}

/** Generic POST helper for one-off authenticated calls (e.g. auth endpoints). */
export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) });
}

// ── Notes ─────────────────────────────────────────────────────────────────────────────────

export function listNotes(params: {
  note_type?: string;
  tag?: string;
  folder?: string;
  status?: string;
  page?: number;
  page_size?: number;
  limit?: number;
  q?: string;
  search?: string;
} = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null) q.set(k, String(v)); });
  const qs = q.toString();
  return request<{ items: unknown[]; total: number }>(`/notes${qs ? `?${qs}` : ''}`);
}

export function getNote(id: string) {
  return request<unknown>(`/notes/${id}`, { method: 'GET' });
}

export function createNote(data: Record<string, unknown>) {
  return request<unknown>('/notes/', { method: 'POST', body: JSON.stringify(data) });
}

export function updateNote(id: string, data: Record<string, unknown>) {
  return request<unknown>(`/notes/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export function deleteNote(id: string) {
  return request<unknown>(`/notes/${id}`, { method: 'DELETE' });
}

export function listTags() {
  return request<string[]>('/notes/tags');
}

export function listFolders() {
  return request<string[]>('/notes/folders');
}

export function listTemplates() {
  return request<unknown[]>('/notes/templates');
}

export function getDailyNote(date: string) {
  return request<unknown>(`/notes/daily/${date}`);
}

export function ingestFile(file: File): Promise<unknown> {
  const fd = new FormData();
  fd.append('file', file);
  return fetch(`${BASE}/notes/ingest/file`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  }).then(async (res) => {
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
  });
}

export function ingestUrl(url: string, _unused?: unknown) {
  return request<unknown>('/notes/ingest/url', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

// ── AI (convenience wrappers around api/ai standalone functions) ─────────────────
// These live here so legacy code calling `api.summarizeNote` etc. still works.

export function summarizeNote(id: string) {
  return request<{ summary: string }>(`/ai/summarize/${id}`, { method: 'POST' });
}

export function critiqueNote(id: string) {
  return request<unknown>(`/ai/critique/${id}`, { method: 'POST' });
}

export function suggestLinks(id: string) {
  return request<{ suggestions: Array<{ title: string; reason: string }> }>(
    `/ai/suggest-links/${id}`, { method: 'POST' },
  );
}

// ── Search ──────────────────────────────────────────────────────────────────────────────

export function search(
  q: string,
  mode: 'hybrid' | 'semantic' | 'keyword' = 'hybrid',
  params: { limit?: number } = {},
) {
  const qs = new URLSearchParams({ q, mode });
  if (params.limit) qs.set('limit', String(params.limit));
  return request<{ items: unknown[]; total: number }>(`/search?${qs}`);
}

export function semanticSearch(q: string, limit = 20) {
  return request<unknown>(`/search/semantic?q=${encodeURIComponent(q)}&limit=${limit}`);
}

export function hybridSearch(q: string, limit = 20) {
  return request<unknown>(`/search/hybrid?q=${encodeURIComponent(q)}&limit=${limit}`);
}

export function getSimilarNotes(id: string, limit = 6) {
  return request<unknown[]>(`/notes/${id}/similar?limit=${limit}`);
}

// ── Graph ────────────────────────────────────────────────────────────────────────────

export function getGraph() {
  return request<{ nodes: unknown[]; edges: unknown[] }>('/graph/');
}

export function getFullGraph() {
  return request<unknown>('/graph');
}

export function getLightRagGraph() {
  return request<unknown>('/graph/lightrag');
}

export function getGraphEntities(type?: string) {
  return request<unknown[]>(`/graph/entities${type ? `?type=${encodeURIComponent(type)}` : ''}`);
}

export function getGraphNode(id: string) {
  return request<unknown>(`/graph/nodes/${id}`);
}

export function getNeighborhood(id: string) {
  return request<unknown>(`/graph/neighborhood/${id}`);
}

export function getGraphStats() {
  return request<unknown>('/graph/stats');
}

export function getClusters() {
  return request<unknown>('/graph/clusters');
}

// ── LightRAG ──────────────────────────────────────────────────────────────────────────

export function ingestNote(id: string) {
  return request<unknown>(`/lightrag/ingest/${id}`, { method: 'POST' });
}

export function getLightRagNode(id: string) {
  return request<unknown>(`/lightrag/node/${id}`, { method: 'GET' });
}

export function streamQuery(
  q: string,
  onChunk: (token: string) => void,
  onDone: () => void,
): () => void {
  const url = `${BASE}/lightrag/stream?q=${encodeURIComponent(q)}`;
  const es = new EventSource(url);
  es.onmessage = (evt: MessageEvent) => {
    if (evt.data === '[DONE]') { es.close(); onDone(); }
    else { onChunk(evt.data); }
  };
  es.onerror = () => { es.close(); onDone(); };
  return () => es.close();
}

// ── AI ───────────────────────────────────────────────────────────────────────────────────

export function chat(
  message: string,
  mode: 'hybrid' | 'semantic' | 'keyword' = 'hybrid',
  context?: string,
) {
  return request<{ response: string }>('/ai/chat', {
    method: 'POST',
    body: JSON.stringify({ message, mode, context }),
  });
}

export function triggerAiAnalysis(noteId: string) {
  return request<unknown>(`/ai/analyze/${noteId}`, { method: 'POST' });
}

export function generateLinkedNotes(noteId: string) {
  return request<unknown[]>(`/ai/link-suggestions/${noteId}`, { method: 'POST' });
}

export function getAiHistory(sessionId: string) {
  return request<unknown[]>(`/ai/history/${sessionId}`);
}

// ── Vault ─────────────────────────────────────────────────────────────────────────────

export function triggerVaultSync() {
  return request<unknown>('/vault/sync', { method: 'POST' });
}

// ── Default export (legacy compat) ───────────────────────────────────────────────

const api = {
  // notes
  listNotes, getNote, createNote, updateNote, deleteNote,
  listTags, listFolders, listTemplates, getDailyNote,
  ingestFile, ingestUrl,
  // ai (on api object for legacy callers)
  summarizeNote, critiqueNote, suggestLinks,
  // search
  search, semanticSearch, hybridSearch, getSimilarNotes,
  // graph
  getGraph, getFullGraph, getLightRagGraph, getGraphEntities, getGraphNode,
  getNeighborhood, getGraphStats, getClusters,
  // lightrag
  ingestNote, getLightRagNode, streamQuery,
  // ai
  chat, triggerAiAnalysis, generateLinkedNotes, getAiHistory,
  // vault
  triggerVaultSync,
  // util
  setActiveVaultPath, post,
};

export default api;
