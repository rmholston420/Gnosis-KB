/**
 * TagInput
 * ========
 * Pill-style tag editor with autocomplete from GET /tags/.
 *
 * Usage:
 *   <TagInput tags={tags} onChange={setTags} />
 *
 * Keyboard shortcuts:
 *   Enter / comma / Tab — add current input as a tag
 *   Backspace           — remove last tag when input is empty
 *   ArrowUp/Down        — navigate autocomplete dropdown
 *   Escape              — close dropdown
 *
 * Autocomplete:
 *   Fetches the full tag list once (stale 5 min via React Query).
 *   Filters client-side as the user types — no extra API calls.
 */

import { useCallback, useEffect, useRef, useState, KeyboardEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, Tag } from 'lucide-react';
import api from '../services/api';

interface TagRow {
  tag: string;
  count: number;
}

interface TagInputProps {
  /** Current tag array (controlled). */
  tags: string[];
  /** Called whenever the tag list changes. */
  onChange: (tags: string[]) => void;
  /** Input placeholder text. */
  placeholder?: string;
  /** Whether the input is disabled. */
  disabled?: boolean;
}

export default function TagInput({
  tags,
  onChange,
  placeholder = 'Add tag\u2026',
  disabled = false,
}: TagInputProps) {
  const [inputValue, setInputValue] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [highlightedIdx, setHighlightedIdx] = useState<number>(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch all tags once — used for autocomplete
  const { data: tagData } = useQuery<TagRow[]>({
    queryKey: ['tags'],
    queryFn: () => (api.listTags() as unknown) as Promise<TagRow[]>,
    staleTime: 5 * 60_000,
  });

  const allTagNames: string[] = (tagData ?? []).map((t) => t.tag);

  // Suggestions: existing tags not yet applied, matching current input
  const suggestions = allTagNames.filter(
    (t) =>
      t.toLowerCase().includes(inputValue.toLowerCase()) &&
      !tags.includes(t) &&
      inputValue.length > 0,
  );

  // ── Dismiss dropdown on outside click ──────────────────────────────────
  useEffect(() => {
    function onOutsideClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', onOutsideClick);
    return () => document.removeEventListener('mousedown', onOutsideClick);
  }, []);

  // ── Helpers ────────────────────────────────────────────────────────────
  const addTag = useCallback(
    (raw: string) => {
      const tag = raw.trim().toLowerCase().replace(/,/g, '');
      if (!tag || tags.includes(tag)) return;
      onChange([...tags, tag]);
      setInputValue('');
      setDropdownOpen(false);
      setHighlightedIdx(-1);
    },
    [tags, onChange],
  );

  const removeTag = useCallback(
    (tag: string) => onChange(tags.filter((t) => t !== tag)),
    [tags, onChange],
  );

  // ── Keyboard handling ─────────────────────────────────────────────────
  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (disabled) return;

    if (e.key === 'Enter' || e.key === ',' || e.key === 'Tab') {
      e.preventDefault();
      if (highlightedIdx >= 0 && suggestions[highlightedIdx]) {
        addTag(suggestions[highlightedIdx]);
      } else {
        addTag(inputValue);
      }
      return;
    }

    if (e.key === 'Backspace' && inputValue === '' && tags.length > 0) {
      removeTag(tags[tags.length - 1]);
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIdx((i) => Math.min(i + 1, suggestions.length - 1));
      return;
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIdx((i) => Math.max(i - 1, 0));
      return;
    }

    if (e.key === 'Escape') {
      setDropdownOpen(false);
      setHighlightedIdx(-1);
    }
  }

  function handleInputChange(value: string) {
    // Treat comma as a submit trigger (handled in keydown), but clear it here
    const clean = value.replace(/,/g, '');
    setInputValue(clean);
    setDropdownOpen(clean.length > 0);
    setHighlightedIdx(-1);
  }

  return (
    <div
      ref={containerRef}
      className="relative flex flex-wrap items-center gap-1.5 px-3 py-1.5 border-b border-border bg-bg-primary min-h-[36px]"
      onClick={() => !disabled && inputRef.current?.focus()}
    >
      <Tag size={12} className="text-text-faint flex-shrink-0" />

      {/* Existing tag chips */}
      {tags.map((tag) => (
        <span
          key={tag}
          className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/25 select-none"
        >
          {tag}
          {!disabled && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); removeTag(tag); }}
              className="ml-0.5 hover:text-white transition-colors leading-none"
              aria-label={`Remove tag ${tag}`}
            >
              <X size={10} />
            </button>
          )}
        </span>
      ))}

      {/* Text input — always rendered; disabled attribute controls editability */}
      <input
        ref={inputRef}
        type="text"
        value={inputValue}
        onChange={(e) => handleInputChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => inputValue.length > 0 && setDropdownOpen(true)}
        placeholder={placeholder}
        disabled={disabled}
        className="flex-1 min-w-[120px] bg-transparent text-xs text-text-primary outline-none placeholder-text-faint disabled:cursor-not-allowed"
        aria-label="Add tag"
        aria-autocomplete="list"
        aria-expanded={dropdownOpen && suggestions.length > 0}
      />

      {/* Autocomplete dropdown */}
      {dropdownOpen && suggestions.length > 0 && (
        <ul
          role="listbox"
          className="absolute left-0 top-full z-50 mt-1 w-64 rounded-md border border-border bg-bg-elevated shadow-lg overflow-hidden"
        >
          {suggestions.slice(0, 12).map((suggestion, idx) => (
            <li
              key={suggestion}
              role="option"
              aria-selected={idx === highlightedIdx}
              onMouseDown={(e) => { e.preventDefault(); addTag(suggestion); }}
              onMouseEnter={() => setHighlightedIdx(idx)}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs cursor-pointer transition-colors ${
                idx === highlightedIdx
                  ? 'bg-accent-cyan/15 text-accent-cyan'
                  : 'text-text-secondary hover:bg-bg-tertiary'
              }`}
            >
              <Tag size={10} className="flex-shrink-0 opacity-60" />
              {suggestion}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
