import { useState, useEffect, useRef, useCallback } from 'react';
import { appConfig } from '../api/config';
import { TOKEN_STORAGE_KEY } from '../api/client';
import { apiGetJobStatus } from '../api/upload';
import { apiGetDeckCards } from '../api/decks';
import type { Card, JobStatus } from '../api/types';

export interface GenerationState {
  status: JobStatus | 'connecting' | 'idle';
  totalChunks: number;
  doneChunks: number;
  cardsCreated: number;
  deckId: number | null;
  cards: Card[];
  warnings: string[];
  errorMessage: string | null;
  notice: string | null;
  isVision: boolean;
  isPollingFallback: boolean;
}

export function useGenerationJob(jobId: number | null) {
  const [state, setState] = useState<GenerationState>({
    status: jobId ? 'connecting' : 'idle',
    totalChunks: 0,
    doneChunks: 0,
    cardsCreated: 0,
    deckId: null,
    cards: [],
    warnings: [],
    errorMessage: null,
    notice: null,
    isVision: false,
    isPollingFallback: false,
  });

  const stateRef = useRef(state);
  stateRef.current = state;

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isTerminalRef = useRef(false);

  // Helper to deduplicate cards by ID
  const mergeCards = useCallback((existing: Card[], incoming: Card[]): Card[] => {
    const map = new Map<number, Card>();
    existing.forEach((c) => map.set(c.id, c));
    incoming.forEach((c) => map.set(c.id, c));
    return Array.from(map.values()).sort((a, b) => a.id - b.id);
  }, []);

  // Hydrate full card list from REST once deck is ready
  const hydrateCards = useCallback(async (deckId: number) => {
    try {
      const fullCards = await apiGetDeckCards(deckId);
      setState((prev) => ({
        ...prev,
        cards: mergeCards(prev.cards, fullCards),
        cardsCreated: fullCards.length,
      }));
    } catch {
      // Non-fatal if live cards are already present
    }
  }, [mergeCards]);

  // Terminal state setter (rule a & b: never regress, idempotent)
  const setTerminalState = useCallback(
    (status: 'ready' | 'failed', deckId?: number | null, errorMsg?: string | null) => {
      isTerminalRef.current = true;

      // Stop all timers and socket
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.close(1000);
        socketRef.current = null;
      }

      setState((prev) => {
        const resolvedDeckId = deckId ?? prev.deckId;
        return {
          ...prev,
          status,
          deckId: resolvedDeckId,
          errorMessage: errorMsg ?? prev.errorMessage,
        };
      });

      if (status === 'ready' && deckId) {
        hydrateCards(deckId);
      }
    },
    [hydrateCards]
  );

  // Fallback Polling every 3s
  const startPolling = useCallback(() => {
    if (pollTimerRef.current || isTerminalRef.current || !jobId) return;

    setState((prev) => ({ ...prev, isPollingFallback: true }));

    const runPoll = async () => {
      if (isTerminalRef.current || !jobId) return;
      try {
        const job = await apiGetJobStatus(jobId);

        // Snapshot update (rule a: do not regress)
        if (isTerminalRef.current) return;

        setState((prev) => ({
          ...prev,
          totalChunks: Math.max(prev.totalChunks, job.total_chunks),
          doneChunks: Math.max(prev.doneChunks, job.done_chunks),
          cardsCreated: Math.max(prev.cardsCreated, job.cards_created),
          deckId: job.deck_id,
          notice: job.notice ?? prev.notice,
          isVision: Boolean(job.vision_mode ?? job.is_vision ?? prev.isVision),
        }));

        if (job.status === 'ready') {
          setTerminalState('ready', job.deck_id);
        } else if (job.status === 'failed') {
          setTerminalState('failed', job.deck_id, job.error_message || 'Document generation failed.');
        }
      } catch {
        // Continue polling
      }
    };

    runPoll();
    pollTimerRef.current = setInterval(runPoll, 3000);
  }, [jobId, setTerminalState]);

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

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          switch (msg.type) {
            case 'snapshot': {
              // Rule a: ignore snapshot if terminal event received
              if (isTerminalRef.current) return;
              const snapData = msg.data || msg;
              const isVision = Boolean(snapData.vision_mode ?? snapData.is_vision ?? msg.vision_mode ?? msg.is_vision);
              const notice = snapData.notice ?? msg.notice;
              const statusVal = snapData.status || msg.status;

              setState((prev) => ({
                ...prev,
                status: statusVal === 'ready' || statusVal === 'failed' ? statusVal : 'processing',
                totalChunks: snapData.total_chunks || prev.totalChunks,
                doneChunks: snapData.done_chunks || prev.doneChunks,
                cardsCreated: snapData.cards_created || prev.cardsCreated,
                notice: notice ?? prev.notice,
                isVision: isVision || prev.isVision,
              }));

              if (statusVal === 'ready') {
                setTerminalState('ready');
              } else if (statusVal === 'failed') {
                setTerminalState('failed', null, snapData.error_message || msg.error_message || 'Generation failed');
              }
              break;
            }

            case 'chunk_done':
              if (isTerminalRef.current) return;
              setState((prev) => ({
                ...prev,
                status: 'processing',
                doneChunks: msg.chunk_index + 1,
                totalChunks: msg.total_chunks || prev.totalChunks,
                cardsCreated: msg.cards_created,
                cards: msg.new_cards?.length ? mergeCards(prev.cards, msg.new_cards) : prev.cards,
              }));
              break;

            case 'chunk_failed':
              if (isTerminalRef.current) return;
              setState((prev) => ({
                ...prev,
                warnings: [...prev.warnings, `Chunk ${msg.chunk_index + 1}: ${msg.reason || 'Skipped chunk'}`],
              }));
              break;

            case 'ready':
              // Rule b: terminal events can arrive twice; make harmless
              setTerminalState('ready', msg.deck_id);
              break;

            case 'failed':
              setTerminalState('failed', null, msg.message || 'Generation failed.');
              break;
          }
        } catch {
          // JSON parse error on malformed message
        }
      };

      ws.onclose = (event) => {
        if (isTerminalRef.current) return;

        // Requirement 2: do NOT reconnect on close codes 4401, 4403, 4404
        if (event.code === 4401) {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
          window.location.href = '/login?expired=1';
          return;
        }

        if (event.code === 4403) {
          setTerminalState('failed', null, 'Connection rejected: Invalid origin (4403).');
          return;
        }

        if (event.code === 4404) {
          setTerminalState('failed', null, 'Generation job not found or unauthorized (4404).');
          return;
        }

        // Other close codes: start polling fallback immediately and reconnect with backoff
        startPolling();

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
        // Trigger polling fallback on socket error
        startPolling();
      };
    } catch {
      startPolling();
    }
  }, [jobId, mergeCards, setTerminalState, startPolling]);

  // Lifecycle
  useEffect(() => {
    isTerminalRef.current = false;
    reconnectAttemptsRef.current = 0;

    if (jobId) {
      connectWs();
    }

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      if (socketRef.current) {
        socketRef.current.close(1000);
        socketRef.current = null;
      }
    };
  }, [jobId, connectWs]);

  return state;
}
