/**
 * CommandPalette.test.tsx
 * =======================
 * Tests for the Cmd-K command palette (search + navigation).
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

const mockSearchNotes = vi.fn();
vi.mock('../../../services/api', () => ({
  default: {
    searchNotes: (...args: unknown[]) => mockSearchNotes(...args),
    listNotes:   vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}));

function renderPalette(onClose = vi.fn()) {
  return render(
    <MemoryRouter>
      <CommandPalette onClose={onClose} />
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockSearchNotes.mockReset();
  mockNavigate.mockReset();
  mockSearchNotes.mockResolvedValue({ items: [], total: 0 });
});

describe('CommandPalette', () => {
  it('renders the search input', () => {
    renderPalette();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('input is auto-focused on mount', () => {
    renderPalette();
    const input = screen.getByRole('textbox');
    expect(document.activeElement).toBe(input);
  });

  it('shows empty state with no query', () => {
    renderPalette();
    // With empty input there should be no result rows yet
    expect(screen.queryByRole('option')).not.toBeInTheDocument();
  });

  it('calls searchNotes when query is typed', async () => {
    renderPalette();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'karma' } });
    await waitFor(() => expect(mockSearchNotes).toHaveBeenCalled());
  });

  it('pressing Escape calls onClose', () => {
    const onClose = vi.fn();
    renderPalette(onClose);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('renders a result item when search returns data', async () => {
    mockSearchNotes.mockResolvedValue({
      items: [{ id: 'n1', title: 'Karma', slug: 'karma', note_type: 'permanent', tags: [] }],
      total: 1,
    });
    renderPalette();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'karma' } });
    await waitFor(() => expect(screen.getByText('Karma')).toBeInTheDocument());
  });

  it('clicking a result navigates to the note and calls onClose', async () => {
    mockSearchNotes.mockResolvedValue({
      items: [{ id: 'n1', title: 'Karma', slug: 'karma', note_type: 'permanent', tags: [] }],
      total: 1,
    });
    const onClose = vi.fn();
    renderPalette(onClose);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'karma' } });
    await waitFor(() => screen.getByText('Karma'));
    fireEvent.click(screen.getByText('Karma'));
    expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('n1'));
    expect(onClose).toHaveBeenCalled();
  });
});
