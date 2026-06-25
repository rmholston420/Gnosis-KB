/**
 * TagInput — multi-tag input with autocomplete from existing vault tags.
 */
import React, { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { TagRow } from '../types';

interface TagInputProps {
  value:    string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  disabled?:    boolean;
}

export function TagInput({ value, onChange, placeholder = 'Add tag\u2026', disabled }: TagInputProps) {
  const [input, setInput]       = useState('');
  const [open,  setOpen]        = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: tagData } = useQuery({
    queryKey: ['tags'],
    queryFn:  () => api.listTags(),
    staleTime: 60_000,
  });

  const rawTags = tagData ?? [];
  const allTagNames: string[] = Array.isArray(rawTags)
    ? rawTags.map((t: string | TagRow) => (typeof t === 'string' ? t : t.tag))
    : [];

  const suggestions = allTagNames.filter(
    (t) => t.toLowerCase().includes(input.toLowerCase()) && !value.includes(t),
  );

  function addTag(tag: string) {
    const clean = tag.trim().toLowerCase().replace(/\s+/g, '-');
    if (clean && !value.includes(clean)) onChange([...value, clean]);
    setInput('');
    setOpen(false);
  }

  function removeTag(tag: string) {
    onChange(value.filter((t) => t !== tag));
  }

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if ((e.key === 'Enter' || e.key === ',') && input.trim()) {
      e.preventDefault();
      addTag(input);
    } else if (e.key === 'Backspace' && !input && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (inputRef.current && !inputRef.current.closest('[data-tag-input]')?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div data-tag-input className="relative flex flex-wrap gap-1 p-1 border border-gnosis-border rounded bg-gnosis-surface min-h-[36px]">
      {value.map((tag) => (
        <span
          key={tag}
          className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-gnosis-accent/20 text-gnosis-accent text-xs"
        >
          #{tag}
          {!disabled && (
            <button
              type="button"
              onClick={() => removeTag(tag)}
              className="hover:text-red-400 transition-colors"
              aria-label={`Remove tag ${tag}`}
            >
              \xd7
            </button>
          )}
        </span>
      ))}
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => { setInput(e.target.value); setOpen(true); }}
        onKeyDown={handleKey}
        onFocus={() => setOpen(true)}
        placeholder={value.length === 0 ? placeholder : ''}
        disabled={disabled}
        className="flex-1 min-w-[80px] bg-transparent outline-none text-xs text-gnosis-fg placeholder:text-gnosis-muted"
      />
      {open && suggestions.length > 0 && (
        <ul className="absolute left-0 top-full mt-1 z-50 w-full bg-gnosis-surface border border-gnosis-border rounded shadow-lg max-h-40 overflow-y-auto">
          {suggestions.slice(0, 12).map((tag) => (
            <li key={tag}>
              <button
                type="button"
                onMouseDown={(e) => { e.preventDefault(); addTag(tag); }}
                className="w-full text-left px-3 py-1.5 text-xs hover:bg-gnosis-border transition-colors"
              >
                #{tag}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default TagInput;
