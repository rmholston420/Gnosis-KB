/**
 * SettingsPage.test.tsx
 * Covers: provider load, model select + save, RAG mode radio,
 * export format toggle, vault-sync button state, security section.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockStore = { ragMode: 'hybrid', setRagMode: vi.fn() };
vi.mock('../../store/useAppStore', () => ({ useAppStore: () => mockStore }));

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
    const radios = screen.getAllByRole('radio', { name: '' });
    // There are RAG radios + export radios; check RAG labels
    expect(screen.getByText('Hybrid')).toBeInTheDocument();
    expect(screen.getByText('Local')).toBeInTheDocument();
    expect(screen.getByText('Global')).toBeInTheDocument();
  });

  it('calls setRagMode when a different mode is selected', async () => {
    wrap();
    await waitFor(() => screen.getByText('Local'));
    // Find the radio input for Local and click it
    const radios = screen.getAllByRole('radio');
    // hybrid is checked by default (index 0 among rag radios)
    const localRadio = radios.find((r) => (r as HTMLInputElement).value === 'local');
    expect(localRadio).toBeTruthy();
    fireEvent.click(localRadio!);
    expect(mockStore.setRagMode).toHaveBeenCalledWith('local');
  });
});

describe('SettingsPage — export', () => {
  it('renders markdown and JSON format options', async () => {
    wrap();
    await waitFor(() => screen.getByText('Markdown ZIP'));
    expect(screen.getByText('JSON')).toBeInTheDocument();
  });

  it('renders Download export button', async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /download export/i })).toBeInTheDocument()
    );
  });
});

describe('SettingsPage — vault sync', () => {
  it('renders Sync Now button', async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /sync now/i })).toBeInTheDocument()
    );
  });
});

describe('SettingsPage — security', () => {
  it('renders security section heading', async () => {
    wrap();
    await waitFor(() => expect(screen.getByText('Security')).toBeInTheDocument());
  });

  it('mentions JWT', async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByText(/jwt-based/i)).toBeInTheDocument()
    );
  });
});
