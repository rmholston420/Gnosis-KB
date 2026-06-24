/**
 * VaultTree — hierarchical folder + file tree for the vault.
 * Renders the note tree in the left sidebar with expand/collapse, type badges,
 * and navigation to individual notes.
 */
import React, { useState, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ChevronRight, ChevronDown, FileText, Folder, FolderOpen } from 'lucide-react';
import { useNotes } from '../../hooks/useNotes';
import { NODE_COLORS } from '../../lib/graphUtils';
import type { Note } from '../../types';

interface TreeNode {
  label:    string;
  path:     string;
  note?:    Note;
  children: TreeNode[];
}

/** Build a nested tree structure from a flat notes list. */
function buildTree(notes: Note[]): TreeNode[] {
  const root: TreeNode = { label: 'root', path: '', children: [] };
  const map: Record<string, TreeNode> = { '': root };

  // Sort notes so folders are stable
  const sorted = [...notes].sort((a, b) =>
    (a.folder ?? '').localeCompare(b.folder ?? ''),
  );

  for (const note of sorted) {
    const folderPath = note.folder ?? '';
    const segments   = folderPath ? folderPath.split('/') : [];

    let current = root;
    let acc = '';
    for (const seg of segments) {
      acc = acc ? `${acc}/${seg}` : seg;
      if (!map[acc]) {
        const node: TreeNode = { label: seg, path: acc, children: [] };
        map[acc] = node;
        current.children.push(node);
      }
      current = map[acc];
    }
    // Attach the note leaf
    current.children.push({
      label:    note.title,
      path:     `note:${note.note_id}`,
      note,
      children: [],
    });
  }

  return root.children;
}

interface TreeNodeRowProps {
  node:       TreeNode;
  depth:      number;
  activeId:   string;
}

function TreeNodeRow({ node, depth, activeId }: TreeNodeRowProps) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(depth < 2);
  const isFolder   = node.children.length > 0 && !node.note;
  const isNote     = !!node.note;
  const isActive   = isNote && node.note!.note_id === activeId;
  const typeColor  = isNote
    ? (NODE_COLORS[node.note!.note_type ?? 'default'] ?? NODE_COLORS['default'])
    : undefined;

  const handleClick = () => {
    if (isFolder)     setExpanded(!expanded);
    else if (isNote)  navigate(`/notes/${node.note!.note_id}`);
  };

  return (
    <>
      <button
        onClick={handleClick}
        className={`w-full flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors ${
          isActive
            ? 'bg-gnosis-accent/15 text-gnosis-accent'
            : 'text-gnosis-muted hover:text-gnosis-fg hover:bg-gnosis-hover'
        }`}
        style={{ paddingLeft: `${8 + depth * 12}px` }}
        aria-expanded={isFolder ? expanded : undefined}
      >
        {isFolder ? (
          expanded
            ? <FolderOpen size={12} className="flex-shrink-0" />
            : <Folder     size={12} className="flex-shrink-0" />
        ) : (
          <FileText size={12} className="flex-shrink-0" style={{ color: typeColor }} />
        )}

        <span className="truncate flex-1 text-left">{node.label}</span>

        {isFolder && (
          expanded
            ? <ChevronDown  size={10} className="flex-shrink-0" />
            : <ChevronRight size={10} className="flex-shrink-0" />
        )}
      </button>

      {isFolder && expanded && node.children.map((child) => (
        <TreeNodeRow key={child.path} node={child} depth={depth + 1} activeId={activeId} />
      ))}
    </>
  );
}

/** VaultTree sidebar component. */
export function VaultTree() {
  const location  = useNavigate();
  const { pathname } = useLocation();
  const { data } = useNotes();
  const notes = data?.items ?? [];

  // Extract active note ID from path
  const activeId = pathname.startsWith('/notes/')
    ? pathname.replace('/notes/', '').split('?')[0]
    : '';

  const tree = useMemo(() => buildTree(notes), [notes]);

  return (
    <nav className="overflow-y-auto flex-1 py-1" aria-label="Vault tree">
      {tree.map((node) => (
        <TreeNodeRow key={node.path} node={node} depth={0} activeId={activeId} />
      ))}
      {notes.length === 0 && (
        <p className="text-xs text-gnosis-muted px-3 py-2">No notes yet.</p>
      )}
    </nav>
  );
}
