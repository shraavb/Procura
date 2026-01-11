"""
Embedding service for vector generation.
"""
import logging
from functools import lru_cache

from openai import OpenAI

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """Service for generating text embeddings using OpenAI."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    def create_embedding(self, text: str) -> list[float]:
        """
        Create an embedding vector for the given text.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Cannot create embedding for empty text")

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text.strip(),
                dimensions=self.dimensions,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to create embedding: {e}")
            raise

    def create_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Create embeddings for multiple texts in a single API call.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter out empty texts
        valid_texts = [t.strip() for t in texts if t and t.strip()]

        if not valid_texts:
            return []

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=valid_texts,
                dimensions=self.dimensions,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Failed to create batch embeddings: {e}")
            raise


# Singleton instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
