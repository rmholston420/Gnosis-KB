import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from '../api';

class MockEventSource {
  url: string;
  listeners: Record<string, Array<(event: { data: string }) => void>> = {};

  constructor(url: string) {
    this.url = url;
  }

  addEventListener(type: string, listener: (event: { data: string }) => void) {
    this.listeners[type] ??= [];
    this.listeners[type].push(listener);
  }

  close() {}
}

describe('api.streamQuery', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal('EventSource', MockEventSource as unknown as typeof EventSource);
  });

  it('accepts query only (1 arg)', () => {
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
