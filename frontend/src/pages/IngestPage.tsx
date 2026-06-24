import { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { Note } from '../types';
import { Upload, Link, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function IngestPage() {
  const [url, setUrl] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // ---- File upload --------------------------------------------------------
  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      const results: Note[] = [];
      for (const file of files) {
        const note = await api.ingestFile(file) as Note;
        results.push(note);
      }
      return results;
    },
    onSuccess: (notes: Note[]) => {
      setSuccess(`Uploaded ${notes.length} file(s) successfully.`);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setError(msg);
      setSuccess(null);
    },
  });

  // ---- URL ingest ---------------------------------------------------------
  const urlMutation = useMutation({
    mutationFn: () => api.ingestUrl(url) as Promise<Note>,
    onSuccess: (note: Note) => {
      setSuccess(`Ingested: ${note.title}`);
      setError(null);
      setUrl('');
      void queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'URL ingest failed';
      setError(msg);
      setSuccess(null);
    },
  });

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (acceptedFiles: File[]) => {
      setError(null);
      setSuccess(null);
      uploadMutation.mutate(acceptedFiles);
    },
    accept: {
      'text/plain':     ['.txt'],
      'text/markdown':  ['.md'],
      'application/pdf': ['.pdf'],
    },
    maxSize: 10 * 1024 * 1024, // 10 MB
  });

  const isLoading = uploadMutation.isPending || urlMutation.isPending;

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-xl font-semibold text-text-primary">Ingest Content</h1>

      {/* Feedback */}
      {error && (
        <div className="mb-4 rounded-lg bg-error-highlight border border-error px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-lg bg-success-highlight border border-success px-4 py-3 text-sm text-success">
          {success}
        </div>
      )}

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`mb-6 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 transition-colors ${
          isDragActive
            ? 'border-accent-teal bg-accent-teal/5'
            : 'border-border-default hover:border-accent-teal/50 hover:bg-bg-elevated'
        }`}
      >
        <input {...getInputProps()} />
        <Upload size={32} className={`mb-3 ${ isDragActive ? 'text-accent-teal' : 'text-text-faint' }`} />
        <p className="text-sm font-medium text-text-primary">
          {isDragActive ? 'Drop files here' : 'Drag & drop files, or click to browse'}
        </p>
        <p className="mt-1 text-xs text-text-muted">.txt, .md, .pdf \u00b7 max 10 MB each</p>
        {isLoading && (
          <div className="mt-4 flex items-center gap-2 text-xs text-text-muted">
            <Loader2 size={14} className="animate-spin" />
            Uploading\u2026
          </div>
        )}
      </div>

      {/* URL ingest */}
      <div className="rounded-xl border border-border-default bg-bg-secondary p-5">
        <h2 className="mb-3 text-sm font-medium text-text-primary">Ingest from URL</h2>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Link size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint" />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') urlMutation.mutate(); }}
              placeholder="https://example.com/article"
              className="w-full rounded-lg border border-border-default bg-bg-elevated py-2 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-faint focus:border-accent-teal focus:outline-none"
            />
          </div>
          <button
            onClick={() => urlMutation.mutate()}
            disabled={!url.trim() || isLoading}
            className="rounded-lg bg-accent-teal px-4 py-2 text-sm font-medium text-white hover:bg-accent-teal/80 disabled:opacity-50 transition-colors"
          >
            {urlMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : 'Ingest'}
          </button>
        </div>
      </div>

      {/* Recent ingests link */}
      <div className="mt-6 text-center">
        <button
          onClick={() => navigate('/notes')}
          className="text-xs text-text-muted hover:text-text-primary transition-colors"
        >
          View all notes \u2192
        </button>
      </div>
    </div>
  );
}
