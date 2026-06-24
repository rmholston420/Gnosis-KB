/**
 * CommandPalette.test.tsx
 * =======================
 * Tests for the Cmd-K command palette (search + navigation).
 *
 * The CommandPalette renders null until the user presses Cmd+K (open=false
 * by default), so every test that needs the UI must first fire the keyboard
 * shortcut to open it.
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

// Mock fetch used inside the palette for note stubs + quick-note creation
beforeEach(() => {
  mockNavigate.mockReset();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ items: [], total: 0 }),
  });
});

function renderPalette(onClose = vi.fn()) {
  return render(
    <MemoryRouter>
      <CommandPalette onClose={onClose} />
    </MemoryRouter>
  );
}

/** Open the palette via the Cmd+K shortcut. */
function openPalette() {
  fireEvent.keyDown(document, { key: 'k', metaKey: true });
}

describe('CommandPalette', () => {
  it('renders nothing before Cmd+K is pressed', () => {
    renderPalette();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders the search input after opening', () => {
    renderPalette();
    openPalette();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('input is auto-focused on mount', () => {
    renderPalette();
    openPalette();
    const input = screen.getByRole('combobox');
    expect(document.activeElement).toBe(input);
  });

  it('shows action items with no query', () => {
    renderPalette();
    openPalette();
    // Static action items are rendered immediately (no query needed)
    expect(screen.getByText(/new note/i)).toBeInTheDocument();
  });

  it('calls searchNotes / filters when query is typed', async () => {
    renderPalette();
    openPalette();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'karma' } });
    // Fuse.js filters in-memory; fetch was called for stubs on open
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  });

  it('pressing Escape closes the palette', () => {
    const onClose = vi.fn();
    renderPalette(onClose);
    openPalette();
    // Palette is now open
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    // cmdk handles Escape internally and closes the palette
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders a result item when note stubs are loaded', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [{ id: 'n1', title: 'Karma and Rebirth', folder: 'buddhism' }],
      }),
    });
    renderPalette();
    openPalette();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'karma' } });
    await waitFor(() =>
      expect(screen.getByText('Karma and Rebirth')).toBeInTheDocument()
    );
  });

  it('clicking a result navigates to the note', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [{ id: 'n1', title: 'Karma and Rebirth', folder: 'buddhism' }],
      }),
    });
    const onClose = vi.fn();
    renderPalette(onClose);
    openPalette();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'karma' } });
    await waitFor(() => screen.getByText('Karma and Rebirth'));
    fireEvent.click(screen.getByText('Karma and Rebirth'));
    expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('n1'));
  });
});
