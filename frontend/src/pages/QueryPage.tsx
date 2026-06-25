/**
 * QueryPage — LightRAG / semantic query interface.
 *
 * Provides a streaming query UI backed by the LightRAG SSE endpoint.
 * Users can switch between hybrid, semantic, and keyword RAG modes.
 */
import React, { useState, useRef, useEffect } from 'react';
import api from '../services/api';
import type { SearchResult } from '../types';

type RagMode = 'hybrid' | 'semantic' | 'keyword';

const MODES: { label: string; value: RagMode }[] = [
  { label: 'Hybrid',   value: 'hybrid'   },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Keyword',  value: 'keyword'  },
];

interface QueryResult {
  answer:   string;
  sources:  SearchResult[];
  mode:     RagMode;
}

export default function QueryPage() {
  const [query,     setQuery]     = useState('');
  const [mode,      setMode]      = useState<RagMode>('hybrid');
  const [streaming, setStreaming] = useState(false);
  const [answer,    setAnswer]    = useState('');
  const [sources,   setSources]   = useState<SearchResult[]>([]);
  const [history,   setHistory]   = useState<QueryResult[]>([]);
  const [error,     setError]     = useState<string | null>(null);
  const esRef   = useRef<EventSource | null>(null);
  const answerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (answerRef.current) {
      answerRef.current.scrollTop = answerRef.current.scrollHeight;
    }
  }, [answer]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    setAnswer('');
    setSources([]);
    setError(null);
    setStreaming(true);
    esRef.current?.close();

    const stop = api.streamQuery(
      q,
      (token) => setAnswer((prev) => prev + token),
      () => {
        setStreaming(false);
        setHistory((prev) => [
          { answer, sources, mode },
          ...prev.slice(0, 9),
        ]);
      },
    );

    esRef.current = null;
    void stop; // streamQuery returns cleanup; close handled by onDone
  }

  function handleStop() {
    esRef.current?.close();
    setStreaming(false);
  }

  // Fetch context sources alongside the stream
  useEffect(() => {
    const q = query.trim();
    if (!streaming || !q) return;
    api.search(q, mode, { limit: 5 })
      .then((res) => setSources((res.items ?? []) as unknown as SearchResult[]))
      .catch(() => { /* non-fatal */ });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streaming]);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <h1 className="text-lg font-semibold text-gnosis-fg">RAG Query</h1>

      {/* Input form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question about your notes…"
          disabled={streaming}
          className="flex-1 px-3 py-2 rounded-md bg-gnosis-bg border border-gnosis-border
                     text-gnosis-fg text-sm focus:outline-none focus:ring-2 focus:ring-gnosis-accent
                     disabled:opacity-50"
        />
        {streaming ? (
          <button
            type="button"
            onClick={handleStop}
            className="px-4 py-2 rounded-md bg-red-500 text-white text-sm font-medium
                       hover:bg-red-600 transition-colors"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            className="px-4 py-2 rounded-md bg-gnosis-accent text-white text-sm font-medium
                       hover:opacity-90 transition-opacity"
          >
            Ask
          </button>
        )}
      </form>

      {/* Mode selector */}
      <div className="flex gap-1">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            onClick={() => setMode(m.value)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors
              ${
                mode === m.value
                  ? 'bg-gnosis-accent text-white'
                  : 'bg-gnosis-surface text-gnosis-muted hover:text-gnosis-fg'
              }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <p role="alert" className="text-sm text-red-500">{error}</p>
      )}

      {/* Streaming answer */}
      {(answer || streaming) && (
        <div
          ref={answerRef}
          className="p-4 rounded-lg bg-gnosis-surface border border-gnosis-border
                     text-sm text-gnosis-fg whitespace-pre-wrap max-h-80 overflow-y-auto"
        >
          {answer}
          {streaming && <span className="animate-pulse ml-1">|█</span>}
        </div>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold text-gnosis-muted uppercase tracking-wide mb-2">
            Sources
          </h2>
          <ul className="space-y-1">
            {sources.map((s: SearchResult) => (
              <li key={s.note_id}>
                <a
                  href={`/notes/${s.note_id}`}
                  className="block px-3 py-2 rounded bg-gnosis-surface border border-gnosis-border
                             hover:border-gnosis-accent text-xs transition-colors"
                >
                  <span className="font-medium text-gnosis-fg">{s.title}</span>
                  {s.score != null && (
                    <span className="ml-2 text-gnosis-muted">{s.score.toFixed(2)}</span>
                  )}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* History */}
      {history.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold text-gnosis-muted uppercase tracking-wide mb-2">
            Recent Queries
          </h2>
          <ul className="space-y-2">
            {history.map((h: QueryResult, i: number) => (
              <li
                key={i}
                className="px-3 py-2 rounded bg-gnosis-surface border border-gnosis-border text-xs"
              >
                <p className="text-gnosis-muted">{h.mode}</p>
                <p className="text-gnosis-fg line-clamp-2">{h.answer}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
