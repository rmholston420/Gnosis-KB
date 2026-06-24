/**
 * IngestPage.extended.test.tsx
 * Covers file upload, URL ingest, error/success banners, empty-URL guard,
 * Enter-key shortcut, and navigate-to-notes button.
 * Uncovered lines: 17-32, 46, 67-69, 82
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// ---- Mocks -----------------------------------------------------------------
const mockIngestFile = vi.fn();
const mockIngestUrl  = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    ingestFile: (...a: unknown[]) => mockIngestFile(...a),
    ingestUrl:  (...a: unknown[]) => mockIngestUrl(...a),
  },
}));

// react-dropzone: expose onDrop so we can call it directly
let capturedOnDrop: ((files: File[]) => void) | null = null;
vi.mock('react-dropzone', () => ({
  useDropzone: (opts: { onDrop: (files: File[]) => void }) => {
    capturedOnDrop = opts.onDrop;
    return {
      getRootProps: () => ({ 'data-testid': 'dropzone' }),
      getInputProps: () => ({ 'data-testid': 'file-input' }),
      isDragActive: false,
    };
  },
}));

import IngestPage from '@/pages/IngestPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderPage() {
  return render(
    <MemoryRouter>
      <IngestPage />
    </MemoryRouter>
  );
}

describe('IngestPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedOnDrop = null;
  });

  it('renders heading and drop zone', () => {
    renderPage();
    expect(screen.getByText(/Ingest Content/i)).toBeTruthy();
    expect(screen.getByTestId('dropzone')).toBeTruthy();
  });

  it('renders URL input and ingest button', () => {
    renderPage();
    expect(screen.getByPlaceholderText(/https:/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /ingest/i })).toBeTruthy();
  });

  it('ingest button is disabled when URL is empty', () => {
    renderPage();
    const btn = screen.getByRole('button', { name: /ingest/i });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it('enables ingest button when URL has value', () => {
    renderPage();
    const input = screen.getByPlaceholderText(/https:/i);
    fireEvent.change(input, { target: { value: 'https://example.com' } });
    const btn = screen.getByRole('button', { name: /ingest/i });
    expect((btn as HTMLButtonElement).disabled).toBe(false);
  });

  it('successful URL ingest shows success banner and navigates', async () => {
    mockIngestUrl.mockResolvedValue({ id: 'n1', title: 'Test Article' });
    renderPage();
    const input = screen.getByPlaceholderText(/https:/i);
    fireEvent.change(input, { target: { value: 'https://example.com/article' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    await waitFor(() => expect(screen.getByText(/Ingested:/i)).toBeTruthy());
    expect(mockNavigate).toHaveBeenCalledWith('/notes/n1');
  });

  it('URL ingest error shows error banner', async () => {
    mockIngestUrl.mockRejectedValue(new Error('Network error'));
    renderPage();
    const input = screen.getByPlaceholderText(/https:/i);
    fireEvent.change(input, { target: { value: 'https://bad.url' } });
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    await waitFor(() => expect(screen.getByText(/Network error/i)).toBeTruthy());
  });

  it('pressing Enter in URL input triggers ingest', async () => {
    mockIngestUrl.mockResolvedValue({ id: 'n2', title: 'Key Article' });
    renderPage();
    const input = screen.getByPlaceholderText(/https:/i);
    fireEvent.change(input, { target: { value: 'https://example.com/key' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(mockIngestUrl).toHaveBeenCalled());
  });

  it('non-Enter keydown does not trigger ingest', async () => {
    renderPage();
    const input = screen.getByPlaceholderText(/https:/i);
    fireEvent.change(input, { target: { value: 'https://example.com' } });
    fireEvent.keyDown(input, { key: 'a' });
    await new Promise((r) => setTimeout(r, 50));
    expect(mockIngestUrl).not.toHaveBeenCalled();
  });

  it('file drop triggers handleFiles and shows success', async () => {
    mockIngestFile.mockResolvedValue({ id: 'f1', title: 'Uploaded Note' });
    renderPage();
    expect(capturedOnDrop).toBeTruthy();
    const fakeFile = new File(['content'], 'test.md', { type: 'text/markdown' });
    await act(async () => { capturedOnDrop?.([fakeFile]); });
    await waitFor(() =>
      expect(screen.getByText(/Uploaded 1 file/i)).toBeTruthy()
    );
  });

  it('file drop error shows error banner', async () => {
    mockIngestFile.mockRejectedValue(new Error('File too large'));
    renderPage();
    const fakeFile = new File(['x'], 'big.pdf', { type: 'application/pdf' });
    await act(async () => { capturedOnDrop?.([fakeFile]); });
    await waitFor(() =>
      expect(screen.getByText(/File too large/i)).toBeTruthy()
    );
  });

  it('View all notes button navigates to /notes', () => {
    renderPage();
    const btn = screen.getByRole('button', { name: /View all notes/i });
    fireEvent.click(btn);
    expect(mockNavigate).toHaveBeenCalledWith('/notes');
  });
});
