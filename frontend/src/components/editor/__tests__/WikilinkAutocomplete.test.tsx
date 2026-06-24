/**
 * WikilinkAutocomplete.test.tsx
 * Covers: renders with query, filters results, keyboard nav,
 * onSelect callback, onClose callback, empty-results state.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---------------------------------------------------------------------------
// vi.hoisted — mockNotes must exist before the vi.mock factory below runs.
// ---------------------------------------------------------------------------
const { mockNotes } = vi.hoisted(() => {
  const mockNotes = [
    {
      id: '1', title: 'Alpha Note', slug: 'alpha-note', note_type: 'permanent',
      status: 'draft', folder: '10-zettelkasten', word_count: 10, tags: [],
      created_at: '', modified_at: '', is_deleted: false,
      vector_indexed: false, graph_indexed: false,
    },
    {
      id: '2', title: 'Beta Note', slug: 'beta-note', note_type: 'permanent',
      status: 'draft', folder: '10-zettelkasten', word_count: 5, tags: [],
      created_at: '', modified_at: '', is_deleted: false,
      vector_indexed: false, graph_indexed: false,
    },
    {
      id: '3', title: 'Gamma Record', slug: 'gamma-record', note_type: 'permanent',
      status: 'draft', folder: '10-zettelkasten', word_count: 3, tags: [],
      created_at: '', modified_at: '', is_deleted: false,
      vector_indexed: false, graph_indexed: false,
    },
  ];
  return { mockNotes };
});

vi.mock('../../../services/api', () => ({
  default: {
    listNotes: vi.fn().mockResolvedValue({ items: mockNotes, total: 3 }),
  },
}));

import WikilinkAutocomplete from '../WikilinkAutocomplete';

const defaultProps = {
  query: 'al',
  anchorRect: new DOMRect(10, 20, 0, 16),
  onSelect: vi.fn(),
  onClose: vi.fn(),
};

function wrap(props = defaultProps) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <WikilinkAutocomplete {...props} />
    </QueryClientProvider>
  );
}

beforeEach(() => vi.clearAllMocks());

describe('WikilinkAutocomplete — render', () => {
  it('renders a listbox container', async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByRole('listbox')).toBeInTheDocument()
    );
  });

  it('shows notes matching the query', async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByText('Alpha Note')).toBeInTheDocument()
    );
  });

  it('filters out non-matching notes', async () => {
    wrap();
    await waitFor(() => screen.getByText('Alpha Note'));
    expect(screen.queryByText('Gamma Record')).not.toBeInTheDocument();
  });

  it('shows empty state when no notes match', async () => {
    wrap({ ...defaultProps, query: 'zzznomatch' });
    await waitFor(() =>
      expect(screen.queryByRole('option')).not.toBeInTheDocument()
    );
  });
});

describe('WikilinkAutocomplete — interaction', () => {
  it('calls onSelect with note title when an option is clicked', async () => {
    const onSelect = vi.fn();
    wrap({ ...defaultProps, query: 'al', onSelect });
    await waitFor(() => screen.getByText('Alpha Note'));
    fireEvent.click(screen.getByText('Alpha Note'));
    expect(onSelect).toHaveBeenCalledWith('Alpha Note');
  });

  it('calls onClose when Escape key is pressed', async () => {
    const onClose = vi.fn();
    wrap({ ...defaultProps, onClose });
    await waitFor(() => screen.getByRole('listbox'));
    fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('highlights first item on ArrowDown', async () => {
    wrap();
    await waitFor(() => screen.getByRole('listbox'));
    fireEvent.keyDown(screen.getByRole('listbox'), { key: 'ArrowDown' });
    const options = screen.getAllByRole('option');
    expect(options[0]).toHaveAttribute('aria-selected', 'true');
  });
});
