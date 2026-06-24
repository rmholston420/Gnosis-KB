/// <reference types="vitest/globals" />
import { useEditorStore } from '../editorStore';

describe('editorStore', () => {
  beforeEach(() => { useEditorStore.setState(useEditorStore.getInitialState?.()); });

  it('initial state has empty body and edit mode', () => {
    const s = useEditorStore.getState();
    expect(s.body).toBe('');
    expect(s.mode).toBe('edit');
    expect(s.pendingChanges).toBe(false);
  });

  it('setBody marks pendingChanges', () => {
    useEditorStore.getState().setBody('Hello world');
    const s = useEditorStore.getState();
    expect(s.body).toBe('Hello world');
    expect(s.pendingChanges).toBe(true);
  });

  it('setTitle marks pendingChanges', () => {
    useEditorStore.getState().setTitle('New Title');
    const s = useEditorStore.getState();
    expect(s.title).toBe('New Title');
    expect(s.pendingChanges).toBe(true);
  });

  it('setMode changes mode without marking dirty', () => {
    useEditorStore.getState().setMode('preview');
    expect(useEditorStore.getState().mode).toBe('preview');
    expect(useEditorStore.getState().pendingChanges).toBe(false);
  });

  it('markSaved clears pendingChanges', () => {
    useEditorStore.getState().setBody('Some content');
    useEditorStore.getState().markSaved();
    expect(useEditorStore.getState().pendingChanges).toBe(false);
    expect(useEditorStore.getState().isDirty).toBe(false);
  });

  it('reset clears everything', () => {
    useEditorStore.getState().setBody('stuff');
    useEditorStore.getState().setTitle('Title');
    useEditorStore.getState().reset();
    const s = useEditorStore.getState();
    expect(s.body).toBe('');
    expect(s.title).toBe('');
    expect(s.pendingChanges).toBe(false);
  });
});
