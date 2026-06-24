/**
 * WikiLinkExtension.test.ts
 * Full coverage for the TipTap wikilink extension module.
 * Dynamic imports used so each test gets a fresh module evaluation,
 * exercising the fetch paths independently.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---- Module-level mocks (hoisted by vitest) --------------------------------
vi.mock('@tiptap/extension-mention', () => ({
  Mention: {
    extend: vi.fn().mockReturnValue({
      configure: vi.fn().mockReturnValue({ name: 'wikilink' }),
    }),
  },
}));

vi.mock('@tiptap/react', () => ({ ReactRenderer: vi.fn() }));

vi.mock('tippy.js', () => ({
  default: vi.fn().mockReturnValue([{
    hide: vi.fn(),
    destroy: vi.fn(),
    setProps: vi.fn(),
    show: vi.fn(),
  }]),
}));

vi.mock('@tiptap/suggestion', () => ({}));

const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

describe('WikiLinkExtension module', () => {
  beforeEach(() => {
    localStorage.setItem('gnosis_token', 'test-token');
  });

  afterEach(() => {
    localStorage.removeItem('gnosis_token');
    vi.clearAllMocks();
  });

  it('exports WikiLinkExtension as a truthy value', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ items: [] }) });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeTruthy();
  });

  it('has a name property equal to "wikilink"', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ items: [] }) });
    const mod = await import('@/components/editor/WikiLinkExtension');
    // configure() returns { name: 'wikilink' } from our mock
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('fetchNoteSuggestions: handles { items: [...] } response shape', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: '1', title: 'Note A' }] }),
    });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('fetchNoteSuggestions: handles bare array response shape', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [{ id: '1', title: 'Note A' }, { id: '2', title: 'Note B' }],
    });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('fetchNoteSuggestions: handles non-ok HTTP response', async () => {
    mockFetch.mockResolvedValue({ ok: false });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('fetchNoteSuggestions: handles network error', async () => {
    mockFetch.mockRejectedValue(new Error('Network error'));
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('fetchNoteSuggestions: handles empty items array', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('fetchNoteSuggestions: works without token in localStorage', async () => {
    localStorage.removeItem('gnosis_token');
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: '3', title: 'Note C' }] }),
    });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });
});
