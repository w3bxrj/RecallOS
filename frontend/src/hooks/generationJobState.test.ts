import { describe, it, expect } from 'vitest';
import {
  INITIAL_GENERATION_STATE,
  handleJobMessage,
  handlePollUpdate,
  calculateProgress,
  mergeCards,
  type GenerationState,
} from './generationJobState';
import type { Card } from '../api/types';

describe('Document Generation Message Handling and Progress State', () => {
  const baseState: GenerationState = {
    ...INITIAL_GENERATION_STATE,
    status: 'connecting',
  };

  // 1. Snapshot ready with no later event
  it('handles snapshot ready with no later event', () => {
    const snapshotMsg = {
      type: 'snapshot',
      data: {
        status: 'ready',
        deck_id: 25,
        done_chunks: 2,
        total_chunks: 2,
        cards_created: 8,
        error_message: null,
        notice: null,
        is_vision: false,
        vision_mode: false,
      },
    };

    const { nextState, isTerminal, deckIdToHydrate } = handleJobMessage(baseState, snapshotMsg);

    expect(nextState.status).toBe('ready');
    expect(nextState.deckId).toBe(25);
    expect(nextState.cardsCreated).toBe(8);
    expect(nextState.doneChunks).toBe(2);
    expect(nextState.totalChunks).toBe(2);
    expect(isTerminal).toBe(true);
    expect(deckIdToHydrate).toBe(25);

    const progress = calculateProgress(nextState.doneChunks, nextState.totalChunks, true);
    expect(progress.percent).toBe(100);
    expect(progress.chunkText).toBe('Completed');
    expect(progress.isValid).toBe(true);
  });

  // 2. Snapshot then ready (duplicate terminal event)
  it('handles snapshot then ready (duplicate terminal) idempotently', () => {
    // First: snapshot indicates ready
    const snapshotMsg = {
      type: 'snapshot',
      data: {
        status: 'ready',
        deck_id: 25,
        done_chunks: 2,
        total_chunks: 2,
        cards_created: 8,
      },
    };
    const step1 = handleJobMessage(baseState, snapshotMsg);
    expect(step1.nextState.status).toBe('ready');
    expect(step1.nextState.deckId).toBe(25);
    expect(step1.isTerminal).toBe(true);

    // Second: separate terminal event arrives with ready
    const readyMsg = {
      type: 'ready',
      data: {
        deck_id: 25,
        cards_created: 8,
      },
    };
    const step2 = handleJobMessage(step1.nextState, readyMsg);

    expect(step2.nextState.status).toBe('ready');
    expect(step2.nextState.deckId).toBe(25);
    expect(step2.nextState.cardsCreated).toBe(8);
    expect(step2.isTerminal).toBe(true);
    expect(step2.deckIdToHydrate).toBe(25);
  });

  // 3. Chunk_done in vision mode with missing chunk_index
  it('handles chunk_done in vision mode with missing chunk_index without producing NaN', () => {
    const processingState: GenerationState = {
      ...baseState,
      status: 'processing',
      totalChunks: 4,
      doneChunks: 0,
      isVision: true,
    };

    // chunk_done arrives with chunk_index missing (undefined), but total_chunks and new_cards provided
    const chunkDoneMsg = {
      type: 'chunk_done',
      data: {
        // chunk_index is omitted
        total_chunks: 4,
        cards_created: 3,
        new_cards: [
          { id: 1, deck_id: 10, topic: 'Biology', question: 'Q1', answer: 'A1', created_at: '' },
          { id: 2, deck_id: 10, topic: 'Biology', question: 'Q2', answer: 'A2', created_at: '' },
        ],
      },
    };

    const { nextState, isTerminal } = handleJobMessage(processingState, chunkDoneMsg);

    expect(isTerminal).toBe(false);
    expect(Number.isFinite(nextState.doneChunks)).toBe(true);
    expect(isNaN(nextState.doneChunks)).toBe(false);
    expect(nextState.doneChunks).toBe(1); // Safely defaulted from prev 0 + 1
    expect(nextState.totalChunks).toBe(4);
    expect(nextState.cardsCreated).toBe(3);
    expect(nextState.cards.length).toBe(2);

    const progress = calculateProgress(nextState.doneChunks, nextState.totalChunks, false);
    expect(progress.isValid).toBe(true);
    expect(progress.chunkText).toBe('Chunk 1 of 4');
    expect(progress.percent).toBe(25);
    expect(isNaN(progress.percent)).toBe(false);
  });

  // 4. Snapshot with null or missing numbers
  it('handles snapshot with null or missing numbers and shows Starting...', () => {
    const nullNumbersMsg = {
      type: 'snapshot',
      data: {
        status: 'queued',
        done_chunks: null,
        total_chunks: null,
        cards_created: null,
        deck_id: null,
      },
    };

    const { nextState, isTerminal } = handleJobMessage(baseState, nullNumbersMsg);

    expect(isTerminal).toBe(false);
    expect(Number.isFinite(nextState.doneChunks)).toBe(true);
    expect(Number.isFinite(nextState.totalChunks)).toBe(true);
    expect(Number.isFinite(nextState.cardsCreated)).toBe(true);
    expect(nextState.doneChunks).toBe(0);
    expect(nextState.totalChunks).toBe(0);
    expect(nextState.cardsCreated).toBe(0);

    const progress = calculateProgress(nextState.doneChunks, nextState.totalChunks, false);
    expect(progress.isValid).toBe(false);
    expect(progress.chunkText).toBe('Starting...');
    expect(progress.percent).toBe(0);
    expect(progress.percent).toBeGreaterThanOrEqual(0);
    expect(progress.percent).toBeLessThanOrEqual(100);
    expect(isNaN(progress.percent)).toBe(false);
  });

  // 5. Polling returns ready while no socket event arrived
  it('handles polling returning ready while no socket event arrived', () => {
    const polledJob = {
      id: 99,
      deck_id: 42,
      status: 'ready' as const,
      total_chunks: 3,
      done_chunks: 3,
      cards_created: 12,
      is_vision: false,
      vision_mode: false,
      notice: null,
      error_message: null,
      created_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    };

    const { nextState, isTerminal, deckIdToHydrate } = handlePollUpdate(baseState, polledJob);

    expect(nextState.status).toBe('ready');
    expect(nextState.deckId).toBe(42);
    expect(nextState.cardsCreated).toBe(12);
    expect(nextState.doneChunks).toBe(3);
    expect(nextState.totalChunks).toBe(3);
    expect(isTerminal).toBe(true);
    expect(deckIdToHydrate).toBe(42);

    const progress = calculateProgress(nextState.doneChunks, nextState.totalChunks, true);
    expect(progress.percent).toBe(100);
    expect(progress.isValid).toBe(true);
  });

  // Extra verification: card deduplication and progress clamping
  it('deduplicates cards properly and clamps progress strictly between 0 and 100', () => {
    const existing: Card[] = [
      { id: 1, deck_id: 5, topic: 'OS', question: 'Q1', answer: 'A1', created_at: '' },
    ];
    const incoming: Card[] = [
      { id: 1, deck_id: 5, topic: 'OS', question: 'Q1 updated', answer: 'A1', created_at: '' },
      { id: 2, deck_id: 5, topic: 'OS', question: 'Q2', answer: 'A2', created_at: '' },
    ];
    const merged = mergeCards(existing, incoming);
    expect(merged.length).toBe(2);
    expect(merged[0].id).toBe(1);
    expect(merged[0].question).toBe('Q1 updated');

    // Clamping over 100% or under 0%
    const over100 = calculateProgress(10, 5, false);
    expect(over100.percent).toBe(100);
    expect(over100.chunkText).toBe('Chunk 10 of 5');

    const negative = calculateProgress(-1, 5, false);
    expect(negative.isValid).toBe(false);
    expect(negative.chunkText).toBe('Starting...');
    expect(negative.percent).toBe(0);
  });
});
