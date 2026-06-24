/// <reference types="vitest/globals" />
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiGet, apiPost, apiPut, apiDelete } from '../client';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

function makeResponse(data: unknown, status = 200) {
  return {
    ok:     status >= 200 && status < 300,
    status,
    json:   () => Promise.resolve(data),
    text:   () => Promise.resolve(JSON.stringify(data)),
  } as unknown as Response;
}

describe('API client helpers', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('apiGet calls fetch with GET', async () => {
    mockFetch.mockResolvedValue(makeResponse({ ok: true }));
    await apiGet('/notes/');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/notes/'),
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('apiPost calls fetch with POST and JSON body', async () => {
    mockFetch.mockResolvedValue(makeResponse({ note_id: '123' }));
    await apiPost('/notes/', { title: 'Hello' });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/notes/'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('apiPut calls fetch with PUT', async () => {
    mockFetch.mockResolvedValue(makeResponse({ note_id: '123' }));
    await apiPut('/notes/123', { title: 'Updated' });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ method: 'PUT' }),
    );
  });

  it('apiDelete calls fetch with DELETE', async () => {
    mockFetch.mockResolvedValue({ ok: true, status: 204, json: vi.fn(), text: vi.fn() } as unknown as Response);
    await apiDelete('/notes/123');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('throws on non-2xx responses', async () => {
    mockFetch.mockResolvedValue(makeResponse({ detail: 'Not found' }, 404));
    await expect(apiGet('/notes/missing')).rejects.toThrow();
  });
});
