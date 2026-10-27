import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Layers,
  Trash2,
  Eye,
  Calendar,
  FileText,
  AlertCircle,
  UploadCloud,
  RotateCcw,
} from 'lucide-react';
import { m } from 'motion/react';
import { apiListDecks, apiGetDeckCards, apiDeleteDeck } from '../api/decks';
import type { Card, DeckListItem } from '../api/types';
import { useToast } from '../context/ToastContext';
import { Skeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ConfirmModal } from '../components/common/ConfirmModal';
import { Modal } from '../components/ui/Modal';
import { Spinner } from '../components/common/Spinner';
import { Button } from '../components/ui/Button';

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
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-txt-primary">
            Flashcard Decks
          </h1>
          <p className="text-sm text-txt-muted mt-1">
            Browse your study collections, review cards, or generate new ones from documents.
          </p>
        </div>
        <Link
          to="/upload"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand hover:bg-brand-hover text-white font-semibold text-sm shadow-sm transition-colors shrink-0"
        >
          <UploadCloud className="w-4 h-4" />
          <span>Upload Document</span>
        </Link>
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-surface rounded-2xl p-6 border border-border-subtle shadow-card space-y-4"
            >
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-8 w-full mt-4 rounded-xl" />
            </div>
          ))}
        </div>
      )}

      {/* Error State */}
      {!isLoading && error && (
        <div className="bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 rounded-3xl p-8 text-center max-w-md mx-auto space-y-4 shadow-card">
          <AlertCircle className="w-8 h-8 text-rose-600 dark:text-rose-400 mx-auto" />
          <p className="text-sm font-semibold text-rose-900 dark:text-rose-200">{error}</p>
          <Button
            type="button"
            variant="danger"
            onClick={fetchDecks}
            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && decks.length === 0 && (
        <EmptyState
          icon={Layers}
          title="No decks found"
          description="Upload your lecture notes or textbooks to automatically generate spaced repetition flashcards."
          actionText="Upload Notes"
          actionHref="/upload"
        />
      )}

      {/* Decks Grid with Hover Lift */}
      {!isLoading && !error && decks.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {decks.map((deck) => (
            <m.div
              key={deck.id}
              whileHover={{ y: -3, transition: { duration: 0.18, ease: 'easeOut' } }}
              className="bg-surface rounded-2xl border border-border-subtle shadow-card hover:shadow-card-hover hover:border-brand/40 transition-all p-6 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <h3 className="text-base font-bold text-txt-primary line-clamp-2">
                    {deck.title}
                  </h3>
                  <button
                    type="button"
                    onClick={() => setDeckToDelete(deck)}
                    className="text-txt-muted hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 p-1.5 rounded-lg transition-colors shrink-0 cursor-pointer"
                    title={`Delete deck ${deck.title}`}
                    aria-label={`Delete deck ${deck.title}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="space-y-1.5 text-xs text-txt-muted mb-6">
                  <div className="flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-txt-muted shrink-0" />
                    <span className="truncate">{deck.source_filename}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-txt-muted shrink-0" />
                    <span>
                      {new Date(deck.created_at).toLocaleDateString(undefined, {
                        dateStyle: 'medium',
                      })}
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-border-subtle flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/50 text-brand border border-indigo-100/60 dark:border-indigo-900/60 tabular-nums">
                  {deck.card_count} {deck.card_count === 1 ? 'card' : 'cards'}
                </span>

                <button
                  type="button"
                  onClick={() => handleViewCards(deck)}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-brand hover:underline transition-colors cursor-pointer"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>View Cards</span>
                </button>
              </div>
            </m.div>
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
      <Modal
        isOpen={Boolean(activeDeck)}
        onClose={() => setActiveDeck(null)}
        title={activeDeck?.title || 'Deck Cards'}
        description={`${deckCards.length} ${deckCards.length === 1 ? 'card' : 'cards'} in this collection`}
        maxWidth="lg"
      >
        <div className="max-h-[60vh] overflow-y-auto space-y-3 pr-1">
          {isLoadingCards ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3">
              <Spinner size="md" />
              <p className="text-xs text-txt-muted">Loading cards...</p>
            </div>
          ) : deckCards.length === 0 ? (
            <p className="text-center py-12 text-txt-muted text-sm">
              No cards found in this deck.
            </p>
          ) : (
            deckCards.map((card, idx) => (
              <div
                key={card.id}
                className="p-4 rounded-2xl border border-border-subtle bg-surface-muted space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/50 text-brand border border-indigo-100/60 dark:border-indigo-900/60">
                    {card.topic}
                  </span>
                  <span className="text-xs text-txt-muted font-mono tabular-nums">
                    #{idx + 1}
                  </span>
                </div>
                <p className="text-sm font-semibold text-txt-primary">
                  {card.question}
                </p>
                <div className="p-3 rounded-xl bg-surface border border-border-subtle text-xs text-txt-secondary leading-relaxed">
                  <span className="font-semibold text-txt-primary">Answer: </span>
                  {card.answer}
                </div>
              </div>
            ))
          )}
        </div>
        <div className="pt-4 mt-2 border-t border-border-subtle flex justify-end">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setActiveDeck(null)}
          >
            Close
          </Button>
        </div>
      </Modal>
    </div>
  );
};
