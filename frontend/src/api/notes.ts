/**
 * Notes API — typed wrappers around the FastAPI /api/v1/notes endpoints.
 */
import client from './client';
import type { Note, PaginatedNotes, BacklinksResponse } from '../types';

export interface CreateNotePayload {
  title: string;
  body: string;
  note_type?: string;
  status?: string;
  tags?: string[];
  folder?: string;
  source_url?: string;
}

export interface UpdateNotePayload extends Partial<CreateNotePayload> {
  last_reviewed?: string;
}

export interface ListNotesParams {
  folder?: string;
  type?: string;
  status?: string;
  tags?: string;
  search?: string;
  page?: number;
  limit?: number;
}

/** List notes with optional filters. */
export async function listNotes(params?: ListNotesParams): Promise<PaginatedNotes> {
  const { data } = await client.get<PaginatedNotes>('/api/v1/notes', { params });
  return data;
}

/** Get a single note by ID including its backlinks. */
export async function getNote(noteId: string): Promise<Note> {
  const { data } = await client.get<Note>(`/api/v1/notes/${noteId}`);
  return data;
}

/** Create a new note. Writes .md to the vault filesystem. */
export async function createNote(payload: CreateNotePayload): Promise<Note> {
  const { data } = await client.post<Note>('/api/v1/notes', payload);
  return data;
}

/** Update an existing note. */
export async function updateNote(noteId: string, payload: UpdateNotePayload): Promise<Note> {
  const { data } = await client.put<Note>(`/api/v1/notes/${noteId}`, payload);
  return data;
}

/** Soft-delete a note (marks is_deleted=true; vault file remains). */
export async function deleteNote(noteId: string): Promise<void> {
  await client.delete(`/api/v1/notes/${noteId}`);
}

/** Get all notes that link TO this note. */
export async function getBacklinks(noteId: string): Promise<BacklinksResponse> {
  const { data } = await client.get<BacklinksResponse>(`/api/v1/notes/${noteId}/backlinks`);
  return data;
}

/** Get all notes this note links OUT to. */
export async function getOutlinks(noteId: string): Promise<BacklinksResponse> {
  const { data } = await client.get<BacklinksResponse>(`/api/v1/notes/${noteId}/outlinks`);
  return data;
}

/** Get or create today's daily note. */
export async function getDailyNote(): Promise<Note> {
  const { data } = await client.get<Note>('/api/v1/notes/daily');
  return data;
}

/** Get orphaned notes (zero incoming + zero outgoing links). */
export async function getOrphans(): Promise<Note[]> {
  const { data } = await client.get<Note[]>('/api/v1/notes/orphans');
  return data;
}

/** Create a note from a saved template. */
export async function createFromTemplate(templateSlug: string): Promise<Note> {
  const { data } = await client.post<Note>(`/api/v1/notes/from-template/${templateSlug}`);
  return data;
}
