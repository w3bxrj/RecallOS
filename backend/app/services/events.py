from typing import Protocol, List, Dict, Any


class JobEventPublisher(Protocol):
    """Event publisher protocol for generation pipeline lifecycle events."""

    def chunk_done(
        self,
        job_id: int,
        chunk_index: int,
        total_chunks: int,
        new_cards: List[Dict[str, Any]],
        cards_created: int,
    ) -> None:
        """Invoked when a chunk finishes processing and cards are created."""
        ...

    def chunk_failed(
        self,
        job_id: int,
        chunk_index: int,
        reason: str,
    ) -> None:
        """Invoked when a chunk fails to produce valid cards or encounters an error."""
        ...

    def ready(
        self,
        job_id: int,
        deck_id: int,
        cards_created: int,
    ) -> None:
        """Invoked when the generation job finishes successfully with at least 1 card."""
        ...

    def failed(
        self,
        job_id: int,
        message: str,
    ) -> None:
        """Invoked when the generation job fails completely with zero cards."""
        ...


class NullJobEventPublisher:
    """Default no-op implementation of JobEventPublisher for Phase 3."""

    def chunk_done(
        self,
        job_id: int,
        chunk_index: int,
        total_chunks: int,
        new_cards: List[Dict[str, Any]],
        cards_created: int,
    ) -> None:
        pass

    def chunk_failed(
        self,
        job_id: int,
        chunk_index: int,
        reason: str,
    ) -> None:
        pass

    def ready(
        self,
        job_id: int,
        deck_id: int,
        cards_created: int,
    ) -> None:
        pass

    def failed(
        self,
        job_id: int,
        message: str,
    ) -> None:
        pass


default_event_publisher: JobEventPublisher = NullJobEventPublisher()
