/**
 * SettingsPage.extended.test.tsx
 * Targets uncovered lines in SettingsPage.tsx
 *
 * Key fix: getProviders must return a full ProviderInfo shape so
 * SettingsPage.tsx doesn't crash on providerInfo.models.map().
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
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

// Full ProviderInfo shape — models[] must be present to avoid crash at line 175
const PROVIDER_INFO = {
  provider: 'ollama',
  model: 'mistral',
  available: true,
  models: ['mistral', 'llama3'],
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
  mockGetProviders.mockResolvedValue(PROVIDER_INFO);
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — loading + error', () => {
  it('shows loading state initially', () => {
    // Keep getProviders pending so loading spinner stays visible
    mockGetProviders.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/loading provider info/i)).toBeTruthy();
  });

  it('shows error when getProviders rejects', async () => {
    mockGetProviders.mockRejectedValue(new Error('Provider load failed'));
    renderPage();
    await waitFor(() =>
      expect(screen.queryByText(/could not load provider/i)).toBeTruthy()
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — content', () => {
  it('renders provider name after load', async () => {
    renderPage();
    await waitFor(() => expect(screen.queryByText('ollama')).toBeTruthy());
  });

  it('renders model selector with options', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByRole('option', { name: 'mistral' })).toBeTruthy()
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — save model', () => {
  it('Save model button is present after load', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /save model/i })).toBeTruthy()
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — sync', () => {
  it('Sync Now button is present', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /sync now/i })).toBeTruthy()
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
describe('SettingsPage — export', () => {
  it('Export Vault button is present', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /export vault/i })).toBeTruthy()
    );
  });
});
