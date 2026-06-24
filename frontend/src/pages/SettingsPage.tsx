import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Settings,
  Cpu,
  CircleCheck,
  Radio,
  Shield,
  Download,
  RefreshCw,
} from 'lucide-react';
import api from '../services/api';
import type { AppSettings, ExportFormat } from '../types/api';

const RAG_MODES = [
  {
    value: 'hybrid',
    label: 'Hybrid Vector + graph traversal (recommended)',
    description: 'Uses local embeddings first, then graph neighbors for context expansion.',
  },
  {
    value: 'local',
    label: 'Local Vector similarity only',
    description: 'Fastest path for tight, semantically-similar note retrieval.',
  },
  {
    value: 'global',
    label: 'Global Graph-wide community search',
    description: 'Best for discovery across distant areas of the vault graph.',
  },
] as const;

const EXPORT_FORMATS: Array<{ value: ExportFormat; label: string }> = [
  { value: 'markdown', label: 'Markdown ZIP' },
  { value: 'json', label: 'JSON' },
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
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [exportFormat, setExportFormat] = useState<ExportFormat>('markdown');
  const [exporting, setExporting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [exportError, setExportError] = useState('');
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [selectedModel, setSelectedModel] = useState('');
  const [syncStatus, setSyncStatus] = useState<'idle' | 'active' | 'error'>('idle');
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let mounted = true;
    api.getSettings()
      .then((data) => {
        if (!mounted) return;
        setSettings(data);
        setSelectedModel(data.ai.model);
      })
      .catch(() => {})
      .finally(() => {
        if (!mounted) return;
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const es = new EventSource('/api/v1/sync/events');
    eventSourceRef.current = es;

    es.addEventListener('sync_started', () => setSyncStatus('active'));
    es.addEventListener('sync_completed', () => setSyncStatus('idle'));
    es.addEventListener('sync_error', () => setSyncStatus('error'));

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, []);

  const providerBadge = useMemo(() => {
    if (!settings) return null;
    if (settings.ai.connected) {
      return (
        <span className="ml-auto flex items-center gap-1 text-xs text-green-400">
          <CircleCheck size={12} /> Connected
        </span>
      );
    }
    return <span className="ml-auto text-xs text-red-400">Disconnected</span>;
  }, [settings]);

  const handleSaveModel = async () => {
    if (!settings || selectedModel === settings.ai.model) return;
    setSaveState('saving');
    try {
      const updated = await api.patchSettings({ ai: { model: selectedModel } });
      setSettings(updated);
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

  if (!settings) {
    return (
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="animate-pulse space-y-6">
          <div className="h-4 w-32 rounded bg-bg-tertiary" />
          <div className="h-24 rounded-xl bg-bg-elevated" />
          <div className="h-24 rounded-xl bg-bg-elevated" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-8 max-w-2xl">
      <div className="flex items-center gap-2">
        <Settings size={16} className="text-text-muted" />
        <h1 className="text-base font-semibold text-text-primary">Settings</h1>
      </div>

      <section className="space-y-4">
        <SectionHeader icon={<Cpu size={14} className="text-text-muted" />} title="AI Provider" status={providerBadge} />
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <span className="text-text-muted">Provider</span>
            <span className="text-text-primary capitalize">{settings.ai.provider}</span>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="model-select" className="text-xs text-text-muted">Active model</label>
            <select
              id="model-select"
              value={selectedModel}
              onChange={(e) => {
                setSelectedModel(e.target.value);
                setSaveState('idle');
              }}
              className="w-full rounded bg-bg-elevated border border-border text-sm px-3 py-1.5 text-text-primary focus:outline-none"
            >
              {settings.ai.available_models.map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={handleSaveModel}
            disabled={saveState === 'saving' || selectedModel === settings.ai.model}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-accent-teal/10 text-accent-teal text-xs hover:bg-accent-teal/20 disabled:opacity-40 transition-colors"
          >
            {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved' : 'Save model'}
          </button>
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeader icon={<Radio size={14} className="text-text-muted" />} title="RAG Mode" />
        <div className="space-y-3">
          {RAG_MODES.map((mode) => (
            <label key={mode.value} className="flex items-start gap-3 rounded-lg border border-border bg-bg-elevated px-3 py-2.5">
              <input
                type="radio"
                name="rag-mode"
                value={mode.value}
                checked={settings.rag.mode === mode.value}
                onChange={() => {
                  setSettings((prev) => prev ? { ...prev, rag: { ...prev.rag, mode: mode.value } } : prev);
                }}
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

      <section className="space-y-4">
        <SectionHeader icon={<Download size={14} className="text-text-muted" />} title="Export Vault" />

        {exportError && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs px-3 py-2 rounded">
            {exportError}
          </div>
        )}

        <div className="rounded-xl border border-border bg-bg-elevated px-4 py-4 space-y-3">
          <p className="text-sm text-text-muted">
            Export your vault as either a Markdown ZIP or raw JSON snapshot.
          </p>
          <div className="flex flex-wrap gap-4">
            {EXPORT_FORMATS.map((format) => (
              <label key={format.value} className="flex items-center gap-2 text-sm text-text-primary">
                <input
                  type="radio"
                  name="export-format"
                  value={format.value}
                  checked={exportFormat === format.value}
                  onChange={() => setExportFormat(format.value)}
                />
                {format.label}
              </label>
            ))}
          </div>
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center gap-2 px-4 py-2 bg-bg-elevated hover:bg-bg-tertiary border border-border rounded text-sm text-text-primary disabled:opacity-50 transition-colors"
          >
            <Download size={14} />
            {exporting ? 'Preparing export…' : 'Download export'}
          </button>
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeader
          icon={<RefreshCw size={14} className="text-text-muted" />}
          title="Vault Sync"
          status={
            syncStatus === 'active' ? (
              <span className="ml-auto text-xs text-accent-teal">Syncing…</span>
            ) : syncStatus === 'error' ? (
              <span className="ml-auto text-xs text-red-400">Error</span>
            ) : null
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

      <section className="space-y-4">
        <SectionHeader icon={<Shield size={14} className="text-text-muted" />} title="Security" />
        <div className="rounded-xl border border-border bg-bg-elevated px-4 py-4 space-y-2 text-sm text-text-muted">
          <p>
            Authentication token is stored locally under
            <code className="text-xs bg-bg-tertiary px-1 py-0.5 rounded mx-1">gnosis_token</code>
            and attached as a bearer token for API requests.
          </p>
          <p>
            For production, rotate secrets regularly and serve the frontend over HTTPS only.
          </p>
          <p className="text-xs text-text-faint">
            Active API base URL: <code className="text-xs bg-bg-tertiary px-1.5 py-0.5 rounded">{api.defaults.baseURL ?? '/api/v1'}</code>
          </p>
        </div>
      </section>
    </div>
  );
}
