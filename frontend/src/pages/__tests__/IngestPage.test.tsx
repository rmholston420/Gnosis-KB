/**
 * IngestPage.test.tsx
 * ===================
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IngestPage from '../IngestPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockIngestUrl  = vi.fn();
const mockIngestFile = vi.fn();
vi.mock('../../services/api', () => ({
  default: {
    ingestUrl:  (...args: unknown[]) => mockIngestUrl(...args),
    ingestFile: (...args: unknown[]) => mockIngestFile(...args),
  },
}));

function renderPage() {
  return render(<MemoryRouter><IngestPage /></MemoryRouter>);
}

beforeEach(() => {
  mockIngestUrl.mockReset();
  mockIngestFile.mockReset();
  mockNavigate.mockReset();
  mockIngestUrl.mockResolvedValue({ id: 'new-note', title: 'Example Article' });
  mockIngestFile.mockResolvedValue({ id: 'new-note', title: 'Uploaded File' });
});

describe('IngestPage', () => {
  it('renders without crashing', () => {
    renderPage();
    expect(document.body).toBeInTheDocument();
  });

  it('renders a URL input field', () => {
    renderPage();
    expect(screen.getByPlaceholderText(/https?:|url/i)).toBeInTheDocument();
  });

  it('renders an Ingest / Submit button for URL', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /ingest|submit|import/i })).toBeInTheDocument();
  });

  it('calls ingestUrl when URL form is submitted', async () => {
    renderPage();
    const urlInput = screen.getByPlaceholderText(/https?:|url/i);
    fireEvent.change(urlInput, { target: { value: 'https://example.com/article' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest|submit|import/i }));
    await waitFor(() =>
      expect(mockIngestUrl).toHaveBeenCalledWith('https://example.com/article', undefined)
    );
  });

  it('navigates to the new note after successful URL ingest', async () => {
    renderPage();
    const urlInput = screen.getByPlaceholderText(/https?:|url/i);
    fireEvent.change(urlInput, { target: { value: 'https://example.com/article' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest|submit|import/i }));
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('new-note'))
    );
  });
});
