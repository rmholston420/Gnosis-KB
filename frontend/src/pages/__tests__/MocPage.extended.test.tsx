/**
 * MocPage.extended.test.tsx
 *
 * MocPage.tsx uses raw axios calls — vi.mock('axios') is required.
 * waitFor callbacks MUST use expect().toBeTruthy() so waitFor retries
 * on failure; queryByText/queryByRole return null (no throw) and would
 * exit waitFor immediately without the assertion wrapper.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockAxiosPost = vi.fn();
vi.mock('axios', () => ({
  default: {
    post:   (...a: unknown[]) => mockAxiosPost(...a),
    get:    vi.fn().mockResolvedValue({ data: [] }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
    create: vi.fn().mockReturnThis(),
  },
}));

import MocPage from '@/pages/MocPage';

const MOC_RESPONSE = {
  topic: 'Buddhism',
  moc_title: 'Buddhism Overview',
  vault_path: '00-maps/Buddhism Overview.md',
  sections: [
    {
      heading: 'Introduction',
      wikilinks: ['Emptiness', 'Dependent Origination'],
      summary: 'Core concepts of Buddhist philosophy.',
    },
    {
      heading: 'Core Concepts',
      wikilinks: ['Sunyata', 'Pratityasamutpada'],
      summary: 'Key teachings.',
    },
  ],
  markdown: '# Buddhism Overview\n\n## Introduction\n\n## Core Concepts\n',
  note_count: 24,
};

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter>
        <MocPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockAxiosPost.mockResolvedValue({ data: MOC_RESPONSE });
});

// Helper: fill topic and click Generate, then wait for result title
async function generateMoc() {
  fireEvent.change(screen.getByPlaceholderText(/e\.g\. EEG signal processing/i), {
    target: { value: 'Buddhism' },
  });
  fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
  // waitFor MUST assert (throws on failure) so it retries until title appears
  await waitFor(() =>
    expect(screen.queryByText('Buddhism Overview')).toBeTruthy()
  );
}

describe('MocPage — loading + error states', () => {
  it('shows loading state while mutation is pending', async () => {
    mockAxiosPost.mockReturnValue(new Promise(() => {}));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. EEG signal processing/i), {
      target: { value: 'Buddhism' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() =>
      expect(screen.queryByText(/generating/i)).toBeTruthy()
    );
  });

  it('shows error state when mutation rejects', async () => {
    mockAxiosPost.mockRejectedValue(new Error('Network Error'));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. EEG signal processing/i), {
      target: { value: 'Buddhism' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() =>
      expect(screen.queryByText(/error|network error|generation failed/i)).toBeTruthy()
    );
  });
});

describe('MocPage — rendered content', () => {
  it('renders MOC title after generation', async () => {
    renderPage();
    await generateMoc();
    // title appears in the sidebar result box
    expect(screen.getByText('Buddhism Overview')).toBeInTheDocument();
  });

  it('renders section headings from response', async () => {
    renderPage();
    await generateMoc();
    // MocSectionCard renders heading inside nested spans —
    // check document text content rather than a single node
    await waitFor(() =>
      expect(document.body.textContent).toMatch(/Introduction/)
    );
    expect(document.body.textContent).toMatch(/Core Concepts/);
  });
});

describe('MocPage — tab switching', () => {
  it('switches to Markdown tab and shows Markdown Output header', async () => {
    renderPage();
    await generateMoc();
    const markdownTab = screen.getByRole('tab', { name: /markdown/i });
    fireEvent.click(markdownTab);
    await waitFor(() =>
      expect(screen.queryByText(/markdown output/i)).toBeTruthy()
    );
  });
});

describe('MocPage — copy button', () => {
  it('copies markdown to clipboard', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    renderPage();
    await generateMoc();
    const markdownTab = screen.getByRole('tab', { name: /markdown/i });
    fireEvent.click(markdownTab);
    await waitFor(() => expect(screen.queryByText(/markdown output/i)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /copy/i }));
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalled()
    );
  });
});
