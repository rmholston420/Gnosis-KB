/**
 * SearchResults.test.tsx
 * Tests for the SearchResults component.
 *
 * Note: The Highlight sub-component wraps query-matching substrings in <mark>
 * which splits the h3 text across multiple DOM nodes.  We must therefore use
 * getByRole('heading') with a flexible name matcher instead of getByText().
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect } from 'vitest';
import { SearchResults } from '../SearchResults';
import type { SearchResult } from '../../../types';

const makeResult = (overrides: Partial<SearchResult> = {}): SearchResult => ({
  note_id: 'r1',
  title: 'EEG Alpha Waves',
  snippet: 'Alpha waves appear during relaxed wakefulness.',
  score: 0.92,
  tags: ['neuroscience', 'brainwaves'],
  note_type: 'permanent',
  ...overrides,
});

function Wrapper({ children }: { children: React.ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

describe('SearchResults', () => {
  it('renders a result card with title and snippet', () => {
    render(
      <Wrapper>
        <SearchResults
          results={[makeResult()]}
          query="alpha"
          onResultClick={() => {}}
          isLoading={false}
          isError={false}
        />
      </Wrapper>
    );
    // Title text is split by <mark> — use heading role with name regex
    expect(screen.getByRole('heading', { name: /EEG Alpha Waves/i })).toBeInTheDocument();
    expect(screen.getByText(/alpha waves appear/i)).toBeInTheDocument();
  });

  it('highlights the query term in the snippet', () => {
    render(
      <Wrapper>
        <SearchResults
          results={[makeResult()]}
          query="alpha"
          onResultClick={() => {}}
          isLoading={false}
          isError={false}
        />
      </Wrapper>
    );
    const marks = document.querySelectorAll('mark, .highlight, [data-highlight]');
    expect(marks.length).toBeGreaterThan(0);
  });

  it('renders multiple results', () => {
    const results = [
      makeResult({ note_id: 'r1', title: 'EEG Alpha Waves' }),
      makeResult({ note_id: 'r2', title: 'Theta Rhythm' }),
      makeResult({ note_id: 'r3', title: 'Gamma Oscillations' }),
    ];
    render(
      <Wrapper>
        <SearchResults
          results={results}
          query="waves"
          onResultClick={() => {}}
          isLoading={false}
          isError={false}
        />
      </Wrapper>
    );
    // All three titles present (some may be <mark>-split)
    expect(screen.getByRole('heading', { name: /EEG Alpha Waves/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Theta Rhythm/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Gamma Oscillations/i })).toBeInTheDocument();
  });

  it('calls onResultClick when a result is clicked', () => {
    const onResultClick = vi.fn();
    render(
      <Wrapper>
        <SearchResults
          results={[makeResult()]}
          query="alpha"
          onResultClick={onResultClick}
          isLoading={false}
          isError={false}
        />
      </Wrapper>
    );
    fireEvent.click(screen.getByRole('heading', { name: /EEG Alpha Waves/i }));
    // onResultClick is called via the parent button's onClick — bubble up
    expect(onResultClick).toHaveBeenCalledWith('r1');
  });

  it('shows tags on each result card', () => {
    render(
      <Wrapper>
        <SearchResults
          results={[makeResult()]}
          query="alpha"
          onResultClick={() => {}}
          isLoading={false}
          isError={false}
        />
      </Wrapper>
    );
    // Tags are joined as 'neuroscience, brainwaves' in a single span
    expect(screen.getByText(/neuroscience/)).toBeInTheDocument();
    expect(screen.getByText(/brainwaves/)).toBeInTheDocument();
  });

  it('shows score badge', () => {
    render(
      <Wrapper>
        <SearchResults
          results={[makeResult({ score: 0.92 })]}
          query="alpha"
          onResultClick={() => {}}
          isLoading={false}
          isError={false}
        />
      </Wrapper>
    );
    // Score is displayed as '92%' (toFixed(0) * 100)
    expect(screen.getByText(/92/)).toBeInTheDocument();
  });

  it('shows nothing extra when results=[] and no query', () => {
    render(
      <Wrapper>
        <SearchResults
          results={[]}
          query=""
          onResultClick={() => {}}
          isLoading={false}
          isError={false}
        />
      </Wrapper>
    );
    expect(screen.queryByText(/no results/i)).toBeNull();
  });
});
