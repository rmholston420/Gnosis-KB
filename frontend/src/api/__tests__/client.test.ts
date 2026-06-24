/**
 * api/client.ts — Axios instance behaviour
 *
 * What we test:
 *  1. Request interceptor injects Authorization header when token is present
 *  2. Request interceptor omits header when no token is stored
 *  3. Response interceptor on 401: clears token + redirects to /login
 *  4. Response interceptor passes through non-401 errors unchanged
 *  5. Response interceptor passes successful responses through untouched
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import { apiClient } from '../client';

const mock = new MockAdapter(apiClient);

// ---------------------------------------------------------------------------
// window.location stub
// jsdom blocks window.location.href assignments (navigation is a no-op).
// We replace location with a plain writable object so the interceptor's
// `window.location.href = '/login'` is observable in tests.
// ---------------------------------------------------------------------------
let locationStub: { href: string };
const originalLocation = window.location;

beforeEach(() => {
  mock.reset();
  localStorage.clear();

  locationStub = { href: 'http://localhost:3000/' };
  Object.defineProperty(window, 'location', {
    writable: true,
    configurable: true,
    value: locationStub,
  });
});

afterEach(() => {
  Object.defineProperty(window, 'location', {
    writable: true,
    configurable: true,
    value: originalLocation,
  });
});

describe('apiClient request interceptor', () => {
  it('attaches Bearer token when gnosis_token is in localStorage', async () => {
    localStorage.setItem('gnosis_token', 'my-secret-token');
    mock.onGet('/api/v1/test').reply(200, { ok: true });

    const resp = await apiClient.get('/api/v1/test');
    expect(resp.config.headers['Authorization']).toBe('Bearer my-secret-token');
  });

  it('omits Authorization header when no token is stored', async () => {
    mock.onGet('/api/v1/test').reply(200, {});

    const resp = await apiClient.get('/api/v1/test');
    expect(resp.config.headers['Authorization']).toBeUndefined();
  });
});

describe('apiClient response interceptor', () => {
  it('removes token and redirects to /login on 401', async () => {
    localStorage.setItem('gnosis_token', 'stale-token');
    mock.onGet('/api/v1/protected').reply(401, { detail: 'Not authenticated' });

    await expect(apiClient.get('/api/v1/protected')).rejects.toThrow();

    expect(localStorage.getItem('gnosis_token')).toBeNull();
    // The interceptor sets window.location.href = '/login'.
    // Our writable stub captures the assignment directly.
    expect(window.location.href).toBe('/login');
  });

  it('re-rejects non-401 errors without touching localStorage or location', async () => {
    localStorage.setItem('gnosis_token', 'good-token');
    mock.onGet('/api/v1/broken').reply(500, { detail: 'Server error' });

    await expect(apiClient.get('/api/v1/broken')).rejects.toMatchObject({
      response: { status: 500 },
    });

    expect(localStorage.getItem('gnosis_token')).toBe('good-token');
    expect(window.location.href).not.toBe('/login');
  });

  it('passes 200 responses through unchanged', async () => {
    mock.onGet('/api/v1/notes').reply(200, [{ id: 'abc' }]);

    const resp = await apiClient.get('/api/v1/notes');
    expect(resp.status).toBe(200);
    expect(resp.data).toEqual([{ id: 'abc' }]);
  });
});
