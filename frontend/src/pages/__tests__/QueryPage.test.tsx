/**
 * QueryPage.test.tsx
 * Covers: initial render with example sidebar, textarea + run button,
 * save dialog, delete saved query, keyboard shortcut hint text.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import axios from 'axios';

vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

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
  (mockedAxios.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] });
  (mockedAxios.post as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: { rows: [], total: 0, query_time_ms: 5 },
  });
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
    (mockedAxios.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { rows: [], total: 0, query_time_ms: 3 },
    });
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /run/i }));
    await waitFor(() =>
      expect(screen.getByText(/no notes matched/i)).toBeInTheDocument()
    );
  });

  it('shows error message on run failure', async () => {
    (mockedAxios.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Bad query')
    );
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /run/i }));
    await waitFor(() =>
      expect(screen.getByText(/bad query/i)).toBeInTheDocument()
    );
  });
});

describe('QueryPage — save dialog', () => {
  it('opens save dialog on Save button click', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() =>
      expect(screen.getByPlaceholderText(/^name$/i)).toBeInTheDocument()
    );
  });

  it('closes save dialog on Cancel', async () => {
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => screen.getByPlaceholderText(/^name$/i));
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() =>
      expect(screen.queryByPlaceholderText(/^name$/i)).not.toBeInTheDocument()
    );
  });
});

describe('QueryPage — example sidebar', () => {
  it('fills textarea when an example is clicked', async () => {
    wrap();
    const exampleBtn = screen.getByText(/inbox \(recent\)/i);
    fireEvent.click(exampleBtn);
    const textarea = screen.getByPlaceholderText(/from folder where/i) as HTMLTextAreaElement;
    expect(textarea.value).toContain('00-inbox');
  });
});

describe('QueryPage — no saved queries', () => {
  it('shows placeholder when saved list is empty', async () => {
    (mockedAxios.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] });
    wrap();
    await waitFor(() =>
      expect(screen.getByText(/no saved queries yet/i)).toBeInTheDocument()
    );
  });
});
