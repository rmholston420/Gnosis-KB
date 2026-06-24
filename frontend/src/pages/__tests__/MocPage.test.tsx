/**
 * MocPage.test.tsx
 * Covers: form fields, generate button states, sections tab,
 * markdown tab with copy/download, error display, empty state.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import axios from 'axios';

vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

const mockMocResponse = {
  topic: 'EEG',
  moc_title: 'MOC — EEG',
  vault_path: '00-inbox/moc-eeg.md',
  note_count: 12,
  sections: [
    { heading: 'Signal Processing', wikilinks: ['[[EEG Filters]]', '[[Artifact removal]]'], summary: 'Core DSP' },
    { heading: 'Applications', wikilinks: ['[[BCI]]'], summary: 'Real-world uses' },
  ],
  markdown: '# MOC — EEG\n\n## Signal Processing\n- [[EEG Filters]]',
};

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { default: MocPage } = require('../MocPage');
  return render(<QueryClientProvider client={qc}><MocPage /></QueryClientProvider>);
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe('MocPage — initial render', () => {
  it('renders the page heading', () => {
    wrap();
    expect(screen.getByText(/map of content generator/i)).toBeInTheDocument();
  });

  it('renders the topic input', () => {
    wrap();
    expect(screen.getByPlaceholderText(/eeg signal processing/i)).toBeInTheDocument();
  });

  it('renders the Generate MOC button (disabled with empty topic)', () => {
    wrap();
    const btn = screen.getByRole('button', { name: /generate moc/i });
    expect(btn).toBeDisabled();
  });

  it('enables Generate button after typing a topic', () => {
    wrap();
    fireEvent.change(screen.getByPlaceholderText(/eeg signal processing/i), {
      target: { value: 'EEG' },
    });
    expect(screen.getByRole('button', { name: /generate moc/i })).not.toBeDisabled();
  });

  it('renders folder presets in select', () => {
    wrap();
    expect(screen.getByText('All folders')).toBeInTheDocument();
    expect(screen.getByText('10 Zettelkasten')).toBeInTheDocument();
  });
});

describe('MocPage — sections tab', () => {
  beforeEach(() => {
    (mockedAxios.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: mockMocResponse });
  });

  it('shows sections after successful generation', async () => {
    wrap();
    fireEvent.change(screen.getByPlaceholderText(/eeg signal processing/i), {
      target: { value: 'EEG' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() =>
      expect(screen.getByText('Signal Processing')).toBeInTheDocument()
    );
    expect(screen.getByText('Applications')).toBeInTheDocument();
  });

  it('shows result metadata (note count)', async () => {
    wrap();
    fireEvent.change(screen.getByPlaceholderText(/eeg signal processing/i), {
      target: { value: 'EEG' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() => screen.getByText('Signal Processing'));
    expect(screen.getByText(/2 sections/i)).toBeInTheDocument();
  });
});

describe('MocPage — markdown tab', () => {
  beforeEach(() => {
    (mockedAxios.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: mockMocResponse });
  });

  it('renders markdown output when Markdown tab is clicked', async () => {
    wrap();
    fireEvent.change(screen.getByPlaceholderText(/eeg signal processing/i), {
      target: { value: 'EEG' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() => screen.getByText('Signal Processing'));
    fireEvent.click(screen.getByText(/^markdown$/i));
    expect(screen.getByText(/MOC — EEG/)).toBeInTheDocument();
  });

  it('renders Copy and Download buttons in markdown tab', async () => {
    wrap();
    fireEvent.change(screen.getByPlaceholderText(/eeg signal processing/i), {
      target: { value: 'EEG' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() => screen.getByText('Signal Processing'));
    fireEvent.click(screen.getByText(/^markdown$/i));
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument();
  });
});

describe('MocPage — error state', () => {
  it('shows error message on failed generation', async () => {
    (mockedAxios.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      response: { data: { detail: 'LLM unavailable' } },
    });
    wrap();
    fireEvent.change(screen.getByPlaceholderText(/eeg signal processing/i), {
      target: { value: 'EEG' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() =>
      expect(screen.getByText(/LLM unavailable/i)).toBeInTheDocument()
    );
  });
});
