/**
 * IngestPage.test.tsx
 * ===================
 * IngestPage uses useMutation directly, so tests must provide a
 * QueryClientProvider.
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
  mockIngestUrl.mockResolvedValue({ job_id: 'job-1' });
  mockIngestFile.mockResolvedValue({ job_id: 'job-2' });
});

describe('IngestPage', () => {
  it('renders without crashing', () => {
    renderPage();
    expect(document.body).toBeInTheDocument();
  });

  it('renders a URL input field when URL mode selected', () => {
    renderPage();
    // Switch to URL mode
    fireEvent.click(screen.getByRole('button', { name: /url/i }));
    expect(screen.getByPlaceholderText(/https/i)).toBeInTheDocument();
  });

  it('renders an Ingest button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /ingest/i })).toBeInTheDocument();
  });

  it('calls ingestUrl when URL form is submitted', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /url/i }));
    const urlInput = screen.getByPlaceholderText(/https/i);
    fireEvent.change(urlInput, { target: { value: 'https://example.com/article' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    await waitFor(() =>
      expect(mockIngestUrl).toHaveBeenCalledWith(
        expect.objectContaining({ url: 'https://example.com/article' })
      )
    );
  });

  it('shows job queued message after successful URL ingest', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /url/i }));
    const urlInput = screen.getByPlaceholderText(/https/i);
    fireEvent.change(urlInput, { target: { value: 'https://example.com/article' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    await waitFor(() =>
      expect(screen.getByText(/job queued/i)).toBeInTheDocument()
    );
  });
});
