/**
 * SyncPage — manual vault sync trigger + status display.
 */
import React from 'react';
import { useMutation } from '@tanstack/react-query';
import { triggerVaultSync } from '../services/api';
import { useAiStore } from '../store/aiStore';

export default function SyncPage() {
  const syncStatus   = useAiStore((s) => s.vaultSyncStatus);
  const syncProgress = useAiStore((s) => s.vaultSyncProgress);

  const syncMutation = useMutation({
    mutationFn: triggerVaultSync,
  });

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gnosis-fg mb-6">Vault Sync</h1>

      <div className="rounded-xl border border-gnosis-border bg-gnosis-surface p-6 space-y-4">
        {/* Status indicator */}
        <div className="flex items-center gap-3">
          <span
            className={[
              'h-3 w-3 rounded-full',
              syncStatus === 'syncing' ? 'bg-yellow-400 animate-pulse' :
              syncStatus === 'error'   ? 'bg-red-500' :
              'bg-emerald-500',
            ].join(' ')}
          />
          <span className="text-sm text-gnosis-fg capitalize">
            {syncStatus === 'idle'    ? 'Up to date' :
             syncStatus === 'syncing' ? `Syncing… ${syncProgress ?? 0}%` :
             'Sync error'}
          </span>
        </div>

        {/* Progress bar */}
        {syncStatus === 'syncing' && typeof syncProgress === 'number' && (
          <div className="h-1 bg-gnosis-border rounded-full overflow-hidden">
            <div
              className="h-full bg-gnosis-accent transition-all duration-300"
              style={{ width: `${syncProgress}%` }}
            />
          </div>
        )}

        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending || syncStatus === 'syncing'}
          className="w-full py-2 rounded-lg bg-gnosis-accent text-white text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          {syncMutation.isPending ? 'Starting sync…' : 'Sync Now'}
        </button>

        {syncMutation.isError && (
          <p className="text-sm text-red-500">
            {(syncMutation.error as Error)?.message ?? 'Sync failed'}
          </p>
        )}
      </div>
    </div>
  );
}
