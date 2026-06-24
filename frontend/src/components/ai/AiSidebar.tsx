/**
 * AiSidebar — collapsible AI tools panel shown alongside the note editor.
 * Provides: note summary, link suggestions, tag suggestions, and Zettelkasten critique.
 */
import React, { useState } from 'react';
import { Sparkles, Link2, Tag, MessageSquare, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { useNoteSummary, useLinkSuggestions, useTagSuggestions, useNoteCritique } from '../../hooks/useAI';
import type { LinkSuggestion, TagSuggestion, AiCritique } from '../../types';

interface AiSidebarProps {
  noteId: string | null;
  /** Called when user accepts a link suggestion — parent inserts the wikilink. */
  onInsertLink?: (suggestion: LinkSuggestion) => void;
  /** Called when user accepts a tag suggestion. */
  onInsertTag?:  (tag: string) => void;
}

/** Collapsible section wrapper. */
function Section({
  title, icon, children, defaultOpen = false,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-gnosis-border last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gnosis-muted hover:text-gnosis-fg transition-colors"
        aria-expanded={open}
      >
        {icon}
        <span className="font-medium">{title}</span>
        <span className="ml-auto">{open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</span>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

/** Summary section. */
function SummarySection({ noteId }: { noteId: string }) {
  const { mutate, data, isPending } = useNoteSummary(noteId);
  return (
    <Section title="AI Summary" icon={<Sparkles size={12} />}>
      {data ? (
        <p className="text-xs text-gnosis-fg leading-relaxed">{data.summary}</p>
      ) : (
        <button
          onClick={() => mutate()}
          disabled={isPending}
          className="text-xs text-gnosis-accent hover:underline flex items-center gap-1"
        >
          {isPending && <Loader2 size={10} className="animate-spin" />}
          Generate summary
        </button>
      )}
    </Section>
  );
}

/** Link suggestions section. */
function LinkSection({
  noteId, onInsertLink,
}: { noteId: string; onInsertLink?: (s: LinkSuggestion) => void }) {
  const { data: suggestions = [], isLoading } = useLinkSuggestions(noteId);
  return (
    <Section title="Suggested Links" icon={<Link2 size={12} />}>
      {isLoading ? (
        <Loader2 size={12} className="animate-spin text-gnosis-muted" />
      ) : suggestions.length === 0 ? (
        <p className="text-xs text-gnosis-muted">No suggestions yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {suggestions.map((s) => (
            <li key={s.target_note_id} className="flex items-start justify-between gap-2">
              <div>
                <p className="text-xs font-medium text-gnosis-fg">{s.target_title}</p>
                <p className="text-xs text-gnosis-muted leading-tight">{s.reason}</p>
              </div>
              {onInsertLink && (
                <button
                  onClick={() => onInsertLink(s)}
                  className="text-xs text-gnosis-accent hover:underline flex-shrink-0"
                >
                  Insert
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/** Tag suggestions section. */
function TagSection({
  noteId, onInsertTag,
}: { noteId: string; onInsertTag?: (tag: string) => void }) {
  const { data: suggestions = [], isLoading } = useTagSuggestions(noteId);
  return (
    <Section title="Suggested Tags" icon={<Tag size={12} />}>
      {isLoading ? (
        <Loader2 size={12} className="animate-spin text-gnosis-muted" />
      ) : suggestions.length === 0 ? (
        <p className="text-xs text-gnosis-muted">No tag suggestions.</p>
      ) : (
        <div className="flex flex-wrap gap-1">
          {suggestions.map((s) => (
            <button
              key={s.tag}
              onClick={() => onInsertTag?.(s.tag)}
              className="text-xs px-2 py-0.5 rounded-full bg-gnosis-muted/10 text-gnosis-muted hover:bg-gnosis-accent/20 hover:text-gnosis-accent transition-colors"
            >
              #{s.tag}
            </button>
          ))}
        </div>
      )}
    </Section>
  );
}

/** Zettelkasten critique section. */
function CritiqueSection({ noteId }: { noteId: string }) {
  const { mutate, data, isPending } = useNoteCritique(noteId);
  return (
    <Section title="ZK Critique" icon={<MessageSquare size={12} />}>
      {data ? (
        <CritiqueResult critique={data} />
      ) : (
        <button
          onClick={() => mutate()}
          disabled={isPending}
          className="text-xs text-gnosis-accent hover:underline flex items-center gap-1"
        >
          {isPending && <Loader2 size={10} className="animate-spin" />}
          Run critique
        </button>
      )}
    </Section>
  );
}

function CritiqueResult({ critique }: { critique: AiCritique }) {
  const items: Array<{ label: string; score: number; feedback: string }> = [
    { label: 'Atomicity',         score: critique.atomicity_score,      feedback: critique.atomicity_feedback },
    { label: 'Connectivity',      score: critique.connectivity_score,   feedback: critique.connectivity_feedback },
    { label: 'Self-containedness',score: critique.standalone_score,     feedback: critique.standalone_feedback },
    { label: 'Insight density',   score: critique.insight_score,        feedback: critique.insight_feedback },
  ];
  return (
    <ul className="space-y-2">
      {items.map(({ label, score, feedback }) => (
        <li key={label}>
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-xs font-medium text-gnosis-fg">{label}</span>
            <span className={`text-xs font-bold ${ score >= 4 ? 'text-green-400' : score >= 2 ? 'text-yellow-400' : 'text-red-400' }`}>
              {score}/5
            </span>
          </div>
          <p className="text-xs text-gnosis-muted leading-tight">{feedback}</p>
        </li>
      ))}
    </ul>
  );
}

/**
 * AiSidebar renders collapsible AI tool sections for the active note.
 */
export function AiSidebar({ noteId, onInsertLink, onInsertTag }: AiSidebarProps) {
  if (!noteId) {
    return (
      <div className="h-full flex items-center justify-center text-xs text-gnosis-muted p-4">
        Open a note to use AI tools.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-gnosis-surface border-l border-gnosis-border">
      <div className="px-3 py-2 border-b border-gnosis-border flex items-center gap-2">
        <Sparkles size={13} className="text-gnosis-accent" />
        <span className="text-xs font-semibold text-gnosis-fg">AI Tools</span>
      </div>
      <SummarySection noteId={noteId} />
      <LinkSection    noteId={noteId} onInsertLink={onInsertLink} />
      <TagSection     noteId={noteId} onInsertTag={onInsertTag} />
      <CritiqueSection noteId={noteId} />
    </div>
  );
}
