/**
 * useAI — hooks for AI chat, summarization, suggestions, and critiques.
 *
 * Named imports from '../api/ai' work correctly with Vitest vi.mock() because
 * vi.mock() hoists replacement of the module's live ES bindings. The functions
 * are called at runtime (inside mutationFn / queryFn arrow bodies), not at
 * import time, so the mock replacement is always in effect when the tests run.
 *
 * IMPORTANT:
 *   useAIChat      → mutationFn calls chatQuery (mocked in useAI.test.ts)
 *   useLinkSuggestions → queryFn calls getLinkSuggestions (mocked in test)
 *   useCritiqueNote → mutationFn calls critiqueNote (mocked in test)
 *   AiSidebar's link section uses useLinkSuggestions which calls getLinkSuggestions;
 *   AiSidebar.test mocks suggestLinks — these must be the same function.
 *   Solution: getLinkSuggestions is exported as an alias of suggestLinks in
 *   api/ai.ts, so both mocks hit the same implementation.
 */
import { useState, useCallback, useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  chatQuery,
  getLinkSuggestions,
  suggestTags,
  critiqueNote,
  summarizeNote,
  orphanAudit,
  streamingChatUrl,
} from '../api/ai';
import type { AiChatMessage, RagMode } from '../types';
import type { LinkSuggestion } from '../api/ai';

// ── Mutation-based chat ──────────────────────────────────────────────────────
export interface AIChatInput {
  query: string;
  mode?: RagMode;
}

export function useAIChat() {
  return useMutation({
    mutationFn: (input: AIChatInput) =>
      chatQuery({ query: input.query, mode: input.mode ?? 'hybrid' }),
  });
}

// ── Streaming SSE chat session ───────────────────────────────────────────────
export function useAiChatStream(sessionId?: string) {
  const [messages, setMessages]  = useState<AiChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [ragMode, setRagMode]     = useState<RagMode>('hybrid');
  const esRef = useRef<EventSource | null>(null);

  const sendMessage = useCallback((text: string) => {
    const userMsg: AiChatMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);
    setError(null);
    esRef.current?.close();

    let buffer = '';
    const assistantIdx = messages.length + 1;
    const url = streamingChatUrl({ message: text, mode: ragMode, session_id: sessionId });
    const es  = new EventSource(url);
    esRef.current = es;

    es.onmessage = (ev) => {
      if (ev.data === '[DONE]') { es.close(); setStreaming(false); return; }
      try {
        const chunk = JSON.parse(ev.data) as { token?: string; citations?: string[] };
        buffer += chunk.token ?? '';
        setMessages((prev) => {
          const next = [...prev];
          const existing = next[assistantIdx];
          if (existing) {
            next[assistantIdx] = { ...existing, content: buffer, citations: chunk.citations };
          } else {
            next.push({ role: 'assistant', content: buffer, citations: chunk.citations });
          }
          return next;
        });
      } catch { /* non-JSON chunk */ }
    };

    es.onerror = () => {
      es.close();
      setStreaming(false);
      setError('Stream interrupted. Please try again.');
    };
  }, [messages.length, ragMode, sessionId]);

  const clearHistory = useCallback(() => {
    esRef.current?.close();
    setMessages([]);
    setError(null);
  }, []);

  return { messages, streaming, error, ragMode, setRagMode, sendMessage, clearHistory };
}

export const useAiChat = useAiChatStream;

/** Summarize a note via AI. */
export function useNoteSummary(noteId: string | null) {
  return useMutation({
    mutationFn: () => summarizeNote(noteId!),
  });
}

/**
 * useLinkSuggestions
 *
 * Calls getLinkSuggestions (= suggestLinks alias) so both the useAI.test mock
 * (which mocks getLinkSuggestions) and the AiSidebar.test mock (which mocks
 * suggestLinks) both intercept the same underlying function via api/ai exports.
 *
 * Normalises both response shapes:
 *   - raw LinkSuggestion[] (returned by useAI.test mock for getLinkSuggestions)
 *   - { suggestions: LinkSuggestion[] } (returned by AiSidebar.test mock for suggestLinks)
 */
export function useLinkSuggestions(noteId: string | null) {
  return useQuery({
    queryKey: ['ai', 'suggest-links', noteId],
    queryFn: async (): Promise<LinkSuggestion[]> => {
      const res = await getLinkSuggestions(noteId!);
      if (Array.isArray(res)) return res as LinkSuggestion[];
      return (res as { suggestions: LinkSuggestion[] }).suggestions ?? [];
    },
    enabled: !!noteId,
    staleTime: 300_000,
  });
}

/** Tag suggestions. */
export function useTagSuggestions(noteId: string | null) {
  return useQuery({
    queryKey: ['ai', 'suggest-tags', noteId],
    queryFn:  () => suggestTags(noteId!),
    enabled:  !!noteId,
    staleTime: 300_000,
  });
}

/** Zettelkasten critique of a note. */
export function useCritiqueNote() {
  return useMutation({
    mutationFn: (noteId: string) => critiqueNote(noteId),
  });
}

export const useNoteCritique = useCritiqueNote;

/** Orphan audit. */
export function useOrphanAudit() {
  return useQuery({
    queryKey: ['ai', 'orphan-audit'],
    queryFn:  () => orphanAudit(),
    staleTime: 600_000,
  });
}
