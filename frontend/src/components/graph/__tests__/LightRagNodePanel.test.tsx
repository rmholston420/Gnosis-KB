/**
 * LightRagNodePanel.test.tsx
 * ==========================
 * Tests for the graph node detail side-panel (LightRAG neighbour info).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LightRagNodePanel from '../LightRagNodePanel';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockGetGraphNode = vi.fn();
vi.mock('../../../services/api', () => ({
  default: {
    getGraphNode: (...args: unknown[]) => mockGetGraphNode(...args),
  },
}));

const sampleNodeData = {
  id: 'node-1',
  title: 'Dependent Origination',
  description: 'The teaching of interdependent causation.',
  neighbours: [
    { id: 'node-2', title: 'Emptiness', weight: 0.9 },
    { id: 'node-3', title: 'Karma', weight: 0.7 },
  ],
  edges: [],
};

function renderPanel(nodeId = 'node-1', onClose = vi.fn()) {
  return render(
    <MemoryRouter>
      <LightRagNodePanel nodeId={nodeId} onClose={onClose} />
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockGetGraphNode.mockReset();
  mockNavigate.mockReset();
  mockGetGraphNode.mockResolvedValue(sampleNodeData);
});

describe('LightRagNodePanel', () => {
  it('shows loading state initially', () => {
    mockGetGraphNode.mockReturnValue(new Promise(() => {}));
    renderPanel();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders node title after loading', async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByText('Dependent Origination')).toBeInTheDocument()
    );
  });

  it('renders node description', async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByText(/interdependent causation/i)).toBeInTheDocument()
    );
  });

  it('renders neighbour nodes', async () => {
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText('Emptiness')).toBeInTheDocument();
      expect(screen.getByText('Karma')).toBeInTheDocument();
    });
  });

  it('calls api.getGraphNode with nodeId', async () => {
    renderPanel('node-1');
    await waitFor(() => expect(mockGetGraphNode).toHaveBeenCalledWith('node-1'));
  });

  it('clicking a neighbour navigates to that node', async () => {
    renderPanel();
    await waitFor(() => screen.getByText('Emptiness'));
    fireEvent.click(screen.getByText('Emptiness'));
    expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('node-2'));
  });

  it('renders Close button and calls onClose', async () => {
    const onClose = vi.fn();
    renderPanel('node-1', onClose);
    await waitFor(() => screen.getByText('Dependent Origination'));
    const closeBtn = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it('shows error state when getGraphNode rejects', async () => {
    mockGetGraphNode.mockRejectedValue(new Error('not found'));
    renderPanel();
    await waitFor(() =>
      expect(screen.getByText(/error|failed|not found/i)).toBeInTheDocument()
    );
  });
});
