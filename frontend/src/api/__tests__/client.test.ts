import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';

import { apiClient } from '@/api/client';

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
  localStorage.clear();
});

afterEach(() => {
  mock.restore();
});

describe('apiClient request interceptor', () => {
  it('attaches Bearer token when gnosis_token is in localStorage', async () => {
    localStorage.setItem('gnosis_token', 'my-secret-token');
    mock.onGet('/api/v1/test').reply((config) => [
      200,
      {},
      config.headers,
    ]);

    const resp = await apiClient.get('/api/v1/test');
    expect(resp.config.headers?.['Authorization']).toBe('Bearer my-secret-token');
  });

  it('omits Authorization header when no token is stored', async () => {
    mock.onGet('/api/v1/test').reply(200, {});

    const resp = await apiClient.get('/api/v1/test');
    expect(resp.config.headers?.['Authorization']).toBeUndefined();
  });
});

describe('apiClient response interceptor', () => {
  it('removes token and redirects to /login on 401', async () => {
    localStorage.setItem('gnosis_token', 'stale-token');
    mock.onGet('/api/v1/protected').reply(401, { detail: 'Not authenticated' });

    await expect(apiClient.get('/api/v1/protected')).rejects.toMatchObject({
      response: { status: 401 },
    });
    expect(localStorage.getItem('gnosis_token')).toBeNull();
  });

  it('re-rejects non-401 errors without touching localStorage', async () => {
    localStorage.setItem('gnosis_token', 'good-token');
    mock.onGet('/api/v1/broken').reply(500, { detail: 'Server error' });

    await expect(apiClient.get('/api/v1/broken')).rejects.toMatchObject({
      response: { status: 500 },
    });
    expect(localStorage.getItem('gnosis_token')).toBe('good-token');
  });

  it('passes 200 responses through unchanged', async () => {
    mock.onGet('/api/v1/notes').reply(200, [{ id: 'abc' }]);

    const resp = await apiClient.get('/api/v1/notes');
    expect(resp.status).toBe(200);
    expect(resp.data).toEqual([{ id: 'abc' }]);
  });
});
