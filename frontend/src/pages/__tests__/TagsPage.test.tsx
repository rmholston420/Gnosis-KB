/**
 * TagsPage.test.tsx
 * =================
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TagsPage from '../TagsPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockGetTags = vi.fn();
vi.mock('../../services/api', () => ({
  default: { getTags: (...args: unknown[]) => mockGetTags(...args) },
}));

const tags = [
  { name: 'buddhism', count: 12 },
  { name: 'madhyamaka', count: 5 },
  { name: 'meditation', count: 8 },
];

function renderPage() {
  return render(<MemoryRouter><TagsPage /></MemoryRouter>);
}

beforeEach(() => {
  mockGetTags.mockReset();
  mockNavigate.mockReset();
  mockGetTags.mockResolvedValue(tags);
});

describe('TagsPage', () => {
  it('renders page heading', () => {
    renderPage();
    expect(screen.getByText(/tags/i)).toBeInTheDocument();
  });

  it('renders tag names after loading', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('buddhism')).toBeInTheDocument());
    expect(screen.getByText('madhyamaka')).toBeInTheDocument();
  });

  it('renders tag counts', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('12')).toBeInTheDocument());
  });

  it('clicking a tag navigates to filtered notes', async () => {
    renderPage();
    await waitFor(() => screen.getByText('buddhism'));
    fireEvent.click(screen.getByText('buddhism'));
    expect(mockNavigate).toHaveBeenCalledWith(expect.stringContaining('buddhism'));
  });

  it('shows empty state when no tags', async () => {
    mockGetTags.mockResolvedValue([]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/no tags|empty/i)).toBeInTheDocument()
    );
  });
});
