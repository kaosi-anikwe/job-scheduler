import { createConfig, createClient } from '@hey-api/client-fetch';
import { toast } from 'sonner';

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

// Automatically toast on any non-2xx response
apiClient.interceptors.response.use(async (response) => {
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.clone().json() as Record<string, unknown>;
      const detail = body['detail'];
      if (typeof detail === 'string') message = detail;
      else if (detail !== undefined) message = JSON.stringify(detail);
    } catch { /* non-JSON body */ }
    toast.error(message);
  }
  return response;
});

/**
 * Unwrap a hey-api SDK call, returning data directly.
 * On error the interceptor has already shown the toast; this throws so
 * callers can bail out early without further handling.
 */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown }>,
): Promise<T> {
  const { data, error } = await call;
  if (error !== undefined || data === undefined) {
    throw error ?? new Error('API request failed');
  }
  return data;
}
