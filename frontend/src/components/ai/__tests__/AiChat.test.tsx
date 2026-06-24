/**
 * AiChat.test.tsx
 * ===============
 * Tests for the streaming AI chat panel component.
 * We mock the global fetch so SSE streaming is controlled in tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AiChat from '../AiChat';
import { useAppStore } from '../../../store/useAppStore';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// Stub fetch to return a minimal SSE stream
function makeFetchStub(chunks: string[]) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return vi.fn().mockResolvedValue({
    ok: true,
    body: stream,
  });
}

function renderChat() {
  return render(<MemoryRouter><AiChat /></MemoryRouter>);
}

beforeEach(() => {
  useAppStore.setState({ chatMessages: [], sessionId: null, ragMode: 'hybrid' });
  mockNavigate.mockReset();
  vi.restoreAllMocks();
});

describe('AiChat', () => {
  it('renders the message input', () => {
    renderChat();
    expect(screen.getByPlaceholderText(/ask/i)).toBeInTheDocument();
  });

  it('renders the Send button', () => {
    renderChat();
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  it('Send button is disabled when input is empty', () => {
    renderChat();
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled();
  });

  it('Send button is enabled when input has text', () => {
    renderChat();
    const input = screen.getByPlaceholderText(/ask/i);
    fireEvent.change(input, { target: { value: 'What is emptiness?' } });
    expect(screen.getByRole('button', { name: /send/i })).not.toBeDisabled();
  });

  it('renders RAG mode selector buttons', () => {
    renderChat();
    expect(screen.getByText(/hybrid/i)).toBeInTheDocument();
  });

  it('shows empty state when no messages', () => {
    renderChat();
    // No message bubbles present
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
  });

  it('shows user message in store after sending', async () => {
    global.fetch = makeFetchStub([]);
    renderChat();
    const input = screen.getByPlaceholderText(/ask/i);
    fireEvent.change(input, { target: { value: 'What is emptiness?' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() =>
      expect(useAppStore.getState().chatMessages.some((m) => m.role === 'user')).toBe(true)
    );
  });

  it('clears input after sending', async () => {
    global.fetch = makeFetchStub([]);
    renderChat();
    const input = screen.getByPlaceholderText(/ask/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() => expect(input.value).toBe(''));
  });

  it('renders Clear button', () => {
    renderChat();
    expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
  });

  it('Clear button clears chat messages', () => {
    useAppStore.setState({ chatMessages: [{ role: 'user', content: 'hi' }] });
    renderChat();
    fireEvent.click(screen.getByRole('button', { name: /clear/i }));
    expect(useAppStore.getState().chatMessages).toHaveLength(0);
  });
});
