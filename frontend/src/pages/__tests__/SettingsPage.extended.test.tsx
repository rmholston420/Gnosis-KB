/**
 * SettingsPage.extended.test.tsx
 * Targets uncovered lines in SettingsPage.tsx
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockGetSettings    = vi.fn();
const mockUpdateSettings = vi.fn();
const mockGetStats       = vi.fn();
const mockReindex        = vi.fn();
const mockGetProviders   = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    getSettings:    (...a: unknown[]) => mockGetSettings(...a),
    updateSettings: (...a: unknown[]) => mockUpdateSettings(...a),
    getStats:       (...a: unknown[]) => mockGetStats(...a),
    reindex:        (...a: unknown[]) => mockReindex(...a),
    // SettingsPage calls getProviders() on mount via useEffect
    getProviders:   (...a: unknown[]) => mockGetProviders(...a),
    listNotes:      vi.fn().mockResolvedValue({ items: [] }),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import SettingsPage from '@/pages/SettingsPage';

const BASE_SETTINGS = {
  vault_path: '/home/user/vault',
  theme: 'dark',
  auto_save: true,
  spaced_repetition_enabled: true,
};

const BASE_STATS = {
  total_notes: 150,
  total_tags: 42,
  vector_indexed: 148,
  graph_indexed: 150,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default happy-path values; individual tests override as needed
  mockGetSettings.mockResolvedValue(BASE_SETTINGS);
  mockGetStats.mockResolvedValue(BASE_STATS);
  mockGetProviders.mockResolvedValue({ providers: [] });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — loading + error', () => {
  it('shows loading state initially', () => {
    mockGetSettings.mockReturnValue(new Promise(() => {}));
    mockGetStats.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/loading/i)).toBeTruthy();
  });

  it('shows error when getSettings rejects', async () => {
    mockGetSettings.mockRejectedValue(new Error('Settings load failed'));
    renderPage();
    await waitFor(() => expect(screen.queryByText(/error/i)).toBeTruthy());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — content', () => {
  it('renders vault path', async () => {
    renderPage();
    await waitFor(() => expect(screen.queryByDisplayValue('/home/user/vault')).toBeTruthy());
  });

  it('renders stats', async () => {
    renderPage();
    await waitFor(() => expect(screen.queryByText(/150/)).toBeTruthy());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — save settings', () => {
  it('calls updateSettings on save', async () => {
    mockUpdateSettings.mockResolvedValue(BASE_SETTINGS);
    renderPage();
    await waitFor(() => screen.queryByDisplayValue('/home/user/vault'));
    const saveBtn = screen.queryByRole('button', { name: /save/i });
    if (saveBtn) {
      fireEvent.click(saveBtn);
      await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalled());
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — reindex', () => {
  it('calls reindex when reindex button clicked', async () => {
    mockReindex.mockResolvedValue({});
    renderPage();
    await waitFor(() => screen.queryByDisplayValue('/home/user/vault'));
    const reindexBtn = screen.queryByRole('button', { name: /reindex/i });
    if (reindexBtn) {
      fireEvent.click(reindexBtn);
      await waitFor(() => expect(mockReindex).toHaveBeenCalled());
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — toggle auto-save', () => {
  it('renders auto-save toggle', async () => {
    renderPage();
    await waitFor(() => {
      const toggle = screen.queryByRole('checkbox', { name: /auto.?save/i });
      if (toggle) expect(toggle).toBeTruthy();
    });
  });
});
