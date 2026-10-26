import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Layers,
  Trash2,
  Eye,
  Calendar,
  FileText,
  AlertCircle,
  X,
  UploadCloud,
  RotateCcw,
} from 'lucide-react';
import { apiListDecks, apiGetDeckCards, apiDeleteDeck } from '../api/decks';
import type { Card, DeckListItem } from '../api/types';
import { useToast } from '../context/ToastContext';
import { Skeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ConfirmModal } from '../components/common/ConfirmModal';
import { Spinner } from '../components/common/Spinner';

export const DecksPage: React.FC = () => {
  const toast = useToast();

  const [decks, setDecks] = useState<DeckListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Card viewing modal state
  const [activeDeck, setActiveDeck] = useState<DeckListItem | null>(null);
  const [deckCards, setDeckCards] = useState<Card[]>([]);
  const [isLoadingCards, setIsLoadingCards] = useState(false);

  // Deletion modal state
  const [deckToDelete, setDeckToDelete] = useState<DeckListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchDecks = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiListDecks();
      setDecks(data);
    } catch {
      setError('Failed to load decks. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDecks();
  }, [fetchDecks]);

  const handleViewCards = async (deck: DeckListItem) => {
    setActiveDeck(deck);
    setIsLoadingCards(true);
    try {
      const cards = await apiGetDeckCards(deck.id);
      setDeckCards(cards);
    } catch {
      toast.error('Failed to load cards for this deck.');
      setActiveDeck(null);
    } finally {
      setIsLoadingCards(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deckToDelete) return;
    setIsDeleting(true);
    try {
      await apiDeleteDeck(deckToDelete.id);
      setDecks((prev) => prev.filter((d) => d.id !== deckToDelete.id));
      toast.success(`Deleted deck "${deckToDelete.title}"`);
      setDeckToDelete(null);
    } catch {
      toast.error('Failed to delete deck. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Flashcard Decks
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Browse your study collections, review cards, or generate new ones from documents.
          </p>
        </div>
        <Link
          to="/upload"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm shadow-sm transition-colors shrink-0"
        >
          <UploadCloud className="w-4 h-4" />
          <span>Upload Document</span>
        </Link>
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-xs space-y-4">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-8 w-full mt-4" />
            </div>
          ))}
        </div>
      )}

      {/* Error State */}
      {!isLoading && error && (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center max-w-md mx-auto space-y-3">
          <AlertCircle className="w-8 h-8 text-rose-600 mx-auto" />
          <p className="text-sm font-semibold text-rose-900">{error}</p>
          <button
            onClick={fetchDecks}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && decks.length === 0 && (
        <EmptyState
          icon={Layers}
          title="No decks found"
          description="Upload your first lecture notes or textbook to automatically generate spaced repetition flashcards."
          actionText="Upload Notes"
          actionHref="/upload"
        />
      )}

      {/* Decks Grid */}
      {!isLoading && !error && decks.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {decks.map((deck) => (
            <div
              key={deck.id}
              className="bg-white rounded-2xl border border-slate-200/90 shadow-xs hover:shadow-md transition-all duration-200 p-6 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <h3 className="text-base font-bold text-slate-900 line-clamp-2">
                    {deck.title}
                  </h3>
                  <button
                    onClick={() => setDeckToDelete(deck)}
                    className="text-slate-400 hover:text-rose-600 p-1 rounded-lg transition-colors shrink-0"
                    title="Delete deck"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="space-y-1.5 text-xs text-slate-500 mb-6">
                  <div className="flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span className="truncate">{deck.source_filename}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span>
                      {new Date(deck.created_at).toLocaleDateString(undefined, {
                        dateStyle: 'medium',
                      })}
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100">
                  {deck.card_count} {deck.card_count === 1 ? 'card' : 'cards'}
                </span>

                <button
                  onClick={() => handleViewCards(deck)}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-700 transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>View Cards</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={Boolean(deckToDelete)}
        title="Delete Deck?"
        message={`Are you sure you want to delete "${deckToDelete?.title}"? All associated cards, review histories, and states will be permanently deleted.`}
        confirmText="Delete"
        isDestructive
        isLoading={isDeleting}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeckToDelete(null)}
      />

      {/* Cards Viewing Modal */}
      {activeDeck && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl border border-slate-100 animate-scale-up">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  {activeDeck.title}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {deckCards.length} {deckCards.length === 1 ? 'card' : 'cards'} in this collection
                </p>
              </div>
              <button
                onClick={() => setActiveDeck(null)}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-xl transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Cards Body */}
            <div className="p-6 overflow-y-auto space-y-4 flex-1">
              {isLoadingCards ? (
                <div className="py-12 flex flex-col items-center justify-center gap-3">
                  <Spinner size="md" />
                  <p className="text-xs text-slate-400">Loading cards...</p>
                </div>
              ) : deckCards.length === 0 ? (
                <p className="text-center py-12 text-slate-400 text-sm">
                  No cards found in this deck.
                </p>
              ) : (
                deckCards.map((card, idx) => (
                  <div
                    key={card.id}
                    className="p-4 rounded-2xl border border-slate-200/80 bg-slate-50/50 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100">
                        {card.topic}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">#{idx + 1}</span>
                    </div>
                    <p className="text-sm font-semibold text-slate-900">
                      {card.question}
                    </p>
                    <div className="p-2.5 rounded-xl bg-white border border-slate-200/60 text-xs text-slate-700">
                      <span className="font-semibold text-slate-900">Answer: </span>
                      {card.answer}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => setActiveDeck(null)}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
