import React, { useEffect, useState } from 'react';
import {
  Settings,
  CircleCheck,
  Radio,
  Shield,
  Download,
  RefreshCw,
  XCircle,
  Loader2,
} from 'lucide-react';
import api, { type ProviderInfo } from '../services/api';
import { useAppStore, type RagMode } from '../store/useAppStore';

const RAG_MODES: Array<{ value: RagMode; label: string; description: string }> = [
  {
    value: 'hybrid',
    label: 'Hybrid',
    description: 'Vector + graph traversal (recommended) — uses local embeddings first, then graph neighbors for context expansion.',
  },
  {
    value: 'local',
    label: 'Local',
    description: 'Vector similarity only — fastest path for tight, semantically-similar note retrieval.',
  },
  {
    value: 'global',
    label: 'Global',
    description: 'Graph-wide community search — best for discovery across distant areas of the vault graph.',
  },
];

function SectionHeader({ icon, title, status }: { icon: React.ReactNode; title: string; status?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 pb-2 border-b border-border">
      {icon}
      <h2 className="text-sm font-semibold text-text-primary">{title}</h2>
      {status ? <span className="ml-auto">{status}</span> : null}
    </div>
  );
}

export default function SettingsPage() {
  const { ragMode, setRagMode } = useAppStore();

  const [providerInfo, setProviderInfo] = useState<ProviderInfo | null>(null);
  const [providerLoading, setProviderLoading] = useState(true);
  const [providerError, setProviderError]   = useState(false);
  const [selectedModel, setSelectedModel]   = useState('');
  const [saveState, setSaveState]           = useState<'idle' | 'saving' | 'saved'>('idle');

  const [exportFormat, setExportFormat]     = useState<'markdown' | 'json'>('markdown');
  const [exporting, setExporting]           = useState(false);
  const [exportError, setExportError]       = useState('');

  const [syncing, setSyncing]               = useState(false);
  const [syncStatus, setSyncStatus]         = useState<'idle' | 'active' | 'error'>('idle');

  // Load provider info
  useEffect(() => {
    let mounted = true;
    setProviderLoading(true);
    setProviderError(false);
    api.getProviders()
      .then((data) => {
        if (!mounted) return;
        setProviderInfo(data);
        setSelectedModel(data?.model ?? '');
      })
      .catch(() => { if (mounted) setProviderError(true); })
      .finally(() => { if (mounted) setProviderLoading(false); });
    return () => { mounted = false; };
  }, []);

  const handleSaveModel = async () => {
    if (!providerInfo || selectedModel === providerInfo.model) return;
    setSaveState('saving');
    try {
      await api.setModel(selectedModel);
      setProviderInfo((prev) => prev ? { ...prev, model: selectedModel } : prev);
      setSaveState('saved');
      window.setTimeout(() => setSaveState('idle'), 1400);
    } catch {
      setSaveState('idle');
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setExportError('');
    try {
      const blob = await api.exportVault(exportFormat);
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
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.syncObsidian();
      setSyncStatus('idle');
    } catch {
      setSyncStatus('error');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-8 max-w-2xl">
      <div className="flex items-center gap-2">
        <Settings size={16} className="text-text-muted" />
        <h1 className="text-base font-semibold text-text-primary">Settings</h1>
      </div>

      {/* Provider Section */}
      <section className="space-y-4">
        <SectionHeader
          icon={<Radio size={14} className="text-text-muted" />}
          title="AI Provider"
          status={
            !providerLoading && providerInfo
              ? providerInfo.available
                ? <span className="flex items-center gap-1 text-xs text-green-400"><CircleCheck size={12} /> Connected</span>
                : <span className="text-xs text-red-400">Unavailable</span>
              : null
          }
        />

        {providerLoading && (
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <Loader2 size={14} className="animate-spin" />
            <span>Loading provider info…</span>
          </div>
        )}

        {providerError && !providerLoading && (
          <div className="flex items-center gap-2 text-sm text-red-400">
            <XCircle size={14} />
            <span>Could not load provider info.</span>
          </div>
        )}

        {!providerLoading && !providerError && providerInfo && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <span className="text-text-muted">Provider</span>
              <span className="text-text-primary">{providerInfo.provider}</span>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="model-select" className="text-xs text-text-muted">Active model</label>
              <select
                id="model-select"
                value={selectedModel}
                onChange={(e) => { setSelectedModel(e.target.value); setSaveState('idle'); }}
                className="w-full rounded bg-bg-elevated border border-border text-sm px-3 py-1.5 text-text-primary focus:outline-none"
              >
                {(providerInfo.models ?? []).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
            <button
              type="button"
              aria-label="Save model"
              onClick={handleSaveModel}
              disabled={saveState === 'saving' || selectedModel === providerInfo.model}
              className="flex items-center gap-2 px-3 py-1.5 rounded bg-accent-teal/10 text-accent-teal text-xs hover:bg-accent-teal/20 disabled:opacity-40 transition-colors"
            >
              {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved' : 'Save model'}
            </button>
          </div>
        )}
      </section>

      {/* RAG Mode */}
      <section className="space-y-4">
        <SectionHeader icon={<Radio size={14} className="text-text-muted" />} title="RAG Mode" />
        <div className="space-y-3">
          {RAG_MODES.map((mode) => (
            <label key={mode.value} className="flex items-start gap-3 rounded-lg border border-border bg-bg-elevated px-3 py-2.5">
              <input
                type="radio"
                name="rag-mode"
                value={mode.value}
                checked={ragMode === mode.value}
                onChange={() => setRagMode(mode.value)}
                className="mt-0.5"
              />
              <span className="space-y-0.5">
                <span className="text-sm text-text-primary">{mode.label}</span>
                <span className="block text-xs text-text-muted">{mode.description}</span>
              </span>
            </label>
          ))}
        </div>
      </section>

      {/* Export */}
      <section className="space-y-4">
        <SectionHeader icon={<Download size={14} className="text-text-muted" />} title="Export Vault" />
        {exportError && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs px-3 py-2 rounded">
            {exportError}
          </div>
        )}
        <div className="rounded-xl border border-border bg-bg-elevated px-4 py-4 space-y-3">
          <p className="text-sm text-text-muted">Export your vault as either a Markdown ZIP or raw JSON snapshot.</p>
          <div className="flex flex-wrap gap-4">
            {(['markdown', 'json'] as const).map((fmt) => (
              <label key={fmt} className="flex items-center gap-2 text-sm text-text-primary">
                <input
                  type="radio"
                  name="export-format"
                  value={fmt}
                  checked={exportFormat === fmt}
                  onChange={() => setExportFormat(fmt)}
                />
                {fmt === 'markdown' ? 'Markdown ZIP' : 'JSON'}
              </label>
            ))}
          </div>
          <button
            type="button"
            aria-label="Export Vault"
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center gap-2 px-4 py-2 bg-bg-elevated hover:bg-bg-tertiary border border-border rounded text-sm text-text-primary disabled:opacity-50 transition-colors"
          >
            <Download size={14} />
            {exporting ? 'Preparing export…' : 'Export Vault'}
          </button>
        </div>
      </section>

      {/* Sync */}
      <section className="space-y-4">
        <SectionHeader
          icon={<RefreshCw size={14} className="text-text-muted" />}
          title="Vault Sync"
          status={
            syncStatus === 'active'
              ? <span className="ml-auto text-xs text-accent-teal">Syncing…</span>
              : syncStatus === 'error'
              ? <span className="ml-auto text-xs text-red-400">Error</span>
              : null
          }
        />
        <div className="rounded-xl border border-border bg-bg-elevated px-4 py-4 space-y-3">
          <p className="text-sm text-text-muted">
            Pull the latest notes from your Obsidian vault and refresh graph, vector, and cache indexes.
          </p>
          <button
            type="button"
            onClick={handleSync}
            disabled={syncing || syncStatus === 'active'}
            className="flex items-center gap-2 px-4 py-2 bg-bg-elevated hover:bg-bg-tertiary border border-border rounded text-sm text-text-primary disabled:opacity-50 transition-colors"
          >
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing…' : 'Sync Now'}
          </button>
        </div>
      </section>

      {/* Security */}
      <section className="space-y-4">
        <SectionHeader icon={<Shield size={14} className="text-text-muted" />} title="Security" />
        <div className="rounded-xl border border-border bg-bg-elevated px-4 py-4 space-y-2 text-sm text-text-muted">
          <p>
            Authentication token is stored locally under
            <code className="text-xs bg-bg-tertiary px-1 py-0.5 rounded mx-1">gnosis_token</code>
            and attached as a bearer token for API requests.
          </p>
          <p>For production, rotate secrets regularly and serve the frontend over HTTPS only.</p>
        </div>
      </section>
    </div>
  );
}
