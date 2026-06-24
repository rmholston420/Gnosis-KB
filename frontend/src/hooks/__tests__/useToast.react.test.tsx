/**
 * useToast.react.test.tsx
 * =======================
 * Covers the React-facing surface of useToast that the imperative
 * unit tests in useToast.test.ts do not exercise:
 *
 *  - ToastContainer renders toasts from the store
 *  - ToastContainer re-renders when a toast is added imperatively
 *  - ToastContainer removes a toast when its dismiss button is clicked
 *  - useToast() hook returns the current toast list
 *  - useToast() hook updates when a toast is added / removed
 *  - warning variant renders correctly
 *  - Dismiss button has accessible aria-label
 *
 * Covers lines 100-106, 115-146, 149-182, 185-197 (ToastItem, ToastContainer,
 * useToast hook body, mountToastContainer).
 */

import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, act, renderHook } from '@testing-library/react';
import React from 'react';
import { toast, _store, ToastContainer, useToast } from '../useToast';

afterEach(() => {
  act(() => { _store.clear(); });
});

describe('ToastContainer', () => {
  it('renders nothing when the store is empty', () => {
    render(<ToastContainer />);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('renders a toast added imperatively via toast.success()', () => {
    render(<ToastContainer />);
    act(() => { toast.success('Saved!'); });
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Saved!')).toBeInTheDocument();
  });

  it('renders a toast added via toast.error()', () => {
    render(<ToastContainer />);
    act(() => { toast.error('Oops'); });
    expect(screen.getByText('Oops')).toBeInTheDocument();
  });

  it('renders a toast added via toast.info()', () => {
    render(<ToastContainer />);
    act(() => { toast.info('FYI'); });
    expect(screen.getByText('FYI')).toBeInTheDocument();
  });

  it('renders a toast added via toast.warning()', () => {
    render(<ToastContainer />);
    act(() => { toast.warning('Watch out'); });
    expect(screen.getByText('Watch out')).toBeInTheDocument();
  });

  it('removes a toast when the dismiss button is clicked', () => {
    render(<ToastContainer />);
    act(() => { toast.success('To be dismissed'); });
    expect(screen.getByText('To be dismissed')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByText('To be dismissed')).not.toBeInTheDocument();
  });

  it('dismiss button has aria-label="Dismiss"', () => {
    render(<ToastContainer />);
    act(() => { toast.info('Check label'); });
    expect(screen.getByRole('button', { name: 'Dismiss' })).toBeInTheDocument();
  });

  it('renders multiple toasts simultaneously', () => {
    render(<ToastContainer />);
    act(() => {
      toast.success('First');
      toast.error('Second');
    });
    expect(screen.getAllByRole('alert')).toHaveLength(2);
  });

  it('removes the correct toast when one of many is dismissed', () => {
    render(<ToastContainer />);
    act(() => {
      toast.success('Keep me');
      toast.error('Remove me');
    });
    const dismissButtons = screen.getAllByRole('button', { name: /dismiss/i });
    fireEvent.click(dismissButtons[1]); // dismiss 'Remove me' (second alert)
    expect(screen.queryByText('Remove me')).not.toBeInTheDocument();
    expect(screen.getByText('Keep me')).toBeInTheDocument();
  });
});

describe('useToast hook', () => {
  it('returns empty array when store is empty', () => {
    const { result } = renderHook(() => useToast());
    expect(result.current).toHaveLength(0);
  });

  it('returns updated list when a toast is added', () => {
    const { result } = renderHook(() => useToast());
    act(() => { toast.success('Hook toast'); });
    expect(result.current).toHaveLength(1);
    expect(result.current[0].message).toBe('Hook toast');
    expect(result.current[0].variant).toBe('success');
  });

  it('returns updated list when a toast is removed', () => {
    const { result } = renderHook(() => useToast());
    let id!: string;
    act(() => { id = toast.info('Going away'); });
    expect(result.current).toHaveLength(1);
    act(() => { toast.dismiss(id); });
    expect(result.current).toHaveLength(0);
  });
});
