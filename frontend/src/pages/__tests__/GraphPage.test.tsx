/**
 * GraphPage.test.tsx
 * ==================
 * GraphPage renders a single-canvas view (GraphView2D + GraphControls).
 * We stub the canvas-heavy sub-components and assert the controls and
 * overlay interactions that are actually present.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// ---------------------------------------------------------------------------
// Stub GraphView2D — canvas/WebGL not available in jsdom
// ---------------------------------------------------------------------------
vi.mock('../../components/graph/GraphView2D', () => ({
  GraphView2D: ({ onNodeClick }: { onNodeClick?: (n: unknown) => void }) =>
    React.createElement('div', { 'data-testid': 'graph-view' },
      React.createElement('button', {
        'data-testid': 'node-btn',
        onClick: () => onNodeClick && onNodeClick({ note_id: 'n1', title: 'EEG Note', note_type: 'permanent', status: 'evergreen', folder: '', word_count: 10, tag_count: 0, incoming_link_count: 1, outgoing_link_count: 0 }),
      }, 'Simulate node click')
    ),
}));

// Stub GraphControls — renders the real controls markup would need canvas
vi.mock('../../components/graph/GraphControls', () => ({
  GraphControls: () => React.createElement('div', { 'data-testid': 'graph-controls' }, 'Controls'),
}));

// Stub NodeDetailOverlay
vi.mock('../../components/graph/NodeDetailOverlay', () => ({
  NodeDetailOverlay: ({ node, onClose }: { node: { title: string }; onClose: () => void }) =>
    React.createElement('div', { 'data-testid': 'node-detail' },
      node.title,
      React.createElement('button', { onClick: onClose }, 'Close')
    ),
}));

import GraphPage from '../GraphPage';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('GraphPage — render', () => {
  it('renders the graph view', () => {
    wrap();
    expect(screen.getByTestId('graph-view')).toBeInTheDocument();
  });

  it('renders the graph controls overlay', () => {
    wrap();
    expect(screen.getByTestId('graph-controls')).toBeInTheDocument();
  });

  it('does not show node detail panel initially', () => {
    wrap();
    expect(screen.queryByTestId('node-detail')).toBeNull();
  });
});

describe('GraphPage — node click', () => {
  it('shows NodeDetailOverlay when a node is clicked', async () => {
    wrap();
    fireEvent.click(screen.getByTestId('node-btn'));
    await waitFor(() =>
      expect(screen.getByTestId('node-detail')).toBeInTheDocument()
    );
    expect(screen.getByText('EEG Note')).toBeInTheDocument();
  });

  it('hides NodeDetailOverlay when close is clicked', async () => {
    wrap();
    fireEvent.click(screen.getByTestId('node-btn'));
    await waitFor(() => screen.getByTestId('node-detail'));
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    await waitFor(() =>
      expect(screen.queryByTestId('node-detail')).toBeNull()
    );
  });
});
