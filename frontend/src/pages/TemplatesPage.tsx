import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateNote } from '../hooks/useNotes';

interface Template {
  id:       string;
  name:     string;
  icon:     string;
  noteType: 'permanent' | 'fleeting' | 'literature' | 'journal' | 'map' | 'project';
  body:     string;
}

const TEMPLATES: Template[] = [
  {
    id: 'permanent', name: 'Permanent Note', icon: '📌', noteType: 'permanent',
    body: '## Idea\n\n## Why it matters\n\n## Connections\n\n## References\n',
  },
  {
    id: 'fleeting', name: 'Fleeting Note', icon: '⚡', noteType: 'fleeting',
    body: '## Capture\n\n_Process this within 48 hours._\n',
  },
  {
    id: 'literature', name: 'Literature Note', icon: '📚', noteType: 'literature',
    body: '## Source\n\n## Key ideas\n\n## Quotes\n\n## My take\n',
  },
  {
    id: 'journal', name: 'Journal Entry', icon: '📓', noteType: 'journal',
    body: `## ${new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}\n\n## Reflections\n\n## Intentions\n`,
  },
  {
    id: 'moc', name: 'Map of Content', icon: '🗺️', noteType: 'map',
    body: '## Overview\n\n## Key notes\n\n## Subtopics\n',
  },
  {
    id: 'project', name: 'Project Note', icon: '🚧', noteType: 'project',
    body: '## Goal\n\n## Tasks\n- [ ] \n\n## Notes\n\n## Done\n',
  },
];

export default function TemplatesPage() {
  const navigate   = useNavigate();
  const createNote = useCreateNote();
  const [creating, setCreating] = useState<string | null>(null);

  const handleCreate = async (tpl: Template) => {
    setCreating(tpl.id);
    try {
      const note = await createNote.mutateAsync({
        title:     `New ${tpl.name}`,
        body:      tpl.body,
        note_type: tpl.noteType,
        status:    'draft',
      });
      navigate(`/notes/${note.note_id}/edit`);
    } finally {
      setCreating(null);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gnosis-bg text-gnosis-fg">
      <div className="px-6 pt-6 pb-4 border-b border-gnosis-border">
        <h1 className="text-xl font-semibold">Templates</h1>
        <p className="text-sm text-gnosis-muted mt-1">
          Start a new note from a structured template.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {TEMPLATES.map((tpl) => (
            <button
              key={tpl.id}
              onClick={() => handleCreate(tpl)}
              disabled={creating === tpl.id}
              className="flex flex-col gap-2 p-5 rounded-xl text-left
                         bg-gnosis-surface border border-gnosis-border
                         hover:border-gnosis-accent hover:bg-gnosis-surface/80
                         disabled:opacity-60 transition-all group"
            >
              <span className="text-3xl">{tpl.icon}</span>
              <span className="font-medium text-gnosis-fg group-hover:text-gnosis-accent transition-colors">
                {creating === tpl.id ? 'Creating…' : tpl.name}
              </span>
              <span className="text-xs text-gnosis-muted capitalize">{tpl.noteType}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
