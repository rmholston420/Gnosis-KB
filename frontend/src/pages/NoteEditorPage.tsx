/**
 * NoteEditorPage
 * ==============
 * Full note editor with:
 *   - SplitPane: left = editor, right = AI sidebar + backlinks
 *   - FrontmatterPanel: collapsible YAML frontmatter editor
 *   - BacklinksPanel: incoming wikilinks list
 *   - AiSidebar: AI tools (summary, link/tag suggestions, critique)
 *   - WikilinkAutocomplete: floating autocomplete when user types [[
 *   - NoteTemplateGallery: template picker for new notes
 */

import React, { useRef, useState, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, PanelRight, PanelRightClose } from 'lucide-react';
import api from '../services/api';
import NoteEditor from '../components/NoteEditor';
import { useAppStore }          from '../store/useAppStore';
import { useEditorStore }       from '../store/editorStore';
import { SplitPane }            from '../components/layout/SplitPane';
import { FrontmatterPanel, type Frontmatter } from '../components/editor/FrontmatterPanel';
import { BacklinksPanel }       from '../components/editor/BacklinksPanel';
import { AiSidebar }            from '../components/ai/AiSidebar';
import WikilinkAutocomplete, { useWikilinkDetector } from '../components/editor/WikilinkAutocomplete';
import { NoteTemplateGallery } from '../components/notes/NoteTemplateGallery';
import type { NoteTemplate }   from '../components/notes/NoteTemplateGallery';
import { Loader2 }             from 'lucide-react';
import type { Note, NoteCreate, NoteType, LinkSuggestion } from '../types';

// ---- helpers ---------------------------------------------------------------
function noteToFrontmatter(note: Note): Frontmatter {
  return {
    title:       note.title ?? '',
    note_type:   note.note_type ?? 'permanent',
    status:      note.status   ?? 'inbox',
    tags:        note.tags     ?? [],
    folder:      note.folder   ?? '',
    source_url:  note.source_url ?? '',
    created_at:  note.created_at  ?? '',
    modified_at: note.modified_at ?? '',
  };
}

export default function NoteEditorPage() {
  const { id } = useParams<{ id?: string }>();
  const [searchParams] = useSearchParams();
  const navigate        = useNavigate();
  const queryClient     = useQueryClient();
  const { setActiveNoteId } = useAppStore();

  // Right-panel (AI + backlinks) visibility
  const [showRightPanel, setShowRightPanel] = useState(true);

  // ---- Template gallery (new-note flow) -----------------------------------
  const [showTemplateGallery, setShowTemplateGallery] = useState(!id);
  const [chosenTemplate, setChosenTemplate]           = useState<NoteTemplate | null>(null);

  // ---- Wikilink autocomplete ----------------------------------------------
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [bodyValue, setBodyValue] = useState('');
  const { wikilinkQuery, insertWikilink } = useWikilinkDetector(textareaRef, bodyValue, setBodyValue);

  // ---- Frontmatter local state (new note) ----------------------------------
  const [fmOverride, setFmOverride] = useState<Partial<Frontmatter>>({});

  // ---- AI sidebar: insert link callback -----------------------------------
  const handleInsertLink = useCallback((s: LinkSuggestion) => {
    const wikilink = `[[${s.target_title}]]`;
    if (textareaRef.current) {
      const el    = textareaRef.current;
      const start = el.selectionStart;
      const end   = el.selectionEnd;
      const next  = bodyValue.slice(0, start) + wikilink + bodyValue.slice(end);
      setBodyValue(next);
    }
  }, [bodyValue]);

  // ---- Data fetching -------------------------------------------------------
  const { data: note, isLoading } = useQuery<Note>({
    queryKey: ['note', id],
    queryFn:  () => api.getNote(id!) as Promise<Note>,
    enabled:  !!id,
  });

  const createMutation = useMutation({
    mutationFn: (data: NoteCreate) => api.createNote(data) as Promise<Note>,
    onSuccess: (newNote: Note) => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['notes-titles'] });
      navigate(`/notes/${newNote.id ?? newNote.note_id}`, { replace: true });
      setActiveNoteId(newNote.id ?? newNote.note_id);
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

  // ---- Handlers ------------------------------------------------------------
  function handleTemplateSelect(template: NoteTemplate) {
    setChosenTemplate(template);
    setShowTemplateGallery(false);
    setBodyValue(template.body);
  }

  // ---- Loading -------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-text-muted" size={24} />
      </div>
    );
  }

  // ---- Derived values ------------------------------------------------------
  const activeNoteId = id ?? null;
  const fm: Frontmatter = note
    ? { ...noteToFrontmatter(note), ...fmOverride }
    : {
        title:       searchParams.get('title') ?? '',
        note_type:   chosenTemplate?.note_type ?? 'permanent',
        status:      'inbox',
        tags:        [],
        folder:      chosenTemplate?.folder ?? '10-zettelkasten',
        source_url:  '',
        created_at:  '',
        modified_at: '',
        ...fmOverride,
      };

  // ---- Right panel (AI + backlinks) ----------------------------------------
  const rightPanel = (
    <div className="h-full flex flex-col overflow-y-auto">
      <AiSidebar
        noteId={activeNoteId}
        onInsertLink={handleInsertLink}
        onInsertTag={(tag) => {
          setFmOverride((prev) => ({ ...prev, tags: [...(prev.tags ?? fm.tags), tag] }));
        }}
      />
      <div className="p-3">
        <BacklinksPanel noteId={activeNoteId} />
      </div>
    </div>
  );

  // ---- Editor area (shared between new + edit flows) ----------------------
  function editorArea(saveHandler: (body: string, title?: string) => Promise<void>, isPending: boolean) {
    const blankNote: Note = note ?? {
      note_id:       '',
      id:            '',
      title:         fm.title,
      slug:          '',
      body:          bodyValue || chosenTemplate?.body || '',
      note_type:     fm.note_type as NoteType,
      status:        fm.status as Note['status'],
      folder:        fm.folder,
      word_count:    0,
      is_deleted:    false,
      vector_indexed: false,
      graph_indexed:  false,
      frontmatter:   {},
      tags:          fm.tags,
      outgoing_links: [],
      incoming_links: [],
    };

    return (
      <div className="flex flex-col h-full">
        {/* Frontmatter panel */}
        <div className="flex-shrink-0 p-3 border-b border-border">
          <FrontmatterPanel
            fm={fm}
            onChange={(updated) => setFmOverride((prev) => ({ ...prev, ...updated }))}
          />
        </div>

        {/* Editor */}
        <div className="flex-1 overflow-hidden relative">
          <NoteEditor
            note={blankNote}
            onSave={saveHandler}
            isLoading={isPending}
            onBodyChange={setBodyValue}
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

  // ---- New note flow -------------------------------------------------------
  if (!id) {
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
                <button className="ml-2 underline" onClick={() => setShowTemplateGallery(true)}>change</button>
              </span>
            )}
            <button
              onClick={() => setShowRightPanel(!showRightPanel)}
              className="p-1 text-text-muted hover:text-text-primary transition-colors"
              aria-label={showRightPanel ? 'Hide sidebar' : 'Show sidebar'}
            >
              {showRightPanel ? <PanelRightClose size={14} /> : <PanelRight size={14} />}
            </button>
          </div>

          <div className="flex-1 overflow-hidden">
            {showRightPanel ? (
              <SplitPane
                left={editorArea(
                  async (body, title) => {
                    await createMutation.mutateAsync({
                      title: title || fm.title || 'Untitled',
                      body,
                      folder:    fm.folder,
                      note_type: fm.note_type as NoteType,
                      tags:      fm.tags,
                    });
                  },
                  createMutation.isPending,
                )}
                right={rightPanel}
                defaultSplit={0.62}
              />
            ) : (
              editorArea(
                async (body, title) => {
                  await createMutation.mutateAsync({
                    title: title || fm.title || 'Untitled',
                    body,
                    folder:    fm.folder,
                    note_type: fm.note_type as NoteType,
                    tags:      fm.tags,
                  });
                },
                createMutation.isPending,
              )
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
      <div className="px-4 py-2 border-b border-border flex-shrink-0 flex items-center justify-between">
        <button
          onClick={() => navigate('/notes')}
          className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary"
        >
          <ArrowLeft size={13} /> All Notes
        </button>
        <button
          onClick={() => setShowRightPanel(!showRightPanel)}
          className="p-1 text-text-muted hover:text-text-primary transition-colors"
          aria-label={showRightPanel ? 'Hide sidebar' : 'Show sidebar'}
        >
          {showRightPanel ? <PanelRightClose size={14} /> : <PanelRight size={14} />}
        </button>
      </div>

      <div className="flex-1 overflow-hidden">
        {showRightPanel ? (
          <SplitPane
            left={editorArea(
              async (body, title) => updateMutation.mutateAsync({ body, title }),
              updateMutation.isPending,
            )}
            right={rightPanel}
            defaultSplit={0.62}
          />
        ) : (
          editorArea(
            async (body, title) => updateMutation.mutateAsync({ body, title }),
            updateMutation.isPending,
          )
        )}
      </div>
    </div>
  );
}
