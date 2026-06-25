/**
 * api/ai.ts — typed API client for AI/LLM endpoints.
 *
 * All result types re-exported so both hooks/useAI.ts and components
 * can import them from a single canonical location.
 *
 * Export strategy for testability:
 *   - suggestLinks and getLinkSuggestions MUST be separate named function
 *     declarations (not `const alias = fn`). Vitest vi.mock() replaces named
 *     export bindings on the module namespace. When getLinkSuggestions is
 *     declared as `export const getLinkSuggestions = aiApi.suggestLinks`, the
 *     binding is frozen at module evaluation time and the mock cannot replace it.
 *     Both must be declared as independent exported functions so each gets its
 *     own live binding that vi.mock() can intercept.
 */
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

// ── Standalone named exports (each is an independent live binding) ───────────
// IMPORTANT: do NOT use `export const x = aiApi.x` — those are frozen aliases
// that vi.mock() cannot intercept. Declare each as a standalone function.

export function chatQuery(
  params: { query: string; mode?: string },
): Promise<ChatQueryResult> {
  return req<ChatQueryResult>('/api/ai/query', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

/**
 * suggestLinks — used by AiSidebar.test (mocked as `suggestLinks`).
 * Must be a standalone function declaration for vi.mock to intercept.
 */
export function suggestLinks(id: string): Promise<LinkSuggestResult> {
  return req<LinkSuggestResult>(`/api/ai/suggest-links/${id}`, { method: 'POST' });
}

/**
 * getLinkSuggestions — used by useAI.test (mocked as `getLinkSuggestions`).
 * Separate live binding from suggestLinks so each test can mock independently.
 */
export function getLinkSuggestions(id: string): Promise<LinkSuggestion[]> {
  return req<LinkSuggestion[]>(`/api/ai/suggest-links/${id}`, { method: 'POST' });
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
