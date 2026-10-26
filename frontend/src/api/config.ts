// Config for API and WebSocket URLs

const rawApiUrl = import.meta.env.VITE_API_URL?.trim();
const rawWsUrl = import.meta.env.VITE_WS_URL?.trim();

export interface ConfigStatus {
  isValid: boolean;
  errorMessage?: string;
  apiUrl: string;
  wsUrl: string;
}

export function getAppConfig(): ConfigStatus {
  const isProd = import.meta.env.PROD;

  if (isProd) {
    if (!rawApiUrl || !rawWsUrl) {
      return {
        isValid: false,
        errorMessage: 'Missing environment configuration: VITE_API_URL and VITE_WS_URL must be set in production.',
        apiUrl: '',
        wsUrl: '',
      };
    }

    if (!rawApiUrl.startsWith('https://')) {
      return {
        isValid: false,
        errorMessage: `VITE_API_URL must use HTTPS protocol in production. Received: ${rawApiUrl}`,
        apiUrl: '',
        wsUrl: '',
      };
    }

    if (!rawWsUrl.startsWith('wss://')) {
      return {
        isValid: false,
        errorMessage: `VITE_WS_URL must use WSS protocol in production. Received: ${rawWsUrl}`,
        apiUrl: '',
        wsUrl: '',
      };
    }

    return {
      isValid: true,
      apiUrl: rawApiUrl.replace(/\/+$/, ''),
      wsUrl: rawWsUrl.replace(/\/+$/, ''),
    };
  }

  // Development environment
  return {
    isValid: true,
    apiUrl: (rawApiUrl || 'http://localhost:8000').replace(/\/+$/, ''),
    wsUrl: (rawWsUrl || 'ws://localhost:8000').replace(/\/+$/, ''),
  };
}

export const appConfig = getAppConfig();
