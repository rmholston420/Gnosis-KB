/**
 * SplitPane — resizable two-column layout primitive.
 * Used by the NoteEditorPage to split the editor and preview/sidebar panels.
 */
import React, { useRef, useState, useCallback, useEffect } from 'react';

interface SplitPaneProps {
  /** Left/main panel. */
  left:        React.ReactNode;
  /** Right panel. */
  right:       React.ReactNode;
  /** Initial left-panel width as a fraction of total (0 – 1). */
  defaultSplit?: number;
  /** Minimum left-panel width in pixels. */
  minLeft?:    number;
  /** Minimum right-panel width in pixels. */
  minRight?:   number;
  className?:  string;
}

const DIVIDER_W = 4;

/**
 * SplitPane renders two resizable panels separated by a draggable divider.
 * Persists split ratio to localStorage under key `gnosis-split`.
 */
export function SplitPane({
  left, right,
  defaultSplit = 0.5,
  minLeft  = 260,
  minRight = 200,
  className,
}: SplitPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [splitFraction, setSplit] = useState(() => {
    const saved = parseFloat(localStorage.getItem('gnosis-split') ?? '');
    return isNaN(saved) ? defaultSplit : saved;
  });
  const dragging = useRef(false);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const { left: boxLeft, width } = containerRef.current.getBoundingClientRect();
      const raw = (e.clientX - boxLeft) / width;
      const clamped = Math.max(
        minLeft  / width,
        Math.min(1 - (minRight + DIVIDER_W) / width, raw),
      );
      setSplit(clamped);
      localStorage.setItem('gnosis-split', String(clamped));
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup',   onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup',   onUp);
    };
  }, [minLeft, minRight]);

  return (
    <div
      ref={containerRef}
      className={`flex h-full overflow-hidden ${className ?? ''}`}
    >
      {/* Left panel */}
      <div
        className="h-full overflow-auto flex-shrink-0"
        style={{ width: `calc(${splitFraction * 100}% - ${DIVIDER_W / 2}px)` }}
      >
        {left}
      </div>

      {/* Divider */}
      <div
        role="separator"
        aria-label="Resize panes"
        onMouseDown={onMouseDown}
        className="flex-shrink-0 bg-gnosis-border hover:bg-gnosis-accent transition-colors cursor-col-resize"
        style={{ width: DIVIDER_W }}
      />

      {/* Right panel */}
      <div className="flex-1 h-full overflow-auto min-w-0">
        {right}
      </div>
    </div>
  );
}
