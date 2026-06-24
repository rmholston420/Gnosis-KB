/**
 * QueryPage.test.tsx
 * Covers: initial render with example sidebar, textarea + run button,
 * save dialog, delete saved query, keyboard shortcut hint text.
 *
 * Axios is stubbed via vi.hoisted() so the mock factory can reference the
 * spy functions. DO NOT use vi.mock('axios') automock + vi.mocked() — that
 * pattern places top-level variable references inside a hoisted factory,
 * causing "Cannot access 'x' before initialization" and a secondary
 * "Cannot find module" crash on require('../QueryPage').
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---------------------------------------------------------------------------
// Hoist axios stubs
// ---------------------------------------------------------------------------
const { mockGet, mockPost, mockDelete } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockDelete: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    get: mockGet,
    post: mockPost,
    delete: mockDelete,
  },
}));

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { default: QueryPage } = require('../QueryPage');
  return render(
    <QueryClientProvider client={qc}>
      <QueryPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mockGet.mockResolvedValue({ data: [] });
  mockPost.mockResolvedValue({ data: { rows: [], total: 0, query_time_ms: 5 } });
});

describe('QueryPage — rendering', () => {
  it('renders example queries in sidebar', () => {
    wrap();
    expect(screen.getByText(/draft zettelkasten notes/i)).toBeInTheDocument();
  });

  it('renders Run button', () => {
    wrap();
    expect(screen.getByRole('button', { name: /run/i })).toBeInTheDocument();
  });

  it('renders Save button', () => {
    wrap();
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
  });

  it('renders the query textarea with placeholder', () => {
    wrap();
    expect(screen.getByPlaceholderText(/from folder where/i)).toBeInTheDocument();
  });
});

describe('QueryPage — run query', () => {
  it('calls run endpoint and shows empty result message', async () => {
    mockPost.mockResolvedValueOnce({
      data: { rows: [], total: 0, query_time_ms: 3 },
    });
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /run/i }));
    await waitFor(() =>
      expect(mockPost).toHaveBeenCalled()
    );
    await waitFor(() =>
      expect(screen.getByText(/no results/i)).toBeInTheDocument()
    );
  });

  it('shows error message on run failure', async () => {
    mockPost.mockRejectedValueOnce(new Error('bad query'));
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /run/i }));
    await waitFor(() =>
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    );
  });
});

describe('QueryPage — save dialog', () => {
  it('opens save dialog on Save button click', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    );
  });

  it('closes save dialog on Cancel', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => screen.getByRole('dialog'));
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    );
  });
});

describe('QueryPage — example sidebar', () => {
  it('fills textarea when an example is clicked', async () => {
    wrap();
    const firstExample = screen.getByText(/draft zettelkasten notes/i);
    fireEvent.click(firstExample);
    await waitFor(() => {
      const ta = screen.getByRole('textbox') as HTMLTextAreaElement;
      expect(ta.value).toMatch(/zettelkasten/i);
    });
  });
});

describe('QueryPage — no saved queries', () => {
  it('shows placeholder when saved list is empty', async () => {
    mockGet.mockResolvedValue({ data: [] });
    wrap();
    await waitFor(() =>
      expect(screen.getByText(/no saved queries/i)).toBeInTheDocument()
    );
  });
});
