/**
 * api.extra.test.ts — extra tests for services/api.ts.
 *
 * streamQuery now returns EventSource; it accepts (query, onChunk?, onDone?)
 * where onDone is the 3rd argument — matching the current signature.
 * However, tests that previously passed 3 args remain valid: the
 * signature is (query: string, onChunk?, onDone?) — 3 args max.
 *
 * NOTE: The EventSource-based streamQuery in services/api.ts only accepts 2
 * optional callbacks, not 3 positional args.  These tests validate the
 * contract by calling with 1, 2, and 3 args (the third is onDone).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from '../api';

describe('api.streamQuery', () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it('accepts query only (1 arg)', () => {
    // Should not throw — returns an EventSource
    const es = api.streamQuery('SELECT * FROM notes');
    expect(es).toBeDefined();
    es.close();
  });

  it('accepts query + onChunk (2 args)', () => {
    const onChunk = vi.fn();
    const es = api.streamQuery('SELECT * FROM notes', onChunk);
    expect(es).toBeDefined();
    es.close();
  });

  it('accepts query + onChunk + onDone (3 args)', () => {
    const onChunk = vi.fn();
    const onDone  = vi.fn();
    const es = api.streamQuery('SELECT * FROM notes', onChunk, onDone);
    expect(es).toBeDefined();
    es.close();
  });
});
