import { describe, it, expect, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useEditorStore } from '../editorStore';

beforeEach(() => {
  useEditorStore.setState({ pendingChanges: false, mode: 'edit', noteId: null, title: '', body: '' });
});

describe('editorStore', () => {
  it('starts with no pending changes', () => {
    const { result } = renderHook(() => useEditorStore());
    expect(result.current.pendingChanges).toBe(false);
  });

  it('setBody marks pending', () => {
    const { result } = renderHook(() => useEditorStore());
    act(() => result.current.setBody('new content'));
    expect(result.current.pendingChanges).toBe(true);
    expect(result.current.body).toBe('new content');
  });

  it('setTitle marks pending', () => {
    const { result } = renderHook(() => useEditorStore());
    act(() => result.current.setTitle('New Title'));
    expect(result.current.pendingChanges).toBe(true);
  });

  it('reset clears pending', () => {
    const { result } = renderHook(() => useEditorStore());
    act(() => result.current.setBody('dirty'));
    act(() => result.current.reset());
    expect(result.current.pendingChanges).toBe(false);
    expect(result.current.body).toBe('');
  });

  it('setMode toggles preview', () => {
    const { result } = renderHook(() => useEditorStore());
    act(() => result.current.setMode('preview'));
    expect(result.current.mode).toBe('preview');
    act(() => result.current.setMode('edit'));
    expect(result.current.mode).toBe('edit');
  });
});
