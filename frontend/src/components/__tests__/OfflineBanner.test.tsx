/**
 * OfflineBanner
 * =============
 * Tests the banner component that shows when the user is offline and
 * displays the count of queued operations.
 *
 * What we test (7 cases):
 *  1.  Banner is hidden when isOnline=true and queuedCount=0
 *  2.  Banner is visible when isOnline=false
 *  3.  Shows 'offline' text when isOnline=false
 *  4.  Shows queued count when queuedCount > 0
 *  5.  Shows a 'Sync now' button when isOnline=true and queuedCount > 0
 *  6.  Clicking 'Sync now' calls triggerSync
 *  7.  Banner hidden when isOnline=true and queuedCount=0 (no residual UI)
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import OfflineBanner from '../OfflineBanner';

function renderBanner(props: {
  isOnline?: boolean;
  queuedCount?: number;
  triggerSync?: () => void;
} = {}) {
  return render(
    <OfflineBanner
      isOnline={props.isOnline ?? true}
      queuedCount={props.queuedCount ?? 0}
      triggerSync={props.triggerSync ?? vi.fn()}
    />,
  );
}

afterEach(() => vi.clearAllMocks());

describe('OfflineBanner', () => {
  it('is hidden when isOnline=true and queuedCount=0', () => {
    const { container } = renderBanner({ isOnline: true, queuedCount: 0 });
    // banner should not be in the DOM or should be invisible
    expect(container.firstChild).toBeNull();
  });

  it('is visible when isOnline=false', () => {
    renderBanner({ isOnline: false });
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('shows offline text when isOnline=false', () => {
    renderBanner({ isOnline: false });
    expect(screen.getByText(/offline/i)).toBeInTheDocument();
  });

  it('shows queued count when queuedCount > 0', () => {
    renderBanner({ isOnline: false, queuedCount: 3 });
    expect(screen.getByText(/3/)).toBeInTheDocument();
  });

  it('shows Sync now button when online with pending items', () => {
    renderBanner({ isOnline: true, queuedCount: 2 });
    expect(screen.getByRole('button', { name: /sync now/i })).toBeInTheDocument();
  });

  it('clicking Sync now calls triggerSync', () => {
    const triggerSync = vi.fn();
    renderBanner({ isOnline: true, queuedCount: 2, triggerSync });
    fireEvent.click(screen.getByRole('button', { name: /sync now/i }));
    expect(triggerSync).toHaveBeenCalledOnce();
  });

  it('is hidden when isOnline=true and queuedCount=0 (no residual UI)', () => {
    const { container } = renderBanner({ isOnline: true, queuedCount: 0 });
    expect(container.firstChild).toBeNull();
  });
});
