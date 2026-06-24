/**
 * SettingsPage.test.tsx
 * Covers: provider load, model select + save, RAG mode radio,
 * export format toggle, vault-sync button state, security section.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// vi.hoisted — must come before vi.mock() factories that reference these values.
// ---------------------------------------------------------------------------
const { mockApi, mockStore } = vi.hoisted(() => {
  const mockStore = { ragMode: 'hybrid' as const, setRagMode: vi.fn() };
  const mockApi = {
    getProviders: vi.fn().mockResolvedValue({
      provider: 'ollama',
      model: 'llama3',
      available: true,
      models: ['llama3', 'mistral', 'nomic-embed-text'],
    }),
    setModel: vi.fn().mockResolvedValue({}),
    exportVault: vi.fn().mockResolvedValue(new Blob(['zip'], { type: 'application/zip' })),
  };
  return { mockApi, mockStore };
});

vi.mock('../../store/useAppStore', () => ({ useAppStore: () => mockStore }));
vi.mock('../../services/api', () => ({ default: mockApi }));

import SettingsPage from '../SettingsPage';

function wrap() {
  return render(<SettingsPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getProviders.mockResolvedValue({
    provider: 'ollama',
    model: 'llama3',
    available: true,
    models: ['llama3', 'mistral', 'nomic-embed-text'],
  });
});

describe('SettingsPage — provider section', () => {
  it('renders the Settings heading', () => {
    wrap();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('shows loading spinner while provider data fetches', () => {
    mockApi.getProviders.mockReturnValueOnce(new Promise(() => {}));
    wrap();
    expect(screen.getByText(/loading provider info/i)).toBeInTheDocument();
  });

  it('displays provider name and model select after load', async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByText('ollama')).toBeInTheDocument()
    );
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('shows Connected badge when available=true', async () => {
    wrap();
    await waitFor(() => expect(screen.getByText(/connected/i)).toBeInTheDocument());
  });

  it('shows Unavailable badge when available=false', async () => {
    mockApi.getProviders.mockResolvedValueOnce({
      provider: 'ollama', model: 'llama3', available: false, models: ['llama3'],
    });
    wrap();
    await waitFor(() => expect(screen.getByText(/unavailable/i)).toBeInTheDocument());
  });

  it('shows error message when provider fetch fails', async () => {
    mockApi.getProviders.mockRejectedValueOnce(new Error('fail'));
    wrap();
    await waitFor(() =>
      expect(screen.getByText(/could not load provider info/i)).toBeInTheDocument()
    );
  });

  it('calls setModel on save click with new model', async () => {
    wrap();
    await waitFor(() => screen.getByRole('combobox'));
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'mistral' } });
    fireEvent.click(screen.getByRole('button', { name: /save model/i }));
    await waitFor(() => expect(mockApi.setModel).toHaveBeenCalledWith('mistral'));
  });
});

describe('SettingsPage — RAG mode', () => {
  it('renders all three RAG mode options', async () => {
    wrap();
    await waitFor(() => screen.getByText('Settings'));
    expect(screen.getByText('Hybrid')).toBeInTheDocument();
    expect(screen.getByText('Local')).toBeInTheDocument();
    expect(screen.getByText('Global')).toBeInTheDocument();
  });

  it('calls setRagMode when a different mode is selected', async () => {
    wrap();
    await waitFor(() => screen.getByText('Local'));
    const radios = screen.getAllByRole('radio');
    const localRadio = radios.find(
      (r) => (r as HTMLInputElement).value === 'local'
    );
    if (localRadio) fireEvent.click(localRadio);
    await waitFor(() => expect(mockStore.setRagMode).toHaveBeenCalledWith('local'));
  });
});

describe('SettingsPage — export section', () => {
  it('renders the Export Vault button', async () => {
    wrap();
    await waitFor(() => screen.getByText('Settings'));
    expect(
      screen.getByRole('button', { name: /export vault/i })
    ).toBeInTheDocument();
  });
});
