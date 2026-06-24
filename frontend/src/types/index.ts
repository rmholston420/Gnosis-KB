/**
 * types/index.ts — canonical shared TypeScript types for Gnosis-KB.
 * Expanded to resolve all tsc errors.
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
  note_id:     string;
  /** Convenience alias — same value as note_id. Set by API layer. */
  id:          string;
  title:       string;
  body:        string;
  note_type?:  NoteType;
  status?:     NoteStatus;
  tags?:       string[];
  folder?:     string;
  slug?:       string;
  source_url?: string;
  word_count?: number;
  is_deleted?: boolean;
  frontmatter?: Record<string, unknown>;
  backlinks?:  Backlink[];
  /** Populated on full-note fetches */
  incoming_links?: LinkRef[];
  outgoing_links?: LinkRef[];
  created_at:  string;
  updated_at:  string;
  modified_at?: string;
  incoming_link_count?: number;
  outgoing_link_count?: number;
  tag_count?:  number;
}

export interface LinkRef {
  note_id:  string;
  title:    string;
  excerpt?: string;
}

/**
 * Lightweight note representation used in lists, search results, and wikilink popups.
 * Avoids shipping the full `body` when only metadata is needed.
 */
export interface NoteListItem {
  note_id:    string;
  id:         string;
  title:      string;
  note_type?: NoteType;
  status?:    NoteStatus;
  tags?:      string[];
  folder?:    string;
  slug?:      string;
  word_count?: number;
  created_at: string;
  updated_at: string;
  incoming_link_count?: number;
  outgoing_link_count?: number;
  tag_count?: number;
}

export interface NoteListResponse {
  items: Note[];
  total: number;
  page?: number;
  per_page?: number;
}

export interface NoteCreate {
  title:      string;
  body:       string;
  note_type?: NoteType;
  status?:    NoteStatus;
  tags?:      string[];
  folder?:    string;
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
  note_id:  string;
  title:    string;
  excerpt?: string;
}

export interface TagRow {
  tag:   string;
  count: number;
}

export interface NoteTemplate {
  id:        string;
  name:      string;
  noteType:  NoteType;
  body:      string;
  tags?:     string[];
  folder?:   string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Search
// ─────────────────────────────────────────────────────────────────────────────

export type SearchMode = 'hybrid' | 'semantic' | 'keyword' | 'fulltext';

export interface SearchResult {
  note_id:   string;
  title:     string;
  excerpt:   string;
  /** Alias for excerpt — some API versions return `snippet` */
  snippet?:  string;
  score:     number;
  slug?:     string;
  tags?:     string[];
  note_type?: NoteType;
  folder?:   string;
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
  note_id:   string;
  title:     string;
  /** Canonical type field used by the API */
  note_type?: NoteType;
  /** Alias kept for react-force-graph compatibility */
  type?:     NoteType;
  status?:   NoteStatus;
  excerpt?:  string;
  x?:        number;
  y?:        number;
  cluster_id?: number;
  incoming_link_count?: number;
  outgoing_link_count?: number;
  tag_count?: number;
  word_count?: number;
  folder?:   string;
  tags?:     string[];
  modified_at?: string;
}

export interface GraphEdge {
  /** Canonical source field */
  source_id:  string;
  /** Alias used by react-force-graph and some API versions */
  source?:    string;
  /** Canonical target field */
  target_id:  string;
  /** Alias used by react-force-graph and some API versions */
  target?:    string;
  link_type?: string;
  link_text?: string;
  weight?:    number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Entity summary returned by the LightRAG /graph/entities endpoint. */
export interface GraphEntitySummary {
  entity_id:   string;
  label:       string;
  description: string;
  source_ids:  string[];
  score?:      number;
}

// ─────────────────────────────────────────────────────────────────────────────
// AI
// ─────────────────────────────────────────────────────────────────────────────

export interface LinkSuggestion {
  target_note_id: string;
  target_title:   string;
  reason:         string;
  score?:         number;
  /** Legacy field alias */
  title?:         string;
}

export interface TagSuggestion {
  tag:    string;
  reason: string;
  score?: number;
}

export interface AiCritique {
  strengths:    string[];
  weaknesses:   string[];
  suggestions:  string[];
  overall?:     string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat
// ─────────────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role:    'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatSource {
  note_id: string;
  title:   string;
  score?:  number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Vault
// ─────────────────────────────────────────────────────────────────────────────

export interface VaultInfo {
  name:      string;
  path:      string;
  note_count: number;
  last_synced?: string;
}
