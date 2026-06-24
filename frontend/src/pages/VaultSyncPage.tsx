import React, { useState } from 'react';
import { RefreshCw, CheckCircle2, AlertCircle, FolderSync } from 'lucide-react';

type SyncStatus = 'idle' | 'syncing' | 'success' | 'error';

async function triggerSync(): Promise<{ status: string; notes_synced?: number }> {
  const base = import.meta.env.VITE_API_BASE_URL ?? '';
  const resp = await fetch(`${base}/api/v1/vault/sync`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${localStorage.getItem('gnosis_token') ?? ''}`,
    },
  });
  if (!resp.ok) throw new Error(`Sync failed: ${resp.status}`);
  return resp.json() as Promise<{ status: string; notes_synced?: number }>;
}

export default function VaultSyncPage() {
  const [status, setStatus] = useState<SyncStatus>('idle');
  const [message, setMessage] = useState<string>('');

  const handleSync = async () => {
    setStatus('syncing');
    setMessage('');
    try {
      const result = await triggerSync();
      setStatus('success');
      setMessage(
        result.notes_synced != null
          ? `Sync complete — ${result.notes_synced} notes updated.`
          : 'Vault sync complete.'
      );
    } catch (err) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Sync failed.');
    }
  };

  return (
    <div className="p-6 max-w-xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <FolderSync size={24} className="text-gnosis-accent" />
        <h1 className="text-xl font-semibold text-gnosis-fg">Vault Sync</h1>
      </div>

      <p className="text-sm text-gnosis-muted mb-6">
        Trigger a full re-index of your Obsidian vault. This will scan all markdown files,
        update embeddings, and refresh the knowledge graph.
      </p>

      <button
        onClick={() => { void handleSync(); }}
        disabled={status === 'syncing'}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gnosis-accent
                   text-white font-medium text-sm transition-opacity
                   disabled:opacity-50 disabled:cursor-not-allowed
                   hover:opacity-90 active:opacity-80"
      >
        <RefreshCw size={16} className={status === 'syncing' ? 'animate-spin' : ''} />
        {status === 'syncing' ? 'Syncing…' : 'Sync Vault Now'}
      </button>

      {status === 'success' && (
        <div className="mt-4 flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
          <CheckCircle2 size={16} />
          {message}
        </div>
      )}

      {status === 'error' && (
        <div className="mt-4 flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
          <AlertCircle size={16} />
          {message}
        </div>
      )}
    </div>
  );
}
