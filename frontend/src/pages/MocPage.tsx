import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Map, Loader2, AlertCircle, Download, Copy, CheckCheck, ChevronDown, ChevronRight, Sparkles } from 'lucide-react';
import axios from 'axios';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8010';

// ---- Types ---------------------------------------------------------------

interface MocSection {
  heading: string;
  wikilinks: string[];
  summary: string;
}

interface MocResponse {
  topic: string;
  moc_title: string;
  vault_path: string;
  sections: MocSection[];
  markdown: string;
  note_count: number;
}

interface MocRequest {
  topic: string;
  tag?: string;
  folder?: string;
  max_notes: number;
}

// ---- API -----------------------------------------------------------------

const generateMoc = (req: MocRequest): Promise<MocResponse> =>
  axios.post(`${API}/api/v1/ai/generate-moc`, req).then(r => r.data);

// ---- Folder presets ------------------------------------------------------

const FOLDER_PRESETS = [
  { label: 'All folders', value: '' },
  { label: '00 Inbox', value: '00-inbox' },
  { label: '10 Zettelkasten', value: '10-zettelkasten' },
  { label: '20 Projects', value: '20-projects' },
  { label: '30 Areas', value: '30-areas' },
  { label: '40 Resources', value: '40-resources' },
  { label: '70 Sources', value: '70-sources' },
];

// ---- MocSectionCard ------------------------------------------------------

function MocSectionCard({ section, idx }: { section: MocSection; idx: number }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 bg-gray-50 dark:bg-gray-800 text-left hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 text-xs font-bold flex-shrink-0">
          {idx + 1}
        </span>
        <span className="font-semibold text-sm flex-1">{section.heading}</span>
        <span className="text-xs text-gray-400">{section.wikilinks.length} notes</span>
        {open ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
      </button>
      {open && (
        <div className="px-4 py-3 space-y-2">
          {section.summary && (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">{section.summary}</p>
          )}
          <div className="flex flex-wrap gap-1.5">
            {section.wikilinks.map(link => (
              <span
                key={link}
                className="inline-block rounded-full bg-blue-50 dark:bg-blue-900/20 px-2.5 py-0.5 text-xs text-blue-700 dark:text-blue-300 font-mono"
              >
                {link}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---- MarkdownPreview -----------------------------------------------------

function MarkdownPreview({ markdown }: { markdown: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'moc.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Markdown Output</span>
        <div className="flex gap-2">
          <button
            aria-label="Copy"
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            {copied ? <CheckCheck size={13} className="text-green-500" /> : <Copy size={13} />}
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            aria-label="Download"
            onClick={handleDownload}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <Download size={13} />
            Download
          </button>
        </div>
      </div>
      <pre className="flex-1 overflow-auto p-4 font-mono text-xs text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 whitespace-pre-wrap">
        {markdown}
      </pre>
    </div>
  );
}

// ---- Main Page -----------------------------------------------------------

export default function MocPage() {
  const [topic, setTopic] = useState('');
  const [tag, setTag] = useState('');
  const [folder, setFolder] = useState('');
  const [maxNotes, setMaxNotes] = useState(60);
  const [activeTab, setActiveTab] = useState<'sections' | 'markdown'>('sections');

  const mutation = useMutation({
    mutationFn: () =>
      generateMoc({
        topic: topic.trim(),
        tag: tag.trim() || undefined,
        folder: folder || undefined,
        max_notes: maxNotes,
      }),
  });

  const result = mutation.data;
  const mutationError = mutation.error as { message?: string } | null;
  const errorMsg = mutationError?.message ?? (mutation.isError ? 'Generation failed.' : null);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
        <Map size={20} className="text-violet-500" />
        <div>
          <h1 className="text-lg font-semibold">Map of Content Generator</h1>
          <p className="text-xs text-gray-400">AI-groups your notes into a structured hub note with wikilinks</p>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* ---- Left: form panel ---- */}
        <aside className="flex w-72 flex-shrink-0 flex-col gap-4 border-r border-gray-200 dark:border-gray-800 p-5 overflow-y-auto">
          <div className="space-y-1">
            <label className="block text-sm font-medium">Topic <span className="text-red-400">*</span></label>
            <input
              value={topic}
              onChange={e => setTopic(e.target.value)}
              placeholder="e.g. EEG signal processing"
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
            />
            <p className="text-xs text-gray-400">The central theme of the MOC</p>
          </div>

          <div className="space-y-1">
            <label className="block text-sm font-medium">Filter by tag</label>
            <input
              value={tag}
              onChange={e => setTag(e.target.value)}
              placeholder="e.g. eeg (leave blank for all)"
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
            />
          </div>

          <div className="space-y-1">
            <label className="block text-sm font-medium">Filter by folder</label>
            <select
              value={folder}
              onChange={e => setFolder(e.target.value)}
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              {FOLDER_PRESETS.map(p => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="block text-sm font-medium">Max notes to scan</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={5}
                max={200}
                step={5}
                value={maxNotes}
                onChange={e => setMaxNotes(Number(e.target.value))}
                className="flex-1"
              />
              <span className="w-8 text-right text-sm font-mono">{maxNotes}</span>
            </div>
          </div>

          <button
            onClick={() => mutation.mutate()}
            disabled={!topic.trim() || mutation.isPending}
            aria-label="Generate MOC"
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm text-white font-medium hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {mutation.isPending
              ? <><Loader2 size={15} className="animate-spin" /> Generating…</>
              : <><Sparkles size={15} /> Generate MOC</>}
          </button>

          {result && (
            <div className="rounded-lg bg-violet-50 dark:bg-violet-900/20 p-3 text-xs text-violet-700 dark:text-violet-300 space-y-1">
              <p className="font-semibold">{result.moc_title}</p>
              <p>{result.sections.length} sections · {result.note_count} notes scanned</p>
              <p className="font-mono text-violet-500 dark:text-violet-400">{result.vault_path}</p>
            </div>
          )}

          {errorMsg && (
            <div className="flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-xs text-red-600 dark:text-red-400">
              <AlertCircle size={13} className="mt-0.5 flex-shrink-0" />
              <span>Error: {errorMsg}</span>
            </div>
          )}
        </aside>

        {/* ---- Right: results ---- */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {!result && !mutation.isPending && (
            <div className="flex h-full flex-col items-center justify-center text-gray-300 dark:text-gray-600 gap-4">
              <Map size={56} />
              <div className="text-center">
                <p className="text-sm font-medium">No MOC generated yet</p>
                <p className="text-xs mt-1">Enter a topic and click Generate MOC</p>
              </div>
            </div>
          )}

          {mutation.isPending && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-violet-500">
              <Loader2 size={36} className="animate-spin" />
              <p className="text-sm">Analysing vault and grouping notes…</p>
            </div>
          )}

          {result && !mutation.isPending && (
            <div className="flex flex-1 flex-col overflow-hidden">
              {/* Tab bar — role="tab" so tests can query by role */}
              <div role="tablist" className="flex border-b border-gray-200 dark:border-gray-800 px-4">
                {(['sections', 'markdown'] as const).map(tab => (
                  <button
                    key={tab}
                    role="tab"
                    aria-selected={activeTab === tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === tab
                        ? 'border-violet-500 text-violet-600 dark:text-violet-400'
                        : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                    }`}
                  >
                    {tab === 'sections' ? `Sections (${result.sections.length})` : 'Markdown'}
                  </button>
                ))}
              </div>

              {/* Sections tab */}
              {activeTab === 'sections' && (
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  <p className="text-xs text-gray-400">
                    {result.note_count} notes scanned · save to <span className="font-mono">{result.vault_path}</span>
                  </p>
                  {result.sections.map((sec, i) => (
                    <MocSectionCard key={sec.heading} section={sec} idx={i} />
                  ))}
                </div>
              )}

              {/* Markdown tab */}
              {activeTab === 'markdown' && (
                <div className="flex flex-1 overflow-hidden">
                  <MarkdownPreview markdown={result.markdown} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
