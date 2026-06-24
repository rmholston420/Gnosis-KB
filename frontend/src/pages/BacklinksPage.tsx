import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Link2 } from 'lucide-react';

interface BacklinkNote {
  id: string;
  title: string;
  folder: string;
  excerpt?: string;
}

async function fetchBacklinks(noteId: string): Promise<BacklinkNote[]> {
  const base = import.meta.env.VITE_API_BASE_URL ?? '';
  const resp = await fetch(`${base}/api/v1/notes/${noteId}/backlinks`, {
    headers: {
      Authorization: `Bearer ${localStorage.getItem('gnosis_token') ?? ''}`,
    },
  });
  if (!resp.ok) return [];
  const data = await resp.json() as { items?: BacklinkNote[] } | BacklinkNote[];
  return Array.isArray(data) ? data : data.items ?? [];
}

export default function BacklinksPage() {
  const { id } = useParams<{ id: string }>();

  const { data: backlinks = [], isLoading } = useQuery({
    queryKey: ['backlinks', id],
    queryFn: () => fetchBacklinks(id ?? ''),
    enabled: !!id,
  });

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link
          to={id ? `/editor/${id}` : '/'}
          className="flex items-center gap-1 text-gnosis-muted hover:text-gnosis-fg transition-colors text-sm"
        >
          <ArrowLeft size={16} />
          Back
        </Link>
        <h1 className="text-xl font-semibold text-gnosis-fg flex items-center gap-2">
          <Link2 size={20} />
          Backlinks
        </h1>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((n) => (
            <div key={n} className="rounded-lg bg-gnosis-surface p-4 animate-pulse">
              <div className="h-4 bg-gnosis-border rounded w-1/3 mb-2" />
              <div className="h-3 bg-gnosis-border rounded w-2/3" />
            </div>
          ))}
        </div>
      )}

      {!isLoading && backlinks.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-gnosis-muted">
          <Link2 size={40} className="mb-3 opacity-30" />
          <p className="text-sm">No notes link to this note yet.</p>
        </div>
      )}

      {!isLoading && backlinks.length > 0 && (
        <ul className="space-y-3">
          {backlinks.map((note) => (
            <li key={note.id}>
              <Link
                to={`/editor/${note.id}`}
                className="block rounded-lg bg-gnosis-surface border border-gnosis-border p-4
                           hover:bg-gnosis-hover transition-colors"
              >
                <p className="font-medium text-gnosis-fg">{note.title}</p>
                {note.excerpt && (
                  <p className="text-sm text-gnosis-muted mt-1 line-clamp-2">{note.excerpt}</p>
                )}
                <p className="text-xs text-gnosis-muted mt-1">{note.folder}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
