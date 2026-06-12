import { createConfig, createClient } from '@hey-api/client-fetch';

/**
 * Factory-configured hey-api client pointing at the same-origin backend
 * (Nginx proxies /api/v1 upstream). Base URL is empty so all fetch calls
 * go to the same host serving the SPA.
 */
export const apiClient = createClient(
  createConfig({
    baseUrl: '',
  }),
);
