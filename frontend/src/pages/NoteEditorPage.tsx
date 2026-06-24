/**
 * NoteEditorPage
 * ==============
 * Wraps the NoteEditor for both new-note and edit-note flows.
 *
 * New-note flow:
 *   1. On first render (no :id param) the NoteTemplateGallery modal opens.
 *   2. User picks a template (or "blank") → gallery closes, editor opens
 *      pre-populated with template body/type/folder.
 *   3. WikilinkAutocomplete floats above the textarea whenever the user
 *      types [[ and there is a non-empty query string after it.
 *
 * Edit-note flow:
 *   - Existing note loaded via React Query; wikilink autocomplete works
 *     the same way in the editing textarea.
 *
 * Wikilink autocomplete wiring
 * ----------------------------
 * NoteEditor renders a <textarea> for the body.  This page attaches
 * a ref to that textarea via the `textareaRef` prop, uses
 * `useWikilinkDetector` to parse the caret, and renders
 * `WikilinkAutocomplete` as a portal-style overlay.
 */

import React, { useRef, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import NoteEditor from '../components/NoteEditor';
import { useAppStore } from '../store/useAppStore';
import { Loader2, ArrowLeft } from 'lucide-react';
import type { Note, NoteCreate, NoteType } from '../types';
import WikilinkAutocomplete, { useWikilinkDetector } from '../components/editor/WikilinkAutocomplete';
import { NoteTemplateGallery } from '../components/notes/NoteTemplateGallery';
import type { NoteTemplate } from '../components/notes/NoteTemplateGallery';

export default function NoteEditorPage() {
  const { id } = useParams<{ id?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setActiveNoteId } = useAppStore();

  // ---- Template gallery state (new-note flow only) -------------------------
  const [showTemplateGallery, setShowTemplateGallery] = useState(!id);
  const [chosenTemplate, setChosenTemplate] = useState<NoteTemplate | null>(null);

  // ---- Wikilink autocomplete -----------------------------------------------
  const editorWrapperRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Body state mirrors the NoteEditor's internal value so we can run the
  // wikilink detector on every keystroke without prop-drilling.
  const [bodyValue, setBodyValue] = useState('');

  const { wikilinkQuery, insertWikilink } =
    useWikilinkDetector(textareaRef, bodyValue, setBodyValue);

  // ---- Data fetching -------------------------------------------------------
  const { data: note, isLoading } = useQuery<Note>({
    queryKey: ['note', id],
    queryFn: () => api.getNote(id!) as Promise<Note>,
    enabled: !!id,
  });

  const createMutation = useMutation({
    mutationFn: (data: NoteCreate) => api.createNote(data) as Promise<Note>,
    onSuccess: (newNote: Note) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['notes-titles'] });
      navigate(`/notes/${newNote.id}`, { replace: true });
      setActiveNoteId(newNote.id);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ body, title }: { body: string; title?: string }) =>
      api.updateNote(id!, { body, title }) as Promise<Note>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['note', id] });
      queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
  });

  // ---- Template selection handler -----------------------------------------
  function handleTemplateSelect(template: NoteTemplate) {
    setChosenTemplate(template);
    setShowTemplateGallery(false);
    setBodyValue(template.body);
  }

  // ---- Loading state -------------------------------------------------------
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-text-muted" size={24} />
      </div>
    );
  }

  // ---- New note flow -------------------------------------------------------
  if (!id) {
    const prefillTitle = searchParams.get('title') ?? '';
    const folder   = chosenTemplate?.folder ?? '10-zettelkasten';
    const noteType = chosenTemplate?.note_type ?? 'permanent';
    const initialBody = bodyValue || chosenTemplate?.body || '';

    const blankNote: Note = {
      id: '',
      title: prefillTitle,
      slug: '',
      body: initialBody,
      body_html: '',
      note_type: noteType as NoteType,
      status: 'draft',
      folder,
      word_count: 0,
      is_deleted: false,
      vector_indexed: false,
      graph_indexed: false,
      frontmatter: {},
      tags: [],
      outgoing_links: [],
      incoming_links: [],
    };

    return (
      <>
        {showTemplateGallery && (
          <NoteTemplateGallery
            onSelect={handleTemplateSelect}
            onClose={() => setShowTemplateGallery(false)}
          />
        )}

        <div className="h-full flex flex-col">
          <div className="px-4 py-2 border-b border-border flex-shrink-0 flex items-center justify-between">
            <button
              onClick={() => navigate(-1)}
              className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary"
            >
              <ArrowLeft size={13} /> Back
            </button>
            {chosenTemplate && (
              <span className="text-xs text-text-muted">
                Template: <strong>{chosenTemplate.name}</strong>
                <button
                  className="ml-2 underline"
                  onClick={() => setShowTemplateGallery(true)}
                >
                  change
                </button>
              </span>
            )}
          </div>

          <div className="flex-1 overflow-hidden relative" ref={editorWrapperRef}>
            <NoteEditor
              note={blankNote}
              onSave={async (body, title) => {
                await createMutation.mutateAsync({
                  title: title || prefillTitle || 'Untitled',
                  body,
                  folder,
                  note_type: noteType as NoteType,
                });
              }}
              isLoading={createMutation.isPending}
              onBodyChange={(v) => {
                setBodyValue(v);
              }}
              textareaRef={textareaRef}
            />

            {wikilinkQuery !== null && (
              <WikilinkAutocomplete
                anchorRect={new DOMRect()}
                query={wikilinkQuery}
                onSelect={(title: string) => insertWikilink(title)}
                onClose={() => insertWikilink('')}
              />
            )}
          </div>
        </div>
      </>
    );
  }

  // ---- Edit existing note --------------------------------------------------
  if (!note) return <div className="p-6 text-accent-red">Note not found.</div>;

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b border-border flex-shrink-0">
        <button
          onClick={() => navigate('/notes')}
          className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary"
        >
          <ArrowLeft size={13} /> All Notes
        </button>
      </div>
      <div className="flex-1 overflow-hidden relative" ref={editorWrapperRef}>
        <NoteEditor
          note={note}
          onSave={async (body, title) => {
            await updateMutation.mutateAsync({ body, title });
          }}
          isLoading={updateMutation.isPending}
          onBodyChange={(v) => {
            setBodyValue(v);
          }}
          textareaRef={textareaRef}
        />

        {wikilinkQuery !== null && (
          <WikilinkAutocomplete
            anchorRect={new DOMRect()}
            query={wikilinkQuery}
            onSelect={(title: string) => insertWikilink(title)}
            onClose={() => insertWikilink('')}
          />
        )}
      </div>
    </div>
  );
}
