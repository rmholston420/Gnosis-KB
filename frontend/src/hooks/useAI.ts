/**
 * hooks/useAI.ts — TanStack Query + Mutation hooks for AI features.
 */
import { useMutation, useQuery } from '@tanstack/react-query';
import { aiApi } from '../api/ai';
import type {
  SummarizeResult,
  CritiqueResult,
  LinkSuggestResult,
  TagSuggestResult,
} from '../api/ai';

// ── Note Summary ──────────────────────────────────────────────────────────────

/**
 * Returns a mutation so the caller can trigger summarisation on demand
 * via `mutate(noteId)` / `mutateAsync(noteId)`.
 */
export function useNoteSummary(noteId: string | null | undefined) {
  return useMutation({
    mutationFn: (id?: string) => aiApi.summarizeNote((id ?? noteId)!),
  });
}

// ── Note Critique ─────────────────────────────────────────────────────────────

export function useNoteCritique(noteId: string | null | undefined) {
  return useMutation({
    mutationFn: (id?: string): Promise<CritiqueResult> => aiApi.critiqueNote((id ?? noteId)!),
  });
}

// ── Link Suggestions ──────────────────────────────────────────────────────────

export function useLinkSuggestions(noteId: string | null | undefined) {
  return useQuery({
    queryKey: ['ai', 'link-suggestions', noteId],
    queryFn:  (): Promise<LinkSuggestResult> => aiApi.suggestLinks(noteId!),
    enabled:  Boolean(noteId),
  });
}

// ── Tag Suggestions ───────────────────────────────────────────────────────────

export function useTagSuggestions(noteId: string | null | undefined) {
  return useQuery({
    queryKey: ['ai', 'tag-suggestions', noteId],
    queryFn:  (): Promise<TagSuggestResult> => aiApi.suggestTags(noteId!),
    enabled:  Boolean(noteId),
  });
}

// ── Re-exports of result types for convenience ────────────────────────────────
export type { SummarizeResult, CritiqueResult, LinkSuggestResult, TagSuggestResult };
