/**
 * types/index.ts — canonical shared TypeScript types for Gnosis-KB.
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
  | 'literature';

export interface Note {
  note_id:    string;
  title:      string;
  body:       string;
  note_type?: NoteType;
  tags?:      string[];
  folder?:    string;
  frontmatter?: Record<string, unknown>;
  backlinks?: Backlink[];
  created_at: string;
  updated_at: string;
  incoming_link_count?: number;
  outgoing_link_count?: number;
}

export interface NoteCreate {
  title:      string;
  body:       string;
  note_type?: NoteType;
  tags?:      string[];
  folder?:    string;
  frontmatter?: Record<string, unknown>;
}

export interface NoteUpdate {
  title?:      string;
  body?:       string;
  note_type?:  NoteType;
  tags?:       string[];
  folder?:     string;
  frontmatter?: Record<string, unknown>;
}

export interface Backlink {
  note_id: string;
  title:   string;
  excerpt?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Search
// ─────────────────────────────────────────────────────────────────────────────

export interface SearchResult {
  note_id:  string;
  title:    string;
  excerpt:  string;
  score:    number;
  slug?:    string;
  tags?:    string[];
  note_type?: NoteType;
  matched_at?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Graph
// ─────────────────────────────────────────────────────────────────────────────

export interface GraphNode {
  note_id:   string;
  title:     string;
  type?:     NoteType;
  x?:        number;
  y?:        number;
  cluster_id?: number;
  incoming_link_count?: number;
  outgoing_link_count?: number;
  tags?:     string[];
}

export interface GraphEdge {
  source_id:  string;
  target_id:  string;
  link_type?: string;
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
// Chat / AI
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
