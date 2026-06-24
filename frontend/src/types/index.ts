// ============================================================
// Core domain types for Gnosis Knowledge Base
// ============================================================

export type NoteType =
  | 'permanent'
  | 'fleeting'
  | 'literature'
  | 'journal'
  | 'map'
  | 'reference'
  | 'project'
  | 'template'
  | 'area'
  | 'resource'
  | 'moc';

export type NoteStatus = 'draft' | 'in-progress' | 'evergreen' | 'inbox' | 'active' | 'someday' | 'done' | 'archived';

export type RagMode = 'local' | 'global' | 'hybrid';

export type SearchMode = 'hybrid' | 'semantic' | 'keyword' | 'fulltext';

export interface Tag {
  name: string;
  description: string;
  note_count: number;
}

export interface LinkRef {
  source_id: string;
  target_id: string;
  link_text: string;
  link_type: string;
  context?: string;
}

export interface Note {
  note_id:  string;   // canonical API key
  id:       string;   // alias (same as note_id for compatibility)
  title:    string;
  slug:     string;
  body:     string;
  body_html?: string;
  note_type: NoteType;
  status:   NoteStatus;
  vault_path?: string;
  folder:   string;
  excerpt?: string;
  source_url?: string;
  word_count: number;
  created_at?: string;
  modified_at?: string;
  last_reviewed?: string;
  is_deleted: boolean;
  vector_indexed: boolean;
  graph_indexed: boolean;
  frontmatter: Record<string, unknown>;
  tags: string[];
  outgoing_links: LinkRef[];
  incoming_links: LinkRef[];
  // Graph extras (populated on detail endpoints)
  incoming_link_count?: number;
  outgoing_link_count?: number;
  cluster_id?: number;
}

export interface NoteListItem {
  note_id: string;
  id:      string;   // alias
  title:   string;
  slug:    string;
  note_type: NoteType;
  status:  NoteStatus;
  folder:  string;
  excerpt?: string;
  word_count: number;
  created_at?: string;
  modified_at?: string;
  tags: string[];
}

export interface PaginatedNotes {
  items: Note[];
  total: number;
  page:  number;
  limit: number;
  pages: number;
}

export interface NoteListResponse extends PaginatedNotes {}

export interface NoteCreate {
  title:     string;
  body?:     string;
  note_type?: NoteType;
  status?:   NoteStatus;
  folder?:   string;
  tags?:     string[];
  source_url?: string;
  frontmatter?: Record<string, unknown>;
  id?:       string;
  last_reviewed?: string;
}

/** Like NoteCreate but with body guaranteed non-undefined (for createNote API call). */
export interface CreateNotePayload extends Omit<NoteCreate, 'body'> {
  body: string;
}

export interface NoteUpdate {
  title?:    string;
  body?:     string;
  note_type?: NoteType;
  status?:   NoteStatus;
  folder?:   string;
  tags?:     string[];
  source_url?: string;
  frontmatter?: Record<string, unknown>;
  last_reviewed?: string;
}

// ---- Search ----
export interface SearchResult {
  note_id:    string;
  title:      string;
  slug:       string;
  folder:     string;
  note_type?: NoteType;
  status?:    NoteStatus;
  score?:     number;
  highlight?: string;
  excerpt?:   string;
  snippet?:   string;   // alias used by some backend modes
  tags?:      string[];
  modified_at?: string;
}

export interface SearchResponse {
  query:      string;
  mode:       string;
  items:      SearchResult[];  // primary key (aligned with API)
  results?:   SearchResult[]; // legacy alias
  total:      number;
  elapsed_ms?: number;
}

// ---- Backlinks ----
export interface BacklinkEntry {
  source_note_id: string;
  note_id:        string; // alias for backwards-compat
  title:          string;
  modified_at?:   string;
  context?:       string;
}

export interface BacklinksResponse {
  backlinks: BacklinkEntry[];
  count:     number;
}

// ---- Graph ----
export interface GraphNode {
  note_id:  string;
  id?:      string; // alias
  title:    string;
  type?:    string;
  note_type?: NoteType;
  status?:  NoteStatus;
  folder?:  string;
  excerpt?: string;
  word_count?: number;
  tag_count?:  number;
  tags?:       string[];
  incoming_link_count: number;
  outgoing_link_count: number;
  cluster_id?: number;
  modified_at?: string;
}

export interface GraphEdge {
  source_id:  string;
  target_id:  string;
  source?:    string; // alias
  target?:    string; // alias
  link_text?: string;
  link_type?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphStats {
  total_notes:    number;
  total_links:    number;
  orphan_count:   number;
  avg_degree:     number;
  density:        number;
  most_connected: Array<{ note_id: string; degree: number; title: string }>;
}

export interface GraphPath {
  path:     string[];   // ordered list of note IDs
  length:   number;
  titles:   string[];
}

// ---- AI ----
export interface AiChatMessage {
  role:      'user' | 'assistant' | 'system';
  content:   string;
  citations?: string[];
  timestamp?: string;
}

export interface AiChatResponse {
  answer:     string;
  sources:    string[];
  mode:       string;
  session_id?: string;
}

export interface LinkSuggestion {
  target_note_id: string;
  target_title:   string;
  reason:         string;
  score?:         number;
}

export interface TagSuggestion {
  tag:    string;
  reason: string;
  score?: number;
}

export interface AiCritique {
  note_id:               string;
  atomicity_score:       number;
  atomicity_feedback:    string;
  connectivity_score:    number;
  connectivity_feedback: string;
  standalone_score:      number;
  standalone_feedback:   string;
  insight_score:         number;
  insight_feedback:      string;
  overall_feedback:      string;
  action_items?:         string[];
}

export interface SummarizeResponse {
  note_id:        string;
  title:          string;
  summary:        string;
  key_concepts:   string[];
  suggested_tags: string[];
}

// ---- Graph entity (LightRAG) ----
export interface GraphEntitySummary {
  id:     string;
  label?: string;
  type?:  string;
  rank?:  number;
}

// ---- TagRow (used by TagInput) ----
export interface TagRow {
  name:        string;
  note_count?: number;
}

// ---- Legacy aliases (keep for backwards compat) ----
export type ChatMessage  = AiChatMessage;
export type ChatResponse = AiChatResponse;
export type { AiCritique as CritiqueResponse };
