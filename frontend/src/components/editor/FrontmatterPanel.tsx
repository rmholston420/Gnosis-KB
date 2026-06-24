/**
 * FrontmatterPanel — structured editor for note YAML frontmatter.
 * Renders editable fields for title, type, status, tags, folder, and source URL.
 * Avoids free-form YAML; instead uses typed inputs per field.
 */
import React from 'react';
import {
  FileType, Tag, Folder, Link, AlertCircle, CheckCircle, Clock,
} from 'lucide-react';

const NOTE_TYPES = [
  'permanent', 'fleeting', 'project', 'area',
  'resource', 'journal', 'moc', 'literature',
] as const;

const NOTE_STATUSES = ['inbox', 'active', 'someday', 'done', 'archived'] as const;

export interface Frontmatter {
  title:      string;
  note_type:  string;
  status:     string;
  tags:       string[];
  folder:     string;
  source_url: string;
  created_at: string;
  modified_at:string;
}

interface FrontmatterPanelProps {
  fm:        Frontmatter;
  onChange:  (updated: Partial<Frontmatter>) => void;
  readonly?: boolean;
}

/** Small labelled field wrapper. */
function Field({ label, icon, children }: { label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gnosis-muted flex-shrink-0 w-4">{icon}</span>
      <span className="text-xs text-gnosis-muted w-20 flex-shrink-0">{label}</span>
      <div className="flex-1">{children}</div>
    </div>
  );
}

export function FrontmatterPanel({ fm, onChange, readonly = false }: FrontmatterPanelProps) {
  const inputClass = `w-full text-xs bg-transparent border-b border-gnosis-border focus:border-gnosis-accent outline-none py-0.5 text-gnosis-fg ${
    readonly ? 'opacity-60 cursor-not-allowed' : ''
  }`;

  return (
    <div
      className="bg-gnosis-surface border border-gnosis-border rounded-lg p-3 space-y-2"
      aria-label="Note frontmatter"
    >
      {/* Title */}
      <Field label="Title" icon={<FileType size={11} />}>
        <input
          type="text"
          value={fm.title}
          onChange={(e) => onChange({ title: e.target.value })}
          className={inputClass}
          disabled={readonly}
          aria-label="Note title"
        />
      </Field>

      {/* Type */}
      <Field label="Type" icon={<FileType size={11} />}>
        <select
          value={fm.note_type}
          onChange={(e) => onChange({ note_type: e.target.value })}
          className={`${inputClass} appearance-none cursor-pointer`}
          disabled={readonly}
          aria-label="Note type"
        >
          {NOTE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </Field>

      {/* Status */}
      <Field label="Status" icon={<CheckCircle size={11} />}>
        <select
          value={fm.status}
          onChange={(e) => onChange({ status: e.target.value })}
          className={`${inputClass} appearance-none cursor-pointer`}
          disabled={readonly}
          aria-label="Note status"
        >
          {NOTE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </Field>

      {/* Tags */}
      <Field label="Tags" icon={<Tag size={11} />}>
        <input
          type="text"
          value={fm.tags.join(', ')}
          onChange={(e) => onChange({ tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) })}
          placeholder="tag1, tag2, \u2026"
          className={inputClass}
          disabled={readonly}
          aria-label="Note tags (comma separated)"
        />
      </Field>

      {/* Folder */}
      <Field label="Folder" icon={<Folder size={11} />}>
        <input
          type="text"
          value={fm.folder}
          onChange={(e) => onChange({ folder: e.target.value })}
          placeholder="area/project"
          className={inputClass}
          disabled={readonly}
          aria-label="Note folder"
        />
      </Field>

      {/* Source URL */}
      <Field label="Source" icon={<Link size={11} />}>
        <input
          type="url"
          value={fm.source_url}
          onChange={(e) => onChange({ source_url: e.target.value })}
          placeholder="https://\u2026"
          className={inputClass}
          disabled={readonly}
          aria-label="Source URL"
        />
      </Field>

      {/* Timestamps (read-only) */}
      {(fm.created_at || fm.modified_at) && (
        <div className="flex items-center gap-4 pt-1 text-xs text-gnosis-muted">
          {fm.created_at && (
            <span className="flex items-center gap-1">
              <Clock size={9} /> Created {new Date(fm.created_at).toLocaleDateString()}
            </span>
          )}
          {fm.modified_at && (
            <span className="flex items-center gap-1">
              <AlertCircle size={9} /> Modified {new Date(fm.modified_at).toLocaleDateString()}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
