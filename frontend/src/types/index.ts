/**
 * types/index.ts — canonical shared TypeScript types for Gnosis-KB.
 *
 * IMPORTANT: This file must remain a proper ES module.
 * The bare `export {}` below ensures TypeScript treats it as a module
 * even before the first real export statement.
 */
export {};

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
  id:             string;
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
  id:          string;
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
  items: Note[];
  total: number;
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
  source?:    string;
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
 */
export interface AiCritique {
  strengths?:           string[];
  weaknesses?:          string[];
  suggestions?:         string[];
  overall?:             string;
  atomicity_score?:     number;
  atomicity_feedback?:  string;
  connectivity_score?:  number;
  connectivity_feedback?: string;
  standalone_score?:    number;
  standalone_feedback?: string;
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

/** @deprecated Use AIChatMessage instead. Kept for legacy imports. */
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
