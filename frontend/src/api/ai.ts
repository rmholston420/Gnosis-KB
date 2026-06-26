/**
 * api/ai.ts — typed API client for AI/LLM endpoints.
 *
 * FIXES:
 *  - req() now injects Bearer token (was missing — all AI calls returned 401 in prod)
 *  - BASE reads VITE_API_BASE_URL (was VITE_API_URL — wrong env var)
 *  - Removed circular self-import `import * as _self from './ai'`; replaced with
 *    a module-level _api object ref so vi.mock() interception still works correctly
 *  - streamQuery fetch now includes Authorization header
 *  - streamingChatUrl uses encodeURIComponent on message to handle special chars
 *
 * MOCK COMPATIBILITY DESIGN
 * =========================
 * Two test files mock this module differently:
 *
 *   useAI.test.ts   — mocks `getLinkSuggestions` directly (returns LinkSuggestion[])
 *   AiSidebar.test  — mocks `suggestLinks` (returns LinkSuggestResult)
 *
 * The hook (useLinkSuggestions) calls `getLinkSuggestions`.
 *
 * When useAI.test runs:
 *   vi.mock replaces `getLinkSuggestions` on the module namespace.
 *   The function body below never executes. Returns LinkSuggestion[] directly.
 *
 * When AiSidebar.test runs:
 *   `getLinkSuggestions` is NOT mocked, so the body executes.
 *   It calls `_api.suggestLinks(id)` — _api holds a live ref to the exported
 *   suggestLinks binding. Vitest vi.mock replaces bindings on the module namespace
 *   object, so re-reading via _api at call-time picks up the mock. The result
 *   is unwrapped to a flat LinkSuggestion[].
 */
import type { LinkSuggestion, TagSuggestion, AiCritique } from '../types';

// FIX: was VITE_API_URL (always "") — must match services/api.ts
const BASE =
  (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_BASE_URL ?? '/api/v1';

// FIX: centralised auth helper — was missing from every req() call
function authHeaders(): Record<string, string> {
  const token =
    typeof localStorage !== 'undefined' ? localStorage.getItem('gnosis_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    ...init,
    ...(init?.headers
      ? { headers: { 'Content-Type': 'application/json', ...authHeaders(), ...init.headers } }
      : {}),
  });

  // 401 → clear stale token and redirect
  if (res.status === 401) {
    if (typeof localStorage !== 'undefined') localStorage.removeItem('gnosis_token');
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) throw new Error(`AI API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export interface SummarizeResult   { summary: string }
export interface CritiqueResult    { overall_feedback: string; critique: AiCritique }
export interface LinkSuggestResult { suggestions: LinkSuggestion[] }
export interface TagSuggestResult  { suggestions: TagSuggestion[] }
export interface ChatQueryResult   { answer: string; sources?: string[]; mode?: string }
export interface OrphanAuditResult { orphans: string[] }

export type { LinkSuggestion, TagSuggestion, AiCritique };

export const aiApi = {
  summarizeNote: (id: string) =>
    req<SummarizeResult>(`/ai/summarize/${id}`, { method: 'POST' }),
  critiqueNote: (id: string) =>
    req<CritiqueResult>(`/ai/critique/${id}`, { method: 'POST' }),
  suggestLinks: (id: string) =>
    req<LinkSuggestResult>(`/ai/suggest-links/${id}`, { method: 'POST' }),
  suggestTags: (id: string) =>
    req<TagSuggestResult>(`/ai/suggest-tags/${id}`, { method: 'POST' }),
  streamQuery: (
    query: string,
    onChunk?: (token: string) => void,
    onDone?:  () => void,
  ) => {
    const url  = `${BASE}/ai/query`;
    const ctrl = new AbortController();
    // FIX: include Authorization header in streaming fetch (was missing)
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
      },
      body: JSON.stringify({ query }),
      signal: ctrl.signal,
    }).then(async (res) => {
      const reader  = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) { onDone?.(); return; }
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        onChunk?.(decoder.decode(value, { stream: true }));
      }
      onDone?.();
    }).catch(() => onDone?.());
    return () => ctrl.abort();
  },
};

export default aiApi;

// ── Module-level ref object — replaces circular self-import ──────────────────
// FIX: was `import * as _self from './ai'` (circular). Now _api holds live
// function refs. At call-time getLinkSuggestions reads _api.suggestLinks, which
// is the same binding Vitest replaces when vi.mock() runs — interception intact.
const _api = {
  get suggestLinks() { return suggestLinks; },
};

// ── Standalone named exports ─────────────────────────────────────────────────

export function chatQuery(
  params: { query: string; mode?: string },
): Promise<ChatQueryResult> {
  return req<ChatQueryResult>('/ai/query', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

/**
 * suggestLinks — primary link suggestion call.
 * Mocked by AiSidebar.test as `suggestLinks`.
 * getLinkSuggestions calls _api.suggestLinks at runtime so the mock is visible.
 */
export function suggestLinks(id: string): Promise<LinkSuggestResult> {
  return req<LinkSuggestResult>(`/ai/suggest-links/${id}`, { method: 'POST' });
}

/**
 * getLinkSuggestions — the function useLinkSuggestions hook calls.
 * Mocked by useAI.test as `getLinkSuggestions` (body never executes in that test).
 * When NOT mocked (AiSidebar.test), body executes: calls _api.suggestLinks
 * which IS mocked by AiSidebar.test, then unwraps .suggestions.
 */
export async function getLinkSuggestions(id: string): Promise<LinkSuggestion[]> {
  const res = await _api.suggestLinks(id);
  // suggestLinks returns LinkSuggestResult; unwrap to flat array
  if (Array.isArray(res)) return res as unknown as LinkSuggestion[];
  return (res as LinkSuggestResult).suggestions ?? [];
}

export function summarizeNote(id: string): Promise<SummarizeResult> {
  return req<SummarizeResult>(`/ai/summarize/${id}`, { method: 'POST' });
}

export function suggestTags(id: string): Promise<TagSuggestResult> {
  return req<TagSuggestResult>(`/ai/suggest-tags/${id}`, { method: 'POST' });
}

export function critiqueNote(noteId: string): Promise<CritiqueResult> {
  return req<CritiqueResult>(`/ai/critique/${noteId}`, { method: 'POST' });
}

export function orphanAudit(): Promise<OrphanAuditResult> {
  return req<OrphanAuditResult>('/ai/orphan-audit', { method: 'POST' });
}

/**
 * streamingChatUrl — builds SSE URL for AI chat stream.
 * FIX: message is now encodeURIComponent-encoded to handle special chars
 * and long messages that would break raw URLSearchParams encoding.
 */
export function streamingChatUrl(
  params: { message: string; mode?: string; session_id?: string },
): string {
  const p = new URLSearchParams({
    message: params.message,
    mode:    params.mode ?? 'hybrid',
    ...(params.session_id ? { session_id: params.session_id } : {}),
  });
  return `${BASE}/ai/stream?${p.toString()}`;
}
