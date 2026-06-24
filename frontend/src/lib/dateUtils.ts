/**
 * Date utility helpers.
 * Uses plain Date / Intl APIs; no external dependency required.
 */

/** Format a date as YYYY-MM-DD (vault filename format). */
export function toVaultDate(d: Date = new Date()): string {
  return d.toISOString().slice(0, 10);
}

/** Return today's date in YYYY-MM-DD format. */
export function today(): string {
  return toVaultDate(new Date());
}

/** Return a timestamp-style ID matching the spec: YYYYMMDD-HHmmss. */
export function newNoteId(d: Date = new Date()): string {
  const pad = (n: number, len = 2) => String(n).padStart(len, '0');
  return [
    String(d.getFullYear()),
    pad(d.getMonth() + 1),
    pad(d.getDate()),
    '-',
    pad(d.getHours()),
    pad(d.getMinutes()),
    pad(d.getSeconds()),
  ].join('');
}

/** Human-readable relative time ("2 hours ago", "just now"). */
export function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const sec  = Math.floor(diff / 1000);
  if (sec < 60)  return 'just now';
  const min  = Math.floor(sec / 60);
  if (min < 60)  return `${min}m ago`;
  const hr   = Math.floor(min / 60);
  if (hr  < 24)  return `${hr}h ago`;
  const day  = Math.floor(hr  / 24);
  if (day < 30)  return `${day}d ago`;
  const mo   = Math.floor(day / 30);
  if (mo  < 12)  return `${mo}mo ago`;
  return `${Math.floor(mo / 12)}y ago`;
}

/** Format an ISO date string as a human-readable date, e.g. "Jun 24, 2026". */
export function formatDate(isoString: string): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  }).format(new Date(isoString));
}

/** Return the ISO week number for a given date. */
export function isoWeek(d: Date = new Date()): number {
  const jan4 = new Date(d.getFullYear(), 0, 4);
  const startOfWeek1 = jan4.getTime() - (jan4.getDay() || 7) * 86400000;
  return Math.ceil(((d.getTime() - startOfWeek1) / 86400000 + 1) / 7);
}
