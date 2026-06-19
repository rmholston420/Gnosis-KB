import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { Download, CheckCircle, AlertCircle } from 'lucide-react';

export default function SettingsPage() {
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.get('/api/v1/health/').then((r) => r.data),
    refetchInterval: 30_000,
  });

  async function handleVaultExport() {
    setExportMsg('Preparing download…');
    try {
      const resp = await apiClient.get('/api/v1/export/vault.zip', {
        responseType: 'blob',
      });
      const url = URL.createObjectURL(resp.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'gnosis-vault.zip';
      a.click();
      URL.revokeObjectURL(url);
      setExportMsg('Download started!');
    } catch {
      setExportMsg('Export failed — check console');
    }
  }

  const statusOk = health?.status === 'healthy';

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-8">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* Health status */}
      <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <h2 className="mb-3 font-semibold">System Health</h2>
        {health ? (
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              {statusOk ? (
                <CheckCircle className="text-green-500" size={16} />
              ) : (
                <AlertCircle className="text-yellow-500" size={16} />
              )}
              <span className="font-medium capitalize">{health.status}</span>
              <span className="text-gray-500">· uptime {health.uptime_seconds}s</span>
            </div>
            {Object.entries(health.checks as Record<string, string>).map(([svc, st]) => (
              <div key={svc} className="ml-6 flex gap-4">
                <span className="w-20 text-gray-500">{svc}</span>
                <span className={st === 'ok' ? 'text-green-600' : 'text-red-500'}>{st}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">Loading…</p>
        )}
      </section>

      {/* Export */}
      <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <h2 className="mb-1 font-semibold">Export Vault</h2>
        <p className="mb-3 text-sm text-gray-500">
          Download all notes as an Obsidian-compatible zip archive (.md files with YAML frontmatter).
        </p>
        <button
          onClick={handleVaultExport}
          className="flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
        >
          <Download size={15} /> Export vault.zip
        </button>
        {exportMsg && (
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{exportMsg}</p>
        )}
      </section>
    </div>
  );
}
