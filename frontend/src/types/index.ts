/**
 * types/index.ts — canonical shared TypeScript types for Gnosis-KB.
 *
 * Audit fixes (2026-06-25)
 * ------------------------
 * - Removed bare `export {}` — it was a no-op (any file with `export interface`
 *   or `export type` is already an ES module; the comment was misleading).
 * - Note.id made optional: the backend returns `note_id`; requiring `id` caused
 *   silent undefined access in BacklinkPanel and route helpers. Consumers that
 *   need a stable id should use `note.id ?? note.note_id`.
 * - NoteListItem.id made optional for the same reason.
 * - NoteListResponse.items changed from Note[] to NoteListItem[] — list
 *   endpoints return lightweight items without body/backlinks/incoming_links;
 *   using Note[] caused consumers to expect fields never present in list results.
 * - AiCritique score fields documented as [0, 10] range.
 * - ChatMessage deprecated alias annotated with @see and removal target.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Notes
// ─────────────────────────────────────────────────────────────────────────────

export type NoteType =
  | 'permanent'
  | 'fleeting'
  | 'project'
  | 'area'
  | 'resource'
  | 'journal'
  | 'moc'
  | 'literature'
  | 'map';

export type NoteStatus =
  | 'inbox'
  | 'draft'
  | 'active'
  | 'evergreen'
  | 'archived';

export interface Note {
  note_id:        string;
  /** Alias for note_id — populated by the API response normalizer.
   *  Use `note.id ?? note.note_id` for a guaranteed non-undefined value. */
  id?:            string;
  title:          string;
  body:           string;
  body_html?:     string;
  note_type?:     NoteType;
  status?:        NoteStatus;
  tags?:          string[];
  folder?:        string;
  slug?:          string;
  source_url?:    string;
  word_count?:    number;
  is_deleted?:    boolean;
  vector_indexed?: boolean;
  graph_indexed?:  boolean;
  frontmatter?:   Record<string, unknown>;
  backlinks?:     Backlink[];
  incoming_links?: LinkRef[];
  outgoing_links?: LinkRef[];
  created_at:     string;
  updated_at:     string;
  modified_at?:   string;
  incoming_link_count?: number;
  outgoing_link_count?: number;
  tag_count?:     number;
}

export interface LinkRef {
  note_id:    string;
  title:      string;
  excerpt?:   string;
  link_text?: string;
  link_type?: string;
  source_id?: string;
  target_id?: string;
  context?:   string;
}

export interface NoteListItem {
  note_id:     string;
  /** Alias for note_id — populated by the API response normalizer. */
  id?:         string;
  title:       string;
  note_type?:  NoteType;
  status?:     NoteStatus;
  tags?:       string[];
  folder?:     string;
  slug?:       string;
  word_count?:  number;
  created_at:  string;
  updated_at:  string;
  modified_at?: string;
  incoming_link_count?: number;
  outgoing_link_count?: number;
  tag_count?:  number;
}

export interface NoteListResponse {
  /** Lightweight list items — body, backlinks, and link arrays are absent.
   *  Was incorrectly typed as Note[] which caused consumers to expect fields
   *  that list endpoints never return. */
  items:     NoteListItem[];
  total:     number;
  page?:     number;
  per_page?: number;
}

export interface NoteCreate extends Record<string, unknown> {
  title:       string;
  body:        string;
  note_type?:  NoteType;
  status?:     NoteStatus;
  tags?:       string[];
  folder?:     string;
  source_url?: string;
  frontmatter?: Record<string, unknown>;
}

export interface NoteUpdate {
  title?:      string;
  body?:       string;
  note_type?:  NoteType;
  status?:     NoteStatus;
  tags?:       string[];
  folder?:     string;
  source_url?: string;
  frontmatter?: Record<string, unknown>;
}

export interface Backlink {
  note_id:        string;
  title:          string;
  excerpt?:       string;
  context?:       string;
  source_note_id?: string;
}

export interface TagRow {
  tag:   string;
  count: number;
}

export interface NoteTemplate {
  id:       string;
  name:     string;
  noteType: NoteType;
  body:     string;
  tags?:    string[];
  folder?:  string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Search
// ─────────────────────────────────────────────────────────────────────────────

export type SearchMode = 'hybrid' | 'semantic' | 'keyword' | 'fulltext';

export interface SearchResult {
  note_id:    string;
  title:      string;
  excerpt?:   string;
  snippet?:   string;
  score:      number;
  slug?:      string;
  tags?:      string[];
  note_type?: NoteType;
  folder?:    string;
  matched_at?: string;
}

export interface SearchResponse {
  items: SearchResult[];
  total: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Graph
// ─────────────────────────────────────────────────────────────────────────────

export interface GraphNode {
  note_id:    string;
  title:      string;
  note_type?: NoteType;
  type?:      NoteType;
  status?:    NoteStatus;
  excerpt?:   string;
  x?:         number;
  y?:         number;
  cluster_id?: number;
  incoming_link_count?: number;
  outgoing_link_count?: number;
  tag_count?:  number;
  word_count?: number;
  folder?:    string;
  tags?:      string[];
  modified_at?: string;
}

export interface GraphEdge {
  source_id:  string;
  target_id:  string;
  /** Alias for source_id — present on some API responses. */
  source?:    string;
  /** Alias for target_id — present on some API responses. */
  target?:    string;
  link_type?: string;
  link_text?: string;
  weight?:    number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphEntitySummary {
  entity_id:   string;
  id?:         string;   // alias — some consumers use .id
  label:       string;
  description: string;
  source_ids:  string[];
  score?:      number;
}

export interface GraphStats {
  total_nodes:     number;
  total_edges:     number;
  total_notes?:    number;   // alias used by some tests
  orphan_count?:   number;   // alias for isolated_count
  avg_degree:      number;
  most_connected:  Array<{ note_id: string; title: string; degree: number }>;
  isolated_count:  number;
  cluster_count?:  number;
}

// ─────────────────────────────────────────────────────────────────────────────
// AI
// ─────────────────────────────────────────────────────────────────────────────

export interface LinkSuggestion {
  target_note_id: string;
  target_title:   string;
  reason:         string;
  score?:         number;
  title?:         string;
}

export interface TagSuggestion {
  tag:    string;
  reason: string;
  score?: number;
}

/**
 * Zettelkasten-style critique with per-dimension scores.
 * AiSidebar renders atomicity/connectivity/standalone/insight dimensions.
 *
 * All *_score fields are in the range [0, 10]. Consumers rendering score
 * bars must clamp to this range: Math.min(10, Math.max(0, score ?? 0)).
 * The backend may return probability values (0–1) for older model responses;
 * callers should multiply by 10 in that case.
 */
export interface AiCritique {
  strengths?:           string[];
  weaknesses?:          string[];
  suggestions?:         string[];
  overall?:             string;
  /** [0, 10] */
  atomicity_score?:     number;
  atomicity_feedback?:  string;
  /** [0, 10] */
  connectivity_score?:  number;
  connectivity_feedback?: string;
  /** [0, 10] */
  standalone_score?:    number;
  standalone_feedback?: string;
  /** [0, 10] */
  insight_score?:       number;
  insight_feedback?:    string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat
// ─────────────────────────────────────────────────────────────────────────────

export interface AIChatMessage {
  role:    'user' | 'assistant' | 'system';
  content: string;
  meta?:   Record<string, unknown>;
}

/**
 * @deprecated Use {@link AIChatMessage} instead.
 * Target removal: once all import sites have been migrated.
 * Track at: https://github.com/rmholston420/Gnosis-KB/issues
 */
export type ChatMessage = AIChatMessage;

export interface ChatSource {
  note_id: string;
  title:   string;
  score?:  number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Vault
// ─────────────────────────────────────────────────────────────────────────────

export interface VaultInfo {
  name:       string;
  path:       string;
  note_count: number;
  last_synced?: string;
}
