/// <reference types="vitest/globals" />
import {
  extractWikilinks,
  parseWikilinks,
  extractTags,
  buildSlug,
  parseFrontmatter,
  stripMarkdown,
  resolveWikilinks,
} from '../markdownUtils';

describe('markdownUtils', () => {
  describe('extractWikilinks / parseWikilinks alias', () => {
    it('extracts simple wikilinks', () => {
      const links = extractWikilinks('See [[Alpha]] and [[Beta|B]]');
      expect(links).toHaveLength(2);
      expect(links[0].title).toBe('Alpha');
      expect(links[1].alias).toBe('B');
    });
    it('alias returns identical result', () => {
      expect(parseWikilinks('[[Foo]]')).toEqual(extractWikilinks('[[Foo]]'));
    });
  });

  describe('extractTags', () => {
    it('returns unique hashtag-style tags', () => {
      const tags = extractTags('A note about #buddhism and #meditation. Also #buddhism again.');
      expect(tags).toContain('buddhism');
      expect(tags).toContain('meditation');
      expect(tags.filter((t) => t === 'buddhism')).toHaveLength(1);
    });
  });

  describe('buildSlug', () => {
    it('lowercases and replaces spaces with hyphens', () => {
      expect(buildSlug('The Four Noble Truths')).toBe('the-four-noble-truths');
    });
    it('removes special characters', () => {
      expect(buildSlug('Hello, World!')).toBe('hello-world');
    });
  });

  describe('parseFrontmatter', () => {
    it('extracts YAML frontmatter', () => {
      const md = '---\ntitle: Test\ntags: [a, b]\n---\nBody text';
      const { frontmatter, body } = parseFrontmatter(md);
      expect(frontmatter.title).toBe('Test');
      expect(body.trim()).toBe('Body text');
    });
    it('returns empty frontmatter when none present', () => {
      const { frontmatter, body } = parseFrontmatter('Just a body');
      expect(Object.keys(frontmatter)).toHaveLength(0);
      expect(body).toBe('Just a body');
    });
  });

  describe('stripMarkdown', () => {
    it('removes headings', () => {
      expect(stripMarkdown('# Hello')).toBe('Hello');
    });
    it('removes bold/italic markers', () => {
      expect(stripMarkdown('**bold** and _italic_')).not.toContain('**');
    });
  });

  describe('resolveWikilinks', () => {
    it('converts known wikilinks to markdown links', () => {
      const result = resolveWikilinks('See [[Alpha]]', { Alpha: 'abc123' });
      expect(result).toContain('/notes/abc123');
    });
    it('wraps unknown wikilinks in unresolved span', () => {
      const result = resolveWikilinks('See [[Unknown]]', {});
      expect(result).toContain('wikilink-unresolved');
    });
  });
});
