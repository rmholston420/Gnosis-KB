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
  | 'template';

export type NoteStatus = 'draft' | 'in-progress' | 'evergreen';

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
  id: string;
  title: string;
  slug: string;
  body: string;
  body_html: string;
  note_type: NoteType;
  status: NoteStatus;
  vault_path?: string;
  folder: string;
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
}

export interface NoteListItem {
  id: string;
  title: string;
  slug: string;
  note_type: NoteType;
  status: NoteStatus;
  folder: string;
  word_count: number;
  created_at?: string;
  modified_at?: string;
  tags: string[];
}

export interface NoteListResponse {
  items: NoteListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface NoteCreate {
  title: string;
  body?: string;
  note_type?: NoteType;
  status?: NoteStatus;
  folder?: string;
  tags?: string[];
  source_url?: string;
  frontmatter?: Record<string, unknown>;
  id?: string;
  last_reviewed?: string;
}

export interface NoteUpdate {
  title?: string;
  body?: string;
  note_type?: NoteType;
  status?: NoteStatus;
  folder?: string;
  tags?: string[];
  source_url?: string;
  frontmatter?: Record<string, unknown>;
  last_reviewed?: string;
}

// ---- Search ---
export interface SearchResult {
  note_id: string;
  title: string;
  slug: string;
  folder: string;
  note_type: NoteType;
  status: NoteStatus;
  score: number;
  highlight: string;
  tags: string[];
}

export interface SearchResponse {
  query: string;
  mode: string;
  results: SearchResult[];
  total: number;
  elapsed_ms: number;
}

// ---- Graph ----
export interface GraphNode {
  id: string;
  title: string;
  note_type: NoteType;
  status: NoteStatus;
  folder: string;
  word_count: number;
  tag_count: number;
  incoming_link_count: number;
  outgoing_link_count: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  link_text: string;
  link_type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphStats {
  total_notes: number;
  total_links: number;
  orphan_count: number;
  avg_degree: number;
  density: number;
  most_connected: Array<{ note_id: string; degree: number; title: string }>;
}

// ---- AI ----
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

export interface ChatResponse {
  answer: string;
  sources: string[];
  mode: string;
  session_id?: string;
}

export interface SummarizeResponse {
  note_id: string;
  title: string;
  summary: string;
  key_concepts: string[];
  suggested_tags: string[];
}

export interface CritiqueResponse {
  note_id: string;
  atomicity_score: number;
  atomicity_feedback: string;
  connectivity_score: number;
  connectivity_feedback: string;
  self_containedness_score: number;
  self_containedness_feedback: string;
  insight_density_score: number;
  insight_density_feedback: string;
  overall_feedback: string;
  action_items: string[];
}
