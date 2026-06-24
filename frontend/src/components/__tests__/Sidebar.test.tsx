import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from '@/components/Sidebar';

function Wrapper({ children }: { children: React.ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

describe('Sidebar', () => {
  it('renders all nav item labels when expanded', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    // Default state is expanded — all text labels should be visible
    expect(screen.getByText('Notes')).toBeInTheDocument();
    expect(screen.getByText('Search')).toBeInTheDocument();
    expect(screen.getByText('Graph')).toBeInTheDocument();
    expect(screen.getByText('AI Chat')).toBeInTheDocument();
  });

  it('shows brand name when expanded', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    expect(screen.getByText(/gnosis/i)).toBeInTheDocument();
  });

  it('toggle button collapses the sidebar', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    // Initial state: expanded → button says 'Collapse sidebar'
    fireEvent.click(screen.getByLabelText(/collapse sidebar/i));
    // After collapse: text labels are hidden (icon-only mode)
    expect(screen.queryByText('Notes')).toBeNull();
  });

  it('toggle button expands the sidebar', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    // Collapse first
    fireEvent.click(screen.getByLabelText(/collapse sidebar/i));
    // Now expand
    fireEvent.click(screen.getByLabelText(/expand sidebar/i));
    expect(screen.getByText(/gnosis/i)).toBeInTheDocument();
  });

  it('nav links have correct href attributes', () => {
    render(<Wrapper><Sidebar /></Wrapper>);
    expect(screen.getByTitle('Search').closest('a')).toHaveAttribute('href', '/search');
    expect(screen.getByTitle('Graph').closest('a')).toHaveAttribute('href', '/graph');
  });
});
