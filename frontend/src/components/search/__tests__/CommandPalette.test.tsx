/**
 * CommandPalette.test.tsx
 * =======================
 * Tests for the Cmd+K global command palette.
 *
 * The palette is closed by default and opens on Cmd+K.
 * We open it by firing the keyboard shortcut before each relevant test.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CommandPalette from '../CommandPalette';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// Mock api service (palette uses direct fetch, not api module — but guard anyway)
vi.mock('../../../services/api', () => ({ default: {} }));

// Stub global fetch so palette note-loading never makes real requests
beforeEach(() => {
  mockNavigate.mockReset();
  vi.restoreAllMocks();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ items: [] }),
  });
});

function renderPalette(onClose = vi.fn()) {
  return render(<MemoryRouter><CommandPalette onClose={onClose} /></MemoryRouter>);
}

/** Helper: open the palette by firing Cmd+K on the document. */
function openPalette() {
  fireEvent.keyDown(document, { key: 'k', metaKey: true });
}

describe('CommandPalette', () => {
  it('renders the search input after opening', () => {
    renderPalette();
    openPalette();
    expect(screen.getByPlaceholderText(/search notes/i)).toBeInTheDocument();
  });

  it('input is auto-focused on mount', () => {
    renderPalette();
    openPalette();
    const input = screen.getByPlaceholderText(/search notes/i);
    expect(document.activeElement).toBe(input);
  });

  it('shows action items with no query', () => {
    renderPalette();
    openPalette();
    // At least one action should be visible
    expect(screen.getByText(/new note|knowledge graph|search vault|ai chat|settings/i)).toBeInTheDocument();
  });

  it('calls searchNotes / filters when query is typed', async () => {
    renderPalette();
    openPalette();
    const input = screen.getByPlaceholderText(/search notes/i);
    fireEvent.change(input, { target: { value: 'graph' } });
    await waitFor(() => {
      // "Open Knowledge Graph" should still be visible (action filter)
      expect(screen.getByText(/knowledge graph/i)).toBeInTheDocument();
    });
  });

  it('pressing Escape calls onClose', () => {
    const onClose = vi.fn();
    renderPalette(onClose);
    openPalette();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('renders a result item when search returns data', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 'n1', title: 'Sunyata', folder: 'philosophy' }] }),
    });
    renderPalette();
    openPalette();
    const input = screen.getByPlaceholderText(/search notes/i);
    fireEvent.change(input, { target: { value: 'Sunyata' } });
    // The Fuse index builds after open; result appears after debounce/update
    await waitFor(() => expect(screen.queryByText('Sunyata')).toBeInTheDocument(), { timeout: 2000 });
  });

  it('clicking a result navigates to the note and calls onClose', async () => {
    // Pre-seed the notes so Fuse can find 'Sunyata'
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 'n1', title: 'Sunyata', folder: 'philosophy' }] }),
    });
    const onClose = vi.fn();
    renderPalette(onClose);
    openPalette();
    const input = screen.getByPlaceholderText(/search notes/i);
    fireEvent.change(input, { target: { value: 'Sunyata' } });
    await waitFor(() => screen.queryByText('Sunyata'), { timeout: 2000 });
    // cmdk items fire onSelect via keyboard/click simulation
    const item = screen.getByText('Sunyata');
    fireEvent.click(item);
    // navigate should be called (may be called inside cmdk's onSelect)
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('n1'));
    });
  });
});
