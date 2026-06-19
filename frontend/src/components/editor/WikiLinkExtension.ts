/**
 * WikiLinkExtension — TipTap extension for [[Title]] wikilink autocomplete.
 */
import { Mention } from "@tiptap/extension-mention";
import type { MentionNodeAttrs } from "@tiptap/extension-mention";
import {
  SuggestionOptions,
  SuggestionProps,
  SuggestionKeyDownProps,
} from "@tiptap/suggestion";
import { ReactRenderer } from "@tiptap/react";
import tippy, { Instance as TippyInstance } from "tippy.js";
import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import React from "react";

/** Shape returned by the notes list endpoint. */
interface NoteStub {
  id: string;
  title: string;
}

/** Autocomplete list component rendered inside the Tippy popup. */
const WikiLinkList = forwardRef<
  { onKeyDown: (props: SuggestionKeyDownProps) => boolean },
  SuggestionProps<NoteStub>
>((props, ref) => {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const { items, command } = props;

  useEffect(() => { setSelectedIndex(0); }, [items]);

  useImperativeHandle(ref, () => ({
    onKeyDown({ event }: SuggestionKeyDownProps) {
      if (event.key === "ArrowUp") {
        setSelectedIndex((i) => (i + items.length - 1) % items.length);
        return true;
      }
      if (event.key === "ArrowDown") {
        setSelectedIndex((i) => (i + 1) % items.length);
        return true;
      }
      if (event.key === "Enter") {
        const item = items[selectedIndex];
        if (item) command({ id: item.id, label: item.title });
        return true;
      }
      return false;
    },
  }));

  if (!items.length) {
    return React.createElement("div", { className: "wikilink-popup empty" }, "No notes found");
  }

  return React.createElement(
    "ul",
    { className: "wikilink-popup" },
    items.map((item, index) =>
      React.createElement(
        "li",
        {
          key: item.id,
          className: `wikilink-item ${index === selectedIndex ? "selected" : ""}`,
          onClick: () => command({ id: item.id, label: item.title }),
        },
        item.title
      )
    )
  );
});

WikiLinkList.displayName = "WikiLinkList";

async function fetchNoteSuggestions(query: string): Promise<NoteStub[]> {
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  const url = `${base}/api/v1/notes?search=${encodeURIComponent(query)}&limit=10`;
  try {
    const resp = await fetch(url, {
      headers: { Authorization: `Bearer ${localStorage.getItem("gnosis_token") ?? ""}` },
    });
    if (!resp.ok) return [];
    const data = (await resp.json()) as { items?: NoteStub[] } | NoteStub[];
    return Array.isArray(data) ? data : data.items ?? [];
  } catch {
    return [];
  }
}

const buildSuggestion = (): Omit<SuggestionOptions<NoteStub>, "editor"> => ({
  char: "[[",
  allowSpaces: true,
  items: async ({ query }: { query: string }): Promise<NoteStub[]> =>
    fetchNoteSuggestions(query),

  render() {
    let component: ReactRenderer<unknown> | null = null;
    let popup: TippyInstance[] | null = null;
    let container: HTMLElement | null = null;

    return {
      onStart(props: SuggestionProps<NoteStub>) {
        container = document.createElement("div");
        component = new ReactRenderer(WikiLinkList, { props, editor: props.editor });
        if (!props.clientRect) return;
        popup = tippy("body", {
          getReferenceClientRect: props.clientRect as () => DOMRect,
          appendTo: () => document.body,
          content: component.element,
          showOnCreate: true,
          interactive: true,
          trigger: "manual",
          placement: "bottom-start",
        });
      },
      onUpdate(props: SuggestionProps<NoteStub>) {
        component?.updateProps(props);
        if (props.clientRect && popup?.[0]) {
          popup[0].setProps({ getReferenceClientRect: props.clientRect as () => DOMRect });
        }
      },
      onKeyDown(props: SuggestionKeyDownProps): boolean {
        if (props.event.key === "Escape") { popup?.[0]?.hide(); return true; }
        return (
          component?.ref as unknown as
            | { onKeyDown: (p: SuggestionKeyDownProps) => boolean }
            | null
        )?.onKeyDown(props) ?? false;
      },
      onExit() {
        popup?.[0]?.destroy();
        component?.destroy();
        container?.remove();
      },
    };
  },
});

export const WikiLinkExtension = Mention.extend({
  name: "wikilink",
  addAttributes() {
    return {
      ...this.parent?.(),
      label: {
        default: null,
        parseHTML: (el: Element) => el.getAttribute("data-label"),
        renderHTML: (attrs: Record<string, unknown>) => ({ "data-label": attrs.label }),
      },
    };
  },
}).configure({
  HTMLAttributes: { class: "wikilink" },
  // No parameter type annotation — let TS infer the full props shape from
  // MentionOptions so there is no index-signature mismatch (TS2322).
  renderLabel({ node }) {
    const attrs = node.attrs as MentionNodeAttrs;
    return `[[${attrs.label ?? attrs.id ?? ""}]]`;
  },
  suggestion: buildSuggestion(),
});
