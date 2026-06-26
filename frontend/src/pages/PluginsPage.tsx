/**
 * PluginsPage — Plugin / extension registry.
 *
 * Priority 5 (#12): This page previously contained a pure client-side toggle
 * list with no backend.  It is now redesigned around a real plugin API shape:
 *
 *   GET  /api/v1/plugins        → list installed plugins with metadata
 *   POST /api/v1/plugins/{id}/enable   → enable a plugin
 *   POST /api/v1/plugins/{id}/disable  → disable a plugin
 *
 * Until the backend route exists the page renders gracefully with a "coming
 * soon" notice and shows the planned capability surface so the design is
 * locked in before the API is built.
 *
 * The PLANNED_PLUGINS list acts as the authoritative spec for the server
 * — any field added here should be reflected in the Pydantic PluginInfo schema.
 */
import React, { useEffect, useState } from 'react';

// ---------------------------------------------------------------------------
// Types — mirrors the planned GET /api/v1/plugins response shape
// ---------------------------------------------------------------------------

export interface PluginInfo {
  /** Stable machine ID (matches the backend router prefix) */
  id: string;
  name: string;
  description: string;
  /** Semantic version string */
  version: string;
  /** Whether the plugin is currently active server-side */
  enabled: boolean;
  /** Feature flags / capability surface exposed by this plugin */
  capabilities: string[];
  /** True if the plugin ships with Gnosis-KB core; false = user-installed */
  builtin: boolean;
}

// ---------------------------------------------------------------------------
// Planned plugin manifest — this is the source of truth for the API schema
// ---------------------------------------------------------------------------

const PLANNED_PLUGINS: PluginInfo[] = [
  {
    id: 'daily-notes',
    name: 'Daily Notes',
    description: 'Automatically create dated daily note entries in 60-journals/.',
    version: '1.0.0',
    enabled: true,
    capabilities: ['POST /notes/daily', 'sidebar:daily-button'],
    builtin: true,
  },
  {
    id: 'graph-clusters',
    name: 'Graph Clusters',
    description: 'Community detection and cluster colouring on the knowledge graph.',
    version: '1.0.0',
    enabled: true,
    capabilities: ['GET /graph/clusters', 'graph:cluster-overlay'],
    builtin: true,
  },
  {
    id: 'spaced-rep',
    name: 'Spaced Repetition',
    description: 'SM-2 flashcard-style review queue based on note maturity.',
    version: '1.0.0',
    enabled: true,
    capabilities: ['GET /review/queue', 'POST /review/record', 'sidebar:review-count'],
    builtin: true,
  },
  {
    id: 'templates',
    name: 'Templates',
    description: 'Note templates with variable substitution and frontmatter defaults.',
    version: '1.0.0',
    enabled: true,
    capabilities: ['GET /notes/templates', 'editor:template-picker'],
    builtin: true,
  },
  {
    id: 'ingest',
    name: 'Web & File Ingest',
    description: 'Import web pages, PDFs, DOCX, and PPTX as literature notes.',
    version: '1.0.0',
    enabled: true,
    capabilities: ['POST /ingest/file', 'POST /ingest/url', 'POST /ingest/batch'],
    builtin: true,
  },
  {
    id: 'rag-export',
    name: 'RAG Export',
    description: 'Export vault as a structured JSON/JSONL dataset for external RAG pipelines.',
    version: '0.8.0',
    enabled: false,
    capabilities: ['GET /export/rag'],
    builtin: true,
  },
];

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

// ---------------------------------------------------------------------------
// API helpers — used once GET /plugins is implemented
// ---------------------------------------------------------------------------

async function fetchPlugins(): Promise<PluginInfo[]> {
  const token = localStorage.getItem('gnosis_token');
  const res = await fetch(`${API_BASE}/plugins`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function setPluginEnabled(id: string, enabled: boolean): Promise<void> {
  const token = localStorage.getItem('gnosis_token');
  const action = enabled ? 'enable' : 'disable';
  await fetch(`${API_BASE}/plugins/${id}/${action}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PluginsPage() {
  const [plugins, setPlugins] = useState<PluginInfo[]>(PLANNED_PLUGINS);
  const [apiReady, setApiReady] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);

  // Attempt to load live data from the API; fall back to the planned manifest.
  useEffect(() => {
    fetchPlugins()
      .then((data) => {
        setPlugins(data);
        setApiReady(true);
      })
      .catch(() => {
        // API not yet implemented — use the planned manifest with toggles disabled.
        setApiReady(false);
      });
  }, []);

  const toggle = async (id: string) => {
    if (!apiReady) return;
    setToggling(id);
    const target = plugins.find((p) => p.id === id);
    if (!target) return;
    try {
      await setPluginEnabled(id, !target.enabled);
      setPlugins((prev) =>
        prev.map((p) => (p.id === id ? { ...p, enabled: !p.enabled } : p))
      );
    } catch {
      // Leave optimistic update rolled back — could add error toast here
    } finally {
      setToggling(null);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gnosis-bg text-gnosis-fg">
      <div className="px-6 pt-6 pb-4 border-b border-gnosis-border">
        <h1 className="text-xl font-semibold">Plugins</h1>
        <p className="text-sm text-gnosis-muted mt-1">
          Built-in Gnosis-KB modules. Each plugin exposes a documented API
          surface; third-party plugins will be loadable once
          <code className="mx-1 px-1 rounded bg-gnosis-surface text-xs">POST /plugins/install</code>
          lands.
        </p>
        {!apiReady && (
          <p className="mt-2 text-xs text-amber-500">
            ⚠️ Plugin API not yet live — toggles are disabled. Showing planned plugin surface.
          </p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
        {plugins.map((p) => (
          <div
            key={p.id}
            className="p-4 rounded-lg bg-gnosis-surface border border-gnosis-border"
          >
            <div className="flex items-start justify-between gap-4">
              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gnosis-fg">{p.name}</span>
                  <span className="text-xs text-gnosis-muted">v{p.version}</span>
                  {p.builtin && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gnosis-border text-gnosis-muted">
                      built-in
                    </span>
                  )}
                </div>
                <p className="text-sm text-gnosis-muted mt-0.5">{p.description}</p>
                {/* Capability surface */}
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {p.capabilities.map((cap) => (
                    <li
                      key={cap}
                      className="text-[11px] px-1.5 py-0.5 rounded font-mono
                                 bg-gnosis-border/40 text-gnosis-muted"
                    >
                      {cap}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Toggle */}
              <button
                role="switch"
                aria-checked={p.enabled}
                aria-label={`${p.enabled ? 'Disable' : 'Enable'} ${p.name}`}
                onClick={() => toggle(p.id)}
                disabled={!apiReady || toggling === p.id}
                className={[
                  'relative shrink-0 w-10 h-6 rounded-full transition-colors',
                  p.enabled ? 'bg-gnosis-accent' : 'bg-gnosis-border',
                  !apiReady ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
                ].join(' ')}
              >
                <span
                  className={[
                    'absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform',
                    p.enabled ? 'translate-x-5' : 'translate-x-1',
                  ].join(' ')}
                />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
