/**
 * TagBadge — small clickable chip for displaying and navigating to a tag.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Hash } from 'lucide-react';

interface TagBadgeProps {
  tag:       string;
  /** Size variant. */
  size?:     'xs' | 'sm';
  /** Highlight this badge (e.g., it matches the current filter). */
  active?:   boolean;
  /** Navigate to tags page when clicked (default: true). */
  clickable?: boolean;
  /** Called in addition to (or instead of) navigation when clicked. */
  onClick?:  (tag: string) => void;
  className?: string;
}

const SIZE_CLASSES = {
  xs: 'text-xs px-1.5 py-0.5',
  sm: 'text-sm px-2 py-0.5',
};

/**
 * TagBadge renders a single tag as a styled pill.
 * Clicking navigates to /tags?tag=<tag> unless `clickable` is false.
 */
export function TagBadge({
  tag, size = 'xs', active = false, clickable = true, onClick, className,
}: TagBadgeProps) {
  const navigate = useNavigate();

  const handleClick = (e: React.MouseEvent) => {
    if (!clickable && !onClick) return;
    e.stopPropagation();
    onClick?.(tag);
    if (clickable) navigate(`/tags?tag=${encodeURIComponent(tag)}`);
  };

  return (
    <span
      role={clickable || onClick ? 'button' : undefined}
      tabIndex={clickable || onClick ? 0 : undefined}
      onClick={handleClick}
      onKeyDown={(e) => e.key === 'Enter' && handleClick(e as unknown as React.MouseEvent)}
      className={[
        SIZE_CLASSES[size],
        'inline-flex items-center gap-0.5 rounded-full font-mono leading-none transition-colors',
        active
          ? 'bg-gnosis-accent/20 text-gnosis-accent'
          : 'bg-gnosis-muted/10 text-gnosis-muted hover:bg-gnosis-accent/10 hover:text-gnosis-accent',
        (clickable || onClick) ? 'cursor-pointer' : 'cursor-default',
        className ?? '',
      ].join(' ')}
    >
      <Hash size={size === 'xs' ? 9 : 11} />
      {tag}
    </span>
  );
}
