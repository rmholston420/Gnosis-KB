/**
 * noteStubs — lightweight note list loader used by CommandPalette.
 *
 * Kept in its own module so tests can vi.mock('@/lib/noteStubs') cleanly
 * without needing to mock the entire CommandPalette module.
 */

export interface NoteStub {
  id: string;
  title: string;
  folder: string;
}

export async function fetchNoteStubs(): Promise<NoteStub[]> {
  const base = import.meta.env.VITE_API_BASE_URL ?? '';
  try {
    const resp = await fetch(`${base}/api/v1/notes?limit=500`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('gnosis_token') ?? ''}`,
      },
    });
    if (!resp.ok) return [];
    const data = (await resp.json()) as { items?: NoteStub[] } | NoteStub[];
    return Array.isArray(data) ? data : (data.items ?? []);
  } catch {
    return [];
  }
}
