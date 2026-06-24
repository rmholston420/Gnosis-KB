/**
 * AnalyticsPage
 * =============
 * Displays knowledge-graph statistics and top-connected notes.
 */
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { GraphStats } from '../types';

interface StatCardProps {
  label: string;
  value: string | number | undefined;
  sub?:  string;
}

function StatCard({ label, value, sub }: StatCardProps) {
  return (
    <div className="bg-bg-secondary rounded-lg p-4 border border-border">
      <p className="text-xs text-text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-text-primary">
        {value ?? '\u2014'}
      </p>
      {sub && <p className="text-xs text-text-muted mt-0.5">{sub}</p>}
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: stats, isLoading } = useQuery<GraphStats>({
    queryKey: ['graph-stats'],
    queryFn:  () => api.getGraphStats() as Promise<GraphStats>,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-text-muted text-sm">
        Loading analytics\u2026
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-64 text-text-muted text-sm">
        No graph data available.
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-text-primary">Knowledge Graph Analytics</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Notes"   value={stats.total_nodes} />
        <StatCard label="Total Links"   value={stats.total_edges} />
        <StatCard label="Orphan Notes"  value={stats.isolated_count} sub="no connections" />
        <StatCard label="Avg Degree"    value={stats.avg_degree?.toFixed(2)} />
      </div>

      {stats.most_connected && stats.most_connected.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-text-primary mb-2">Most Connected Notes</h2>
          <ul className="space-y-1">
            {stats.most_connected.map((n) => (
              <li key={n.note_id} className="flex items-center justify-between text-sm py-1.5 px-3 rounded bg-bg-secondary">
                <span className="text-text-primary truncate">{n.title}</span>
                <span className="text-xs text-text-muted ml-3 shrink-0">{n.degree} links</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
