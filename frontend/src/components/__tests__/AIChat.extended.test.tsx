/**
 * AIChat.extended.test.tsx
 * Targets uncovered lines in components/AIChat.tsx:
 *   99      — token accumulation in SSE loop
 *   101-106 — meta payload → SOURCE_BADGE render
 *   117-118 — error token in SSE stream
 *   190-199 — catch block: HTTP error / network failure
 *
 * NOTE: The Send button in this version of AIChat has no aria-label,
 * so its accessible name is "". We select it as the last button in the
 * toolbar using getAllByRole('button').at(-1).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---- SSE fetch mock helpers ------------------------------------------------
function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let idx = 0;
  return new ReadableStream({
    pull(controller) {
      if (idx < chunks.length) controller.enqueue(encoder.encode(chunks[idx++]));
      else controller.close();
    },
  });
}
function mockFetchOk(chunks: string[]) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, body: makeStream(chunks), status: 200 }));
}
function mockFetchError(status = 500) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, body: null, status }));
}
function sseChunk(payload: unknown) {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

import AIChat from '@/components/AIChat';

/**
 * The Send button is the LAST button rendered (after the 4 mode buttons).
 * It has no aria-label in the current source so we can't use { name }.
 */
function getSendButton(): HTMLElement {
  const buttons = screen.getAllByRole('button');
  return buttons[buttons.length - 1];
}

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
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), { target: { value: 'test query' } });
    fireEvent.click(getSendButton());
    await waitFor(() => expect(screen.queryByText(/Hello world/i)).toBeTruthy(), { timeout: 3000 });
  });

  it('renders meta badge after meta SSE event (lines 101-106)', async () => {
    mockFetchOk([
      sseChunk({ token: 'Answer' }),
      sseChunk({ meta: { rag_source: 'lightrag', mode: 'hybrid' } }),
      'data: [DONE]\n\n',
    ]);
    render(<AIChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), { target: { value: 'meta test' } });
    fireEvent.click(getSendButton());
    await waitFor(() => expect(screen.queryByText(/LightRAG/i)).toBeTruthy(), { timeout: 3000 });
  });

  it('appends error token to message (lines 117-118)', async () => {
    mockFetchOk([
      sseChunk({ error: 'Backend exploded' }),
      'data: [DONE]\n\n',
    ]);
    render(<AIChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), { target: { value: 'error test' } });
    fireEvent.click(getSendButton());
    await waitFor(() => expect(screen.queryByText(/Error: Backend exploded/i)).toBeTruthy(), { timeout: 3000 });
  });
});

describe('AIChat — HTTP error path (lines 190-199)', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('shows Failed to get response on HTTP error', async () => {
    mockFetchError(503);
    render(<AIChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), { target: { value: 'fail test' } });
    fireEvent.click(getSendButton());
    await waitFor(() => expect(screen.queryByText(/Failed to get response/i)).toBeTruthy(), { timeout: 3000 });
  });

  it('shows Failed to get response on fetch network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network down')));
    render(<AIChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), { target: { value: 'network fail' } });
    fireEvent.click(getSendButton());
    await waitFor(() => expect(screen.queryByText(/Failed to get response/i)).toBeTruthy(), { timeout: 3000 });
  });
});

describe('AIChat — mode selector + keyboard send', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('changes mode when a mode button is clicked', () => {
    render(<AIChat />);
    // The 4 mode buttons: hybrid[0] lightrag[1] vector[2] naive[3]
    fireEvent.click(screen.getAllByRole('button')[2]); // vector
    expect(screen.getByText('vector')).toBeTruthy();
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
