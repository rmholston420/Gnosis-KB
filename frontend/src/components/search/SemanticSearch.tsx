/**
 * SemanticSearch — dedicated UI for pure vector search with similar-notes feature.
 */
import React, { useState } from 'react';
import { Search, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useSemanticSearch, useSimilarNotes } from '../../hooks/useSearch';
import { SearchResults } from './SearchResults';

interface SemanticSearchProps {
  /** Optional: pre-seed with a note ID to find similar notes. */
  seedNoteId?: string | null;
}

/**
 * Semantic search UI. When `seedNoteId` is provided it also renders
 * a "Similar Notes" section fetched by embedding similarity.
 */
export function SemanticSearch({ seedNoteId }: SemanticSearchProps) {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  const { data, isLoading, isError } = useSemanticSearch(query);
  // useSimilarNotes only accepts a single noteId argument
  const { data: similar = [] } = useSimilarNotes(seedNoteId ?? null);

  const handleResultClick = (noteId: string) => navigate(`/notes/${noteId}`);

  return (
    <div className="space-y-6" data-testid="semantic-search">
      {/* Query input */}
      <div className="relative">
        <Sparkles
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gnosis-accent"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Describe what you\u2019re looking for\u2026"
          className="w-full pl-9 pr-4 py-2 text-sm bg-gnosis-surface border border-gnosis-border rounded-lg text-gnosis-fg placeholder-gnosis-muted focus:outline-none focus:ring-1 focus:ring-gnosis-accent"
          aria-label="Semantic search query"
        />
      </div>

      {/* Semantic search results */}
      {query.trim() && (
        <section>
          <h2 className="text-xs font-semibold text-gnosis-muted uppercase tracking-wide mb-2 flex items-center gap-1">
            <Search size={11} /> Semantic results
          </h2>
          <SearchResults
            results={data?.items ?? []}
            query={query}
            isLoading={isLoading}
            isError={isError}
            total={data?.total}
            onResultClick={handleResultClick}
          />
        </section>
      )}

      {/* Similar notes (when seed note ID is provided) */}
      {similar.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold text-gnosis-muted uppercase tracking-wide mb-2 flex items-center gap-1">
            <Sparkles size={11} /> Similar notes
          </h2>
          <SearchResults
            results={similar}
            isLoading={false}
            isError={false}
            onResultClick={handleResultClick}
          />
        </section>
      )}
    </div>
  );
}
