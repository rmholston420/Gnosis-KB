/**
 * SearchResults.test.tsx
 *
 * Key constraints:
 *  - The Highlight sub-component wraps query-matching substrings in <mark>,
 *    splitting h3 title text AND snippet text across multiple DOM nodes.
 *  - Use getByRole('heading', { name: /regex/i }) for titles.
 *  - For snippets, query a substring that begins AFTER any highlighted word
 *    so the text node is contiguous (e.g. /waves appear during/i when
 *    query="alpha" highlights "Alpha" at the start of the snippet).
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
    // Title split by <mark> — use heading role with accessible name regex
    expect(screen.getByRole('heading', { name: /EEG Alpha Waves/i })).toBeInTheDocument();
    // Snippet: "Alpha" is highlighted so text is split; query text after the mark
    expect(screen.getByText(/waves appear during/i)).toBeInTheDocument();
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
    // Click the card button (parent of the heading)
    fireEvent.click(screen.getByRole('heading', { name: /EEG Alpha Waves/i }).closest('button')!);
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
    // Tags rendered as joined string in one span: 'neuroscience, brainwaves'
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
    // Score displayed as '92%' (score * 100, toFixed(0))
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
