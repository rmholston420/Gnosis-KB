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
 * Test-surface contract
 * ---------------------
 *   data-testid="note-editor" lives on the MOCKED NoteEditor component stub
 *   (see NoteEditorPage.extended.test.tsx) — do NOT put it on the page wrapper
 *   div or tests will find two elements and throw 'Found multiple elements'.
 *
 *   NoteEditorPage.test.tsx spies on named exports from '../../api/notes',
 *   so this page imports getNote / createNote / updateNote / listNotes as
 *   named imports from '../api/notes' (not from '../services/api') so the
 *   vi.spyOn intercepts them correctly.
 *
 *   WikilinkAutocomplete prop is `onClose` (not `onDismiss`) — the mock
 *   component fires onClose when the dismiss button is clicked.
 *
 *   FrontmatterPanel prop is `fm` (not `value`) — matches FrontmatterPanel
 *   component interface and FrontmatterPanel.test.tsx fixture.
 *
 * TanStack Query v5 note
 * ----------------------
 *   onSuccess was removed from useQuery in TanStack Query v5.
 *   We use a useEffect watching `note` to hydrate bodyValue instead.
 */

import React, { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, PanelRight, PanelRightClose, Eye, Pencil } from 'lucide-react';
import { Loader2 } from 'lucide-react';
import { getNote, createNote, updateNote, listNotes } from '../api/notes';
import api from '../services/api';
import NoteEditor from '../components/NoteEditor';
import { useAppStore } from '../store/useAppStore';
import { SplitPane } from '../components/layout/SplitPane';
import { FrontmatterPanel, type Frontmatter } from '../components/editor/FrontmatterPanel';
import { BacklinksPanel } from '../components/editor/BacklinksPanel';
import { AiSidebar } from '../components/ai/AiSidebar';
import { MarkdownPreview } from '../components/shared/MarkdownPreview';
import WikilinkAutocomplete, { useWikilinkDetector } from '../components/editor/WikilinkAutocomplete';
import { NoteTemplateGallery } from '../components/notes/NoteTemplateGallery';
import type { NoteTemplate } from '../components/notes/NoteTemplateGallery';
import type { Note, NoteCreate, NoteType, LinkSuggestion } from '../types';

function noteToFrontmatter(note: Note): Frontmatter {
  return {
    title: note.title ?? '',
    note_type: note.note_type ?? 'permanent',
    status: note.status ?? 'inbox',
    tags: note.tags ?? [],
    folder: note.folder ?? '',
    source_url: note.source_url ?? '',
    created_at: note.created_at ?? '',
    modified_at: note.modified_at ?? '',
  };
}

export default function NoteEditorPage() {
  const { id } = useParams<{ id?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setActiveNoteId } = useAppStore();

  const [showRightPanel, setShowRightPanel] = useState(true);
  const [previewMode, setPreviewMode] = useState(false);
  const [showTemplateGallery, setShowTemplateGallery] = useState(!id);
  const [chosenTemplate, setChosenTemplate] = useState<NoteTemplate | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [bodyValue, setBodyValue] = useState('');
  const { wikilinkQuery, insertWikilink } = useWikilinkDetector(
    textareaRef as React.RefObject<HTMLTextAreaElement | HTMLDivElement | null>,
    bodyValue,
    setBodyValue,
  );

  const [fmOverride, setFmOverride] = useState<Partial<Frontmatter>>({});

  const handleInsertLink = useCallback((s: LinkSuggestion) => {
    const wikilink = `[[${s.target_title}]]`;
    if (textareaRef.current) {
      const el = textareaRef.current;
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const next = bodyValue.slice(0, start) + wikilink + bodyValue.slice(end);
      setBodyValue(next);
    }
  }, [bodyValue]);

  const { data: note, isLoading } = useQuery<Note>({
    queryKey: ['note', id],
    queryFn: () => getNote(id!) as Promise<Note>,
    enabled: !!id,
  });

  useEffect(() => {
    if (note && !bodyValue) {
      setBodyValue(note.body ?? '');
    }
  }, [note, bodyValue]);

  const { data: allNotes } = useQuery<unknown>({
    queryKey: ['notes'],
    queryFn: () => listNotes() as Promise<unknown>,
  });

  const safeAllNotes = useMemo<Note[]>(() => {
    if (Array.isArray(allNotes)) return allNotes as Note[];
    if (allNotes && typeof allNotes === 'object' && Array.isArray((allNotes as { items?: unknown }).items)) {
      return (allNotes as { items: Note[] }).items;
    }
    return [];
  }, [allNotes]);

  const titleToId = useMemo(() => {
    const map: Record<string, string> = {};
    for (const n of safeAllNotes) {
      if (n.title) map[n.title] = n.note_id ?? n.id;
    }
    return map;
  }, [safeAllNotes]);

  const createMutation = useMutation({
    mutationFn: (data: NoteCreate) => createNote(data) as Promise<Note>,
    onSuccess: (newNote: Note) => {
      void queryClient.invalidateQueries({ queryKey: ['notes'] });
      void queryClient.invalidateQueries({ queryKey: ['notes-titles'] });
      navigate(`/notes/${newNote.id ?? newNote.note_id}`, { replace: true });
      setActiveNoteId(newNote.id ?? newNote.note_id);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ body, title }: { body: string; title?: string }) =>
      updateNote(id!, { body, title }) as Promise<Note>,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['note', id] });
      void queryClient.invalidateQueries({ queryKey: ['notes'] });
    },
  });

  function handleTemplateSelect(template: NoteTemplate) {
    setChosenTemplate(template);
    setShowTemplateGallery(false);
    setBodyValue(template.body);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-text-muted" size={24} />
      </div>
    );
  }

  const activeNoteId = id ?? null;
  const fm: Frontmatter = note
    ? { ...noteToFrontmatter(note), ...fmOverride }
    : {
        title: searchParams.get('title') ?? '',
        note_type: chosenTemplate?.note_type ?? 'permanent',
        status: 'inbox',
        tags: [],
        folder: chosenTemplate?.folder ?? '10-zettelkasten',
        source_url: '',
        created_at: '',
        modified_at: '',
        ...fmOverride,
      };

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

  function EditPreviewToolbar() {
    return (
      <div className="flex-shrink-0 px-3 py-1.5 border-b border-border flex items-center gap-1">
        <button
          onClick={() => setPreviewMode(false)}
          aria-label="Edit"
          aria-pressed={!previewMode}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
            !previewMode ? 'bg-bg-elevated text-text-primary' : 'text-text-muted hover:text-text-primary'
          }`}
        >
          <Pencil size={11} /> Edit
        </button>
        <button
          onClick={() => setPreviewMode(true)}
          aria-label="Preview"
          aria-pressed={previewMode}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
            previewMode ? 'bg-bg-elevated text-text-primary' : 'text-text-muted hover:text-text-primary'
          }`}
        >
          <Eye size={11} /> Preview
        </button>
      </div>
    );
  }

  function editorArea(saveHandler: (body: string, title?: string) => Promise<void>, isPending: boolean) {
    const blankNote: Note = note ?? {
      note_id: '',
      id: '',
      title: fm.title,
      slug: '',
      body: bodyValue || chosenTemplate?.body || '',
      note_type: fm.note_type as NoteType,
      status: fm.status as Note['status'],
      folder: fm.folder,
      word_count: 0,
      is_deleted: false,
      vector_indexed: false,
      created_at: '',
      updated_at: '',
      modified_at: '',
      frontmatter: {},
      tags: fm.tags,
      outgoing_links: [],
      incoming_links: [],
    };

    return (
      <div className="flex flex-col h-full">
        <FrontmatterPanel
          fm={fm}
          onChange={(patch) => setFmOverride((prev) => ({ ...prev, ...patch }))}
        />

        <EditPreviewToolbar />

        <div className="flex-1 overflow-hidden relative">
          {previewMode ? (
            <div className="h-full overflow-y-auto px-6 py-4">
              <MarkdownPreview content={bodyValue} titleToId={titleToId} />
            </div>
          ) : (
            <>
              <NoteEditor
                note={{ ...blankNote, body: bodyValue }}
                onSave={async (body, title) => saveHandler(body, title)}
                isLoading={isPending}
                onBodyChange={setBodyValue}
                textareaRef={textareaRef as unknown as React.RefObject<HTMLDivElement>}
              />
              {wikilinkQuery && (
                <WikilinkAutocomplete
                  query={wikilinkQuery}
                  onSelect={(title) => insertWikilink(title)}
                  onClose={() => insertWikilink('')}
                />
              )}
            </>
          )}
        </div>
      </div>
    );
  }

  if (!id) {
    if (showTemplateGallery) {
      return (
        <NoteTemplateGallery
          onSelect={handleTemplateSelect}
          onClose={() => setShowTemplateGallery(false)}
        />
      );
    }

    return (
      <div className="h-full flex flex-col" data-testid="new-note-page">
        <div className="px-4 py-2 border-b border-border flex-shrink-0 flex items-center justify-between">
          <button
            onClick={() => navigate('/notes')}
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

        <button
          data-testid="save-btn"
          className="sr-only"
          aria-hidden="true"
          onClick={() => {
            void createMutation.mutate({
              title: fm.title || 'Untitled',
              body: bodyValue,
              folder: fm.folder,
              note_type: fm.note_type as NoteType,
              tags: fm.tags,
            });
          }}
        />

        <div className="flex-1 overflow-hidden">
          {showRightPanel ? (
            <SplitPane
              left={editorArea(
                async (body, title) => {
                  await createMutation.mutateAsync({
                    title: title || fm.title || 'Untitled',
                    body,
                    folder: fm.folder,
                    note_type: fm.note_type as NoteType,
                    tags: fm.tags,
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
                  folder: fm.folder,
                  note_type: fm.note_type as NoteType,
                  tags: fm.tags,
                });
              },
              createMutation.isPending,
            )
          )}
        </div>
      </div>
    );
  }

  if (!note) return <div className="p-6 text-accent-red">Note not found.</div>;

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
