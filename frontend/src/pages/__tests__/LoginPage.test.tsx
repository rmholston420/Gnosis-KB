/**
 * LoginPage.test.tsx
 * ==================
 * Tests for the login form — render, field input, submit success/failure,
 * loading state, and navigation.
 *
 * Cases (9):
 *  1.  Renders email and password inputs
 *  2.  Renders the Sign in button
 *  3.  Updates email field on change
 *  4.  Updates password field on change
 *  5.  Successful submit stores token and navigates to /
 *  6.  Failed fetch (non-ok response) shows error message
 *  7.  Network error shows error message
 *  8.  Button is disabled and shows "Signing in…" while loading
 *  9.  Error message is cleared on new submit attempt
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../LoginPage';

// Mock useNavigate so we can assert navigation calls
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

function setup() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('LoginPage', () => {
  it('renders email and password inputs', () => {
    setup();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('renders the Sign in button', () => {
    setup();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('updates the email field on change', () => {
    setup();
    const input = screen.getByLabelText(/email/i);
    fireEvent.change(input, { target: { value: 'user@example.com' } });
    expect(input).toHaveValue('user@example.com');
  });

  it('updates the password field on change', () => {
    setup();
    const input = screen.getByLabelText(/password/i);
    fireEvent.change(input, { target: { value: 's3cr3t' } });
    expect(input).toHaveValue('s3cr3t');
  });

  it('stores token in localStorage and navigates to / on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok:   true,
      json: async () => ({ access_token: 'tok-abc123' }),
    } as Response);

    setup();
    fireEvent.change(screen.getByLabelText(/email/i),    { target: { value: 'a@b.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pass' } });
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);

    await waitFor(() => {
      expect(localStorage.getItem('gnosis_token')).toBe('tok-abc123');
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  it('shows error message when response is not ok', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false } as Response);

    setup();
    fireEvent.change(screen.getByLabelText(/email/i),    { target: { value: 'a@b.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'bad' } });
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows error message on network failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    setup();
    fireEvent.change(screen.getByLabelText(/email/i),    { target: { value: 'a@b.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pass' } });
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });
  });

  it('button shows "Signing in…" and is disabled while loading', async () => {
    // Use a promise that never resolves so we can inspect mid-flight state
    let resolveReq!: (v: Response) => void;
    global.fetch = vi.fn().mockReturnValue(
      new Promise<Response>((r) => { resolveReq = r; }),
    );

    setup();
    fireEvent.change(screen.getByLabelText(/email/i),    { target: { value: 'a@b.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pass' } });
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /signing in/i });
      expect(btn).toBeDisabled();
    });

    // Resolve the promise to avoid dangling async after the test
    resolveReq({ ok: false } as Response);
  });

  it('clears the error message on a new submit attempt', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: false } as Response)  // first call: fail
      .mockResolvedValueOnce({ ok: true, json: async () => ({ access_token: 'x' }) } as Response);  // second: succeed

    setup();
    fireEvent.change(screen.getByLabelText(/email/i),    { target: { value: 'a@b.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'bad' } });
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });

    // Submit again — error should disappear before the response
    fireEvent.submit(screen.getByRole('button').closest('form')!);
    await waitFor(() => {
      expect(screen.queryByText(/invalid email or password/i)).not.toBeInTheDocument();
    });
  });
});
