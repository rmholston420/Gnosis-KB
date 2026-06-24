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

    // Cleanup SSE on unmount — copy ref to local var so the closure
    // captures the current value at effect-run time, not cleanup time.
    const es = eventSourceRef.current;
    return () => es?.close();
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
      const blob = await (api as unknown as {
        exportVault: (fmt: ExportFormat) => Promise<Blob>;
      }).exportVault(exportFormat);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = exportFormat === 'markdown' ? 'gnosis-vault.zip' : 'gnosis-vault.json';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setExportError('Export failed. Try again.');
    } finally {
      setExporting(false);
    }
  }

  const handleVaultSync = useCallback(() => {
    setSyncState('running');
    setSyncLines([]);
    setSyncError('');

    eventSourceRef.current?.close();
    const token = localStorage.getItem('gnosis_token') ?? '';
    const base  = import.meta.env.VITE_API_BASE_URL ?? '';
    const url   = `${base}/api/v1/vault/sync/stream?token=${encodeURIComponent(token)}`;
    const es    = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (ev: MessageEvent) => {
      const line = ev.data as string;
      if (line === '[DONE]') {
        es.close();
        setSyncState('done');
        return;
      }
      setSyncLines((prev) => [...prev, line]);
    };

    es.onerror = () => {
      es.close();
      setSyncState('error');
      setSyncError('Sync stream disconnected. Check server logs.');
    };
  }, []);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-8 max-w-2xl">

      {/* ── Page header ────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2">
        <Settings size={16} className="text-text-muted" />
        <h1 className="text-base font-semibold text-text-primary">Settings</h1>
      </div>

      {/* ── AI Provider ────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-border">
          <Cpu size={14} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">AI Provider</h2>
          {provider?.available && (
            <span className="ml-auto flex items-center gap-1 text-xs text-green-400">
              <CheckCircle2 size={12} /> Connected
            </span>
          )}
          {provider && !provider.available && (
            <span className="ml-auto flex items-center gap-1 text-xs text-red-400">
              <AlertCircle size={12} /> Unavailable
            </span>
          )}
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs px-3 py-2 rounded">
            {error}
          </div>
        )}

        {provider && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <span className="text-text-muted">Provider</span>
              <span className="text-text-primary capitalize">{provider.provider}</span>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-text-muted" htmlFor="model-select">
                Active model
              </label>
              <select
                id="model-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full rounded bg-bg-elevated border border-border text-sm px-3 py-1.5 text-text-primary focus:outline-none"
              >
                {provider.models.filter(isChatModel).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <button
              onClick={() => void handleModelSave()}
              disabled={saving || selectedModel === provider.model}
              className="flex items-center gap-2 px-3 py-1.5 rounded bg-accent-teal/10 text-accent-teal text-xs hover:bg-accent-teal/20 disabled:opacity-40 transition-colors"
            >
              {saving ? <RefreshCw size={12} className="animate-spin" /> : <Save size={12} />}
              {saved ? 'Saved!' : 'Save model'}
            </button>
          </div>
        )}

        {!provider && !error && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <RefreshCw size={12} className="animate-spin" /> Loading provider info…
          </div>
        )}
      </section>

      {/* ── RAG Mode ───────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-border">
          <Database size={14} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">RAG Mode</h2>
        </div>
        <div className="space-y-2">
          {RAG_MODES.map(({ value, label, desc }) => (
            <label
              key={value}
              className="flex items-start gap-3 rounded-lg border border-border p-3 cursor-pointer hover:bg-bg-elevated transition-colors"
            >
              <input
                type="radio"
                name="rag-mode"
                value={value}
                checked={ragMode === value}
                onChange={() => setRagMode(value)}
                className="mt-0.5"
              />
              <div>
                <div className="text-sm font-medium text-text-primary">{label}</div>
                <div className="text-xs text-text-muted">{desc}</div>
              </div>
            </label>
          ))}
        </div>
      </section>

      {/* ── Export ─────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-border">
          <Download size={14} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">Export Vault</h2>
        </div>

        {exportError && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs px-3 py-2 rounded">
            {exportError}
          </div>
        )}

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="export-format"
              value="markdown"
              checked={exportFormat === 'markdown'}
              onChange={() => setExportFormat('markdown')}
            />
            <Archive size={13} className="text-text-muted" />
            <span className="text-sm text-text-primary">Markdown ZIP</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="export-format"
              value="json"
              checked={exportFormat === 'json'}
              onChange={() => setExportFormat('json')}
            />
            <FileJson size={13} className="text-text-muted" />
            <span className="text-sm text-text-primary">JSON</span>
          </label>
        </div>

        <button
          onClick={() => void handleExport()}
          disabled={exporting}
          className="flex items-center gap-2 px-4 py-2 bg-bg-elevated hover:bg-bg-tertiary border border-border rounded text-sm text-text-primary disabled:opacity-50 transition-colors"
        >
          {exporting
            ? <RefreshCw size={13} className="animate-spin text-accent-cyan" />
            : <Download size={13} className="text-text-muted" />}
          {exporting ? 'Exporting…' : 'Download export'}
        </button>

        <p className="text-xs text-text-faint">
          Exports all notes in the active vault. Attachments and binary files
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
