import React from 'react';
import { useGraphStats } from '../hooks/useGraph';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="flex flex-col gap-1 p-5 rounded-xl bg-gnosis-surface border border-gnosis-border">
      <span className="text-sm text-gnosis-muted">{label}</span>
      <span className="text-3xl font-semibold tabular-nums text-gnosis-fg">{value}</span>
      {sub && <span className="text-xs text-gnosis-muted">{sub}</span>}
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: stats, isLoading, isError } = useGraphStats();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gnosis-muted">
        Loading vault analytics…
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        Failed to load analytics.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-gnosis-bg text-gnosis-fg">
      <div className="px-6 pt-6 pb-4 border-b border-gnosis-border">
        <h1 className="text-xl font-semibold">Analytics</h1>
        <p className="text-sm text-gnosis-muted mt-1">Vault health and graph metrics.</p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {/* KPI grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total Notes"       value={stats.total_notes} />
          <StatCard label="Total Links"       value={stats.total_links} />
          <StatCard label="Orphan Notes"      value={stats.orphan_count} sub="no connections" />
          <StatCard label="Avg Degree"        value={stats.avg_degree.toFixed(2)} sub="links per note" />
          <StatCard label="Graph Density"     value={(stats.density * 100).toFixed(2) + '%'} />
          <StatCard
            label="Most Connected"
            value={stats.most_connected[0]?.title ?? '—'}
            sub={stats.most_connected[0] ? `${stats.most_connected[0].degree} links` : undefined}
          />
        </div>

        {/* Top connected notes */}
        {stats.most_connected.length > 0 && (
          <section>
            <h2 className="text-base font-semibold mb-3">Top Connected Notes</h2>
            <div className="space-y-2">
              {stats.most_connected.map((n) => (
                <div
                  key={n.note_id}
                  className="flex items-center justify-between px-4 py-3
                             rounded-lg bg-gnosis-surface border border-gnosis-border"
                >
                  <span className="text-sm">{n.title}</span>
                  <span className="text-xs text-gnosis-muted tabular-nums">{n.degree} links</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
