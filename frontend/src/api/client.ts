// Typed HTTP client with auth injection, cold-start handling, and error normalization
import { appConfig } from './config';
import { ApiClientError, ApiErrorPayload } from './types';

export const TOKEN_STORAGE_KEY = 'recallos_token';

// In-flight request and wake-up state management
type WakeupListener = (isWaking: boolean) => void;
const wakeupListeners: Set<WakeupListener> = new Set();
let slowRequestCount = 0;

function notifyWakeupListeners() {
  const isWaking = slowRequestCount > 0;
  wakeupListeners.forEach((cb) => cb(isWaking));
}

export function subscribeToWakeup(callback: WakeupListener): () => void {
  wakeupListeners.add(callback);
  callback(slowRequestCount > 0);
  return () => {
    wakeupListeners.delete(callback);
  };
}

export interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  isReviewSubmit?: boolean;
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 90_000; // 90 seconds for Render wake-up

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    skipAuth = false,
    isReviewSubmit = false,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    headers: customHeaders = {},
    ...customInit
  } = options;

  const url = endpoint.startsWith('http') ? endpoint : `${appConfig.apiUrl}${endpoint}`;
  const method = (customInit.method || 'GET').toUpperCase();

  // Retry policy: GET requests retry up to 3 times on network / 502 / 503 errors with 3s delay.
  // POST/PATCH/DELETE never retry, EXCEPT review POST (isReviewSubmit) which carries an idempotency request_id.
  const canRetry = method === 'GET' || isReviewSubmit;
  const maxRetries = canRetry ? 3 : 0;

  let attempt = 0;

  while (attempt <= maxRetries) {
    attempt++;

    // Track slow request (> 4s) to trigger wake-up banner
    let isMarkedSlow = false;
    const slowTimer = setTimeout(() => {
      isMarkedSlow = true;
      slowRequestCount++;
      notifyWakeupListeners();
    }, 4000);

    const controller = new AbortController();
    const abortTimer = setTimeout(() => {
      controller.abort();
    }, timeoutMs);

    try {
      const headers: Record<string, string> = {
        ...(customHeaders as Record<string, string>),
      };

      // Attach token if present and not skipped
      if (!skipAuth) {
        const token = localStorage.getItem(TOKEN_STORAGE_KEY);
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      }

      // Do not set Content-Type if sending FormData (browser sets boundary)
      if (!(customInit.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
      }

      const response = await fetch(url, {
        ...customInit,
        method,
        headers,
        signal: controller.signal,
      });

      // Clear timers
      clearTimeout(slowTimer);
      clearTimeout(abortTimer);
      if (isMarkedSlow) {
        slowRequestCount = Math.max(0, slowRequestCount - 1);
        notifyWakeupListeners();
        isMarkedSlow = false;
      }

      // 401 handling
      if (response.status === 401) {
        const isAuthEndpoint =
          endpoint.includes('/api/auth/login') || endpoint.includes('/api/auth/register');

        if (!isAuthEndpoint) {
          // Clear token on authenticated 401 and redirect to login
          localStorage.removeItem(TOKEN_STORAGE_KEY);
          if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
            window.location.href = '/login?expired=1';
          }
        }
      }

      // Render cold-start temporary errors: 502 / 503
      if ((response.status === 502 || response.status === 503) && attempt <= maxRetries) {
        await new Promise((res) => setTimeout(res, 3000));
        continue;
      }

      if (!response.ok) {
        let errPayload: ApiErrorPayload = {
          code: 'HTTP_ERROR',
          message: `Request failed with status ${response.status}`,
        };

        try {
          const json = await response.json();
          if (json && typeof json === 'object') {
            if (json.error && typeof json.error === 'object') {
              errPayload = {
                code: json.error.code || 'HTTP_ERROR',
                message: json.error.message || errPayload.message,
                ...json.error,
              };
            } else if (json.detail) {
              errPayload.message = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
            }
          }
        } catch {
          // Fallback if not JSON (e.g. HTML 502/503 from reverse proxy)
          if (response.status === 502 || response.status === 503) {
            errPayload.message = 'The server is currently waking up or unavailable. Please retry in a few seconds.';
          }
        }

        throw new ApiClientError(response.status, errPayload);
      }

      // 204 No Content
      if (response.status === 204) {
        return undefined as T;
      }

      const data = await response.json();
      return data as T;
    } catch (err: unknown) {
      clearTimeout(slowTimer);
      clearTimeout(abortTimer);
      if (isMarkedSlow) {
        slowRequestCount = Math.max(0, slowRequestCount - 1);
        notifyWakeupListeners();
      }

      // Check if we should retry network errors
      if (err instanceof ApiClientError) {
        throw err;
      }

      // AbortError or Network fetch failure
      const isAbort = (err as Error)?.name === 'AbortError';
      if (attempt <= maxRetries && !isAbort) {
        await new Promise((res) => setTimeout(res, 3000));
        continue;
      }

      if (isAbort) {
        throw new ApiClientError(408, {
          code: 'REQUEST_TIMEOUT',
          message: 'The request timed out. The server may still be waking up. Please try again.',
        });
      }

      throw new ApiClientError(0, {
        code: 'NETWORK_ERROR',
        message: 'Could not connect to the server. Please check your internet connection or backend status.',
      });
    }
  }

  throw new ApiClientError(503, {
    code: 'SERVICE_UNAVAILABLE',
    message: 'Server failed to respond after multiple attempts. Please try again.',
  });
}
