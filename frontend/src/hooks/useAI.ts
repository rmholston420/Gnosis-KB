/**
 * useAI — hooks for AI chat, link suggestions, tag suggestions, critiques.
 *
 * LINK SUGGESTIONS BINDING CONTRACT
 * ==================================
 * useLinkSuggestions calls `getLinkSuggestions` from api/ai.
 *
 *   useAI.test:      mocks `getLinkSuggestions` directly — body never runs.
 *   AiSidebar.test:  does NOT use useLinkSuggestions — LinkSection calls
 *                    suggestLinks directly via its own useQuery.
 *
 * See AiSidebar.tsx and api/ai.ts for the full explanation.
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
import type { AIChatMessage } from '../types';
import type { LinkSuggestion } from '../api/ai';
import type { ChatQueryResult, CritiqueResult } from '../api/ai';

/** RagMode is a subset of SearchMode — alias for clarity. */
export type RagMode = 'hybrid' | 'semantic' | 'keyword';

// ── Mutation-based chat ───────────────────────────────────────────────────────
export interface AIChatInput {
  query: string;
  mode?: RagMode;
}

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

// ── Streaming SSE chat session ────────────────────────────────────────────────
export function useAiChatStream(sessionId?: string) {
  const [messages, setMessages]  = useState<AIChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [ragMode, setRagMode]     = useState<RagMode>('hybrid');
  const esRef = useRef<EventSource | null>(null);

  const sendMessage = useCallback((text: string) => {
    const userMsg: AIChatMessage = { role: 'user', content: text };
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
            next[assistantIdx] = { ...existing, content: buffer, meta: { citations: chunk.citations } };
          } else {
            next.push({ role: 'assistant', content: buffer, meta: { citations: chunk.citations } });
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

export function useNoteSummary(noteId: string | null) {
  return useMutation({
    mutationFn: () => summarizeNote(noteId!),
  });
}

export function useLinkSuggestions(noteId: string | null) {
  return useQuery({
    queryKey: ['ai', 'suggest-links', noteId],
    queryFn: (): Promise<LinkSuggestion[]> => getLinkSuggestions(noteId!),
    enabled: !!noteId,
    staleTime: 300_000,
  });
}

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

export function useOrphanAudit() {
  return useQuery({
    queryKey: ['ai', 'orphan-audit'],
    queryFn:  () => orphanAudit(),
    staleTime: 600_000,
  });
}
