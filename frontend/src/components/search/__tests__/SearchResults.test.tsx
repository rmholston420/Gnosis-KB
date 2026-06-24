/**
 * SearchResults.test.tsx
 * Tests for the SearchResults component.
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
        <SearchResults results={[makeResult()]} query="alpha" onResultClick={() => {}} />
      </Wrapper>
    );
    expect(screen.getByText('EEG Alpha Waves')).toBeInTheDocument();
    expect(screen.getByText(/alpha waves appear/i)).toBeInTheDocument();
  });

  it('highlights the query term in the snippet', () => {
    render(
      <Wrapper>
        <SearchResults results={[makeResult()]} query="alpha" onResultClick={() => {}} />
      </Wrapper>
    );
    // The highlighted span should exist
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
        <SearchResults results={results} query="waves" onResultClick={() => {}} />
      </Wrapper>
    );
    expect(screen.getByText('EEG Alpha Waves')).toBeInTheDocument();
    expect(screen.getByText('Theta Rhythm')).toBeInTheDocument();
    expect(screen.getByText('Gamma Oscillations')).toBeInTheDocument();
  });

  it('calls onResultClick when a result is clicked', () => {
    const onResultClick = vi.fn();
    render(
      <Wrapper>
        <SearchResults results={[makeResult()]} query="alpha" onResultClick={onResultClick} />
      </Wrapper>
    );
    fireEvent.click(screen.getByText('EEG Alpha Waves'));
    expect(onResultClick).toHaveBeenCalledWith('r1');
  });

  it('shows tags on each result card', () => {
    render(
      <Wrapper>
        <SearchResults results={[makeResult()]} query="alpha" onResultClick={() => {}} />
      </Wrapper>
    );
    expect(screen.getByText('neuroscience')).toBeInTheDocument();
    expect(screen.getByText('brainwaves')).toBeInTheDocument();
  });

  it('shows score badge', () => {
    render(
      <Wrapper>
        <SearchResults results={[makeResult({ score: 0.92 })]} query="alpha" onResultClick={() => {}} />
      </Wrapper>
    );
    expect(screen.getByText(/0\.9/)).toBeInTheDocument();
  });

  it('shows nothing extra when results=[] and no query', () => {
    render(
      <Wrapper>
        <SearchResults results={[]} query="" onResultClick={() => {}} />
      </Wrapper>
    );
    // No error or empty-state message when no query is present
    expect(screen.queryByText(/no results/i)).toBeNull();
  });
});
