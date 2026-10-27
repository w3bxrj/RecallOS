import type { Card, JobStatus, JobResponse } from '../api/types';

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

export const INITIAL_GENERATION_STATE: GenerationState = {
  status: 'idle',
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
};

// Deduplicate cards by ID while keeping stable ordering
export function mergeCards(existing: Card[], incoming: Card[]): Card[] {
  const map = new Map<number, Card>();
  existing.forEach((c) => {
    if (c && c.id != null) map.set(c.id, c);
  });
  incoming.forEach((c) => {
    if (c && c.id != null) map.set(c.id, c);
  });
  return Array.from(map.values()).sort((a, b) => a.id - b.id);
}

// Progress calculation helper with strict finite guards and 0..100 clamping
export function calculateProgress(
  doneChunks: number,
  totalChunks: number,
  isReady: boolean
): { percent: number; chunkText: string; isValid: boolean } {
  if (isReady) {
    return { percent: 100, chunkText: 'Completed', isValid: true };
  }

  const validTotal = Number.isFinite(totalChunks) && totalChunks > 0;
  const validDone = Number.isFinite(doneChunks) && doneChunks >= 0;

  if (!validTotal || !validDone) {
    return { percent: 0, chunkText: 'Starting...', isValid: false };
  }

  const rawPercent = Math.round((doneChunks / totalChunks) * 100);
  const clampedPercent = Math.min(100, Math.max(0, rawPercent));
  const chunkText = `Chunk ${doneChunks} of ${totalChunks}`;

  return { percent: clampedPercent, chunkText, isValid: true };
}

export interface JobMessageResult {
  nextState: GenerationState;
  isTerminal: boolean;
  deckIdToHydrate: number | null;
}

// Pure handler for WebSocket messages
export function handleJobMessage(
  prevState: GenerationState,
  message: any
): JobMessageResult {
  if (!message || typeof message !== 'object') {
    return { nextState: prevState, isTerminal: prevState.status === 'ready' || prevState.status === 'failed', deckIdToHydrate: null };
  }

  const msgType = message.type;
  const data = message.data && typeof message.data === 'object' ? message.data : message;

  switch (msgType) {
    case 'snapshot': {
      // If already in terminal state, maintain idempotency without regressing
      if (prevState.status === 'ready' || prevState.status === 'failed') {
        const resolvedDeckId = data.deck_id ?? data.deckId ?? prevState.deckId;
        const nextState = resolvedDeckId !== prevState.deckId ? { ...prevState, deckId: resolvedDeckId } : prevState;
        return { nextState, isTerminal: true, deckIdToHydrate: prevState.status === 'ready' ? resolvedDeckId : null };
      }

      const statusVal = data.status || message.status;
      const isReady = statusVal === 'ready';
      const isFailed = statusVal === 'failed';

      const totalChunks = Number.isFinite(data.total_chunks) && data.total_chunks > 0
        ? Number(data.total_chunks)
        : prevState.totalChunks;

      const doneChunks = Number.isFinite(data.done_chunks) && data.done_chunks >= 0
        ? Number(data.done_chunks)
        : prevState.doneChunks;

      const cardsCreated = Number.isFinite(data.cards_created) && data.cards_created >= 0
        ? Number(data.cards_created)
        : prevState.cardsCreated;

      const deckId = data.deck_id ?? data.deckId ?? prevState.deckId ?? null;
      const isVision = Boolean(data.vision_mode ?? data.is_vision ?? message.vision_mode ?? message.is_vision ?? prevState.isVision);
      const notice = data.notice ?? message.notice ?? prevState.notice;
      const errorMessage = isFailed
        ? (data.error_message || message.error_message || prevState.errorMessage || 'Generation failed.')
        : prevState.errorMessage;

      const status: JobStatus | 'connecting' | 'idle' = isReady
        ? 'ready'
        : isFailed
        ? 'failed'
        : 'processing';

      const nextState: GenerationState = {
        ...prevState,
        status,
        totalChunks,
        doneChunks,
        cardsCreated,
        deckId,
        isVision,
        notice,
        errorMessage,
      };

      const isTerminal = isReady || isFailed;
      const deckIdToHydrate = isReady && deckId ? deckId : null;

      return { nextState, isTerminal, deckIdToHydrate };
    }

    case 'chunk_done': {
      if (prevState.status === 'ready' || prevState.status === 'failed') {
        return { nextState: prevState, isTerminal: true, deckIdToHydrate: null };
      }

      // chunk_index is optional (especially in vision mode or streaming chunks)
      let doneChunks = prevState.doneChunks;
      if (Number.isFinite(data.done_chunks) && data.done_chunks >= 0) {
        doneChunks = Number(data.done_chunks);
      } else if (Number.isFinite(data.chunk_index) && data.chunk_index >= 0) {
        doneChunks = Number(data.chunk_index) + 1;
      } else {
        doneChunks = (Number.isFinite(prevState.doneChunks) ? prevState.doneChunks : 0) + 1;
      }

      const totalChunks = Number.isFinite(data.total_chunks) && data.total_chunks > 0
        ? Number(data.total_chunks)
        : prevState.totalChunks;

      const cardsCreated = Number.isFinite(data.cards_created) && data.cards_created >= 0
        ? Number(data.cards_created)
        : prevState.cardsCreated;

      const incomingCards: Card[] = Array.isArray(data.new_cards) ? data.new_cards : [];
      const cards = incomingCards.length > 0 ? mergeCards(prevState.cards, incomingCards) : prevState.cards;

      const nextState: GenerationState = {
        ...prevState,
        status: 'processing',
        doneChunks,
        totalChunks,
        cardsCreated,
        cards,
      };

      return { nextState, isTerminal: false, deckIdToHydrate: null };
    }

    case 'chunk_failed': {
      if (prevState.status === 'ready' || prevState.status === 'failed') {
        return { nextState: prevState, isTerminal: true, deckIdToHydrate: null };
      }

      const chunkLabel = Number.isFinite(data.chunk_index)
        ? `Chunk ${Number(data.chunk_index) + 1}`
        : 'Chunk';
      const reason = data.reason || 'Skipped chunk';

      const nextState: GenerationState = {
        ...prevState,
        warnings: [...prevState.warnings, `${chunkLabel}: ${reason}`],
      };

      return { nextState, isTerminal: false, deckIdToHydrate: null };
    }

    case 'ready': {
      const deckId = data.deck_id ?? data.deckId ?? prevState.deckId ?? null;
      const cardsCreated = Number.isFinite(data.cards_created) && data.cards_created >= 0
        ? Math.max(prevState.cardsCreated, Number(data.cards_created))
        : prevState.cardsCreated;

      const nextState: GenerationState = {
        ...prevState,
        status: 'ready',
        deckId,
        cardsCreated,
      };

      return { nextState, isTerminal: true, deckIdToHydrate: deckId };
    }

    case 'failed': {
      const errorMessage = data.message || data.error_message || prevState.errorMessage || 'Generation failed.';
      const nextState: GenerationState = {
        ...prevState,
        status: 'failed',
        errorMessage,
      };

      return { nextState, isTerminal: true, deckIdToHydrate: null };
    }

    default:
      return { nextState: prevState, isTerminal: prevState.status === 'ready' || prevState.status === 'failed', deckIdToHydrate: null };
  }
}

// Pure handler for HTTP polling updates
export function handlePollUpdate(
  prevState: GenerationState,
  job: Partial<JobResponse> | null | undefined
): JobMessageResult {
  if (!job) {
    return { nextState: prevState, isTerminal: prevState.status === 'ready' || prevState.status === 'failed', deckIdToHydrate: null };
  }

  // Idempotency: do not regress terminal status
  if (prevState.status === 'ready' || prevState.status === 'failed') {
    const resolvedDeckId = job.deck_id ?? prevState.deckId;
    const nextState = resolvedDeckId !== prevState.deckId ? { ...prevState, deckId: resolvedDeckId } : prevState;
    return { nextState, isTerminal: true, deckIdToHydrate: prevState.status === 'ready' ? resolvedDeckId : null };
  }

  const isReady = job.status === 'ready';
  const isFailed = job.status === 'failed';

  const totalChunks = Number.isFinite(job.total_chunks) && (job.total_chunks as number) > 0
    ? Math.max(prevState.totalChunks, Number(job.total_chunks))
    : prevState.totalChunks;

  const doneChunks = Number.isFinite(job.done_chunks) && (job.done_chunks as number) >= 0
    ? Math.max(prevState.doneChunks, Number(job.done_chunks))
    : prevState.doneChunks;

  const cardsCreated = Number.isFinite(job.cards_created) && (job.cards_created as number) >= 0
    ? Math.max(prevState.cardsCreated, Number(job.cards_created))
    : prevState.cardsCreated;

  const deckId = job.deck_id ?? prevState.deckId ?? null;
  const isVision = Boolean(job.vision_mode ?? job.is_vision ?? prevState.isVision);
  const notice = job.notice ?? prevState.notice;
  const errorMessage = isFailed
    ? (job.error_message || prevState.errorMessage || 'Document generation failed.')
    : prevState.errorMessage;

  const status: JobStatus | 'connecting' | 'idle' = isReady
    ? 'ready'
    : isFailed
    ? 'failed'
    : prevState.status === 'idle' || prevState.status === 'connecting'
    ? 'processing'
    : prevState.status;

  const nextState: GenerationState = {
    ...prevState,
    status,
    totalChunks,
    doneChunks,
    cardsCreated,
    deckId,
    isVision,
    notice,
    errorMessage,
  };

  const isTerminal = isReady || isFailed;
  const deckIdToHydrate = isReady && deckId ? deckId : null;

  return { nextState, isTerminal, deckIdToHydrate };
}
