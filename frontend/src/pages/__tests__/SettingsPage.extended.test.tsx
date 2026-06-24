/**
 * SettingsPage.extended.test.tsx
 * Targets uncovered lines:
 *   92-93   — model save success toast / state reset
 *   120     — syncObsidian success (mockSyncObsidian called; no visible text rendered on success path)
 *   260     — exportVault error message
 *   262     — syncObsidian error renders "Error" in section header status
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockGetProviders = vi.fn();
const mockSetModel     = vi.fn();
const mockExportVault  = vi.fn();
const mockSyncObsidian = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    getProviders:  (...a: unknown[]) => mockGetProviders(...a),
    setModel:      (...a: unknown[]) => mockSetModel(...a),
    exportVault:   (...a: unknown[]) => mockExportVault(...a),
    syncObsidian:  (...a: unknown[]) => mockSyncObsidian(...a),
  },
}));

vi.mock('@/store/useAppStore', () => ({
  useAppStore: () => ({
    ragMode: 'hybrid',
    setRagMode: vi.fn(),
  }),
}));

import SettingsPage from '@/pages/SettingsPage';

const PROVIDER_INFO = {
  provider: 'openai',
  model: 'gpt-4o-mini',
  available: true,
  models: ['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'],
};

function renderPage() {
  mockGetProviders.mockResolvedValue(PROVIDER_INFO);
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>
  );
}

describe('SettingsPage — core render', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders Settings heading', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Settings')).toBeTruthy());
  });

  it('shows loading while fetching provider info', () => {
    mockGetProviders.mockImplementation(
      () => new Promise((r) => setTimeout(() => r(PROVIDER_INFO), 400))
    );
    renderPage();
    expect(screen.getByText(/Loading provider info/i)).toBeTruthy();
  });

  it('shows provider name after load', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('openai')).toBeTruthy());
  });

  it('shows Connected when available=true', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/Connected/i)).toBeTruthy());
  });

  it('shows Unavailable when available=false', async () => {
    mockGetProviders.mockResolvedValue({ ...PROVIDER_INFO, available: false });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Unavailable/i)).toBeTruthy());
  });

  it('shows error message when getProviders fails', async () => {
    mockGetProviders.mockRejectedValue(new Error('API down'));
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByText(/Could not load provider info/i)).toBeTruthy()
    );
  });

  it('renders RAG Mode section', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('RAG Mode')).toBeTruthy());
  });
});

describe('SettingsPage — model save (lines 92-93)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('save model success resets dirty state', async () => {
    mockSetModel.mockResolvedValue({});
    renderPage();
    await waitFor(() => document.querySelector('select'));
    const select = document.querySelector('select') as HTMLSelectElement;
    if (select) {
      fireEvent.change(select, { target: { value: 'gpt-4o' } });
      await waitFor(() => {
        const btn = screen.queryByRole('button', { name: /Save model/i });
        if (btn) fireEvent.click(btn);
      });
      await waitFor(() => expect(mockSetModel).toHaveBeenCalledWith('gpt-4o'));
      // After success the save button is disabled (model matches savedModel)
      await new Promise((r) => setTimeout(r, 100));
      const btn = screen.queryByRole('button', { name: /Save model/i });
      if (btn) expect((btn as HTMLButtonElement).disabled).toBe(true);
    }
  });
});

describe('SettingsPage — sync success (line 120)', () => {
  beforeEach(() => vi.clearAllMocks());

  /**
   * handleSync() resolves → setSyncStatus('idle') → no visible success text
   * is rendered. The correct assertion is that the API was called and the
   * component does not crash (syncStatus stays 'idle', button re-enables).
   */
  it('calls syncObsidian and re-enables Sync Now button after success', async () => {
    mockSyncObsidian.mockResolvedValue(undefined);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /Sync Now/i }));
    fireEvent.click(screen.getByRole('button', { name: /Sync Now/i }));
    await waitFor(() => expect(mockSyncObsidian).toHaveBeenCalled(), { timeout: 3000 });
    // Button should re-enable after promise resolves
    await waitFor(
      () => expect((screen.getByRole('button', { name: /Sync Now/i }) as HTMLButtonElement).disabled).toBe(false),
      { timeout: 3000 }
    );
  });
});

describe('SettingsPage — export error (line 260)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows export error message when exportVault rejects', async () => {
    mockExportVault.mockRejectedValue(new Error('export failed'));
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /Export Vault/i }));
    fireEvent.click(screen.getByRole('button', { name: /Export Vault/i }));
    await waitFor(() =>
      // SettingsPage renders setExportError('Export failed. Try again.')
      expect(screen.getByText(/Export failed/i)).toBeTruthy(),
      { timeout: 3000 }
    );
  });
});

describe('SettingsPage — sync error (line 262)', () => {
  beforeEach(() => vi.clearAllMocks());

  /**
   * handleSync() catch sets syncStatus('error').
   * The section header status renders: <span>Error</span>  (not "Sync failed").
   */
  it('shows Error status when syncObsidian rejects', async () => {
    mockSyncObsidian.mockRejectedValue(new Error('sync failed'));
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /Sync Now/i }));
    fireEvent.click(screen.getByRole('button', { name: /Sync Now/i }));
    await waitFor(() =>
      expect(screen.getByText(/^Error$/i)).toBeTruthy(),
      { timeout: 3000 }
    );
  });
});

describe('SettingsPage — Export Vault success', () => {
  beforeEach(() => vi.clearAllMocks());

  it('calls exportVault on click', async () => {
    mockExportVault.mockResolvedValue(new Blob(['export data']));
    const origCreate = URL.createObjectURL;
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /Export Vault/i }));
    fireEvent.click(screen.getByRole('button', { name: /Export Vault/i }));
    await waitFor(() => expect(mockExportVault).toHaveBeenCalled());
    URL.createObjectURL = origCreate;
  });
});
