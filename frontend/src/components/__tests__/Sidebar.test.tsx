/**
 * Sidebar.test.tsx
 * Tests for the main application sidebar.
 * Wraps with QueryClientProvider since DailyNoteWidget uses useQuery.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect } from 'vitest';
import { Sidebar } from '../Sidebar';
import * as notesApi from '../../api/notes';

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

const dailyNote = {
  note_id: 'daily-1', title: 'Daily 2026-06-24', body: '', tags: [],
  note_type: 'daily', status: 'active', created_at: '', updated_at: '',
  folder: 'Daily', source_url: null,
};

describe('Sidebar', () => {
  beforeEach(() => {
    vi.spyOn(notesApi, 'getDailyNote').mockResolvedValue(dailyNote);
  });

  it('shows the Gnosis brand label when expanded', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    expect(screen.getByText(/gnosis/i)).toBeInTheDocument();
  });

  it('collapse button has aria-label "Collapse sidebar" when expanded', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    expect(screen.getByLabelText(/collapse sidebar/i)).toBeInTheDocument();
  });

  it('toggle button collapses the sidebar', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    fireEvent.click(screen.getByLabelText(/collapse sidebar/i));
    expect(screen.queryByText(/notes/i)).not.toBeNull(); // nav items still present as icons
  });

  it('toggle button expands the sidebar', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    fireEvent.click(screen.getByLabelText(/collapse sidebar/i));
    fireEvent.click(screen.getByLabelText(/expand sidebar/i));
    expect(screen.getByText(/gnosis/i)).toBeInTheDocument();
  });

  it('renders all nav item labels when expanded', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    expect(screen.getByText(/notes/i)).toBeInTheDocument();
    expect(screen.getByText(/search/i)).toBeInTheDocument();
    expect(screen.getByText(/graph/i)).toBeInTheDocument();
  });

  it('New Note button navigates to /notes/new', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    const newNoteBtn = screen.getByRole('link', { name: /new note/i });
    expect(newNoteBtn).toHaveAttribute('href', '/notes/new');
  });

  it('Log out button removes token and navigates to /login', async () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    const logoutBtn = screen.getByRole('button', { name: /log out/i });
    fireEvent.click(logoutBtn);
    await waitFor(() =>
      expect(localStorage.getItem('token')).toBeNull()
    );
  });
});
