import { apiClient } from './client';
import { Card, DeckListItem } from './types';

export async function apiListDecks(): Promise<DeckListItem[]> {
  return apiClient<DeckListItem[]>('/api/decks');
}

export async function apiGetDeckCards(deckId: number): Promise<Card[]> {
  return apiClient<Card[]>(`/api/decks/${deckId}/cards`);
}

export async function apiDeleteDeck(deckId: number): Promise<{ status: string; message: string }> {
  return apiClient<{ status: string; message: string }>(`/api/decks/${deckId}`, {
    method: 'DELETE',
  });
}
