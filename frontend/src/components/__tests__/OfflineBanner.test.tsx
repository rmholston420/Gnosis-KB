/**
 * OfflineBanner
 * =============
 *
 * Key facts about the real component:
 *  - Props: isOnline, queuedCount, onSyncClick (async fn) — NOT triggerSync
 *  - The component uses role="status" (aria-live polite), NOT role="alert"
 *  - It is mounted/visible only when isOnline=false
 *  - When isOnline=true the component returns null immediately (mounted=false)
 *  - The button text is "Retry sync" (aria-label="Retry sync now")
 *  - There is NO separate "Sync now" button when online — the banner is
 *    only ever shown while offline
 *
 * What we test (7 cases):
 *  1.  Returns null (renders nothing) when isOnline=true
 *  2.  Renders the status region when isOnline=false
 *  3.  Shows offline message text when isOnline=false
 *  4.  Shows queued count badge when queuedCount > 0
 *  5.  Shows the "Retry sync" button when offline
 *  6.  Clicking "Retry sync" calls onSyncClick
 *  7.  Returns null when isOnline=true regardless of queuedCount
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';
import OfflineBanner from '../OfflineBanner';

function renderBanner(props: {
  isOnline?: boolean;
  queuedCount?: number;
  onSyncClick?: () => Promise<void>;
} = {}) {
  return render(
    <OfflineBanner
      isOnline={props.isOnline ?? true}
      queuedCount={props.queuedCount ?? 0}
      onSyncClick={props.onSyncClick ?? vi.fn().mockResolvedValue(undefined)}
    />,
  );
}

afterEach(() => vi.clearAllMocks());

describe('OfflineBanner', () => {
  it('renders nothing when isOnline=true', () => {
    const { container } = renderBanner({ isOnline: true, queuedCount: 0 });
    expect(container.firstChild).toBeNull();
  });

  it('renders the status region when isOnline=false', () => {
    renderBanner({ isOnline: false });
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows offline message text when isOnline=false', () => {
    renderBanner({ isOnline: false });
    expect(screen.getByText(/you are offline/i)).toBeInTheDocument();
  });

  it('shows queued count when queuedCount > 0', () => {
    renderBanner({ isOnline: false, queuedCount: 3 });
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('shows the Retry sync button when offline', () => {
    renderBanner({ isOnline: false });
    expect(screen.getByRole('button', { name: /retry sync now/i })).toBeInTheDocument();
  });

  it('clicking Retry sync calls onSyncClick', async () => {
    const onSyncClick = vi.fn().mockResolvedValue(undefined);
    renderBanner({ isOnline: false, onSyncClick });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /retry sync now/i }));
    });
    expect(onSyncClick).toHaveBeenCalledOnce();
  });

  it('renders nothing when isOnline=true even with pending items', () => {
    const { container } = renderBanner({ isOnline: true, queuedCount: 5 });
    expect(container.firstChild).toBeNull();
  });
});
