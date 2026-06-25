/**
 * client.test.ts — verifies axios instance headers and interceptors.
 */
import MockAdapter from 'axios-mock-adapter';
import type { AxiosHeaders, AxiosRequestConfig } from 'axios';
import client from '../client';

describe('API client', () => {
  let mock: MockAdapter;

  beforeEach(() => {
    mock = new MockAdapter(client);
    localStorage.clear();
  });

  afterEach(() => {
    mock.restore();
  });

  it('includes Authorization header when token is present', async () => {
    localStorage.setItem('gnosis_token', 'test-token-123');

    mock.onGet('/api/v1/test').reply((config: AxiosRequestConfig) => [
      200,
      {},
      // Cast headers to AxiosHeaders to satisfy MockArrayResponse
      config.headers as AxiosHeaders,
    ]);

    const res = await client.get('/api/v1/test');
    expect(res.config.headers?.['Authorization']).toBe('Bearer test-token-123');
  });

  it('omits Authorization header when no token', async () => {
    mock.onGet('/api/v1/test').reply(200, {});
    const res = await client.get('/api/v1/test');
    expect(res.config.headers?.['Authorization']).toBeUndefined();
  });
});
