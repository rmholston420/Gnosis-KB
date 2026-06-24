/**
 * MocPage.test.tsx
 * Covers: form fields, generate button states, sections tab,
 * markdown tab with copy/download, error display, empty state.
 *
 * Axios is stubbed via vi.hoisted() — NOT via vi.mock('axios') automock.
 * vi.mock() factories are hoisted to the top of the file by Vitest, so any
 * variable referenced inside must itself be created with vi.hoisted().
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---------------------------------------------------------------------------
// Hoist axios stubs so the vi.mock factory can reference them.
// ---------------------------------------------------------------------------
const { mockPost } = vi.hoisted(() => ({
  mockPost: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    post: mockPost,
    get: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockMocResponse = {
  topic: 'EEG',
  moc_title: 'MOC — EEG',
  vault_path: '00-inbox/moc-eeg.md',
  note_count: 12,
  sections: [
    {
      heading: 'Signal Processing',
      wikilinks: ['[[EEG Filters]]', '[[Artifact removal]]'],
      summary: 'Core DSP',
    },
    {
      heading: 'Applications',
      wikilinks: ['[[BCI]]'],
      summary: 'Real-world uses',
    },
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
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getByText(/all folders/i)).toBeInTheDocument();
  });
});

describe('MocPage — sections tab', () => {
  async function generate() {
    mockPost.mockResolvedValueOnce({ data: mockMocResponse });
    wrap();
    fireEvent.change(screen.getByPlaceholderText(/eeg signal processing/i), {
      target: { value: 'EEG' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() =>
      expect(screen.getByText('Signal Processing')).toBeInTheDocument()
    );
  }

  it('shows sections after successful generation', async () => {
    await generate();
    expect(screen.getByText('Signal Processing')).toBeInTheDocument();
    expect(screen.getByText('Applications')).toBeInTheDocument();
  });

  it('shows result metadata (note count)', async () => {
    await generate();
    expect(screen.getByText(/12/)).toBeInTheDocument();
  });
});

describe('MocPage — markdown tab', () => {
  async function generateAndSwitchTab() {
    mockPost.mockResolvedValueOnce({ data: mockMocResponse });
    wrap();
    fireEvent.change(screen.getByPlaceholderText(/eeg signal processing/i), {
      target: { value: 'EEG' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() => screen.getByText('Signal Processing'));
    fireEvent.click(screen.getByRole('tab', { name: /markdown/i }));
  }

  it('renders markdown output when Markdown tab is clicked', async () => {
    await generateAndSwitchTab();
    expect(screen.getByText(/# MOC/)).toBeInTheDocument();
  });

  it('renders Copy and Download buttons in markdown tab', async () => {
    await generateAndSwitchTab();
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument();
  });
});

describe('MocPage — error state', () => {
  it('shows error message on failed generation', async () => {
    mockPost.mockRejectedValueOnce(new Error('Network error'));
    wrap();
    fireEvent.change(screen.getByPlaceholderText(/eeg signal processing/i), {
      target: { value: 'EEG' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() =>
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    );
  });
});
