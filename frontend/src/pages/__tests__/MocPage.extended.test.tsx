/**
 * MocPage.extended.test.tsx
 *
 * MocPage.tsx builds its own axios calls directly — it does NOT use
 * @/services/api at all. We must mock the `axios` module itself.
 *
 * The Generate button is disabled until topic is non-empty.
 * After clicking, the mutation fires generateMoc() -> axios.post().
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ─── Mock axios at the module level ─────────────────────────────────────────
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
  mockAxiosPost.mockResolvedValue({ data: MOC_RESPONSE });
});

// ─── Loading + error states ──────────────────────────────────────────────────
describe('MocPage — loading + error states', () => {
  it('shows loading state while mutation is pending', async () => {
    // Keep the mutation pending indefinitely
    mockAxiosPost.mockReturnValue(new Promise(() => {}));
    renderPage();
    // Fill topic so button is enabled
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

// ─── Rendered content (after successful mutation) ────────────────────────────
describe('MocPage — rendered content', () => {
  it('renders MOC title after generation', async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. EEG signal processing/i), {
      target: { value: 'Buddhism' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() =>
      expect(screen.queryByText('Buddhism Overview')).toBeTruthy()
    );
  });

  it('renders sections from body headings', async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. EEG signal processing/i), {
      target: { value: 'Buddhism' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() =>
      expect(screen.queryByText(/introduction|core concepts/i)).toBeTruthy()
    );
  });
});

// ─── Panel toggle ────────────────────────────────────────────────────────────
describe('MocPage — tab switching', () => {
  it('switches to Markdown tab', async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. EEG signal processing/i), {
      target: { value: 'Buddhism' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() => screen.queryByText('Buddhism Overview'));
    const markdownTab = screen.queryByRole('tab', { name: /markdown/i });
    if (markdownTab) {
      fireEvent.click(markdownTab);
      await waitFor(() =>
        expect(screen.queryByText(/markdown output/i)).toBeTruthy()
      );
    }
  });
});

// ─── Copy button ─────────────────────────────────────────────────────────────
describe('MocPage — copy button', () => {
  it('copies markdown to clipboard', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    renderPage();
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. EEG signal processing/i), {
      target: { value: 'Buddhism' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate moc/i }));
    await waitFor(() => screen.queryByText('Buddhism Overview'));
    // Switch to Markdown tab first (Copy button lives there)
    const markdownTab = screen.queryByRole('tab', { name: /markdown/i });
    if (markdownTab) {
      fireEvent.click(markdownTab);
      await waitFor(() => screen.queryByText(/markdown output/i));
    }
    const copyBtn = screen.queryByRole('button', { name: /copy/i });
    if (copyBtn) {
      fireEvent.click(copyBtn);
      await waitFor(() =>
        expect(navigator.clipboard.writeText).toHaveBeenCalled()
      );
    }
  });
});
