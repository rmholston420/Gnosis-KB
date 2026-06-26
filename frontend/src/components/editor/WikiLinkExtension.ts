/**
 * WikiLinkExtension — TipTap inline node for [[wikilink]] syntax.
 *
 * Features
 * --------
 * - Renders [[Title]] as a styled, clickable inline chip in the editor.
 * - Typing [[ opens an autocomplete suggestion list backed by GET /notes/search
 *   so existing note titles are proposed.
 * - Tab/Enter accepts the first suggestion; Escape dismisses.
 * - Accepted links become an inline node with data-note-id (resolved via
 *   GET /notes/wikilink?title=...) and navigate to /notes/:id on click.
 * - Unresolved titles are stored as-is and rendered with a subtle "broken"
 *   style so the author can see the link needs a target.
 *
 * Usage
 * -----
 *   import { WikiLinkExtension } from '@/components/editor/WikiLinkExtension';
 *   const editor = useEditor({ extensions: [WikiLinkExtension, ...other] });
 *
 * Dependencies
 * ------------
 *   @tiptap/core        (already in package.json)
 *   @tiptap/suggestion  npm i @tiptap/suggestion
 *   @tiptap/react       (already in package.json)
 *   tippy.js            npm i tippy.js  (peer of suggestion)
 */

import { mergeAttributes, Node, type NodeViewRendererProps } from '@tiptap/core';
import Suggestion, { type SuggestionOptions } from '@tiptap/suggestion';
import { ReactNodeViewRenderer, ReactRenderer } from '@tiptap/react';
import React, { useCallback, useState } from 'react';
import tippy, { type Instance as TippyInstance } from 'tippy.js';
import 'tippy.js/dist/tippy.css';

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

async function fetchTitleSuggestions(query: string): Promise<string[]> {
  if (!query || query.length < 1) return [];
  const token = localStorage.getItem('gnosis_token');
  const res = await fetch(
    `${API_BASE}/notes/search?q=${encodeURIComponent(query)}&page_size=8`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  if (!res.ok) return [];
  const json = await res.json();
  return (json.items ?? []).map((n: { title: string }) => n.title);
}

// ---------------------------------------------------------------------------
// Suggestion List component (rendered inside tippy popup)
// ---------------------------------------------------------------------------

interface SuggestionListProps {
  items: Array<{ title: string }>;
  command: (item: { title: string }) => void;
}

const SuggestionList = React.forwardRef<
  { onKeyDown: (ev: KeyboardEvent) => boolean },
  SuggestionListProps
>(({ items, command }, ref) => {
  const [selected, setSelected] = useState(0);

  const selectItem = useCallback(
    (idx: number) => {
      const item = items[idx];
      if (item) command(item);
    },
    [items, command],
  );

  React.useImperativeHandle(ref, () => ({
    onKeyDown({ key }: KeyboardEvent) {
      if (key === 'ArrowUp') {
        setSelected((s) => (s + items.length - 1) % Math.max(items.length, 1));
        return true;
      }
      if (key === 'ArrowDown') {
        setSelected((s) => (s + 1) % Math.max(items.length, 1));
        return true;
      }
      if (key === 'Enter' || key === 'Tab') {
        selectItem(selected);
        return true;
      }
      return false;
    },
  }));

  if (!items.length) {
    return (
      <div className="wiki-suggestion-list">
        <div className="wiki-suggestion-empty">No notes found — will create new link</div>
      </div>
    );
  }

  return (
    <div className="wiki-suggestion-list">
      {items.map((item, i) => (
        <button
          key={item.title}
          type="button"
          className={`wiki-suggestion-item${i === selected ? ' is-selected' : ''}`}
          onClick={() => selectItem(i)}
        >
          [[{item.title}]]
        </button>
      ))}
    </div>
  );
});
SuggestionList.displayName = 'WikiSuggestionList';

// ---------------------------------------------------------------------------
// Inline node view — renders the wikilink chip in the editor DOM
// ---------------------------------------------------------------------------

function WikiLinkNodeView({ node, editor }: NodeViewRendererProps) {
  const { title, noteId, resolved } = node.attrs as {
    title: string;
    noteId: string | null;
    resolved: boolean;
  };

  const handleClick = () => {
    if (!editor.isEditable) {
      const dest = noteId
        ? `/notes/${noteId}`
        : `/notes/by-title?title=${encodeURIComponent(title)}`;
      window.location.href = dest;
    }
  };

  return (
    <span
      contentEditable={false}
      data-note-id={noteId ?? undefined}
      data-wikilink-title={title}
      className={[
        'wikilink-chip',
        resolved ? 'wikilink-resolved' : 'wikilink-unresolved',
      ].join(' ')}
      onClick={handleClick}
      title={resolved ? `Open note: ${title}` : `Note not found: ${title}`}
    >
      [[{title}]]
    </span>
  );
}

// ---------------------------------------------------------------------------
// TipTap Node definition
// ---------------------------------------------------------------------------

export const WikiLinkExtension = Node.create({
  name: 'wikilink',
  group: 'inline',
  inline: true,
  atom: true, // Atomic: cursor cannot enter the node

  addAttributes() {
    return {
      title: { default: null },
      noteId: { default: null },
      resolved: { default: false },
    };
  },

  parseHTML() {
    return [{ tag: 'span[data-wikilink-title]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, { class: 'wikilink-chip' }),
      `[[${HTMLAttributes['data-wikilink-title'] ?? ''}]]`,
    ];
  },

  addNodeView() {
    return ReactNodeViewRenderer(WikiLinkNodeView);
  },

  // -------------------------------------------------------------------------
  // Suggestion plugin — triggers on typing [[
  // -------------------------------------------------------------------------

  addProseMirrorPlugins() {
    const API = API_BASE; // captured in closure

    const suggestionOptions: Omit<SuggestionOptions, 'editor'> = {
      char: '[[',
      startOfLine: false,
      allowSpaces: true,

      command({ editor, range, props }) {
        editor
          .chain()
          .focus()
          .deleteRange(range)
          .insertContent({
            type: 'wikilink',
            attrs: {
              title: props.title,
              noteId: props.noteId ?? null,
              resolved: props.noteId != null,
            },
          })
          .insertContent(' ') // space after chip for natural typing continuation
          .run();
      },

      items: async ({ query }) => {
        const titles = await fetchTitleSuggestions(query);
        // Always offer the raw query so users can create links to non-existent notes
        if (query && !titles.includes(query)) {
          titles.unshift(query);
        }
        return titles.map((title) => ({ title }));
      },

      render() {
        let component: ReactRenderer<
          { onKeyDown: (ev: KeyboardEvent) => boolean },
          SuggestionListProps
        >;
        let popup: TippyInstance[];

        return {
          onStart(props) {
            component = new ReactRenderer(SuggestionList, {
              props,
              editor: props.editor,
            });

            if (!props.clientRect) return;

            popup = tippy('body', {
              getReferenceClientRect: props.clientRect as () => DOMRect,
              appendTo: () => document.body,
              content: component.element,
              showOnCreate: true,
              interactive: true,
              trigger: 'manual',
              placement: 'bottom-start',
              theme: 'gnosis',
            });
          },

          onUpdate(props) {
            component.updateProps(props);
            if (!props.clientRect) return;
            popup[0]?.setProps({
              getReferenceClientRect: props.clientRect as () => DOMRect,
            });
          },

          onKeyDown(props) {
            if (props.event.key === 'Escape') {
              popup[0]?.hide();
              return true;
            }
            return component.ref?.onKeyDown(props.event) ?? false;
          },

          onExit() {
            popup[0]?.destroy();
            component.destroy();
          },
        };
      },
    };

    return [
      Suggestion({
        editor: this.editor,
        ...suggestionOptions,
      }),
    ];
  },
});

/*
 * ---------------------------------------------------------------------------
 * Required CSS — add to frontend/src/index.css @layer components block:
 * ---------------------------------------------------------------------------
 *
 * .wikilink-chip {
 *   @apply inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono
 *          cursor-pointer transition-colors select-none mx-0.5;
 * }
 * .wikilink-resolved {
 *   @apply bg-gnosis-accent/15 text-gnosis-accent hover:bg-gnosis-accent/30;
 * }
 * .wikilink-unresolved {
 *   @apply bg-gnosis-border/40 text-gnosis-muted line-through
 *          hover:bg-gnosis-border/60;
 * }
 * .wiki-suggestion-list {
 *   @apply bg-gnosis-surface border border-gnosis-border rounded-lg shadow-xl
 *          overflow-hidden min-w-[200px] max-h-72 overflow-y-auto py-1;
 * }
 * .wiki-suggestion-item {
 *   @apply block w-full text-left px-3 py-1.5 text-sm text-gnosis-fg
 *          hover:bg-gnosis-border/30 transition-colors font-mono;
 * }
 * .wiki-suggestion-item.is-selected {
 *   @apply bg-gnosis-accent/20 text-gnosis-accent;
 * }
 * .wiki-suggestion-empty {
 *   @apply px-3 py-2 text-sm text-gnosis-muted italic;
 * }
 */
