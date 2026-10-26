// Config for API and WebSocket URLs

export interface ConfigStatus {
  isValid: boolean;
  errorMessage?: string;
  apiUrl: string;
  wsUrl: string;
}

export function getAppConfig(): ConfigStatus {
  if (import.meta.env.PROD) {
    const rawApiUrl = import.meta.env.VITE_API_URL?.trim();
    const rawWsUrl = import.meta.env.VITE_WS_URL?.trim();

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

  // Development environment only
  const devHost = 'localhost:8000';
  const devApi = import.meta.env.VITE_API_URL?.trim() || `http://${devHost}`;
  const devWs = import.meta.env.VITE_WS_URL?.trim() || `ws://${devHost}`;

  return {
    isValid: true,
    apiUrl: devApi.replace(/\/+$/, ''),
    wsUrl: devWs.replace(/\/+$/, ''),
  };
}

export const appConfig = getAppConfig();
