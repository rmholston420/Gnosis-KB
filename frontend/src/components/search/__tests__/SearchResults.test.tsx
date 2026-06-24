/**
 * SearchResults.test.tsx
 * Tests:
 *  - renders a list of results
 *  - shows empty state when results=[]
 *  - shows loading skeleton when isLoading=true
 *  - result items are clickable / navigable
 *  - snippet highlight rendered
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SearchResults } from '../SearchResults';
import type { SearchResult } from '../../../types';

const results: SearchResult[] = [
  { note_id: '1', id: '1', title: 'Emptiness in Madhyamaka', snippet: 'Form is emptiness', score: 0.95, folder: '10-zettelkasten', tags: ['buddhism'], note_type: 'permanent' },
  { note_id: '2', id: '2', title: 'Dependent Origination', snippet: 'All phenomena arise dependently', score: 0.87, folder: '10-zettelkasten', tags: [], note_type: 'permanent' },
];

function Wrapper({ children }: { children: React.ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

describe('SearchResults', () => {
  it('renders result titles', () => {
    render(<Wrapper><SearchResults results={results} isLoading={false} /></Wrapper>);
    expect(screen.getByText('Emptiness in Madhyamaka')).toBeInTheDocument();
    expect(screen.getByText('Dependent Origination')).toBeInTheDocument();
  });

  it('renders snippet text', () => {
    render(<Wrapper><SearchResults results={results} isLoading={false} /></Wrapper>);
    expect(screen.getByText(/Form is emptiness/)).toBeInTheDocument();
  });

  it('shows empty state when results is empty', () => {
    render(<Wrapper><SearchResults results={[]} isLoading={false} /></Wrapper>);
    expect(screen.getByText(/no results/i)).toBeInTheDocument();
  });

  it('shows loading skeletons when isLoading=true', () => {
    render(<Wrapper><SearchResults results={[]} isLoading /></Wrapper>);
    // Loading state should render skeleton placeholders
    expect(document.querySelectorAll('.skeleton').length).toBeGreaterThan(0);
  });

  it('result items link to /notes/:id', () => {
    render(<Wrapper><SearchResults results={results} isLoading={false} /></Wrapper>);
    const links = screen.getAllByRole('link');
    expect(links[0]).toHaveAttribute('href', '/notes/1');
  });
});
