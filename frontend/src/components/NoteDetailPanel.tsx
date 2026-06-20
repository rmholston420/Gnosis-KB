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
          // Critique returns a complex object — flatten to readable text
          const res = (await api.critiqueNote(note.id)) as Record<string, unknown>;
          const overall = (res as { overall?: string }).overall ?? '';
          const raw = (res as {