import { useState, useEffect, useRef, useCallback } from 'react';
import { appConfig } from '../api/config';
import { TOKEN_STORAGE_KEY } from '../api/client';
import { apiGetJobStatus } from '../api/upload';
import { apiGetDeckCards } from '../api/decks';
import {
  type GenerationState,
  INITIAL_GENERATION_STATE,
  handleJobMessage,
  handlePollUpdate,
  mergeCards,
} from './generationJobState';

export type { GenerationState } from './generationJobState';

export function useGenerationJob(jobId: number | null) {
  const [state, setState] = useState<GenerationState>({
    ...INITIAL_GENERATION_STATE,
    status: jobId ? 'connecting' : 'idle',
  });

  const stateRef = useRef(state);
  stateRef.current = state;

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isTerminalRef = useRef(false);
  const hydratedDeckIdRef = useRef<number | null>(null);

  // Stop all active network channels (WebSocket, reconnect timers, polling)
  const stopAll = useCallback(() => {
    isTerminalRef.current = true;
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (socketRef.current) {
      try {
        socketRef.current.close(1000);
      } catch {
        // Safe close
      }
      socketRef.current = null;
    }
  }, []);

  // Hydrate full card list from REST once deck is ready
  const hydrateCards = useCallback(async (deckId: number) => {
    if (hydratedDeckIdRef.current === deckId) return;
    hydratedDeckIdRef.current = deckId;
    try {
      const fullCards = await apiGetDeckCards(deckId);
      setState((prev) => ({
        ...prev,
        cards: mergeCards(prev.cards, fullCards),
        cardsCreated: Math.max(prev.cardsCreated, fullCards.length),
      }));
    } catch {
      // Non-fatal if live cards are already present
    }
  }, []);

  // Poll safety net: runs every 4 seconds while job is not terminal
  const pollJob = useCallback(async () => {
    if (isTerminalRef.current || !jobId) return;
    try {
      const job = await apiGetJobStatus(jobId);
      if (isTerminalRef.current) return;

      const { nextState, isTerminal, deckIdToHydrate } = handlePollUpdate(stateRef.current, job);
      setState(nextState);

      if (isTerminal) {
        stopAll();
        if (deckIdToHydrate) {
          hydrateCards(deckIdToHydrate);
        }
      }
    } catch {
      // Polling will retry on next tick
    }
  }, [jobId, stopAll, hydrateCards]);

  // Connect WebSocket
  const connectWs = useCallback(() => {
    if (!jobId || isTerminalRef.current) return;

    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!token) {
      window.location.href = '/login?expired=1';
      return;
    }

    const wsUrl = `${appConfig.wsUrl}/ws/generate/${jobId}?token=${encodeURIComponent(token)}`;

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setState((prev) => ({ ...prev, isPollingFallback: false }));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const { nextState, isTerminal, deckIdToHydrate } = handleJobMessage(stateRef.current, msg);
          setState(nextState);

          if (isTerminal) {
            stopAll();
            if (deckIdToHydrate) {
              hydrateCards(deckIdToHydrate);
            }
          }
        } catch {
          // JSON parse error
        }
      };

      ws.onclose = (event) => {
        if (isTerminalRef.current) return;

        setState((prev) => ({ ...prev, isPollingFallback: true }));

        if (event.code === 4401) {
          stopAll();
          localStorage.removeItem(TOKEN_STORAGE_KEY);
          window.location.href = '/login?expired=1';
          return;
        }

        if (event.code === 4403) {
          stopAll();
          setState((prev) => ({
            ...prev,
            status: 'failed',
            errorMessage: 'Connection rejected: Invalid origin (4403).',
          }));
          return;
        }

        if (event.code === 4404) {
          stopAll();
          setState((prev) => ({
            ...prev,
            status: 'failed',
            errorMessage: 'Generation job not found or unauthorized (4404).',
          }));
          return;
        }

        // Reconnect with exponential backoff (polling safety net continues running every 4s)
        if (reconnectAttemptsRef.current < 8) {
          reconnectAttemptsRef.current += 1;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current - 1), 15000);
          reconnectTimerRef.current = setTimeout(() => {
            if (!isTerminalRef.current) {
              connectWs();
            }
          }, delay);
        }
      };

      ws.onerror = () => {
        setState((prev) => ({ ...prev, isPollingFallback: true }));
      };
    } catch {
      setState((prev) => ({ ...prev, isPollingFallback: true }));
    }
  }, [jobId, stopAll, hydrateCards]);

  // Lifecycle
  useEffect(() => {
    isTerminalRef.current = false;
    hydratedDeckIdRef.current = null;
    reconnectAttemptsRef.current = 0;

    if (jobId) {
      connectWs();
      // Start 4-second safety net polling immediately
      pollJob();
      pollTimerRef.current = setInterval(pollJob, 4000);
    }

    return () => {
      stopAll();
    };
  }, [jobId, connectWs, pollJob, stopAll]);

  return state;
}
