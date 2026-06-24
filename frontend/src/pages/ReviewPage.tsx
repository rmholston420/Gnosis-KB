/**
 * ReviewPage — spaced-repetition review queue.
 *
 * Data contract (matches test mocks):
 *   GET /api/review/queue  → ReviewCard[]
 *   GET /api/review/stats  → ReviewStats
 *   POST /api/review/{note_id} → { ok: true }
 *
 * ReviewCard shape:
 *   { note_id, note_title, note_body, note_folder, note_tags,
 *     easiness, interval, repetitions, due_date, last_quality }
 *
 * ReviewStats shape:
 *   { due_today, due_this_week, total_enrolled, new_today, reviewed_today }
 *
 * Uses raw fetch() so vi.spyOn(global, 'fetch') works in tests.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const API_BASE = '/api';

interface ReviewCard {
  note_id: string;
  note_title: string;
  note_body: string;
  note_folder: string;
  note_tags: string[];
  easiness: number;
  interval: number;
  repetitions: number;
  due_date: string;
  last_quality: number | null;
}

interface ReviewStats {
  due_today: number;
  due_this_week: number;
  total_enrolled: number;
  new_today: number;
  reviewed_today: number;
}

const QUALITY_LABELS: Record<number, string> = {
  0: 'Blackout',
  1: 'Wrong',
  2: 'Hard',
  3: 'Good',
  4: 'Easy',
  5: 'Perfect',
};

export default function ReviewPage() {
  const navigate = useNavigate();

  const [queue, setQueue] = useState<ReviewCard[]>([]);
  const [_stats, setStats] = useState<ReviewStats | null>(null);
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRating, setShowRating] = useState(false);
  const [sessionDone, setSessionDone] = useState(false);

  // ---- fetch queue + stats ------------------------------------------------
  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [queueRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/review/queue`),
        fetch(`${API_BASE}/review/stats`),
      ]);
      const [queueData, statsData] = await Promise.all([
        queueRes.json() as Promise<ReviewCard[]>,
        statsRes.json() as Promise<ReviewStats>,
      ]);
      setQueue(Array.isArray(queueData) ? queueData : []);
      setStats(statsData);
    } catch {
      setError('Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadQueue(); }, [loadQueue]);

  // ---- submit rating ------------------------------------------------------
  async function submitRating(quality: number) {
    const card = queue[idx];
    try {
      await fetch(`${API_BASE}/review/${card.note_id}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ quality }),
      });
    } catch {
      // best-effort — advance anyway
    }
    advance();
  }

  function advance() {
    setShowRating(false);
    if (idx >= queue.length - 1) {
      setSessionDone(true);
    } else {
      setIdx((i) => i + 1);
    }
  }

  // ---- render states -------------------------------------------------------
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-gnosis-muted text-sm">Loading queue…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <p className="text-gnosis-fg font-medium">{error}</p>
        <button
          onClick={() => void loadQueue()}
          className="px-4 py-2 rounded-lg bg-gnosis-accent text-white text-sm"
        >
          Retry
        </button>
        <button
          onClick={() => navigate('/')}
          className="text-sm text-gnosis-muted underline"
        >
          Back to notes
        </button>
      </div>
    );
  }

  if (sessionDone || queue.length === 0) {
    const isDone = sessionDone;
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <p className="text-gnosis-fg font-medium text-lg">
          {isDone ? 'Session complete!' : 'Nothing due today — great work!'}
        </p>
        {!isDone && (
          <p className="text-gnosis-muted text-sm">Come back tomorrow for your next review.</p>
        )}
        <button
          onClick={() => navigate('/')}
          className="mt-4 px-4 py-2 rounded-lg bg-gnosis-accent text-white text-sm font-medium"
        >
          Back to notes
        </button>
      </div>
    );
  }

  const card = queue[idx];

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gnosis-fg">Review</h1>
        <span className="text-sm text-gnosis-muted">{idx + 1} / {queue.length}</span>
      </div>

      {/* Card */}
      <div className="rounded-xl border border-gnosis-border bg-gnosis-surface p-6 shadow-sm">
        {/* Title */}
        <h2 className="text-lg font-semibold text-gnosis-fg mb-2">{card.note_title}</h2>

        {/* Tags */}
        {card.note_tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {card.note_tags.map((tag) => (
              <span
                key={tag}
                className="px-2 py-0.5 rounded-full bg-gnosis-hover text-gnosis-muted text-xs"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Body preview (via WikilinkPreview if available, else plain) */}
        <div className="text-gnosis-fg text-sm leading-relaxed whitespace-pre-wrap">
          {card.note_body}
        </div>
      </div>

      {/* Action row */}
      <div className="mt-6 flex flex-col gap-4">
        {!showRating ? (
          <button
            aria-label="Rate recall"
            onClick={() => setShowRating(true)}
            className="w-full py-2.5 rounded-lg bg-gnosis-accent text-white font-medium text-sm hover:opacity-90"
          >
            Rate recall
          </button>
        ) : (
          <div className="rounded-xl border border-gnosis-border bg-gnosis-surface p-4">
            <p className="text-sm text-gnosis-muted mb-3 text-center">
              How well did you recall this?
            </p>
            <div className="grid grid-cols-3 gap-2">
              {([0, 1, 2, 3, 4, 5] as const).map((q) => (
                <button
                  key={q}
                  onClick={() => void submitRating(q)}
                  className="py-2 rounded-lg border border-gnosis-border text-sm hover:bg-gnosis-hover transition-colors"
                >
                  {q} — {QUALITY_LABELS[q]}
                </button>
              ))}
            </div>
            <button
              onClick={advance}
              className="mt-3 w-full text-sm text-gnosis-muted underline text-center"
            >
              Skip
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
