/**
 * useAppStore — Zustand state slice
 *
 * Tests each action in isolation after resetting the store to initial state.
 * We use the raw store (no React rendering needed) since all actions are
 * synchronous set() calls.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '../useAppStore';

// Reset store to initial state before every test
beforeEach(() => {
  useAppStore.setState({
    activeNoteId:     null,
    editorMode:       'edit',
    searchQuery:      '',
    sidebarCollapsed: false,
    activeFolder:     null,
    ragMode:          'hybrid',
    chatMessages:     [],
    sessionId:        null,
  });
});

describe('activeNoteId', () => {
  it('defaults to null', () => {
    expect(useAppStore.getState().activeNoteId).toBeNull();
  });

  it('setActiveNoteId updates the value', () => {
    useAppStore.getState().setActiveNoteId('note-123');
    expect(useAppStore.getState().activeNoteId).toBe('note-123');
  });

  it('setActiveNoteId accepts null to deselect', () => {
    useAppStore.getState().setActiveNoteId('note-123');
    useAppStore.getState().setActiveNoteId(null);
    expect(useAppStore.getState().activeNoteId).toBeNull();
  });
});

describe('editorMode', () => {
  it('defaults to edit', () => {
    expect(useAppStore.getState().editorMode).toBe('edit');
  });

  it('setEditorMode transitions to split', () => {
    useAppStore.getState().setEditorMode('split');
    expect(useAppStore.getState().editorMode).toBe('split');
  });

  it('setEditorMode transitions to preview', () => {
    useAppStore.getState().setEditorMode('preview');
    expect(useAppStore.getState().editorMode).toBe('preview');
  });
});

describe('sidebar', () => {
  it('defaults to expanded (sidebarCollapsed = false)', () => {
    expect(useAppStore.getState().sidebarCollapsed).toBe(false);
  });

  it('setSidebarCollapsed sets to true', () => {
    useAppStore.getState().setSidebarCollapsed(true);
    expect(useAppStore.getState().sidebarCollapsed).toBe(true);
  });

  it('toggleSidebar flips the value', () => {
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarCollapsed).toBe(true);
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarCollapsed).toBe(false);
  });
});

describe('searchQuery', () => {
  it('setSearchQuery updates the value', () => {
    useAppStore.getState().setSearchQuery('zettelkasten');
    expect(useAppStore.getState().searchQuery).toBe('zettelkasten');
  });
});

describe('ragMode', () => {
  it('defaults to hybrid', () => {
    expect(useAppStore.getState().ragMode).toBe('hybrid');
  });

  it('setRagMode transitions between modes', () => {
    useAppStore.getState().setRagMode('local');
    expect(useAppStore.getState().ragMode).toBe('local');
    useAppStore.getState().setRagMode('global');
    expect(useAppStore.getState().ragMode).toBe('global');
  });
});

describe('chat messages', () => {
  it('appendChatMessage adds to the list', () => {
    useAppStore.getState().appendChatMessage({ role: 'user', content: 'Hello' });
    expect(useAppStore.getState().chatMessages).toHaveLength(1);
    expect(useAppStore.getState().chatMessages[0]).toEqual({ role: 'user', content: 'Hello' });
  });

  it('appendChatMessage preserves existing messages', () => {
    useAppStore.getState().appendChatMessage({ role: 'user',      content: 'Q' });
    useAppStore.getState().appendChatMessage({ role: 'assistant', content: 'A' });
    expect(useAppStore.getState().chatMessages).toHaveLength(2);
  });

  it('updateLastAssistantMessage updates the last assistant bubble only', () => {
    useAppStore.getState().appendChatMessage({ role: 'user',      content: 'Q1' });
    useAppStore.getState().appendChatMessage({ role: 'assistant', content: '' });
    useAppStore.getState().appendChatMessage({ role: 'user',      content: 'Q2' });
    useAppStore.getState().appendChatMessage({ role: 'assistant', content: '' });

    useAppStore.getState().updateLastAssistantMessage('Final answer');

    const msgs = useAppStore.getState().chatMessages;
    expect(msgs[3].content).toBe('Final answer');
    expect(msgs[1].content).toBe('');  // earlier assistant bubble unchanged
  });

  it('updateLastAssistantMessage is a no-op when no assistant messages exist', () => {
    useAppStore.getState().appendChatMessage({ role: 'user', content: 'Q' });
    useAppStore.getState().updateLastAssistantMessage('ignored');
    expect(useAppStore.getState().chatMessages[0].content).toBe('Q');
  });

  it('clearChat empties messages and resets sessionId', () => {
    useAppStore.getState().appendChatMessage({ role: 'user', content: 'Q' });
    useAppStore.getState().setSessionId('sess-abc');
    useAppStore.getState().clearChat();
    expect(useAppStore.getState().chatMessages).toHaveLength(0);
    expect(useAppStore.getState().sessionId).toBeNull();
  });
});
