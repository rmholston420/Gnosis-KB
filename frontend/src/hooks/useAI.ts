/**
 * useAI hooks — TanStack Query + streaming mutations for all AI features.
 *
 * Both canonical names and test-expected aliases are exported.
 */
import { useMutation, useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { ChatMessage } from '../types';
import { useAppStore } from '../store/useAppStore';

// ─────────────────────────────────────────────────────────────────────────────
// Chat / RAG query
// ─────────────────────────────────────────────────────────────────────────────

export interface AiChatArgs {
  query:      string;
  mode?:      'hybrid' | 'local' | 'global';
  sessionId?: string;
}

export interface AiChatResult {
  answer:    string;
  sources:   Array<{ note_id: string; title: string; score?: number }>;
  sessionId: string;
}

/** Send a chat/RAG query and return the full response. */
export function useAiChat() {
  const appendMsg  = useAppStore((s) => s.appendChatMessage);
  const updateLast = useAppStore((s) => s.updateLastAssistantMessage);
  const setSession = useAppStore((s) => s.setSessionId);

  return useMutation<AiChatResult, Error, AiChatArgs>({
    mutationFn: async (args) => {
      const userMsg: ChatMessage = { role: 'user', content: args.query };
      appendMsg(userMsg);
      appendMsg({ role: 'assistant', content: '' });

      const { answer, sources, session_id } = await api.chat(
        args.query,
        args.mode,
        args.sessionId,
      ) as { answer: string; sources: AiChatResult['sources']; session_id: string };

      updateLast(answer);
      setSession(session_id);
      return { answer, sources, sessionId: session_id };
    },
  });
}

/** Canonical alias kept for backward compat. */
export const useAIChat = useAiChat;

// ─────────────────────────────────────────────────────────────────────────────
// Note critique
// ─────────────────────────────────────────────────────────────────────────────

export interface CritiqueResult {
  critique:    string;
  suggestions: string[];
  score?:      number;
}

/** Fetch a critique / suggestions for a note. Canonical name: useNoteCritique. */
export function useNoteCritique(noteId: string) {
  return useQuery<CritiqueResult>({
    queryKey: ['critique', noteId],
    queryFn:  () => api.critiqueNote(noteId) as Promise<CritiqueResult>,
    enabled:  !!noteId,
  });
}

/** Alias expected by unit tests. */
export const useCritiqueNote = useNoteCritique;

// ─────────────────────────────────────────────────────────────────────────────
// Note summarise
// ─────────────────────────────────────────────────────────────────────────────

export interface SummarizeResult {
  summary:  string;
  keywords: string[];
}

export function useNoteSummary(noteId: string) {
  return useQuery<SummarizeResult>({
    queryKey: ['summary', noteId],
    queryFn:  () => api.summarizeNote(noteId) as Promise<SummarizeResult>,
    enabled:  !!noteId,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Link suggestions
// ─────────────────────────────────────────────────────────────────────────────

export interface LinkSuggestion {
  note_id: string;
  title:   string;
  reason:  string;
  score:   number;
}

export function useLinkSuggestions(noteId: string) {
  return useQuery<LinkSuggestion[]>({
    queryKey: ['links', noteId],
    queryFn:  () => api.suggestLinks(noteId) as Promise<LinkSuggestion[]>,
    enabled:  !!noteId,
  });
}
