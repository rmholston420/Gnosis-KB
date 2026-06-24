/**
 * IngestPage — import files and URLs into the vault.
 */
import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import api from '../services/api';

type IngestMode = 'file' | 'url';

export default function IngestPage() {
  const [mode, setMode]   = useState<IngestMode>('file');
  const [value, setValue] = useState('');
  const [noteType, setNoteType] = useState('permanent');

  const fileMutation = useMutation({
    mutationFn: () => api.ingestFile({ file_path: value, note_type: noteType }),
  });

  const urlMutation = useMutation({
    mutationFn: () => api.ingestUrl({ url: value, note_type: noteType }),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    if (mode === 'file') fileMutation.mutate();
    else urlMutation.mutate();
  };

  const isPending = fileMutation.isPending || urlMutation.isPending;
  const isSuccess = fileMutation.isSuccess || urlMutation.isSuccess;
  const jobId =
    (fileMutation.data as { job_id?: string } | undefined)?.job_id ??
    (urlMutation.data  as { job_id?: string } | undefined)?.job_id;

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gnosis-fg mb-6">Ingest Content</h1>

      {/* Mode toggle */}
      <div className="flex gap-1 mb-4">
        {(['file', 'url'] as IngestMode[]).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); setValue(''); }}
            className={[
              'px-3 py-1 rounded-md text-sm font-medium transition-colors',
              mode === m
                ? 'bg-gnosis-accent text-white'
                : 'bg-gnosis-surface border border-gnosis-border text-gnosis-muted hover:bg-gnosis-hover',
            ].join(' ')}
          >
            {m === 'file' ? 'File path' : 'URL'}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type={mode === 'url' ? 'url' : 'text'}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={mode === 'file' ? '/path/to/note.md' : 'https://example.com/article'}
          className="w-full rounded-lg border border-gnosis-border bg-gnosis-surface px-3 py-2 text-sm text-gnosis-fg focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
        />

        <select
          value={noteType}
          onChange={(e) => setNoteType(e.target.value)}
          className="w-full rounded-lg border border-gnosis-border bg-gnosis-surface px-3 py-2 text-sm text-gnosis-fg"
        >
          {['permanent','fleeting','project','area','resource','journal','moc','literature'].map((t) => (
            <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
          ))}
        </select>

        <button
          type="submit"
          disabled={isPending || !value.trim()}
          className="w-full py-2 rounded-lg bg-gnosis-accent text-white text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          {isPending ? 'Ingesting…' : 'Ingest'}
        </button>
      </form>

      {isSuccess && jobId && (
        <p className="mt-4 text-sm text-gnosis-muted">
          ✓ Job queued — ID: <code className="font-mono text-gnosis-fg">{jobId}</code>
        </p>
      )}
    </div>
  );
}
