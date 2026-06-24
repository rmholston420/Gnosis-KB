/**
 * LinkSuggestions — standalone panel for AI-suggested wikilinks.
 * Used in the inline editor toolbar when user wants on-demand link suggestions.
 *
 * The suggestLinks API call returns LinkSuggestResult = { suggestions: LinkSuggestion[] }.
 * We unwrap .suggestions before filtering/rendering.
 */
import React, { useState } from 'react';
import { Link2, Check, X, Loader2, Sparkles } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { suggestLinks } from '../../api/ai';
import type { LinkSuggestion, LinkSuggestResult } from '../../api/ai';

interface LinkSuggestionsProps {
  noteId:    string;
  /** Called when the user clicks "Insert" on a suggestion. */
  onInsert:  (suggestion: LinkSuggestion) => void;
  /** Called when the panel is dismissed. */
  onDismiss: () => void;
}

/**
 * Renders a scrollable list of AI-generated wikilink suggestions.
 * Each suggestion shows the target title, a reason, and accept/dismiss actions.
 */
export function LinkSuggestions({ noteId, onInsert, onDismiss }: LinkSuggestionsProps) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const { mutate, data: result, isPending } = useMutation<LinkSuggestResult, Error>({
    mutationFn: () => suggestLinks(noteId),
  });

  // Unwrap from { suggestions: [...] } envelope
  const allSuggestions: LinkSuggestion[] = result?.suggestions ?? [];
  const visible = allSuggestions.filter((s) => !dismissed.has(s.target_note_id));

  return (
    <div
      className="bg-gnosis-surface border border-gnosis-border rounded-lg shadow-xl w-80 overflow-hidden"
      role="dialog"
      aria-label="AI link suggestions"
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gnosis-border">
        <Sparkles size={13} className="text-gnosis-accent" />
        <span className="text-xs font-semibold text-gnosis-fg">Suggested Wikilinks</span>
        <button onClick={onDismiss} className="ml-auto text-gnosis-muted hover:text-gnosis-fg">
          <X size={13} />
        </button>
      </div>

      {/* Body */}
      <div className="p-3">
        {!result && !isPending && (
          <button
            onClick={() => mutate()}
            className="w-full text-xs text-gnosis-accent hover:underline flex items-center justify-center gap-1 py-2"
          >
            <Link2 size={11} /> Generate suggestions
          </button>
        )}

        {isPending && (
          <div className="flex items-center justify-center gap-2 py-4 text-gnosis-muted text-xs">
            <Loader2 size={13} className="animate-spin" /> Analyzing note…
          </div>
        )}

        {result && visible.length === 0 && (
          <p className="text-xs text-gnosis-muted text-center py-3">No more suggestions.</p>
        )}

        <ul className="space-y-2">
          {visible.map((s) => (
            <li
              key={s.target_note_id}
              className="flex items-start justify-between gap-2 bg-gnosis-bg rounded p-2"
            >
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gnosis-fg truncate">[[{s.target_title}]]</p>
                <p className="text-xs text-gnosis-muted leading-tight mt-0.5">{s.reason}</p>
                {s.score !== undefined && (
                  <div className="mt-1 h-1 rounded-full bg-gnosis-muted/20 overflow-hidden">
                    <div
                      className="h-full bg-gnosis-accent rounded-full"
                      style={{ width: `${Math.round(s.score * 100)}%` }}
                    />
                  </div>
                )}
              </div>
              <div className="flex flex-col gap-1 flex-shrink-0">
                <button
                  onClick={() => { onInsert(s); setDismissed((p) => new Set([...p, s.target_note_id])); }}
                  className="p-1 text-green-400 hover:text-green-300 transition-colors"
                  aria-label={`Insert link to ${s.target_title}`}
                >
                  <Check size={13} />
                </button>
                <button
                  onClick={() => setDismissed((p) => new Set([...p, s.target_note_id]))}
                  className="p-1 text-gnosis-muted hover:text-gnosis-fg transition-colors"
                  aria-label={`Dismiss suggestion for ${s.target_title}`}
                >
                  <X size={13} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
