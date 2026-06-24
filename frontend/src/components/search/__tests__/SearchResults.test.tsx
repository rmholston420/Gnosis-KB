/**
 * SearchResults.test.tsx
 *
 * Tests aligned to the ACTUAL SearchResults component:
 *  - Items rendered as <button> + useNavigate (not <Link>)
 *  - Snippet lives in `result.excerpt`, not `result.snippet`
 *  - Empty state only shown when results=[] AND query is non-empty
 *  - Loading state uses `animate-pulse` divs, not `.skeleton` class
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SearchResults } from '../SearchResults';
import type { SearchResult } from '../../../types';

// Cast to any so we can add `excerpt` without updating the shared type in this test
const results = [
  {
    note_id: '1',
    id: '1',
    title: 'Emptiness in Madhyamaka',
    excerpt: 'Form is emptiness',
    score: 0.95,
    folder: '10-zettelkasten',
    tags: ['buddhism'],
    note_type: 'permanent',
  },
  {
    note_id: '2',
    id: '2',
    title: 'Dependent Origination',
    excerpt: 'All phenomena arise dependently',
    score: 0.87,
    folder: '10-zettelkasten',
    tags: [],
    note_type: 'permanent',
  },
] as unknown as SearchResult[];

function Wrapper({ children }: { children: React.ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

describe('SearchResults', () => {
  it('renders result titles', () => {
    render(
      <Wrapper>
        <SearchResults results={results} isLoading={false} isError={false} />
      </Wrapper>,
    );
    expect(screen.getByText('Emptiness in Madhyamaka')).toBeInTheDocument();
    expect(screen.getByText('Dependent Origination')).toBeInTheDocument();
  });

  it('renders excerpt text when present', () => {
    render(
      <Wrapper>
        <SearchResults results={results} isLoading={false} isError={false} />
      </Wrapper>,
    );
    // excerpt is rendered inside a <p>; allow partial match
    expect(screen.getByText(/Form is emptiness/)).toBeInTheDocument();
  });

  it('shows empty state when results=[] and query is provided', () => {
    render(
      <Wrapper>
        <SearchResults
          results={[]}
          query="madhyamaka"
          isLoading={false}
          isError={false}
        />
      </Wrapper>,
    );
    // Component renders: No results for \u201c{query}\u201d
    expect(screen.getByText(/No results for/i)).toBeInTheDocument();
  });

  it('shows nothing extra when results=[] and no query', () => {
    const { container } = render(
      <Wrapper>
        <SearchResults results={[]} isLoading={false} isError={false} />
      </Wrapper>,
    );
    // With no query the empty state guard is skipped; just an empty list container
    expect(container.querySelector('.space-y-1\.5')).toBeInTheDocument();
    expect(screen.queryByText(/No results/i)).toBeNull();
  });

  it('shows loading skeletons (animate-pulse divs) when isLoading=true', () => {
    render(
      <Wrapper>
        <SearchResults results={[]} isLoading isError={false} />
      </Wrapper>,
    );
    // Component renders 4 \u00d7 animate-pulse divs when loading
    const pulses = document.querySelectorAll('.animate-pulse');
    expect(pulses.length).toBeGreaterThan(0);
  });

  it('result items are rendered as buttons (component uses navigate, not Link)', () => {
    render(
      <Wrapper>
        <SearchResults results={results} isLoading={false} isError={false} />
      </Wrapper>,
    );
    // Component uses <button onClick={() => navigate(...)}>  — not <a> tags
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThanOrEqual(2);
    // First button contains the first result title
    expect(buttons[0]).toHaveTextContent('Emptiness in Madhyamaka');
  });

  it('shows error state when isError=true', () => {
    render(
      <Wrapper>
        <SearchResults results={[]} isLoading={false} isError />
      </Wrapper>,
    );
    expect(screen.getByText(/Search failed/i)).toBeInTheDocument();
  });
});
