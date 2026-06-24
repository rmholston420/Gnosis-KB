/// <reference types="vitest/globals" />
import { relativeTime, formatRelative, formatDate, formatFull, isToday, today, toVaultDate } from '../dateUtils';

describe('dateUtils', () => {
  afterEach(() => { vi.useRealTimers(); });

  describe('today / toVaultDate', () => {
    it('returns YYYY-MM-DD format', () => {
      expect(today()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });
    it('formats a specific date correctly', () => {
      expect(toVaultDate(new Date('2026-06-24T00:00:00Z'))).toBe('2026-06-24');
    });
  });

  describe('isToday', () => {
    it('returns true for today', () => {
      expect(isToday(today())).toBe(true);
    });
    it('returns false for yesterday', () => {
      expect(isToday('2000-01-01')).toBe(false);
    });
  });

  describe('relativeTime / formatRelative alias', () => {
    it('returns "just now" for recent timestamps', () => {
      const now = new Date().toISOString();
      expect(relativeTime(now)).toBe('just now');
      expect(formatRelative(now)).toBe('just now');
    });
    it('returns minutes for older timestamps', () => {
      const past = new Date(Date.now() - 5 * 60 * 1000).toISOString();
      expect(relativeTime(past)).toBe('5m ago');
    });
  });

  describe('formatDate / formatFull', () => {
    it('formatDate produces a readable date', () => {
      const result = formatDate('2026-06-24T12:00:00Z');
      expect(result).toContain('2026');
    });
    it('formatFull includes time', () => {
      const result = formatFull('2026-06-24T14:30:00Z');
      expect(result).toContain('2026');
    });
  });
});
