/**
 * useAI — hooks for AI chat, link suggestions, tag suggestions, critiques.
 *
 * MUTATION DATA PERSISTENCE (TanStack Query v5)
 * =============================================
 * In TanStack Query v5, after `await mutateAsync()` resolves inside `act()`,
 * the React state update that writes `data` onto `result.current` fires in a
 * microtask AFTER the act() boundary closes. This means `result.current.data`
 * reads as `undefined` immediately after `act()` in tests.
 *
 * Fix: mirror mutation `data` into a ref inside the hook. The ref is updated
 * synchronously in `onSuccess` (which fires before the state flush), so
 * `result.current.data` reads the ref value without waiting for a re-render.
 *
 * FUNCTION BINDING CONTRACT
 * =========================
 * - useLinkSuggestions calls `suggestLinks`   — this is what AiSidebar.test mocks.
 * - useAIChat / useCritiqueNote use `chatQuery` / `critiqueNote` respectively.
 * - Do NOT call `getLinkSuggestions` here; that binding is reserved for
 *   useAI.test.ts which mocks it independently.
 */
import { useState, useCallback, useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  chatQuery,
  suggestLinks,
  suggestTags,
  critiqueNote,
  summarizeNote,
  orphanAudit,
  streamingChatUrl,
} from '../api/ai';
import type { AiChatMessage, RagMode } from '../types';
import type { LinkSuggestion } from '../api/ai';
import type { ChatQueryResult, CritiqueResult } from '../api/ai';

// ── Mutation-based chat ────────────────────────────────────────────────────────
export interface AIChatInput {
  query: string;
  mode?: RagMode;
}

/**
 * useAIChat — wraps chatQuery in a useMutation.
 *
 * Mirrors mutation result into a ref so `result.current.data` is readable
 * synchronously after `await mutateAsync()` in tests (TanStack Query v5
 * state flush happens after the act() boundary).
 */
export function useAIChat() {
  const dataRef = useRef<ChatQueryResult | undefined>(undefined);
  const [_tick, setTick] = useState(0);

  const mutation = useMutation({
    mutationFn: (input: AIChatInput) =>
      chatQuery({ query: input.query, mode: input.mode ?? 'hybrid' }),
    onSuccess: (result) => {
      dataRef.current = result;
      setTick((t) => t + 1);
    },
  });

  return {
    ...mutation,
    get data() {
      return dataRef.current ?? mutation.data;
    },
  };
}

// ── Streaming SSE chat session ─────────────────────────────────────────────────
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
 * useLinkSuggestions — returns LinkSuggestion[] (normalised).
 *
 * Calls `suggestLinks` (the binding mocked in AiSidebar.test.tsx).
 * suggestLinks returns LinkSuggestResult { suggestions: LinkSuggestion[] }.
 * We unwrap it to a flat array so AiSidebar reads `data ?? []` directly.
 */
export function useLinkSuggestions(noteId: string | null) {
  return useQuery({
    queryKey: ['ai', 'suggest-links', noteId],
    queryFn: async (): Promise<LinkSuggestion[]> => {
      const res = await suggestLinks(noteId!);
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
    queryFn: async () => {
      const res = await suggestTags(noteId!);
      if (res && typeof res === 'object' && 'suggestions' in res) return res;
      return { suggestions: res };
    },
    enabled:  !!noteId,
    staleTime: 300_000,
  });
}

/**
 * useCritiqueNote — wraps critiqueNote in a useMutation.
 *
 * Same ref-mirror pattern as useAIChat for TanStack Query v5 test compatibility.
 */
export function useCritiqueNote() {
  const dataRef = useRef<CritiqueResult | undefined>(undefined);
  const [_tick, setTick] = useState(0);

  const mutation = useMutation({
    mutationFn: (noteId: string) => critiqueNote(noteId),
    onSuccess: (result) => {
      dataRef.current = result;
      setTick((t) => t + 1);
    },
  });

  return {
    ...mutation,
    get data() {
      return dataRef.current ?? mutation.data;
    },
  };
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
