/**
 * BacklinksPage — vault-wide backlink explorer.
 * Lists notes with the most incoming links and lets the user
 * browse the graph of connections for any note.
 */
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import api from '../services/api';
import type { Note, LinkRef } from '../types';

export default function BacklinksPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Load all notes sorted by incoming link count
  const { data: notes, isLoading } = useQuery({
    queryKey: ['notes', 'backlinks-overview'],
    queryFn:  () =>
      api.listNotes({ page_size: 500 })
        .then((r) => (r.items ?? []) as unknown as Note[])
        .then((items) =>
          [...items].sort(
            (a, b) => (b.incoming_link_count ?? 0) - (a.incoming_link_count ?? 0),
          ),
        ),
    staleTime: 60_000,
  });

  // Load selected note (with incoming_links)
  const { data: detail } = useQuery({
    queryKey: ['note', selectedId],
    queryFn:  () => api.getNote(selectedId!) as unknown as Promise<Note>,
    enabled:  !!selectedId,
    staleTime: 30_000,
  });

  const backlinks: LinkRef[] = (detail?.incoming_links ?? []) as LinkRef[];

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-lg font-semibold text-gnosis-fg mb-6">Backlinks Explorer</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left: top linked notes */}
        <section>
          <h2 className="text-sm font-semibold text-gnosis-muted uppercase tracking-wide mb-3">
            Most Referenced
          </h2>
          {isLoading && (
            <p className="text-xs text-gnosis-muted animate-pulse">Loading…</p>
          )}
          <ul className="space-y-1">
            {(notes ?? []).slice(0, 30).map((n: Note) => (
              <li key={n.note_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(n.note_id)}
                  className={`w-full text-left px-3 py-2 rounded text-xs transition-colors
                    ${
                      selectedId === n.note_id
                        ? 'bg-gnosis-accent/20 text-gnosis-accent'
                        : 'text-gnosis-fg hover:bg-gnosis-border'
                    }`}
                >
                  <span className="font-medium">{n.title}</span>
                  {(n.incoming_link_count ?? 0) > 0 && (
                    <span className="ml-2 text-gnosis-muted">
                      ← {n.incoming_link_count}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>

        {/* Right: backlinks for selected note */}
        <section>
          {selectedId && detail ? (
            <>
              <h2 className="text-sm font-semibold text-gnosis-muted uppercase tracking-wide mb-3">
                Links into “{detail.title}”
              </h2>
              {backlinks.length === 0 ? (
                <p className="text-xs text-gnosis-muted">No backlinks found.</p>
              ) : (
                <ul className="space-y-2">
                  {backlinks.map((bl: LinkRef) => (
                    <li key={bl.note_id}>
                      <Link
                        to={`/notes/${bl.note_id}`}
                        className="block px-3 py-2 rounded bg-gnosis-surface border border-gnosis-border
                                   hover:border-gnosis-accent text-xs transition-colors"
                      >
                        <span className="font-medium text-gnosis-fg">{bl.title}</span>
                        {bl.excerpt && (
                          <span className="block text-gnosis-muted mt-0.5 line-clamp-2">
                            {bl.excerpt}
                          </span>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-xs text-gnosis-muted">
              Select a note on the left to see its backlinks.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
