/**
 * NoteDetailPanel — right-side panel for viewing a note from the vault list.
 *
 * Features:
 *  - Full note body rendered as Markdown (react-markdown)
 *  - Wikilinks extracted and rendered as clickable chips → navigates to the linked note
 *  - RAG action buttons: Summarize, Critique, Suggest Links
 *  - "Ingest into Graph" button for on-demand LightRAG backfill
 *  - Edit button → navigates to the full NoteEditorPage
 *  - Close button → calls onClose()
 */

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  Edit3,
  Cpu,
  GitBranch,
  Link2,
  FileText,
  Loader2,
  Share2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Note } from '../types';
import api from '../services/api';

interface NoteDetailPanelProps {
  note: Note;
  onClose: () => void;
  /** Called when a wikilink chip is clicked — parent resolves the title to a note id */
  onWikilinkClick?: (title: string) => void;
}

type ActionState = 'idle' | 'loading' | 'done' | 'error';

interface ActionResult {
  type: 'summary' | 'critique' | 'links' | 'ingest';
  content: string;
}

/** Extract [[wikilink]] titles from raw Markdown body. */
function extractWikilinks(body: string): string[] {
  const matches = body.matchAll(/\[\[([^\]]+)\]\]/g);
  const titles = new Set<string>();
  for (const m of matches) {
    titles.add(m[1].split('|')[0].trim()); // handle [[Title|Alias]] syntax
  }
  return Array.from(titles);
}

/** Render Markdown body with wikilinks replaced by styled inline chips. */
function MarkdownWithWikilinks({
  body,
  onWikilinkClick,
}: {
  body: string;
  onWikilinkClick?: (title: string) => void;
}) {
  // Replace [[wikilinks]] with a placeholder span before passing to react-markdown
  // so they don't get mangled. We use a custom rehype plugin approach: replace
  // [[Title]] with an HTML anchor tag that react-markdown renders as-is via
  // rehypeRaw — but to avoid the dep, we instead pre-process the string.
  const processed = body.replace(
    /\[\[([^\]]+)\]\]/g,
    (_, inner) => {
      const [title, alias] = inner.split('|').map((s: string) => s.trim());
      const display = alias || title;
      // Use a custom marker that won't conflict with Markdown syntax
      return `<wikilink data-title="${title}">${display}</wikilink>`;
    }
  );

  return (
    <div className="prose prose-sm prose-invert max-w-none text-text-primary">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Intercept unknown elements — react-markdown passes unrecognised
          // HTML tags through the component map under their tag name.
          // We intercept 'wikilink' here.
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          wikilink: ({ node, ...props }: any) => {
            const title = node?.properties?.dataTitle || '';
            return (
              <button
                onClick={() => onWikilinkClick?.(title)}
                className="inline-flex items-center gap-0.5 text-accent-blue bg-accent-blue/10 hover:bg-accent-blue/20 rounded px-1.5 py-0.5 text-xs font-medium transition-colors cursor-pointer border border-accent-blue/20"
                title={`Open note: ${title}`}
              >
                <Link2 size={9} />
                {props.children}
              </button>
            );
          },
        }}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
}

export default function NoteDetailPanel({
  note,
  onClose,
  onWikilinkClick,
}: NoteDetailPanelProps) {
  const navigate = useNavigate();
  const [actionState, setActionState] = useState<ActionState>('idle');
  const [result, setResult] = useState<ActionResult | null>(null);

  const wikilinks = extractWikilinks(note.body);

  const runAction = useCallback(
    async (type: ActionResult['type']) => {
      setActionState('loading');
      setResult(null);
      try {
        let content = '';
        if (type === 'summary') {
          const res = (await api.summarizeNote(note.id)) as { summary: string };
          content = res.summary;
        } else if (type === 'critique') {
          // Critique returns a structured object — flatten to readable text
          const res = (await api.critiqueNote(note.id)) as {
            overall?: string;
            strengths?: string[];
            weaknesses?: string[];
            suggestions?: string[];
          };
          const sections: string[] = [];
          if (res.overall)    sections.push(res.overall);
          if (res.strengths?.length)  sections.push(`**Strengths**\n${res.strengths.map((s) => `- ${s}`).join('\n')}`);
          if (res.weaknesses?.length) sections.push(`**Weaknesses**\n${res.weaknesses.map((s) => `- ${s}`).join('\n')}`);
          if (res.suggestions?.length) sections.push(`**Suggestions**\n${res.suggestions.map((s) => `- ${s}`).join('\n')}`);
          content = sections.join('\n\n') || 'No critique returned.';
        } else if (type === 'links') {
          const res = (await api.suggestLinks(note.id)) as { suggestions: Array<{ title: string; reason: string }> };
          content = (res.suggestions ?? []).length
            ? res.suggestions.map((s) => `**[[${s.title}]]** — ${s.reason}`).join('\n\n')
            : 'No link suggestions found.';
        } else if (type === 'ingest') {
          await api.ingestNote(note.id);
          content = 'Note successfully ingested into the knowledge graph.';
        }
        setResult({ type, content });
        setActionState('done');
      } catch (err) {
        console.error('NoteDetailPanel action failed:', err);
        setResult({ type, content: 'An error occurred. Please try again.' });
        setActionState('error');
      }
    },
    [note.id]
  );

  const actionLabel: Record<ActionResult['type'], string> = {
    summary: 'Summary',
    critique: 'Critique',
    links: 'Suggested Links',
    ingest: 'Ingest Status',
  };

  return (
    <div className="flex h-full flex-col bg-bg-secondary text-text-primary">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-border-default px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold leading-snug">{note.title}</h2>
          {note.folder && (
            <p className="mt-0.5 truncate text-xs text-text-muted">{note.folder}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={() => navigate(`/notes/${note.id}`)}
            className="rounded p-1.5 text-text-muted hover:bg-bg-tertiary hover:text-text-primary transition-colors"
            title="Edit note"
          >
            <Edit3 size={14} />
          </button>
          <button
            onClick={onClose}
            className="rounded p-1.5 text-text-muted hover:bg-bg-tertiary hover:text-text-primary transition-colors"
            title="Close panel"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Tags */}
      {note.tags && note.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-border-default px-4 py-2">
          {note.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-bg-tertiary px-2 py-0.5 text-xs text-text-muted"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      {/* Wikilinks chip row */}
      {wikilinks.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-border-default px-4 py-2">
          {wikilinks.map((title) => (
            <button
              key={title}
              onClick={() => onWikilinkClick?.(title)}
              className="inline-flex items-center gap-0.5 rounded bg-accent-blue/10 px-1.5 py-0.5 text-xs font-medium text-accent-blue hover:bg-accent-blue/20 transition-colors border border-accent-blue/20"
            >
              <Link2 size={9} />
              {title}
            </button>
          ))}
        </div>
      )}

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <MarkdownWithWikilinks body={note.body} onWikilinkClick={onWikilinkClick} />
      </div>

      {/* Action result */}
      {result && (
        <div className="border-t border-border-default px-4 py-3">
          <p className="mb-1 text-xs font-semibold text-text-muted">
            {actionLabel[result.type]}
          </p>
          <div className="prose prose-sm prose-invert max-w-none text-text-secondary">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.content}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="border-t border-border-default px-3 py-2">
        <div className="flex flex-wrap gap-1.5">
          <ActionButton
            icon={<FileText size={12} />}
            label="Summarize"
            loading={actionState === 'loading' && result?.type === 'summary'}
            onClick={() => runAction('summary')}
          />
          <ActionButton
            icon={<Cpu size={12} />}
            label="Critique"
            loading={actionState === 'loading' && result?.type === 'critique'}
            onClick={() => runAction('critique')}
          />
          <ActionButton
            icon={<Link2 size={12} />}
            label="Suggest Links"
            loading={actionState === 'loading' && result?.type === 'links'}
            onClick={() => runAction('links')}
          />
          <ActionButton
            icon={<Share2 size={12} />}
            label="Ingest"
            loading={actionState === 'loading' && result?.type === 'ingest'}
            onClick={() => runAction('ingest')}
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small reusable action button
// ---------------------------------------------------------------------------
function ActionButton({
  icon,
  label,
  loading,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  loading: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="inline-flex items-center gap-1 rounded bg-bg-tertiary px-2.5 py-1 text-xs font-medium text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors disabled:opacity-50"
    >
      {loading ? <Loader2 size={12} className="animate-spin" /> : icon}
      {label}
    </button>
  );
}
