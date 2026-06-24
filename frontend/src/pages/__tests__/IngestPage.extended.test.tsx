/**
 * IngestPage.extended.test.tsx
 * ============================
 * Extended coverage for IngestPage. All renders must include
 * QueryClientProvider because IngestPage uses useMutation directly.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import IngestPage from '../IngestPage';

const mockIngestUrl  = vi.fn();
const mockIngestFile = vi.fn();
vi.mock('../../services/api', () => ({
  default: {
    ingestUrl:  (...args: unknown[]) => mockIngestUrl(...args),
    ingestFile: (...args: unknown[]) => mockIngestFile(...args),
  },
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><IngestPage /></MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  mockIngestUrl.mockReset();
  mockIngestFile.mockReset();
  mockIngestUrl.mockResolvedValue({ job_id: 'job-url-1' });
  mockIngestFile.mockResolvedValue({ job_id: 'job-file-1' });
});

describe('IngestPage', () => {
  it('renders heading and input', () => {
    renderPage();
    expect(screen.getByText(/ingest content/i)).toBeInTheDocument();
  });

  it('renders File path and URL mode buttons', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /file path/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /url/i })).toBeInTheDocument();
  });

  it('ingest button is disabled when input is empty', () => {
    renderPage();
    const btn = screen.getByRole('button', { name: /ingest/i });
    expect(btn).toBeDisabled();
  });

  it('enables ingest button when input has value', () => {
    renderPage();
    const input = screen.getByPlaceholderText(/\/path\/to\/note/i);
    fireEvent.change(input, { target: { value: '/tmp/note.md' } });
    const btn = screen.getByRole('button', { name: /ingest/i });
    expect(btn).not.toBeDisabled();
  });

  it('successful URL ingest shows job queued message', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /url/i }));
    const input = screen.getByPlaceholderText(/https/i);
    fireEvent.change(input, { target: { value: 'https://example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    await waitFor(() =>
      expect(screen.getByText(/job queued/i)).toBeInTheDocument()
    );
  });

  it('URL ingest calls api.ingestUrl with correct args', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /url/i }));
    const input = screen.getByPlaceholderText(/https/i);
    fireEvent.change(input, { target: { value: 'https://example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    await waitFor(() =>
      expect(mockIngestUrl).toHaveBeenCalledWith(
        expect.objectContaining({ url: 'https://example.com' })
      )
    );
  });

  it('pressing Enter in URL input triggers ingest', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /url/i }));
    const input = screen.getByPlaceholderText(/https/i);
    fireEvent.change(input, { target: { value: 'https://example.com/enter' } });
    fireEvent.submit(input.closest('form')!);
    await waitFor(() =>
      expect(mockIngestUrl).toHaveBeenCalled()
    );
  });

  it('file path ingest calls api.ingestFile with correct args', async () => {
    renderPage();
    const input = screen.getByPlaceholderText(/\/path\/to\/note/i);
    fireEvent.change(input, { target: { value: '/tmp/note.md' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    await waitFor(() =>
      expect(mockIngestFile).toHaveBeenCalledWith(
        expect.objectContaining({ file_path: '/tmp/note.md' })
      )
    );
  });

  it('successful file ingest shows job queued message', async () => {
    renderPage();
    const input = screen.getByPlaceholderText(/\/path\/to\/note/i);
    fireEvent.change(input, { target: { value: '/tmp/note.md' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    await waitFor(() =>
      expect(screen.getByText(/job queued/i)).toBeInTheDocument()
    );
  });
});
