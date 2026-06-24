/**
 * MarkdownPreview — read-only markdown renderer with wikilink resolution.
 * Uses react-markdown + remark-gfm for tables/strikethrough/task lists.
 * Wikilinks ([[Title]]) are intercepted and rendered as router links.
 */
import React from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useNavigate } from 'react-router-dom';

interface MarkdownPreviewProps {
  /** Raw markdown string (may contain wikilinks). */
  content: string;
  /** Map of note title → note_id for resolving wikilinks as clickable links. */
  titleToId?: Record<string, string>;
  className?: string;
}

/** Pre-process wikilinks into pseudo-href before feeding to react-markdown. */
function preprocessWikilinks(
  md: string,
  titleToId: Record<string, string>,
): string {
  return md.replace(
    /\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]/g,
    (_raw, title, alias) => {
      const display = (alias ?? title).trim();
      const id = titleToId[title.trim()];
      if (id) return `[${display}](/notes/${id})`;
      return `<span class="wikilink-dead">${display}</span>`;
    },
  );
}

/**
 * MarkdownPreview renders Markdown to HTML with GFM support and
 * converts wikilinks to in-app router navigation.
 */
export function MarkdownPreview({
  content,
  titleToId = {},
  className,
}: MarkdownPreviewProps) {
  const navigate   = useNavigate();
  const processed  = preprocessWikilinks(content, titleToId);

  const components: Components = {
    // Intercept all anchor clicks: internal routes use navigate(), external open new tab
    a: ({ href, children, ...props }) => {
      if (href?.startsWith('/')) {
        return (
          <a
            href={href}
            onClick={(e) => { e.preventDefault(); navigate(href); }}
            className="text-gnosis-accent hover:underline"
            {...props}
          >
            {children}
          </a>
        );
      }
      return (
        <a href={href} target="_blank" rel="noreferrer noopener" className="text-gnosis-accent hover:underline" {...props}>
          {children}
        </a>
      );
    },

    // Syntax-highlighted code block (basic; upgrade to rehype-highlight if needed)
    code: ({ className: cls, children, ...props }) => {
      const isBlock = cls?.includes('language-');
      return isBlock ? (
        <code className={`${cls ?? ''} rounded block`} {...props}>{children}</code>
      ) : (
        <code className="bg-gnosis-surface px-1 rounded text-gnosis-accent text-sm" {...props}>{children}</code>
      );
    },

    pre: ({ children, ...props }) => (
      <pre className="bg-gnosis-surface border border-gnosis-border rounded-lg p-4 overflow-x-auto text-sm" {...props}>
        {children}
      </pre>
    ),

    // Task list checkboxes
    input: (props) => (
      <input {...props} className="mr-1 accent-gnosis-accent" />
    ),

    // Tables
    table: ({ children, ...props }) => (
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse" {...props}>{children}</table>
      </div>
    ),
    th: ({ children, ...props }) => (
      <th className="border border-gnosis-border px-3 py-1 bg-gnosis-surface text-left text-xs font-semibold text-gnosis-muted" {...props}>
        {children}
      </th>
    ),
    td: ({ children, ...props }) => (
      <td className="border border-gnosis-border px-3 py-1 text-xs" {...props}>{children}</td>
    ),
  };

  return (
    <article
      className={`prose prose-sm prose-invert max-w-none ${
        className ?? ''
      } [&_.wikilink-dead]:text-gnosis-muted [&_.wikilink-dead]:line-through`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {processed}
      </ReactMarkdown>
    </article>
  );
}
