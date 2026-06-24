/**
 * TopBar.test.tsx
 * ===============
 * Tests for the global search bar + "New Note" button in the top chrome.
 *
 * Cases:
 *  1. Renders a search input
 *  2. Renders the New Note button
 *  3. Typing updates the store searchQuery via setSearchQuery
 *  4. Pressing Enter with a non-empty query navigates to /search?q=…
 *  5. Pressing Enter with an empty query does NOT navigate
 *  6. Clicking New Note navigates to /notes/new
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TopBar from '../TopBar';
import { useAppStore } from '../../store/useAppStore';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderTopBar() {
  return render(<MemoryRouter><TopBar /></MemoryRouter>);
}

beforeEach(() => {
  useAppStore.setState({ searchQuery: '' });
  mockNavigate.mockReset();
});

describe('TopBar', () => {
  it('renders a search input', () => {
    renderTopBar();
    expect(screen.getByPlaceholderText(/search vault/i)).toBeInTheDocument();
  });

  it('renders the New Note button', () => {
    renderTopBar();
    expect(screen.getByRole('button', { name: /new note/i })).toBeInTheDocument();
  });

  it('typing in the search box updates store searchQuery', () => {
    renderTopBar();
    const input = screen.getByPlaceholderText(/search vault/i);
    fireEvent.change(input, { target: { value: 'consciousness' } });
    expect(useAppStore.getState().searchQuery).toBe('consciousness');
  });

  it('pressing Enter with non-empty query navigates to /search', () => {
    useAppStore.setState({ searchQuery: 'dharma' });
    renderTopBar();
    const input = screen.getByPlaceholderText(/search vault/i);
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(mockNavigate).toHaveBeenCalledWith('/search?q=dharma');
  });

  it('pressing Enter with empty query does not navigate', () => {
    useAppStore.setState({ searchQuery: '' });
    renderTopBar();
    const input = screen.getByPlaceholderText(/search vault/i);
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('pressing Enter with whitespace-only query does not navigate', () => {
    useAppStore.setState({ searchQuery: '   ' });
    renderTopBar();
    const input = screen.getByPlaceholderText(/search vault/i);
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('clicking New Note navigates to /notes/new', () => {
    renderTopBar();
    fireEvent.click(screen.getByRole('button', { name: /new note/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/notes/new');
  });

  it('non-Enter keypresses do not navigate', () => {
    useAppStore.setState({ searchQuery: 'test' });
    renderTopBar();
    const input = screen.getByPlaceholderText(/search vault/i);
    fireEvent.keyDown(input, { key: 'k' });
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
