import { describe, it, expect, vi, afterEach } from 'vitest';
import { formatRelative, formatFull, isToday } from '../dateUtils';

const NOW = new Date('2026-06-24T20:00:00.000Z');

afterEach(() => vi.useRealTimers());

describe('formatRelative', () => {
  it('shows "just now" for <60 s', () => {
    vi.setSystemTime(NOW);
    const ts = new Date(NOW.getTime() - 30_000).toISOString();
    expect(formatRelative(ts)).toMatch(/just now|seconds? ago/i);
  });

  it('shows minutes ago', () => {
    vi.setSystemTime(NOW);
    const ts = new Date(NOW.getTime() - 5 * 60_000).toISOString();
    expect(formatRelative(ts)).toMatch(/5 min/i);
  });
});

describe('formatFull', () => {
  it('returns a human-readable date string', () => {
    const result = formatFull('2026-06-24T12:00:00Z');
    expect(result).toMatch(/2026/);
    expect(result).toMatch(/Jun/);
  });
});

describe('isToday', () => {
  it('returns true for today', () => {
    vi.setSystemTime(NOW);
    expect(isToday(NOW.toISOString())).toBe(true);
  });

  it('returns false for yesterday', () => {
    vi.setSystemTime(NOW);
    const yesterday = new Date(NOW.getTime() - 86_400_000).toISOString();
    expect(isToday(yesterday)).toBe(false);
  });
});
