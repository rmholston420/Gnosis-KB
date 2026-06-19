/**
 * ReviewPage — SM-2 Spaced Repetition review session.
 *
 * Flow:
 *   1. Load today's due queue from GET /api/v1/review/queue
 *   2. Show one card at a time (note body in preview mode)
 *   3. User clicks "Show answer" to reveal the rating buttons
 *   4. User rates 0-5; POST /api/v1/review/{id} is called
 *   5. Next card is shown; session ends when queue is empty
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Brain, CheckCircle, ChevronRight, RotateCcw, Zap } from 'lucide-react';
import WikilinkPreview from '../components/WikilinkPreview';
import type { NoteListItem, NoteListResponse } from '../types';
import api from '../services/api';

// ---------------------------------------------------------------------------
// Types (mirrors backend schemas/review.py)
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Rating button config
// ---------------------------------------------------------------------------
const RATINGS: { quality: number; label: string; sublabel: string; color: string }[] = [
  { quality: 0, label: 'Blackout',   sublabel: 'complete blank',      color: 'bg-red-700 hover:bg-red-600' },
  { quality: 1, label: 'Wrong',      sublabel: 'wrong, felt hard',    color: 'bg-red-500 hover:bg-red-400' },
  { quality: 2, label: 'Wrong',      sublabel: 'wrong, felt easy',    color: 'bg-orange-500 hover:bg-orange-400' },
  { quality: 3, label: 'Hard',       sublabel: 'correct, difficult',  color: 'bg-yellow-600 hover:bg-yellow-500' },
  { quality: 4, label: 'Good',       sublabel: 'correct, hesitation', color: 'bg-green-600 hover:bg-green-500' },
  { quality: 5, label: 'Perfect',    sublabel: 'instant recall',      color: 'bg-teal-600 hover:bg-teal-500' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ReviewPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [sessionDone, setSessionDone] = useState(false);
  const [reviewed, setReviewed] = useState(0);

  // Fetch due queue
  const { data: queue = [], isLoading, isError } = useQuery<ReviewCard[]>({
    queryKey: ['review-queue'],
    queryFn: () =>
      fetch('/api/v1/review/queue?limit=100').then((r) => r.json()) as Promise<ReviewCard[]>,
  });

  // Fetch stats
  const { data: stats } = useQuery<ReviewStats>({
    queryKey: ['review-stats'],
    queryFn: () =>
      fetch('/api/v1/review/stats').then((r) => r.json()) as Promise<ReviewStats>,
  });

  // Note list for WikilinkPreview title resolution
  const { data: notesData } = useQuery<NoteListResponse>({
    queryKey: ['notes-titles'],
    queryFn: () => api.listNotes({ page_size: 200 }) as Promise<NoteListResponse>,
  });
  const noteList: NoteListItem[] = notesData?.items ?? [];

  // Submit rating mutation
  const { mutate: submitRating, isPending } = useMutation({
    mutationFn: ({ noteId, quality }: { noteId: string; quality: number }) =>
      fetch(`/api/v1/review/${noteId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quality }),
      }).then((r) => r.json()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review-stats'] });
      const next = index + 1;
      if (next >= queue.length) {
        setSessionDone(true);
      } else {
        setIndex(next);
        setRevealed(false);
        setReviewed((r) => r + 1);
      }
    },
  });

  // ---- Render states -------------------------------------------------------

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted">
        <Brain className="w-6 h-6 mr-2 animate-pulse" /> Loading queue…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        Failed to load review queue.
      </div>
    );
  }

  // Session complete (or queue empty)
  if (sessionDone || queue.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6 px-8">
        <CheckCircle className="w-16 h-16 text-teal-500" />
        <h2 className="text-2xl font-semibold text-text-primary">
          {queue.length === 0 ? 'Nothing due today 🎉' : `Session complete!`}
        </h2>
        {queue.length > 0 && (
          <p className="text-text-muted text-sm">
            Reviewed {reviewed + 1} of {queue.length} cards.
          </p>
        )}
        {stats && (
          <div className="grid grid-cols-3 gap-4 mt-2">
            <StatBox label="Due this week" value={stats.due_this_week} />
            <StatBox label="Total enrolled" value={stats.total_enrolled} />
            <StatBox label="Reviewed today" value={stats.reviewed_today} />
          </div>
        )}
        <div className="flex gap-3">
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 rounded bg-bg-elevated text-text-primary text-sm hover:bg-bg-elevated/80 transition-colors"
          >
            Back to notes
          </button>
          <button
            onClick={() => {
              setIndex(0);
              setRevealed(false);
              setSessionDone(false);
              setReviewed(0);
              queryClient.invalidateQueries({ queryKey: ['review-queue'] });
            }}
            className="px-4 py-2 rounded bg-teal-700 hover:bg-teal-600 text-white text-sm flex items-center gap-1 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reload queue
          </button>
        </div>
      </div>
    );
  }

  const card = queue[index];
  const progress = Math.round(((index) / queue.length) * 100);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-3 border-b border-border flex-shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-2 text-text-primary font-medium">
          <Brain className="w-5 h-5 text-teal-400" />
          Review
        </div>
        <div className="flex items-center gap-4 text-xs text-text-muted">
          <span>{index + 1} / {queue.length}</span>
          {stats && <span>{stats.due_today} due today</span>}
          {/* Progress bar */}
          <div className="w-24 h-1.5 bg-bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full bg-teal-500 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Card */}
      <div className="flex-1 overflow-auto px-8 py-6 flex flex-col gap-6">
        {/* Note metadata */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-text-primary leading-snug">
              {card.note_title}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-text-faint">{card.note_folder}</span>
              {card.note_tags.map((t) => (
                <span key={t} className="text-xs px-1.5 py-0.5 bg-bg-elevated text-text-muted rounded">
                  {t}
                </span>
              ))}
            </div>
          </div>
          {/* SM-2 debug info — subtle, for power users */}
          <div className="text-right text-xs text-text-faint space-y-0.5">
            <div>E={card.easiness.toFixed(2)}</div>
            <div>+{card.interval}d</div>
            <div>#{card.repetitions}</div>
          </div>
        </div>

        {/* Note body */}
        <div className="bg-bg-secondary rounded-lg px-6 py-5 min-h-[200px]">
          <WikilinkPreview body={card.note_body} notes={noteList} />
        </div>

        {/* Reveal / Rate section */}
        {!revealed ? (
          <div className="flex justify-center">
            <button
              onClick={() => setRevealed(true)}
              className="px-6 py-2.5 bg-teal-700 hover:bg-teal-600 text-white rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
            >
              <Zap className="w-4 h-4" /> Rate recall
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-text-muted text-center">How well did you recall this note?</p>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
              {RATINGS.map(({ quality, label, sublabel, color }) => (
                <button
                  key={quality}
                  disabled={isPending}
                  onClick={() => submitRating({ noteId: card.note_id, quality })}
                  className={`${color} text-white rounded-lg px-3 py-3 text-center transition-colors disabled:opacity-50 flex flex-col items-center gap-0.5`}
                >
                  <span className="text-sm font-semibold">{quality}</span>
                  <span className="text-xs font-medium">{label}</span>
                  <span className="text-xs opacity-75 leading-tight">{sublabel}</span>
                </button>
              ))}
            </div>
            {/* Skip */}
            <div className="flex justify-end">
              <button
                onClick={() => {
                  const next = index + 1;
                  if (next >= queue.length) setSessionDone(true);
                  else { setIndex(next); setRevealed(false); }
                }}
                className="text-xs text-text-faint hover:text-text-muted flex items-center gap-1"
              >
                Skip <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-bg-secondary rounded-lg px-4 py-3 text-center">
      <div className="text-2xl font-semibold text-text-primary tabular-nums">{value}</div>
      <div className="text-xs text-text-muted mt-0.5">{label}</div>
    </div>
  );
}
