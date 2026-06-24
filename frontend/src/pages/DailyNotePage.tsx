import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import type { Note } from '../types';
import { Loader2, CalendarDays } from 'lucide-react';

export default function DailyNotePage() {
  const navigate = useNavigate();
  const [note, setNote] = useState<Note | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    (api.getDailyNote() as Promise<Note>)
      .then((n) => {
        if (cancelled) return;
        setNote(n);
        navigate(`/notes/${n.id}`, { replace: true });
      })
      .catch(() => { if (!cancelled) setIsLoading(false); })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, [navigate]);

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });

  if (isLoading || !note) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-text-muted" size={24} data-testid="loading" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border flex-shrink-0 bg-bg-primary">
        <CalendarDays size={15} className="text-text-muted" />
        <span className="text-xs font-medium text-text-muted">{today}</span>
      </div>
    </div>
  );
}
