/**
 * AiChat.extended.test.tsx
 * Targets uncovered lines in components/ai/AiChat.tsx:
 *   49-53   — EventSource URL construction (relative path branch)
 *   69-88   — es.onmessage: [DONE], token, error token
 *   91-96   — es.onerror path
 *   179-180 — clearChat button render + click
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ---- Hoisted EventSource mock ----------------------------------------------
const { MockEventSource, mockESInstances } = vi.hoisted(() => {
  const mockESInstances: Array<{
    url: string;
    onmessage: ((e: MessageEvent) => void) | null;
    onerror: (() => void) | null;
    close: ReturnType<typeof vi.fn>;
  }> = [];
  class MockEventSource {
    url: string;
    onmessage: ((e: MessageEvent) => void) | null = null;
    onerror: (() => void) | null = null;
    close = vi.fn();
    constructor(url: string) { this.url = url; mockESInstances.push(this); }
  }
  return { MockEventSource, mockESInstances };
});
vi.stubGlobal('EventSource', MockEventSource);

// ---- useAppStore mock -------------------------------------------------------
const { storeState } = vi.hoisted(() => {
  const storeState = {
    chatMessages: [] as Array<{ role: string; content: string }>,
    appendChatMessage: vi.fn((msg: { role: string; content: string }) => {
      storeState.chatMessages = [...storeState.chatMessages, msg];
    }),
    updateLastAssistantMessage: vi.fn((content: string) => {
      const msgs = [...storeState.chatMessages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') { msgs[i] = { ...msgs[i], content }; break; }
      }
      storeState.chatMessages = msgs;
    }),
    clearChat: vi.fn(() => { storeState.chatMessages = []; }),
  };
  return { storeState };
});
vi.mock('@/store/useAppStore', () => ({ useAppStore: () => storeState }));

import AiChat from '@/components/ai/AiChat';

function getLatestES() { return mockESInstances[mockESInstances.length - 1]; }

describe('AiChat — EventSource messaging (lines 69-88)', () => {
  beforeEach(() => { vi.clearAllMocks(); storeState.chatMessages = []; mockESInstances.length = 0; });

  it('accumulates token messages via onmessage', async () => {
    render(<AiChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), { target: { value: 'hello' } });
    fireEvent.click(screen.getByRole('button', { name: /Send/i }));
    await waitFor(() => expect(getLatestES()).toBeTruthy());
    act(() => {
      getLatestES().onmessage?.({ data: JSON.stringify({ token: 'Hi ' }) } as MessageEvent);
      getLatestES().onmessage?.({ data: JSON.stringify({ token: 'there' }) } as MessageEvent);
    });
    expect(storeState.updateLastAssistantMessage).toHaveBeenLastCalledWith('Hi there');
  });

  it('[DONE] closes EventSource — Send stays disabled when input is empty (line 69)', async () => {
    render(<AiChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), { target: { value: 'done test' } });
    fireEvent.click(screen.getByRole('button', { name: /Send/i }));
    await waitFor(() => expect(getLatestES()).toBeTruthy());
    const es = getLatestES();
    act(() => { es.onmessage?.({ data: '[DONE]' } as MessageEvent); });
    expect(es.close).toHaveBeenCalled();
    // Input was cleared on send — so Send is disabled because input.trim()==='' even after loading=false
    await waitFor(() =>
      expect((screen.getByRole('button', { name: /Send/i }) as HTMLButtonElement).disabled).toBe(true)
    );
  });

  it('appends error token on error payload (lines 78-81)', async () => {
    render(<AiChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), { target: { value: 'err test' } });
    fireEvent.click(screen.getByRole('button', { name: /Send/i }));
    await waitFor(() => expect(getLatestES()).toBeTruthy());
    act(() => { getLatestES().onmessage?.({ data: JSON.stringify({ error: 'oops' }) } as MessageEvent); });
    expect(storeState.updateLastAssistantMessage).toHaveBeenCalledWith(expect.stringContaining('Error: oops'));
  });
});

describe('AiChat — EventSource onerror (lines 91-96)', () => {
  beforeEach(() => { vi.clearAllMocks(); storeState.chatMessages = []; mockESInstances.length = 0; });

  it('calls updateLastAssistantMessage with connection error on onerror', async () => {
    render(<AiChat />);
    fireEvent.change(screen.getByPlaceholderText(/Ask your knowledge base/i), { target: { value: 'onerror test' } });
    fireEvent.click(screen.getByRole('button', { name: /Send/i }));
    await waitFor(() => expect(getLatestES()).toBeTruthy());
    const es = getLatestES();
    act(() => { es.onerror?.(); });
    expect(es.close).toHaveBeenCalled();
    expect(storeState.updateLastAssistantMessage).toHaveBeenCalledWith(expect.stringContaining('Connection error'));
  });
});

describe('AiChat — clearChat button (lines 179-180)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockESInstances.length = 0;
    storeState.chatMessages = [{ role: 'user', content: 'hi' }, { role: 'assistant', content: 'hello' }];
  });

  it('renders Clear button when messages exist and calls clearChat on click', () => {
    render(<AiChat />);
    const clearBtn = screen.getByRole('button', { name: /Clear chat/i });
    expect(clearBtn).toBeTruthy();
    fireEvent.click(clearBtn);
    expect(storeState.clearChat).toHaveBeenCalled();
  });
});

describe('AiChat — empty state', () => {
  beforeEach(() => { vi.clearAllMocks(); mockESInstances.length = 0; storeState.chatMessages = []; });

  it('shows empty state prompt when no messages', () => {
    render(<AiChat />);
    expect(screen.getByText(/Ask anything about your knowledge base/i)).toBeTruthy();
  });
});
