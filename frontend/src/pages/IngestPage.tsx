import { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { Note } from '../types';
import { Upload, Link, Loader2, CheckCircle2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function IngestPage() {
  const [url, setUrl] = useState('');
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const fileMutation = useMutation({
    mutationFn: (file: File) => api.ingestFile(file) as Promise<Note>,
    onSuccess: (note: Note) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      navigate(`/notes/${note.id}`);
    },
  });

  const urlMutation = useMutation({
    mutationFn: (u: string) => api.ingestUrl(u) as Promise<Note>,
    onSuccess: (note: Note) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      navigate(`/notes/${note.id}`);
    },
  });

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
    },
    onDrop: (files) => files[0] && fileMutation.mutate(files[0]),
  });

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-lg font-semibold text-text-primary mb-6">Ingest Documents</h1>

      {/* File drop */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors mb-6 ${
          isDragActive ? 'border-accent-blue bg-accent-blue/5' : 'border-border hover:border-border-muted'
        }`}
      >
        <input {...getInputProps()} />
        {fileMutation.isPending ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="animate-spin text-text-muted" size={32} />
            <p className="text-sm text-text-muted">Processing...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload size={32} className="text-text-muted" />
            <p className="text-sm text-text-primary">Drop PDF, DOCX, PPTX, XLSX, or images</p>
            <p className="text-xs text-text-muted">Or click to select a file</p>
          </div>
        )}
      </div>

      {/* URL ingest */}
      <div className="border border-border rounded-lg p-4">
        <h2 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
          <Link size={14} /> Ingest from URL
        </h2>
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://..."
            className="flex-1 bg-bg-tertiary border border-border rounded px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-blue"
          />
          <button
            onClick={() => url && urlMutation.mutate(url)}
            disabled={!url || urlMutation.isPending}
            className="px-4 py-2 bg-accent-blue hover:bg-blue-600 disabled:opacity-50 text-white text-sm rounded transition-colors"
          >
            {urlMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : 'Ingest'}
          </button>
        </div>
      </div>
    </div>
  );
}
