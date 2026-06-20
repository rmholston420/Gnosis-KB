/**
 * SettingsPage
 * ============
 * Sections:
 *   1. AI Provider   — model picker + connection status
 *   2. RAG Mode      — hybrid / local / global radio
 *   3. Export        — vault export with format picker (markdown zip / JSON)
 *   4. Vault Sync    — trigger full resync + streamed progress log  [Slice 15]
 *   5. Security      — auth info
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Settings, Cpu, Database, Shield, Save, RefreshCw,
  Download, Archive, FileJson, FolderSync, CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import type { RagMode } from '../store/useAppStore';
import api from '../services/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const EMBED_PATTERNS = ['embed', 'nomic', 'mxbai', 'bge', 'e5', 'minilm'];
function isChatModel(name: string) {
  const lower = name.toLowerCase();
  return !EMBED_PATTERNS.some((p) => lower.includes(p));
}

const RAG_MODES: { value: RagMode; label: string; desc: string }[] = [
  { value: 'hybrid', label: 'Hybrid', desc: 'Vector + graph traversal (recommended)' },
  { value: 'local',  label: 'Local',  desc: 'Vector similarity only' },
  { value: 'global', label: 'Global', desc: 'Graph-wide community search' },
];

type ExportFormat = 'markdown' | 'json';

interface ProviderInfo {
  provider: string;
  model: string;
  available: boolean;
  models: string[];
}

// Vault sync states
type SyncState = 'idle' | 'running' | 'done' | 'error';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SettingsPage() {
  const { ragMode, setRagMode } = useAppStore();

  // AI Provider state
  const [provider, setProvider]             = useState<ProviderInfo | null>(null);
  const [selectedModel, setSelectedModel]   = useState('');
  const [saving, setSaving]                 = useState(false);
  const [saved, setSaved]                   = useState(false);
  const [error, setError]                   = useState('');

  // Export state
  const [exportFormat, setExportFormat]     = useState<ExportFormat>('markdown');
  const [exporting, setExporting]           = useState(false);
  const [exportError, setExportError]       = useState('');

  // Vault sync state
  const [syncState, setSyncState]           = useState<SyncState>('idle');
  const [syncLines, setSyncLines]           = useState<string[]>([]);
  const [syncError, setSyncError]           = useState('');
  const logEndRef                           = useRef<HTMLDivElement>(null);
  const eventSourceRef                      = useRef<EventSource | null>(null);

  useEffect(() => {
    api
      .getProviders()
      .then((data) => {
        const p = data as ProviderInfo;
        setProvider(p);
        setSelectedModel(p.model);
      })
      .catch(() => setError('Could not load provider info'));

    // Cleanup SSE on unmount
    return () => eventSourceRef.current?.close();
  }, []);

  // Auto-scroll log to bottom
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [syncLines]);

  async function handleModelSave() {
    if (!selectedModel || selectedModel === provider?.model) return;
    setSaving(true);
    setError('');
    try {
      await api.setModel(selectedModel);
      setProvider((prev) => prev ? { ...prev, model: selectedModel } : prev);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError('Failed to update model');
    } finally {
      setSaving(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    setExportError('');
    try {
      const token = localStorage.getItem('gnosis_token') ?? '';
      const res = await fetch(
        `/api/v1/export/?format=${exportFormat}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(typeof detail.detail === 'string' ? detail.detail : res.statusText);
      }

      const disposition = res.headers.get('Content-Disposition') ?? '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const ext   = exportFormat === 'json' ? 'json' : 'zip';
      const filename = match?.[1] ?? `gnosis-export-${new Date().toISOString().slice(0, 10)}.${ext}`;

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExporting(false);
    }
  }

  /** Open SSE stream to POST /vault/sync?stream=true and display log lines. */
  const handleVaultSync = useCallback(() => {
    if (syncState === 'running') return;

    // Close any previous stream
    eventSourceRef.current?.close();

    setSyncState('running');
    setSyncLines([]);
    setSyncError('');

    // EventSource can only do GET; we use a fetch-based SSE reader instead
    // so we can POST with the Authorization header.
    const token = localStorage.getItem('gnosis_token') ?? '';

    fetch('/api/v1/vault/sync?stream=true', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }).then(async (res) => {
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        const msg = typeof detail.detail === 'string' ? detail.detail : res.statusText;
        setSyncError(msg);
        setSyncState('error');
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        setSyncError('No response body');
        setSyncState('error');
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      async function pump() {
        const { done, value } = await reader!.read();
        if (done) {
          setSyncState('done');
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';
        for (const part of parts) {
          const line = part.replace(/^data:\s*/m, '').trim();
          if (!line) continue;
          if (line === '[done]') {
            setSyncState('done');
            return;
          }
          if (line.startsWith('[error]')) {
            setSyncError(line.replace('[error]', '').trim());
            setSyncState('error');
            return;
          }
          setSyncLines((prev) => [...prev, line]);
        }
        pump();
      }

      pump();
    }).catch((err: unknown) => {
      setSyncError(err instanceof Error ? err.message : 'Sync failed');
      setSyncState('error');
    });
  }, [syncState]);

  const chatModels = provider?.models.filter(isChatModel) ?? [];

  return (
    <div className="max-w-2xl mx-auto px-6 py-8 space-y-8">
      <div className="flex items-center gap-3">
        <Settings size={20} className="text-text-muted" />
        <h1 className="text-lg font-semibold text-text-primary">Settings</h1>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-2 rounded">
          {error}
        </div>
      )}

      {/* ── AI Provider ──────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-border">
          <Cpu size={14} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">AI Provider</h2>
          {provider && (
            <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${
              provider.available
                ? 'bg-green-500/15 text-green-400'
                : 'bg-red-500/15 text-red-400'
            }`}>
              {provider.available ? 'Connected' : 'Unavailable'}
            </span>
          )}
        </div>

        {provider ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-text-secondary">
              <span className="text-text-muted">Provider:</span>
              <span className="font-medium text-text-primary capitalize">{provider.provider}</span>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider">
                Active Model
              </label>
              <div className="flex gap-2">
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="flex-1 bg-bg-tertiary border border-border rounded px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-blue transition-colors"
                >
                  {chatModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <button
                  onClick={handleModelSave}
                  disabled={saving || selectedModel === provider.model}
                  className="flex items-center gap-1.5 px-3 py-2 bg-accent-blue hover:bg-blue-600 disabled:opacity-50 text-white text-sm rounded transition-colors"
                >
                  {saving ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
                  {saved ? 'Saved!' : 'Apply'}
                </button>
              </div>
              <p className="text-xs text-text-muted">
                {chatModels.length} chat models available · embedding models hidden
              </p>
            </div>
          </div>
        ) : (
          <div className="text-sm text-text-muted">Loading provider info…</div>
        )}
      </section>

      {/* ── RAG Mode ─────────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-border">
          <Database size={14} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">RAG Mode</h2>
        </div>

        <div className="space-y-2">
          {RAG_MODES.map(({ value, label, desc }) => (
            <label
              key={value}
              className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                ragMode === value
                  ? 'border-accent-blue bg-accent-blue/10'
                  : 'border-border hover:bg-bg-tertiary'
              }`}
            >
              <input
                type="radio"
                name="ragMode"
                value={value}
                checked={ragMode === value}
                onChange={() => setRagMode(value)}
                className="mt-0.5 accent-blue-500"
              />
              <div>
                <p className="text-sm font-medium text-text-primary">{label}</p>
                <p className="text-xs text-text-muted">{desc}</p>
              </div>
            </label>
          ))}
        </div>
      </section>

      {/* ── Export ───────────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-border">
          <Archive size={14} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">Export Vault</h2>
        </div>

        <p className="text-xs text-text-muted">
          Download all your notes as a zip archive of Markdown files, or as a
          single JSON file containing every note with full metadata.
        </p>

        {exportError && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs px-3 py-2 rounded">
            {exportError}
          </div>
        )}

        <div className="flex items-center gap-3 flex-wrap">
          {/* Format picker */}
          <div className="flex rounded border border-border overflow-hidden text-xs">
            <button
              onClick={() => setExportFormat('markdown')}
              className={`flex items-center gap-1.5 px-3 py-2 transition-colors ${
                exportFormat === 'markdown'
                  ? 'bg-accent-cyan/20 text-accent-cyan border-r border-border'
                  : 'text-text-muted hover:bg-bg-tertiary border-r border-border'
              }`}
            >
              <Archive size={12} /> Markdown (.zip)
            </button>
            <button
              onClick={() => setExportFormat('json')}
              className={`flex items-center gap-1.5 px-3 py-2 transition-colors ${
                exportFormat === 'json'
                  ? 'bg-accent-cyan/20 text-accent-cyan'
                  : 'text-text-muted hover:bg-bg-tertiary'
              }`}
            >
              <FileJson size={12} /> JSON
            </button>
          </div>

          {/* Download button */}
          <button
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center gap-2 px-4 py-2 bg-bg-elevated hover:bg-bg-tertiary border border-border rounded text-sm text-text-primary disabled:opacity-50 transition-colors"
          >
            {exporting
              ? <RefreshCw size={13} className="animate-spin text-text-muted" />
              : <Download size={13} className="text-text-muted" />}
            {exporting ? 'Preparing…' : 'Download'}
          </button>
        </div>

        <p className="text-xs text-text-faint">
          Export is scoped to your vault. Shared vaults you have read access to
          are not included.
        </p>
      </section>

      {/* ── Vault Sync (Slice 15) ───────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-border">
          <FolderSync size={14} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">Vault Sync</h2>
          {syncState === 'done' && (
            <CheckCircle2 size={14} className="ml-auto text-green-400" />
          )}
          {syncState === 'error' && (
            <AlertCircle size={14} className="ml-auto text-red-400" />
          )}
        </div>

        <p className="text-xs text-text-muted">
          Force a full resync of the vault filesystem into the database and
          vector store. Use this after adding notes directly to the
          <code className="text-xs bg-bg-tertiary px-1 py-0.5 rounded mx-1">vault/</code>
          directory, or after an import.
        </p>

        {syncError && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs px-3 py-2 rounded">
            {syncError}
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={handleVaultSync}
            disabled={syncState === 'running'}
            className="flex items-center gap-2 px-4 py-2 bg-bg-elevated hover:bg-bg-tertiary border border-border rounded text-sm text-text-primary disabled:opacity-50 transition-colors"
          >
            {syncState === 'running'
              ? <RefreshCw size={13} className="animate-spin text-accent-cyan" />
              : syncState === 'done'
                ? <CheckCircle2 size={13} className="text-green-400" />
                : <FolderSync size={13} className="text-text-muted" />}
            {syncState === 'running' ? 'Syncing…' : syncState === 'done' ? 'Sync complete' : 'Sync Now'}
          </button>

          {syncState !== 'idle' && (
            <button
              onClick={() => { setSyncState('idle'); setSyncLines([]); setSyncError(''); }}
              className="text-xs text-text-faint hover:text-text-muted transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        {/* Streaming log terminal */}
        {syncLines.length > 0 && (
          <div
            className="rounded border border-border bg-bg-tertiary font-mono text-xs text-text-secondary overflow-y-auto"
            style={{ maxHeight: '220px' }}
          >
            <div className="px-3 py-2 space-y-0.5">
              {syncLines.map((line, i) => {
                const isError   = line.startsWith('error:');
                const isSynced  = line.startsWith('synced:');
                const isSkipped = line.startsWith('skipped:') || line.startsWith('total:') || line.startsWith('done:');
                return (
                  <div
                    key={i}
                    className={`leading-5 ${
                      isError   ? 'text-red-400'
                      : isSynced  ? 'text-green-400'
                      : isSkipped ? 'text-text-faint'
                      : 'text-text-secondary'
                    }`}
                  >
                    {line}
                  </div>
                );
              })}
              <div ref={logEndRef} />
            </div>
          </div>
        )}
      </section>

      {/* ── Security ───────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-border">
          <Shield size={14} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">Security</h2>
        </div>
        <p className="text-sm text-text-muted">
          Authentication is JWT-based. Tokens expire after 24 hours. Change your
          password via the API at{' '}
          <code className="text-xs bg-bg-tertiary px-1.5 py-0.5 rounded">/api/v1/auth/change-password</code>.
        </p>
      </section>
    </div>
  );
}
