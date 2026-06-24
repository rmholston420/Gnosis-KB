/**
 * OfflineBanner
 * =============
 * Tests the sticky top banner that shows when offline or changes are queued.
 *
 * Cases:
 *  1. Nothing shown when online + no queue
 *  2. Shows offline message when offline
 *  3. Shows queued count when online + queue > 0
 *  4. Retry button disabled when offline
 *  5. Retry button calls onSyncClick when online + queue > 0
 *  6. Pluralises "change" correctly for count=1 vs count=2
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { OfflineBanner } from '../OfflineBanner';

function setup(isOnline: boolean, queuedCount: number, onSyncClick = vi.fn()) {
  return render(
    <OfflineBanner
      isOnline={isOnline}
      queuedCount={queuedCount}
      onSyncClick={onSyncClick}
    />,
  );
}

afterEach(() => { vi.clearAllMocks(); });

describe('OfflineBanner', () => {
  it('renders nothing when online and queue is empty', () => {
    const { container } = setup(true, 0);
    expect(container.firstChild).toBeNull();
  });

  it('shows offline message when isOnline=false', () => {
    setup(false, 0);
    expect(screen.getByText(/you are offline/i)).toBeInTheDocument();
  });

  it('shows queued count message when online and queue > 0', () => {
    setup(true, 3);
    expect(screen.getByText(/3 changes queued/i)).toBeInTheDocument();
  });

  it('retry button is disabled when offline', () => {
    setup(false, 2);
    const btn = screen.getByRole('button', { name: /retry sync/i });
    expect(btn).toBeDisabled();
  });

  it('retry button calls onSyncClick when online', () => {
    const onSyncClick = vi.fn();
    setup(true, 1, onSyncClick);
    fireEvent.click(screen.getByRole('button', { name: /retry sync/i }));
    expect(onSyncClick).toHaveBeenCalledOnce();
  });

  it('uses singular "change" for count=1', () => {
    setup(true, 1);
    expect(screen.getByText(/1 change queued/i)).toBeInTheDocument();
  });
});
