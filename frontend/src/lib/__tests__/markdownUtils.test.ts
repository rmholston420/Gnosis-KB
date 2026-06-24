import { describe, it, expect } from 'vitest';
import { parseWikilinks, extractTags, buildSlug } from '../markdownUtils';

describe('parseWikilinks', () => {
  it('extracts bare wikilinks', () => {
    expect(parseWikilinks('See [[Zettelkasten]] and [[Atomic Notes]]')).toEqual([
      { target: 'Zettelkasten', alias: null, raw: '[[Zettelkasten]]' },
      { target: 'Atomic Notes',  alias: null, raw: '[[Atomic Notes]]' },
    ]);
  });

  it('extracts aliased wikilinks', () => {
    const result = parseWikilinks('See [[Zettelkasten|ZK Method]]');
    expect(result[0].target).toBe('Zettelkasten');
    expect(result[0].alias).toBe('ZK Method');
  });

  it('returns empty array when no wikilinks', () => {
    expect(parseWikilinks('No links here.')).toEqual([]);
  });
});

describe('extractTags', () => {
  it('extracts hashtags from body', () => {
    const tags = extractTags('A note about #zettelkasten and #buddhism.');
    expect(tags).toContain('zettelkasten');
    expect(tags).toContain('buddhism');
  });

  it('returns empty array when no tags', () => {
    expect(extractTags('No tags here.')).toEqual([]);
  });
});

describe('buildSlug', () => {
  it('lowercases and hyphenates', () => {
    expect(buildSlug('Zettelkasten Method')).toBe('zettelkasten-method');
  });

  it('strips special characters', () => {
    expect(buildSlug('Hello, World!')).toBe('hello-world');
  });
});
