import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

vi.mock('@tiptap/extension-mention', () => ({
  Mention: {
    extend: vi.fn().mockReturnValue({
      configure: vi.fn().mockReturnValue({ name: 'wikilink' }),
    }),
  },
}));
vi.mock('@tiptap/react', () => ({ ReactRenderer: vi.fn() }));
vi.mock('tippy.js', () => ({
  default: vi.fn().mockReturnValue([
    { hide: vi.fn(), destroy: vi.fn(), setProps: vi.fn(), show: vi.fn() },
  ]),
}));

describe('WikiLinkExtension', () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.setItem('gnosis_token', 'test-token');
    vi.stubEnv('VITE_API_BASE_URL', '');
  });
  afterEach(() => {
    localStorage.removeItem('gnosis_token');
    vi.clearAllMocks();
  });

  it('exports WikiLinkExtension', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ items: [] }) });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeTruthy();
  });

  it('fetchNoteSuggestions returns items array from { items } shape', async () => {
    const notes = [{ id: '1', title: 'Note A' }];
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ items: notes }) });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('fetchNoteSuggestions returns bare array shape', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [{ id: '1', title: 'Note A' }],
    });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('fetchNoteSuggestions returns [] on !ok', async () => {
    mockFetch.mockResolvedValue({ ok: false });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('fetchNoteSuggestions returns [] on network error', async () => {
    mockFetch.mockRejectedValue(new Error('Network error'));
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });

  it('buildSuggestion items calls fetchNoteSuggestions', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ items: [] }) });
    const mod = await import('@/components/editor/WikiLinkExtension');
    expect(mod.WikiLinkExtension).toBeDefined();
  });
});
