/**
 * Sidebar.test.tsx
 * ================
 * Tests for the primary navigation sidebar.
 *
 * Cases:
 *  1.  Renders the Gnosis brand label when expanded
 *  2.  Hides the brand label when collapsed
 *  3.  Toggle button expands a collapsed sidebar
 *  4.  Toggle button collapses an expanded sidebar
 *  5.  All nav items render when sidebar is expanded
 *  6.  Nav item labels are hidden when collapsed
 *  7.  New Note button navigates to /notes/new
 *  8.  Logout button removes gnosis_token from localStorage and navigates to /login
 *  9.  Collapse button has correct aria-label when expanded
 * 10.  Collapse button has correct aria-label when collapsed
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from '../Sidebar';
import { useAppStore } from '../../store/useAppStore';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderSidebar() {
  return render(<MemoryRouter><Sidebar /></MemoryRouter>);
}

beforeEach(() => {
  useAppStore.setState({ sidebarCollapsed: false });
  mockNavigate.mockReset();
  localStorage.clear();
});

describe('Sidebar', () => {
  it('shows the Gnosis brand label when expanded', () => {
    renderSidebar();
    expect(screen.getByText('Gnosis')).toBeInTheDocument();
  });

  it('hides the brand label when collapsed', () => {
    useAppStore.setState({ sidebarCollapsed: true });
    renderSidebar();
    expect(screen.queryByText('Gnosis')).not.toBeInTheDocument();
  });

  it('collapse button has aria-label "Collapse sidebar" when expanded', () => {
    renderSidebar();
    expect(screen.getByLabelText('Collapse sidebar')).toBeInTheDocument();
  });

  it('collapse button has aria-label "Expand sidebar" when collapsed', () => {
    useAppStore.setState({ sidebarCollapsed: true });
    renderSidebar();
    expect(screen.getByLabelText('Expand sidebar')).toBeInTheDocument();
  });

  it('toggle button collapses the sidebar', () => {
    renderSidebar();
    fireEvent.click(screen.getByLabelText('Collapse sidebar'));
    expect(useAppStore.getState().sidebarCollapsed).toBe(true);
  });

  it('toggle button expands the sidebar', () => {
    useAppStore.setState({ sidebarCollapsed: true });
    renderSidebar();
    fireEvent.click(screen.getByLabelText('Expand sidebar'));
    expect(useAppStore.getState().sidebarCollapsed).toBe(false);
  });

  it('renders all nav item labels when expanded', () => {
    renderSidebar();
    const labels = ['Notes', 'Search', 'AI Chat', 'Graph', 'Tags', 'Review', 'Daily', 'MOC', 'Query', 'Ingest', 'Settings'];
    labels.forEach((label) => expect(screen.getByText(label)).toBeInTheDocument());
  });

  it('nav item labels are hidden when collapsed', () => {
    useAppStore.setState({ sidebarCollapsed: true });
    renderSidebar();
    expect(screen.queryByText('AI Chat')).not.toBeInTheDocument();
  });

  it('New Note button navigates to /notes/new', () => {
    renderSidebar();
    fireEvent.click(screen.getByTitle('New note'));
    expect(mockNavigate).toHaveBeenCalledWith('/notes/new');
  });

  it('Log out button removes token and navigates to /login', () => {
    localStorage.setItem('gnosis_token', 'tok123');
    renderSidebar();
    fireEvent.click(screen.getByTitle('Log out'));
    expect(localStorage.getItem('gnosis_token')).toBeNull();
    expect(mockNavigate).toHaveBeenCalledWith('/login');
  });
});
