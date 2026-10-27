from abc import ABC, abstractmethod
from typing import List, Dict, Any


class LLMClient(ABC):
    """Abstract base interface for LLM card generation clients."""

    @abstractmethod
    def generate_cards(self, chunk_text: str) -> List[Dict[str, Any]]:
        """Extracts flashcards from a chunk of study text.

        Returns a list of raw card dictionaries:
        [{'topic': str, 'question': str, 'answer': str, 'distractors': [str, str, str]}]
        """
        pass

    def generate_cards_from_pdf(
        self, pdf_bytes: bytes, page_range_label: str
    ) -> List[Dict[str, Any]]:
        """Extracts flashcards from a sub-PDF chunk of scanned study pages.

        Returns a list of raw card dictionaries, or an empty list if no study content.
        """
        return []
