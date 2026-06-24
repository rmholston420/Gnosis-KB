/**
 * NodeDetailOverlay — slide-in panel shown when a graph node is clicked.
 * Displays note preview, type badge, link counts, and navigation.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink, X, ArrowRight, Tag, Link2 } from 'lucide-react';
import { relativeTime } from '../../lib/dateUtils';
import { NODE_COLORS } from '../../lib/graphUtils';
import type { GraphNode } from '../../types';

interface NodeDetailOverlayProps {
  node:     GraphNode | null;
  onClose:  () => void;
}

/**
 * Rendered as an absolute-positioned overlay on the graph canvas.
 * Closes when the X button is clicked or another node is selected.
 */
export function NodeDetailOverlay({ node, onClose }: NodeDetailOverlayProps) {
  const navigate = useNavigate();

  if (!node) return null;

  const color  = NODE_COLORS[node.type ?? 'default'] ?? NODE_COLORS['default'];
  const noteId = node.note_id;

  return (
    <div
      className="absolute right-4 top-4 z-20 w-72 bg-gnosis-surface border border-gnosis-border rounded-lg shadow-xl p-4 animate-slide-in"
      role="dialog"
      aria-label={`Note details: ${node.title}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-full flex-shrink-0 mt-0.5"
            style={{ background: color }}
          />
          <span className="font-medium text-gnosis-fg text-sm leading-snug">{node.title}</span>
        </div>
        <button
          onClick={onClose}
          className="text-gnosis-muted hover:text-gnosis-fg transition-colors flex-shrink-0"
          aria-label="Close node detail"
        >
          <X size={14} />
        </button>
      </div>

      {/* Type + status */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs px-2 py-0.5 rounded-full bg-gnosis-muted/20 text-gnosis-muted">
          {node.type ?? 'note'}
        </span>
        {node.status && (
          <span className="text-xs text-gnosis-muted">{node.status}</span>
        )}
      </div>

      {/* Excerpt */}
      {node.excerpt && (
        <p className="text-xs text-gnosis-muted leading-relaxed mb-3 line-clamp-3">
          {node.excerpt}
        </p>
      )}

      {/* Link stats */}
      <div className="flex items-center gap-4 text-xs text-gnosis-muted mb-4">
        <span className="flex items-center gap-1">
          <Link2 size={11} />
          <span>{node.incoming_link_count ?? 0} in</span>
        </span>
        <span className="flex items-center gap-1">
          <ArrowRight size={11} />
          <span>{node.outgoing_link_count ?? 0} out</span>
        </span>
        {node.modified_at && (
          <span className="ml-auto">{relativeTime(node.modified_at)}</span>
        )}
      </div>

      {/* Tags */}
      {node.tags && node.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-4">
          {node.tags.slice(0, 5).map((tag) => (
            <span
              key={tag}
              className="flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded bg-gnosis-muted/10 text-gnosis-muted"
            >
              <Tag size={9} />{tag}
            </span>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => { navigate(`/notes/${noteId}`); onClose(); }}
          className="flex-1 flex items-center justify-center gap-1.5 text-xs bg-gnosis-accent text-white rounded px-3 py-1.5 hover:opacity-90 transition-opacity"
        >
          <ExternalLink size={11} /> Open Note
        </button>
      </div>
    </div>
  );
}
