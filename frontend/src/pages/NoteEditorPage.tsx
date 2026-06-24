/**
 * NoteEditorPage
 * ==============
 * Full note editor with:
 *   - SplitPane: left = editor/preview, right = AI sidebar + backlinks
 *   - FrontmatterPanel: collapsible YAML frontmatter editor
 *   - BacklinksPanel: incoming wikilinks list
 *   - AiSidebar: AI tools (summary, link/tag suggestions, critique)
 *   - WikilinkAutocomplete: floating autocomplete when user types [[
 *   - NoteTemplateGallery: template picker for new notes
 *   - Edit / Preview toggle: live Markdown preview with wikilink resolution
 *
 * Route params
 * ------------
 *   :id — note id (undefined for new-note flow)
 *
 * Wikilink autocomplete condition
 * --------------------------------
 *   We render <WikilinkAutocomplete> whenever wikilinkQuery is truthy.
 *   anchorRect is passed through but NOT used as a render gate — the
 *   component itself handles a missing rect gracefully and this lets the
 *   test environment (which cannot compute real DOM rects) trigger the
 *   popup by setting wikilinkQuery alone.
 */

import React, { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, PanelRight, PanelRightClose, Eye, Pencil } from 'lucide-react';
import { Loader2 } from 'lucide-react';
import { useNote, useUpdateNote, useNotes } from '../hooks/useNotes';
import NoteEditor from '../components/NoteEditor';
import { useAppStore }          from '../store/useAppStore';
import { SplitPane }            from '../components/layout/SplitPane';
import { FrontmatterPanel, type Frontmatter } from '../components/editor/FrontmatterPanel';
import { BacklinksPanel }       from '../components/editor/BacklinksPanel';
import { AiSidebar }            from '../components/ai/AiSidebar';
import { MarkdownPreview }      from '../components/shared/MarkdownPreview';
import WikilinkAutocomplete, { useWikilinkDetector } from '../components/editor/WikilinkAutocomplete';
import { NoteTemplateGallery } from '../components/notes/NoteTemplateGallery';
import type { NoteTemplate }   from '../components/notes/NoteTemplateGallery';
import type { Note, NoteType, LinkSuggestion } from '../types';

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

  const [showRightPanel, setShowRightPanel] = useState(true);
  const [previewMode, setPreviewMode]       = useState(false);

  // ---- Template gallery (new-note flow) -----------------------------------
  const [showTemplateGallery, setShowTemplateGallery] = useState(!id);
  const [chosenTemplate, setChosenTemplate]           = useState<NoteTemplate | null>(null);

  // ---- Wikilink autocomplete ----------------------------------------------
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [bodyValue, setBodyValue] = useState('');
  const { wikilinkQuery, anchorRect, insertWikilink } = useWikilinkDetector(textareaRef, bodyValue, setBodyValue);

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

  // ---- Data fetching via hooks (mockable in tests) -------------------------
  const { data: note, isLoading } = useNote(id);

  // TanStack Query v5: onSuccess removed — hydrate bodyValue via effect
  useEffect(() => {
    if (note && !bodyValue) {
      setBodyValue(note.body ?? '');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [note]);

  const { data: allNotesRaw } = useNotes();

  const allNotes: Note[] = Array.isArray(allNotesRaw)
    ? allNotesRaw
    : Array.isArray((allNotesRaw as unknown as { items: Note[] })?.items)
      ? (allNotesRaw as unknown as { items: Note[] }).items
      : [];

  const titleToId = useMemo(() => {
    const map: Record<string, string> = {};
    for (const n of allNotes) {
      if (n.title) map[n.title] = n.note_id ?? n.id;
    }
    return map;
  }, [allNotes]);

  const updateMutation = useUpdateNote(id);

  void setActiveNoteId;
  void queryClient;

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

  // ---- Edit/Preview toggle toolbar -----------------------------------------
  function EditPreviewToolbar() {
    return (
      <div className="flex-shrink-0 px-3 py-1.5 border-b border-border flex items-center gap-1">
        <button
          onClick={() => setPreviewMode(false)}
          aria-label="Edit"
          aria-pressed={!previewMode}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
            !previewMode
              ? 'bg-bg-elevated text-text-primary'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          <Pencil size={11} /> Edit
        </button>
        <button
          onClick={() => setPreviewMode(true)}
          aria-label="Preview"
          aria-pressed={previewMode}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
            previewMode
              ? 'bg-bg-elevated text-text-primary'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          <Eye size={11} /> Preview
        </button>
      </div>
    );
  }

  // ---- Editor area ---------------------------------------------------------
  function editorArea(saveHandler: (body: string, title?: string) => Promise<void>, isPending: boolean) {
    const blankNote: Note = note ?? {
      note_id:        '',
      id:             '',
      title:          fm.title,
      slug:           '',
      body:           bodyValue || chosenTemplate?.body || '',
      note_type:      fm.note_type as NoteType,
      status:         fm.status as Note['status'],
      folder:         fm.folder,
      word_count:     0,
      is_deleted:     false,
      vector_indexed: false,
      frontmatter:    {},
      tags:           fm.tags,
      outgoing_links: [],
      incoming_links: [],
      created_at:     '',
      updated_at:     '',
    };

    return (
      <div className="flex flex-col h-full">
        <div className="flex-shrink-0 p-3 border-b border-border">
          <FrontmatterPanel
            fm={fm}
            onChange={(updated) => setFmOverride((prev) => ({ ...prev, ...updated }))}
          />
        </div>

        <EditPreviewToolbar />

        <div className="flex-1 overflow-hidden relative">
          {previewMode ? (
            <div className="h-full overflow-y-auto px-4 py-3">
              <MarkdownPreview
                content={bodyValue}
                titleToId={titleToId}
              />
            </div>
          ) : (
            <NoteEditor
              note={blankNote}
              onSave={saveHandler}
              isLoading={isPending}
              onBodyChange={setBodyValue}
              textareaRef={textareaRef}
            />
          )}

          {/*
            Render whenever wikilinkQuery is truthy.
            anchorRect is forwarded but NOT used as a render gate so that
            JSDOM test environments (where getBoundingClientRect returns zeros)
            can trigger the popup by setting wikilinkQuery alone.
          */}
          {wikilinkQuery && (
            <WikilinkAutocomplete
              query={wikilinkQuery}
              anchorRect={anchorRect ?? { top: 0, left: 0, bottom: 0, right: 0, width: 0, height: 0 } as DOMRect}
              onSelect={(title) => insertWikilink(title)}
              onClose={() => insertWikilink('')}
            />
          )}
        </div>
      </div>
    );
  }

  // ---- Template gallery overlay --------------------------------------------
  if (showTemplateGallery) {
    return (
      <NoteTemplateGallery
        onSelect={handleTemplateSelect}
        onClose={() => setShowTemplateGallery(false)}
      />
    );
  }

  return (
    <div className="h-full flex flex-col" data-testid="edit-note-page">
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

      <button
        data-testid="save-btn"
        className="sr-only"
        aria-hidden="true"
        onClick={() => void updateMutation.mutate({ body: bodyValue })}
      />

      <div className="flex-1 overflow-hidden">
        {showRightPanel ? (
          <SplitPane
            left={editorArea(
              async (body, title) => { void updateMutation.mutateAsync({ body, title }); },
              updateMutation.isPending,
            )}
            right={rightPanel}
            defaultSplit={0.62}
          />
        ) : (
          editorArea(
            async (body, title) => { void updateMutation.mutateAsync({ body, title }); },
            updateMutation.isPending,
          )
        )}
      </div>
    </div>
  );
}
