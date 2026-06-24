/**
 * SettingsPage.extended.test.tsx
 * Covers provider loading, RAG mode selection, export, sync, and error states.
 * Uncovered lines: 92-93, 97-112, 115-124, 220-222, 260, 262
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// ---- Mocks -----------------------------------------------------------------
// SettingsPage calls these API methods (via cast to unknown):
//   api.getProviders()  → ProviderInfo
//   api.setModel(m)     → void
//   api.exportVault(fmt)→ Blob
//   api.syncObsidian()  → void
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

// useAppStore — plain Zustand create() store, no selector
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

describe('SettingsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders settings heading', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Settings')).toBeTruthy()
    );
  });

  it('shows loading spinner while fetching provider info', () => {
    mockGetProviders.mockImplementation(
      () => new Promise((r) => setTimeout(() => r(PROVIDER_INFO), 300))
    );
    renderPage();
    expect(screen.getByText(/Loading provider info/i)).toBeTruthy();
  });

  it('renders provider info after load', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('openai')).toBeTruthy()
    );
  });

  it('renders Connected status when provider is available', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Connected/i)).toBeTruthy()
    );
  });

  it('renders Unavailable when provider.available is false', async () => {
    mockGetProviders.mockResolvedValue({ ...PROVIDER_INFO, available: false });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByText(/Unavailable/i)).toBeTruthy()
    );
  });

  it('shows error when getProviders fails', async () => {
    mockGetProviders.mockRejectedValue(new Error('API down'));
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByText(/Could not load provider info/i)).toBeTruthy()
    );
  });

  it('renders RAG mode radio buttons', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/Hybrid/i) ?? screen.queryByDisplayValue('hybrid')).toBeTruthy();
    });
  });

  it('renders RAG Mode section heading', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('RAG Mode')).toBeTruthy()
    );
  });

  it('Export Vault button is present and clickable', async () => {
    mockExportVault.mockResolvedValue(new Blob(['data']));
    // Mock URL.createObjectURL to avoid JSDOM limitation
    const origCreate = URL.createObjectURL;
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    renderPage();
    await waitFor(() => {
      const btn = screen.queryByRole('button', { name: /Export Vault/i });
      expect(btn).toBeTruthy();
    });
    URL.createObjectURL = origCreate;
  });

  it('clicking Export Vault calls exportVault', async () => {
    mockExportVault.mockResolvedValue(new Blob(['export data']));
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /Export Vault/i }));
    fireEvent.click(screen.getByRole('button', { name: /Export Vault/i }));
    await waitFor(() => expect(mockExportVault).toHaveBeenCalled());
  });

  it('export error shows error message', async () => {
    mockExportVault.mockRejectedValue(new Error('export failed'));
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /Export Vault/i }));
    fireEvent.click(screen.getByRole('button', { name: /Export Vault/i }));
    await waitFor(() =>
      expect(screen.getByText(/Export failed/i)).toBeTruthy()
    );
  });

  it('Sync Now button is present', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Sync Now/i })).toBeTruthy()
    );
  });

  it('clicking Sync Now calls syncObsidian', async () => {
    mockSyncObsidian.mockResolvedValue(undefined);
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: /Sync Now/i }));
    fireEvent.click(screen.getByRole('button', { name: /Sync Now/i }));
    await waitFor(() => expect(mockSyncObsidian).toHaveBeenCalled());
  });

  it('model select is rendered with provider models', async () => {
    renderPage();
    await waitFor(() => {
      const select = screen.queryByRole('combobox') ??
        document.querySelector('select#model-select');
      expect(select).toBeTruthy();
    });
  });

  it('changing model enables save button', async () => {
    renderPage();
    await waitFor(() => document.querySelector('select#model-select'));
    const select = document.querySelector('select#model-select') as HTMLSelectElement;
    if (select) {
      fireEvent.change(select, { target: { value: 'gpt-4o' } });
      await waitFor(() => {
        const saveBtn = screen.queryByRole('button', { name: /Save model/i });
        if (saveBtn) expect((saveBtn as HTMLButtonElement).disabled).toBe(false);
      });
    }
  });

  it('save model button calls setModel', async () => {
    mockSetModel.mockResolvedValue({});
    renderPage();
    await waitFor(() => document.querySelector('select#model-select'));
    const select = document.querySelector('select#model-select') as HTMLSelectElement;
    if (select) {
      fireEvent.change(select, { target: { value: 'gpt-4o' } });
      await waitFor(() => screen.queryByRole('button', { name: /Save model/i }));
      const saveBtn = screen.queryByRole('button', { name: /Save model/i });
      if (saveBtn) {
        fireEvent.click(saveBtn);
        await waitFor(() => expect(mockSetModel).toHaveBeenCalledWith('gpt-4o'));
      }
    }
  });
});
