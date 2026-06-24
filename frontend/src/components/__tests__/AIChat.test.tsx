/**
 * AIChat.test.tsx — tests for src/components/AIChat.tsx
 *
 * This is the legacy top-level AIChat that uses fetch() + ReadableStream
 * instead of EventSource. We mock globalThis.fetch to return a fake
 * streaming response.
 *
 * jsdom does not provide ReadableStream by default in all configurations;
 * we construct the fake response using a simple string body so that
 * the reader.read() loop completes synchronously after one chunk.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AIChat from '../AIChat';

// ---------------------------------------------------------------------------
// Helpers to build fake SSE fetch responses
// ---------------------------------------------------------------------------
function sseBody(lines: string[]): ReadableStream<Uint8Array> {
  const text = lines.join('\n\n') + '\n\n';
  const encoder = new TextEncoder();
  const bytes = encoder.encode(text);
  return new ReadableStream({
    start(controller) {
      controller.enqueue(bytes);
      controller.close();
    },
  });
}

function okSseResponse(lines: string[]) {
  return Promise.resolve(
    new Response(sseBody(lines), { status: 200 })
  );
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
  // localStorage stub
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(() => 'test-token'),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('AIChat (legacy fetch-based) — render', () => {
  it('renders the empty state placeholder', () => {
    render(<AIChat />);
    expect(screen.getByText(/ask anything about your knowledge base/i)).toBeInTheDocument();
  });

  it('renders mode selector buttons', () => {
    render(<AIChat />);
    expect(screen.getByRole('button', { name: 'hybrid' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'lightrag' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'vector' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'naive' })).toBeInTheDocument();
  });

  it('Send button is disabled when input is empty', () => {
    render(<AIChat />);
    // The send button has no text label — locate by role + look for disabled state
    const buttons = screen.getAllByRole('button');
    // The send button is the last one (after mode buttons)
    const sendBtn = buttons[buttons.length - 1];
    expect(sendBtn).toBeDisabled();
  });

  it('Send button is enabled after typing', () => {
    render(<AIChat />);
    const ta = screen.getByPlaceholderText(/ask your knowledge base/i);
    fireEvent.change(ta, { target: { value: 'What is EEG?' } });
    const buttons = screen.getAllByRole('button');
    const sendBtn = buttons[buttons.length - 1];
    expect(sendBtn).not.toBeDisabled();
  });

  it('switches mode when mode button is clicked', () => {
    render(<AIChat />);
    const vectorBtn = screen.getByRole('button', { name: 'vector' });
    fireEvent.click(vectorBtn);
    // The clicked button should gain the active styling class (bg-accent-teal)
    expect(vectorBtn.className).toContain('bg-accent-teal');
  });
});

describe('AIChat (legacy fetch-based) — send', () => {
  it('renders user message after sending', async () => {
    const fetchMock = vi.fn(() => okSseResponse([
      'data: {"token":"Hello"}',
      'data: [DONE]',
    ]));
    vi.stubGlobal('fetch', fetchMock);

    render(<AIChat />);
    const ta = screen.getByPlaceholderText(/ask your knowledge base/i);
    fireEvent.change(ta, { target: { value: 'What is EEG?' } });
    fireEvent.keyDown(ta, { key: 'Enter', shiftKey: false });

    await waitFor(() =>
      expect(screen.getByText('What is EEG?')).toBeInTheDocument()
    );
  });

  it('streams assistant token into message', async () => {
    const fetchMock = vi.fn(() => okSseResponse([
      'data: {"token":"Signal"}',
      'data: {"token":" processing"}',
      'data: [DONE]',
    ]));
    vi.stubGlobal('fetch', fetchMock);

    render(<AIChat />);
    const ta = screen.getByPlaceholderText(/ask your knowledge base/i);
    fireEvent.change(ta, { target: { value: 'Tell me about DSP' } });
    fireEvent.keyDown(ta, { key: 'Enter', shiftKey: false });

    await waitFor(() =>
      expect(screen.getByText(/Signal processing/)).toBeInTheDocument()
    );
  });

  it('shows error message on non-ok HTTP response', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve(new Response(null, { status: 500 }))
    ));

    render(<AIChat />);
    const ta = screen.getByPlaceholderText(/ask your knowledge base/i);
    fireEvent.change(ta, { target: { value: 'Fail test' } });
    fireEvent.keyDown(ta, { key: 'Enter', shiftKey: false });

    await waitFor(() =>
      expect(screen.getByText(/Failed to get response/i)).toBeInTheDocument()
    );
  });

  it('shows error message on fetch network throw', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('Network down'))));

    render(<AIChat />);
    const ta = screen.getByPlaceholderText(/ask your knowledge base/i);
    fireEvent.change(ta, { target: { value: 'Fail test 2' } });
    fireEvent.keyDown(ta, { key: 'Enter', shiftKey: false });

    await waitFor(() =>
      expect(screen.getByText(/Network down/)).toBeInTheDocument()
    );
  });

  it('does not call fetch when input is empty', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    render(<AIChat />);
    const ta = screen.getByPlaceholderText(/ask your knowledge base/i);
    fireEvent.keyDown(ta, { key: 'Enter', shiftKey: false });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('Shift+Enter does not trigger send', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    render(<AIChat />);
    const ta = screen.getByPlaceholderText(/ask your knowledge base/i);
    fireEvent.change(ta, { target: { value: 'Multi-line' } });
    fireEvent.keyDown(ta, { key: 'Enter', shiftKey: true });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
