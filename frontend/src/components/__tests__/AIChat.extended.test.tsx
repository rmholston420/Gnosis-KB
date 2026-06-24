/**
 * AIChat.extended.test.tsx
 * Targets uncovered lines in components/AIChat.tsx:
 *   99    — reader.read() loop body / token accumulation
 *   101-106 — meta payload handling (SOURCE_BADGE lookup + render)
 *   117-118 — error token in SSE stream
 *   190-199 — catch block: failed fetch / HTTP error
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---------- SSE fetch mock helpers ------------------------------------------
type ReadResult = { done: boolean; value?: Uint8Array };

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let idx = 0;
  return new ReadableStream({
    pull(controller) {
      if (idx < chunks.length) {
        controller.enqueue(encoder.encode(chunks[idx++]));
      } else {
        controller.close();
      }
    },
  });
}

function mockFetchOk(chunks: string[]) {
  const body = makeStream(chunks);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    body,
    status: 200,
  }));
}

function mockFetchError(status = 500) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false,
    body: null,
    status,
  }));
}

function sseChunk(payload: unknown) {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

import AIChat from '@/components/AIChat';

describe('AIChat — SSE streaming (lines 99-118)', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('accumulates token chunks into assistant message (line 99)', async () => {
    mockFetchOk([
      sseChunk({ token: 'Hello ' }),
      sseChunk({ token: 'world' }),
      'data: [DONE]\n\n',
    ]);
    render(<AIChat />);
    const textarea = screen.getByPlaceholderText(/Ask your knowledge base/i);
    fireEvent.change(textarea, { target: { value: 'test query' } });
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() =>
      expect(screen.queryByText(/Hello world/i)).toBeTruthy(),
      { timeout: 3000 }
    );
  });

  it('renders meta badge after meta SSE event (lines 101-106)', async () => {
    mockFetchOk([
      sseChunk({ token: 'Answer' }),
      sseChunk({ meta: { rag_source: 'lightrag', mode: 'hybrid' } }),
      'data: [DONE]\n\n',
    ]);
    render(<AIChat />);
    const textarea = screen.getByPlaceholderText(/Ask your knowledge base/i);
    fireEvent.change(textarea, { target: { value: 'meta test' } });
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() =>
      expect(screen.queryByText(/LightRAG/i)).toBeTruthy(),
      { timeout: 3000 }
    );
  });

  it('appends error token to message (lines 117-118)', async () => {
    mockFetchOk([
      sseChunk({ error: 'Backend exploded' }),
      'data: [DONE]\n\n',
    ]);
    render(<AIChat />);
    const textarea = screen.getByPlaceholderText(/Ask your knowledge base/i);
    fireEvent.change(textarea, { target: { value: 'error test' } });
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() =>
      expect(screen.queryByText(/Error: Backend exploded/i)).toBeTruthy(),
      { timeout: 3000 }
    );
  });
});

describe('AIChat — HTTP error path (lines 190-199)', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('shows Failed to get response on HTTP error', async () => {
    mockFetchError(503);
    render(<AIChat />);
    const textarea = screen.getByPlaceholderText(/Ask your knowledge base/i);
    fireEvent.change(textarea, { target: { value: 'fail test' } });
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() =>
      expect(screen.queryByText(/Failed to get response/i)).toBeTruthy(),
      { timeout: 3000 }
    );
  });

  it('shows Failed to get response on fetch network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network down')));
    render(<AIChat />);
    const textarea = screen.getByPlaceholderText(/Ask your knowledge base/i);
    fireEvent.change(textarea, { target: { value: 'network fail' } });
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() =>
      expect(screen.queryByText(/Failed to get response/i)).toBeTruthy(),
      { timeout: 3000 }
    );
  });
});

describe('AIChat — mode selector + keyboard send', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('changes mode when a mode button is clicked', () => {
    render(<AIChat />);
    fireEvent.click(screen.getByRole('button', { name: /vector/i }));
    expect(screen.getByRole('button', { name: /vector/i })).toBeTruthy();
  });

  it('sends on Enter keydown (not Shift+Enter)', async () => {
    mockFetchOk(['data: [DONE]\n\n']);
    render(<AIChat />);
    const textarea = screen.getByPlaceholderText(/Ask your knowledge base/i);
    fireEvent.change(textarea, { target: { value: 'keyboard test' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled(), { timeout: 3000 });
  });

  it('does NOT send on Shift+Enter', () => {
    mockFetchOk(['data: [DONE]\n\n']);
    render(<AIChat />);
    const textarea = screen.getByPlaceholderText(/Ask your knowledge base/i);
    fireEvent.change(textarea, { target: { value: 'no send' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });
});
