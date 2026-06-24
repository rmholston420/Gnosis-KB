/**
 * LightRagNodePanel
 * =================
 * Slide-in right-side panel shown when a graph node is selected.
 * Fetches full node data by nodeId via api.getGraphNode().
 *
 * Props
 * -----
 *   nodeId   — ID of the node to fetch and display
 *   onClose  — called when user dismisses the panel
 */

import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import './LightRagNodePanel.css';

export interface GraphNeighbour {
  id: string;
  title: string;
  weight?: number;
}

export interface GraphNodeData {
  id: string;
  title: string;
  description?: string;
  neighbours?: GraphNeighbour[];
  edges?: unknown[];
}

interface Props {
  nodeId: string;
  onClose: () => void;
}

export function LightRagNodePanel({ nodeId, onClose }: Props) {
  const navigate = useNavigate();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [node,    setNode]    = useState<GraphNodeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);

  // Fetch node data whenever nodeId changes
  useEffect(() => {
    setLoading(true);
    setError(null);
    setNode(null);
    (api as unknown as { getGraphNode: (id: string) => Promise<GraphNodeData> })
      .getGraphNode(nodeId)
      .then((data) => {
        setNode(data);
      })
      .catch((err: Error) => {
        setError(err.message ?? 'Failed to load node');
      })
      .finally(() => setLoading(false));
  }, [nodeId]);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // Focus panel for a11y
  useEffect(() => {
    if (!loading && panelRef.current) panelRef.current.focus();
  }, [loading]);

  return (
    <div
      className="lrn-panel lrn-panel--open"
      ref={panelRef}
      tabIndex={-1}
      role="complementary"
      aria-label={node ? `Entity panel: ${node.title}` : 'Entity panel'}
    >
      <div className="lrn-header">
        <h2 className="lrn-title">{node?.title ?? (loading ? 'Loading…' : 'Node')}</h2>
        <button
          className="lrn-close"
          onClick={onClose}
          aria-label="Close entity panel"
        >
          ×
        </button>
      </div>

      {loading && (
        <div className="lrn-loading">Loading…</div>
      )}

      {error && (
        <div className="lrn-error">Error: {error}</div>
      )}

      {node && !loading && (
        <>
          {node.description && (
            <section className="lrn-section">
              <p className="lrn-description">{node.description}</p>
            </section>
          )}

          {(node.neighbours ?? []).length > 0 && (
            <section className="lrn-section">
              <h3 className="lrn-section-heading">Neighbours</h3>
              <ul className="lrn-neighbours">
                {(node.neighbours ?? []).map((nb) => (
                  <li key={nb.id}>
                    <button
                      className="lrn-neighbour-btn"
                      onClick={() => navigate(`/graph?node=${nb.id}`)}
                    >
                      {nb.title}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default LightRagNodePanel;
