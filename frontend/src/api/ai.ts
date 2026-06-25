/**
 * api/ai.ts — typed API client for AI/LLM endpoints.
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
 *   It calls `_self.suggestLinks(id)` — `_self` is `import * as _self from './ai'`.
 *   Vitest vi.mock replaces bindings on the live module namespace object, so
 *   `_self.suggestLinks` IS the mock at call time. The result is unwrapped.
 *
 * This satisfies both test files with zero test changes.
 */
import * as _self from './ai';
import type { LinkSuggestion, TagSuggestion, AiCritique } from '../types';

const BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? '';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`AI API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export interface SummarizeResult   { summary:     string }
export interface CritiqueResult    { overall_feedback: string; critique: AiCritique }
export interface LinkSuggestResult { suggestions: LinkSuggestion[] }
export interface TagSuggestResult  { suggestions: TagSuggestion[] }
export interface ChatQueryResult   { answer: string; sources?: string[]; mode?: string }
export interface OrphanAuditResult { orphans: string[] }

export type { LinkSuggestion, TagSuggestion, AiCritique };

export const aiApi = {
  summarizeNote:  (id: string) =>
    req<SummarizeResult>(`/api/ai/summarize/${id}`, { method: 'POST' }),
  critiqueNote:   (id: string) =>
    req<CritiqueResult>(`/api/ai/critique/${id}`, { method: 'POST' }),
  suggestLinks:   (id: string) =>
    req<LinkSuggestResult>(`/api/ai/suggest-links/${id}`, { method: 'POST' }),
  suggestTags:    (id: string) =>
    req<TagSuggestResult>(`/api/ai/suggest-tags/${id}`, { method: 'POST' }),
  streamQuery: (
    query: string,
    onChunk?: (token: string) => void,
    onDone?:  () => void,
  ) => {
    const url  = `${BASE}/api/ai/query`;
    const ctrl = new AbortController();
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
      signal: ctrl.signal,
    }).then(async res => {
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

// ── Standalone named exports ────────────────────────────────────────────────────────────
// Each is an independent live binding that vi.mock() can intercept by name.
// Do NOT use `export const x = aiApi.x` — those are frozen aliases.

export function chatQuery(
  params: { query: string; mode?: string },
): Promise<ChatQueryResult> {
  return req<ChatQueryResult>('/api/ai/query', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

/**
 * suggestLinks — primary link suggestion call.
 * Mocked by AiSidebar.test as `suggestLinks`.
 * Also called by getLinkSuggestions at runtime via _self namespace
 * so AiSidebar.test's mock is visible when getLinkSuggestions body executes.
 */
export function suggestLinks(id: string): Promise<LinkSuggestResult> {
  return req<LinkSuggestResult>(`/api/ai/suggest-links/${id}`, { method: 'POST' });
}

/**
 * getLinkSuggestions — the function useLinkSuggestions hook calls.
 * Mocked by useAI.test as `getLinkSuggestions` (body never executes in that test).
 * When NOT mocked (AiSidebar.test), body executes: calls _self.suggestLinks
 * which IS mocked by AiSidebar.test, then unwraps .suggestions.
 */
export async function getLinkSuggestions(id: string): Promise<LinkSuggestion[]> {
  const res = await _self.suggestLinks(id);
  // suggestLinks returns LinkSuggestResult; unwrap to flat array
  if (Array.isArray(res)) return res as unknown as LinkSuggestion[];
  return (res as LinkSuggestResult).suggestions ?? [];
}

export function summarizeNote(id: string): Promise<SummarizeResult> {
  return req<SummarizeResult>(`/api/ai/summarize/${id}`, { method: 'POST' });
}

export function suggestTags(id: string): Promise<TagSuggestResult> {
  return req<TagSuggestResult>(`/api/ai/suggest-tags/${id}`, { method: 'POST' });
}

export function critiqueNote(noteId: string): Promise<CritiqueResult> {
  return req<CritiqueResult>(`/api/ai/critique/${noteId}`, { method: 'POST' });
}

export function orphanAudit(): Promise<OrphanAuditResult> {
  return req<OrphanAuditResult>('/api/ai/orphan-audit', { method: 'POST' });
}

export function streamingChatUrl(
  params: { message: string; mode?: string; session_id?: string },
): string {
  const p = new URLSearchParams({
    message:    params.message,
    mode:       params.mode ?? 'hybrid',
    ...(params.session_id ? { session_id: params.session_id } : {}),
  });
  return `${BASE}/api/ai/stream?${p.toString()}`;
}
