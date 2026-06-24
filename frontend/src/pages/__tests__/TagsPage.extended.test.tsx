/**
 * TagsPage.extended.test.tsx
 * Covers tag list rendering, click navigation, empty state, and tag counts.
 * Uncovered lines: 21-22, 72, 120, 133
 *
 * TagsPage.normalise() expects the resolved value to BE the tag data directly:
 *   - TagEntry[]          → returned as-is
 *   - Record<string,number> → converted to TagEntry[]
 * Do NOT wrap in { tags: [...] } — that causes 'Objects are not valid as React child'.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

// ---- Mocks -----------------------------------------------------------------
const mockListTags = vi.fn();

vi.mock('@/services/api', () => ({
  default: {
    // TagsPage accesses api.listTags ?? api.getTags via dynamic lookup.
    // Return the tag array directly (NOT wrapped in an object).
    listTags: (...a: unknown[]) => mockListTags(...a),
    getTags:  (...a: unknown[]) => mockListTags(...a),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

import TagsPage from '@/pages/TagsPage';

// TagEntry[] — returned DIRECTLY from mock (no wrapper object)
const TAGS = [
  { name: 'buddhism',   count: 12 },
  { name: 'philosophy', count: 7  },
  { name: 'meditation', count: 3  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <TagsPage />
    </MemoryRouter>
  );
}

describe('TagsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockClear();
  });

  it('renders without crashing', async () => {
    mockListTags.mockResolvedValue(TAGS);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Tags')).toBeTruthy()
    );
  });

  it('renders tags after load', async () => {
    mockListTags.mockResolvedValue(TAGS);
    renderPage();
    await waitFor(() => screen.getByText('buddhism'));
    expect(screen.getByText('philosophy')).toBeTruthy();
    expect(screen.getByText('meditation')).toBeTruthy();
  });

  it('renders tag counts', async () => {
    mockListTags.mockResolvedValue(TAGS);
    renderPage();
    await waitFor(() => screen.getByText('buddhism'));
    expect(screen.getByText('12')).toBeTruthy();
    expect(screen.getByText('7')).toBeTruthy();
  });

  it('shows empty state when no tags returned', async () => {
    mockListTags.mockResolvedValue([]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/No tags yet/i)).toBeTruthy()
    );
  });

  it('clicking a tag navigates with tag query param', async () => {
    mockListTags.mockResolvedValue(TAGS);
    renderPage();
    await waitFor(() => screen.getByText('buddhism'));
    fireEvent.click(screen.getByText('buddhism').closest('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/notes?tag=buddhism');
  });

  it('filter input narrows visible tags', async () => {
    mockListTags.mockResolvedValue(TAGS);
    renderPage();
    await waitFor(() => screen.getByText('buddhism'));
    const filterInput = screen.getByPlaceholderText(/Filter tags/i);
    fireEvent.change(filterInput, { target: { value: 'phil' } });
    await waitFor(() => {
      expect(screen.queryByText('buddhism')).toBeNull();
      expect(screen.getByText('philosophy')).toBeTruthy();
    });
  });

  it('sort toggle button is present and clickable', async () => {
    mockListTags.mockResolvedValue(TAGS);
    renderPage();
    await waitFor(() => screen.getByText('buddhism'));
    // The button's accessible name is its text content — 'A\u2013Z' or 'By count'.
    // title="Sort alphabetically" is the discriminator when text toggles.
    const sortBtn =
      screen.queryByRole('button', { name: /A.Z/i }) ??
      screen.queryByRole('button', { name: /By count/i }) ??
      screen.queryAllByRole('button').find(
        (b) => b.getAttribute('title')?.toLowerCase().includes('sort')
      );
    expect(sortBtn).toBeTruthy();
    if (sortBtn) fireEvent.click(sortBtn as Element);
  });

  it('accepts Record<string,number> response format', async () => {
    // normalise() also handles dict format
    mockListTags.mockResolvedValue({ buddhism: 12, philosophy: 7 });
    renderPage();
    await waitFor(() => screen.getByText('buddhism'));
    expect(screen.getByText('philosophy')).toBeTruthy();
  });

  it('shows error state when API fails', async () => {
    mockListTags.mockRejectedValue(new Error('Tags unavailable'));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Failed to load tags/i)).toBeTruthy()
    );
  });

  it('tag count total is shown in header', async () => {
    mockListTags.mockResolvedValue(TAGS);
    renderPage();
    await waitFor(() => {
      // Header shows (3) next to the Tags heading
      expect(screen.getByText(`(${TAGS.length})`)).toBeTruthy();
    });
  });
});
