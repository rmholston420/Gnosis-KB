/**
 * IngestPage.test.tsx
 * ===================
 * IngestPage renders both file-drop and URL sections unconditionally —
 * there is no tab-toggle. The URL input is always in the DOM.
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

// react-router-dom navigate is used after a successful ingest
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><IngestPage /></MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  mockIngestUrl.mockReset();
  mockIngestFile.mockReset();
  // Resolve with a Note-like object matching what IngestPage destructures
  mockIngestUrl.mockResolvedValue({ id: 'note-1', title: 'Ingested Article' });
  mockIngestFile.mockResolvedValue({ id: 'note-2', title: 'Uploaded File' });
});

describe('IngestPage', () => {
  it('renders without crashing', () => {
    renderPage();
    expect(document.body).toBeInTheDocument();
  });

  it('renders a URL input field', () => {
    renderPage();
    // URL section is always visible — no mode-toggle needed
    expect(screen.getByPlaceholderText(/https/i)).toBeInTheDocument();
  });

  it('renders an Ingest button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /ingest/i })).toBeInTheDocument();
  });

  it('calls ingestUrl when URL form is submitted', async () => {
    renderPage();
    const urlInput = screen.getByPlaceholderText(/https/i);
    fireEvent.change(urlInput, { target: { value: 'https://example.com/article' } });
    fireEvent.click(screen.getByRole('button', { name: /^ingest$/i }));
    await waitFor(() =>
      expect(mockIngestUrl).toHaveBeenCalledWith(
        'https://example.com/article',
        undefined
      )
    );
  });

  it('shows success message after successful URL ingest', async () => {
    renderPage();
    const urlInput = screen.getByPlaceholderText(/https/i);
    fireEvent.change(urlInput, { target: { value: 'https://example.com/article' } });
    fireEvent.click(screen.getByRole('button', { name: /^ingest$/i }));
    await waitFor(() =>
      expect(screen.getByText(/ingested/i)).toBeInTheDocument()
    );
  });
});
