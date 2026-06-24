/**
 * Markdown and wikilink utility functions.
 * These are pure functions with no DOM or React dependencies.
 */

/** Regex that matches [[Title]] and [[Title|Alias]] wikilinks. */
const WIKILINK_RE = /\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]/g;

export interface ParsedWikilink {
  /** The raw matched string, e.g. `[[Foo|Bar]]` */
  raw: string;
  /** The canonical note title, e.g. `Foo` */
  title: string;
  /** Display alias if provided, e.g. `Bar`; otherwise equals `title` */
  alias: string;
  /** Character index in source text where the match starts */
  index: number;
}

/**
 * Extract all wikilinks from a Markdown body string.
 * @param body — raw markdown text
 * @returns ordered list of ParsedWikilink objects
 */
export function extractWikilinks(body: string): ParsedWikilink[] {
  const results: ParsedWikilink[] = [];
  let match: RegExpExecArray | null;
  const re = new RegExp(WIKILINK_RE.source, 'g');
  while ((match = re.exec(body)) !== null) {
    const [raw, title, alias] = match;
    results.push({ raw, title: title.trim(), alias: (alias ?? title).trim(), index: match.index });
  }
  return results;
}

/**
 * Replace all wikilinks in `body` using a mapping of title → noteId.
 * Unresolved links are rendered as plain text.
 */
export function resolveWikilinks(
  body: string,
  titleToId: Record<string, string>,
): string {
  return body.replace(WIKILINK_RE, (_raw, title, alias) => {
    const display = (alias ?? title).trim();
    const id = titleToId[title.trim()];
    if (id) return `[${display}](/notes/${id})`;
    return `<span class="wikilink-unresolved">${display}</span>`;
  });
}

/**
 * Parse YAML frontmatter block from a Markdown string.
 * Returns the frontmatter as a plain object and the body without frontmatter.
 */
export interface FrontmatterResult {
  frontmatter: Record<string, unknown>;
  body: string;
}

export function parseFrontmatter(raw: string): FrontmatterResult {
  const FM_RE = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;
  const match = FM_RE.exec(raw);
  if (!match) return { frontmatter: {}, body: raw };

  const yamlBlock = match[1];
  const body = raw.slice(match[0].length);

  // Lightweight YAML scalar parser (no external dep for simple k:v)
  const frontmatter: Record<string, unknown> = {};
  for (const line of yamlBlock.split('\n')) {
    const colonIdx = line.indexOf(':');
    if (colonIdx === -1) continue;
    const key = line.slice(0, colonIdx).trim();
    const rawVal = line.slice(colonIdx + 1).trim();
    if (!key) continue;
    // Handle inline arrays: [a, b, c]
    if (rawVal.startsWith('[') && rawVal.endsWith(']')) {
      frontmatter[key] = rawVal
        .slice(1, -1)
        .split(',')
        .map((s) => s.trim().replace(/^"|"$/g, ''));
    } else {
      frontmatter[key] = rawVal.replace(/^"|"$/g, '');
    }
  }
  return { frontmatter, body };
}

/**
 * Serialize a frontmatter object + body back into a full Markdown string.
 */
export function serializeFrontmatter(
  frontmatter: Record<string, unknown>,
  body: string,
): string {
  const lines = ['---'];
  for (const [k, v] of Object.entries(frontmatter)) {
    if (Array.isArray(v)) {
      lines.push(`${k}: [${v.join(', ')}]`);
    } else if (v instanceof Date) {
      lines.push(`${k}: ${v.toISOString()}`);
    } else {
      lines.push(`${k}: ${String(v ?? '')}`);
    }
  }
  lines.push('---', '');
  return lines.join('\n') + body;
}

/** Strip markdown syntax to produce plain text (for previews/excerpts). */
export function stripMarkdown(md: string): string {
  return md
    .replace(/^#{1,6}\s+/gm, '')        // headings
    .replace(/\*\*?|__?/g, '')           // bold / italic
    .replace(/~~([^~]+)~~/g, '$1')       // strikethrough
    .replace(/`[^`]+`/g, '')            // inline code
    .replace(/```[\s\S]*?```/g, '')     // fenced code blocks
    .replace(/!?\[([^\]]+)\]\([^)]*\)/g, '$1') // links / images
    .replace(WIKILINK_RE, (_r, t, a) => a ?? t)  // wikilinks
    .replace(/^[>\-*+]\s+/gm, '')      // blockquotes, lists
    .replace(/\n{3,}/g, '\n\n')        // collapse whitespace
    .trim();
}
