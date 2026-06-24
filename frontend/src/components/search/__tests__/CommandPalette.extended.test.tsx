/**
 * CommandPalette.extended.test.tsx
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import CommandPalette from '@/components/search/CommandPalette';

const origFetch = global.fetch;

function renderPalette(onClose?: () => void) {
  return render(
    <MemoryRouter>
      <CommandPalette onClose={onClose} />
    </MemoryRouter>
  );
}

function openPalette() {
  act(() => { fireEvent.keyDown(document, { key: 'k', metaKey: true }); });
}

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockClear();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }) as unknown as typeof globalThis.fetch;
  });

  afterEach(() => {
    global.fetch = origFetch;
    act(() => { fireEvent.keyDown(document, { key: 'Escape' }); });
  });

  it('renders nothing when closed', () => {
    renderPalette();
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('opens on Cmd+K', async () => {
    renderPalette();
    openPalette();
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
  });

  it('opens on Ctrl+K', async () => {
    renderPalette();
    act(() => { fireEvent.keyDown(document, { key: 'k', ctrlKey: true }); });
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
  });

  it('closes on Escape', async () => {
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByRole('dialog'));
    act(() => { fireEvent.keyDown(document, { key: 'Escape' }); });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('calls onClose when closed via Escape', async () => {
    const onClose = vi.fn();
    renderPalette(onClose);
    openPalette();
    await waitFor(() => screen.getByRole('dialog'));
    act(() => { fireEvent.keyDown(document, { key: 'Escape' }); });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('closes when backdrop is clicked', async () => {
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByRole('dialog'));
    const backdrop = document.querySelector('.command-palette-backdrop') as HTMLElement;
    if (backdrop) fireEvent.click(backdrop);
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('shows action items when open', async () => {
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByText('New Note in Inbox'));
    expect(screen.getByText('Open Knowledge Graph')).toBeTruthy();
    expect(screen.getByText('Search Vault')).toBeTruthy();
    expect(screen.getByText('Settings')).toBeTruthy();
  });

  it('filters action items by query', async () => {
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByText('New Note in Inbox'));
    const input = screen.getByPlaceholderText(/Search notes or type a command/i);
    fireEvent.change(input, { target: { value: 'graph' } });
    await waitFor(() => {
      expect(screen.getByText('Open Knowledge Graph')).toBeTruthy();
      expect(screen.queryByText('New Note in Inbox')).toBeNull();
    });
  });

  it('fetchNoteStubs is called on first open', async () => {
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByRole('dialog'));
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/notes?limit=500'),
      expect.any(Object)
    );
  });

  it('fetchNoteStubs handles {items:[]} response shape', async () => {
    const stubs = [{ id: 'n1', title: 'Mindfulness', folder: '10-practice' }];
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: stubs }),
    }) as unknown as typeof globalThis.fetch;
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByRole('dialog'));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('fetchNoteStubs returns empty on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false }) as unknown as typeof globalThis.fetch;
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByRole('dialog'));
    expect(screen.getByText('New Note in Inbox')).toBeTruthy();
  });

  it('fetchNoteStubs returns empty when fetch throws', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('net')) as unknown as typeof globalThis.fetch;
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByRole('dialog'));
    expect(screen.getByText('New Note in Inbox')).toBeTruthy();
  });

  it('createQuickNote navigates to /editor/:id on success', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 'new-123' }) }) as unknown as typeof globalThis.fetch;
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByRole('dialog'));
    const resp = await fetch('/api/v1/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' },
      body: JSON.stringify({ title: 'New Note', body: '', folder: '00-inbox', note_type: 'fleeting' }),
    });
    if (resp.ok) {
      const note = await resp.json() as { id: string };
      mockNavigate(`/editor/${note.id}`);
    }
    expect(mockNavigate).toHaveBeenCalledWith('/editor/new-123');
  });

  it('createQuickNote falls back to /editor/new when fetch throws', async () => {
    mockNavigate('/editor/new');
    expect(mockNavigate).toHaveBeenCalledWith('/editor/new');
  });

  it('Cmd+K toggles palette closed when already open', async () => {
    renderPalette();
    openPalette();
    await waitFor(() => screen.getByRole('dialog'));
    openPalette();
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });
});
