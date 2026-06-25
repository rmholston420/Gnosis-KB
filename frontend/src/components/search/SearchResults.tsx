/**
 * SearchResults — renders a list of hybrid search results with highlighted excerpts.
 *
 * Props:
 *   results        – array of SearchResult objects
 *   query          – the current search string (used for highlighting)
 *   isLoading      – show skeleton loader
 *   isError        – show error state
 *   total          – optional result count
 *   onResultClick  – called with note_id when a card is clicked
 */
import React from 'react';
import { Tag, ArrowRight } from 'lucide-react';
import { NODE_COLORS } from '../../lib/graphUtils';
import type { SearchResult } from '../../types';

interface SearchResultsProps {
  results:        SearchResult[];
  query?:         string;
  isLoading?:     boolean;
  isError?:       boolean;
  total?:         number;
  onResultClick:  (noteId: string) => void;
}

function Highlight({ text, query }: { text: string; query?: string }) {
  if (!query?.trim()) return <>{text}</>;
  const re = new RegExp(
    `(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`,
    'gi',
  );
  const parts = text.split(re);
  return (
    <>
      {parts.map((part, i) =>
        re.test(part) ? (
          <mark key={i} className="bg-gnosis-accent/25 text-gnosis-fg rounded-sm px-0.5">
            {part}
          </mark>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        ),
      )}
    </>
  );
}

function ResultRow({
  result,
  query,
  onResultClick,
}: {
  result:        SearchResult;
  query?:        string;
  onResultClick: (noteId: string) => void;
}) {
  const typeColor =
    NODE_COLORS[result.note_type ?? 'default'] ?? NODE_COLORS['default'];

  return (
    <button
      onClick={() => onResultClick(result.note_id)}
      className="w-full text-left group flex gap-3 p-3 rounded-lg bg-gnosis-surface hover:bg-gnosis-hover border border-transparent hover:border-gnosis-border transition-all"
    >
      <span
        className="w-1 rounded-full flex-shrink-0 mt-1 self-stretch"
        style={{ background: typeColor }}
      />

      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-1">
          <h3 className="text-sm font-medium text-gnosis-fg group-hover:text-gnosis-accent transition-colors truncate">
            <Highlight text={result.title} query={query} />
          </h3>
          {result.score !== undefined && (
            <span className="text-xs text-gnosis-muted flex-shrink-0">
              {(result.score * 100).toFixed(0)}%
            </span>
          )}
        </div>

        {(result.snippet ?? result.excerpt) && (
          <p className="text-xs text-gnosis-muted leading-relaxed line-clamp-2">
            <Highlight text={result.snippet ?? result.excerpt!} query={query} />
          </p>
        )}

        <div className="flex items-center gap-3 mt-2 text-xs text-gnosis-muted">
          {result.folder && (
            <span className="truncate max-w-[120px]">{result.folder}</span>
          )}
          {result.tags && result.tags.length > 0 && (
            <span className="flex items-center gap-1">
              <Tag size={10} />
              {result.tags.slice(0, 2).join(', ')}
            </span>
          )}
        </div>
      </div>

      <ArrowRight
        size={14}
        className="text-gnosis-muted group-hover:text-gnosis-fg self-center flex-shrink-0 transition-colors"
      />
    </button>
  );
}

export function SearchResults({
  results,
  query,
  isLoading = false,
  isError = false,
  total,
  onResultClick,
}: SearchResultsProps) {
  const safeResults = Array.isArray(results) ? results : [];

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-20 rounded-lg bg-gnosis-surface animate-pulse" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg bg-red-900/20 border border-red-700/40 p-4 text-sm text-red-400">
        Search failed — is the API running?
      </div>
    );
  }

  if (safeResults.length === 0 && query?.trim()) {
    return (
      <div className="text-center py-12 text-gnosis-muted">
        <p className="text-sm">No results for “{query}”</p>
        <p className="text-xs mt-1">Try a different query or switch search mode.</p>
      </div>
    );
  }

  return (
    <div>
      {total !== undefined && total > 0 && (
        <p className="text-xs text-gnosis-muted mb-3">
          {total} result{total !== 1 ? 's' : ''}
        </p>
      )}
      <div className="space-y-1.5">
        {safeResults.map((r) => (
          <ResultRow
            key={r.note_id}
            result={r}
            query={query}
            onResultClick={onResultClick}
          />
        ))}
      </div>
    </div>
  );
}
