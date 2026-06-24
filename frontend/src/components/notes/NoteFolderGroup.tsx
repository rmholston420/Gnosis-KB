/**
 * NoteFolderGroup
 * ================
 * Collapsible folder section used in NotesPage sidebar and vault tree.
 * Renders a folder header (with note count) and a list of NoteListItems.
 */
import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Folder, FolderOpen } from 'lucide-react';
import { NoteListItem } from './NoteListItem';
import type { Note } from '../../types';

interface Props {
  folder: string;
  notes: Note[];
  defaultOpen?: boolean;
  selectedId?: string | null;
  onSelect?: (note: Note) => void;
}

export function NoteFolderGroup({
  folder,
  notes,
  defaultOpen = true,
  selectedId,
  onSelect,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  const label = folder === '__root__' ? 'Notes' : folder.replace(/^\d+-/, '');

  return (
    <div className="mb-1">
      {/* Folder header */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 px-2 py-1 rounded hover:bg-gnosis-hover text-gnosis-muted text-xs font-semibold uppercase tracking-wider transition-colors"
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown size={12} className="shrink-0" />
        ) : (
          <ChevronRight size={12} className="shrink-0" />
        )}
        {open ? (
          <FolderOpen size={13} className="shrink-0" />
        ) : (
          <Folder size={13} className="shrink-0" />
        )}
        <span className="flex-1 truncate text-left">{label}</span>
        <span className="ml-auto tabular-nums text-gnosis-muted/60">{notes.length}</span>
      </button>

      {/* Note list */}
      {open && (
        <ul role="list" className="mt-0.5 space-y-px">
          {notes.map((note) => (
            <li key={note.note_id}>
              <NoteListItem
                note={note}
                selected={note.note_id === selectedId}
                onSelect={onSelect}
              />
            </li>
          ))}
          {notes.length === 0 && (
            <li className="px-4 py-2 text-xs text-gnosis-muted/60 italic">Empty folder</li>
          )}
        </ul>
      )}
    </div>
  );
}
