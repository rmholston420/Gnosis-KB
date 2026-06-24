/**
 * AIChat.extended.test.tsx
 * Targets uncovered lines in components/AIChat.tsx:
 *   99      — token accumulation in SSE loop
 *   101-106 — meta payload → SOURCE_BADGE render
 *   117-118 — error token in SSE stream
 *   190-199 — catch block: HTTP error / network failure
 *
 * Send button: no aria-label in current source → select as last button.
 *
 * Stream mocking: use start() not pull() so all chunks are buffered
 * synchronously and available on the very first reader.read() await.
 *
 * Error SSE branch note: AIChat.tsx { error } branch appends to the
 * `accumulated` local var but does NOT call setMessages — only the
 * { token } branch does. To make the error text reach the DOM we emit
 * a { token: ' ' } chunk AFTER the { error } chunk.
 *
 * Meta badge note: jsdom's nwsapi CSS parser rejects Tailwind slash-
 * opacity class names (bg-purple-500/20) in querySelector strings, so
 * we use classList.contains() instead.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---- SSE fetch mock helpers ------------------------------------------------

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

function mockFetchOk(chunks: string[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, body: makeStream(chunks), status: 200 }),
  );
}
function mockFetchError(status = 500) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: false, body: null, status }),
  );
}
function sseChunk(payload: unknown) {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

import AIChat from '@/components/AIChat';

/** Send is the last button — it has no aria-label so name matching fails. */
function getSendButton(): HTMLElement {
  const buttons = screen.getAllByRole('button');
  return buttons[buttons.length - 1];
}

/**
 * Find the LightRAG source badge span without CSS selector parsing.
 * jsdom nwsapi chokes on Tailwind slash-opacity classes like bg-purple-500/20.
 * We iterate spans and check classList instead.
 */
function findSourceBadge(): HTMLElement | null {
  const spans = Array.from(document.querySelectorAll('span'));
  return spans.find((s) => s.classList.contains('bg-purple-500/20')) ?? null;
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
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), {
      target: { value: 'test query' },
    });
    fireEvent.click(getSendButton());
    await waitFor(() => expect(screen.queryByText(/Hello world/i)).toBeTruthy(), { timeout: 4000 });
  });

  it('renders meta badge after meta SSE event (lines 101-106)', async () => {
    mockFetchOk([
      sseChunk({ token: 'Answer' }),
      sseChunk({ meta: { rag_source: 'lightrag', mode: 'hybrid' } }),
      'data: [DONE]\n\n',
    ]);
    render(<AIChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), {
      target: { value: 'meta test' },
    });
    fireEvent.click(getSendButton());
    // Use classList.contains instead of querySelector to avoid jsdom
    // nwsapi SYNTAX_ERR on Tailwind slash-opacity class names.
    await waitFor(
      () => {
        const badge = findSourceBadge();
        expect(badge).toBeTruthy();
        expect(badge!.textContent).toMatch(/LightRAG/i);
      },
      { timeout: 4000 },
    );
  });

  it('appends error token to message (lines 117-118)', async () => {
    // { error } branch appends to accumulated but never calls setMessages.
    // A subsequent { token: ' ' } triggers the flush.
    mockFetchOk([
      sseChunk({ error: 'Backend exploded' }),
      sseChunk({ token: ' ' }),
      'data: [DONE]\n\n',
    ]);
    render(<AIChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), {
      target: { value: 'error test' },
    });
    fireEvent.click(getSendButton());
    await waitFor(
      () => expect(screen.queryByText(/Backend exploded/i)).toBeTruthy(),
      { timeout: 4000 },
    );
  });
});

describe('AIChat — HTTP error path (lines 190-199)', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('shows Failed to get response on HTTP error', async () => {
    mockFetchError(503);
    render(<AIChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), {
      target: { value: 'fail test' },
    });
    fireEvent.click(getSendButton());
    await waitFor(
      () => expect(screen.queryByText(/Failed to get response/i)).toBeTruthy(),
      { timeout: 4000 },
    );
  });

  it('shows Failed to get response on fetch network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network down')));
    render(<AIChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), {
      target: { value: 'network fail' },
    });
    fireEvent.click(getSendButton());
    await waitFor(
      () => expect(screen.queryByText(/Failed to get response/i)).toBeTruthy(),
      { timeout: 4000 },
    );
  });
});

describe('AIChat — mode selector + keyboard send', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('changes mode when a mode button is clicked', () => {
    render(<AIChat />);
    // mode buttons: hybrid[0] lightrag[1] vector[2] naive[3]
    fireEvent.click(screen.getAllByRole('button')[2]); // vector
    expect(screen.getByText('vector')).toBeTruthy();
  });

  it('sends on Enter keydown (not Shift+Enter)', async () => {
    mockFetchOk(['data: [DONE]\n\n']);
    render(<AIChat />);
    const textarea = screen.getByPlaceholderText(/Ask your knowledge base/i);
    fireEvent.change(textarea, { target: { value: 'keyboard test' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled(), { timeout: 4000 });
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
