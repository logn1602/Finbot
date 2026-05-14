"""
Embedding model wrapper for FinBot RAG pipeline.

Uses sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2:
  - 384-dimensional embeddings
  - Multilingual (50+ languages)
  - CPU-friendly (~120 MB model)
  - Zero cost (runs locally)
"""

from __future__ import annotations

import os
from functools import lru_cache
from sentence_transformers import SentenceTransformer

# ── defaults ────────────────────────────────────────────────────
MODEL_NAME = os.getenv(
    "FINBOT_EMBED_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
EMBEDDING_DIM = 384          # output dimension for this model


class EmbeddingModel:
    """Singleton-friendly wrapper around a SentenceTransformer model."""

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    # ── lazy load ───────────────────────────────────────────────
    @property
    def model(self) -> SentenceTransformer:
        """Load the model on first access (avoids startup cost if RAG unused)."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    # ── public API ──────────────────────────────────────────────
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Encode a list of texts into embedding vectors.

        Parameters
        ----------
        texts : list[str]
            Plain-text strings to embed.

        Returns
        -------
        list[list[float]]
            One embedding vector (length ``EMBEDDING_DIM``) per input text.
        """
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,   # unit-length → cosine = dot product
        )
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        """
        Encode a single query string.

        Convenience wrapper that returns a flat list instead of a nested one.
        """
        return self.embed_texts([query])[0]

    @property
    def dimension(self) -> int:
        """Return the embedding dimensionality."""
        return EMBEDDING_DIM


# ── module-level singleton ──────────────────────────────────────
@lru_cache(maxsize=1)
def get_embedding_model() -> EmbeddingModel:
    """Return a cached, shared EmbeddingModel instance."""
    return EmbeddingModel()
