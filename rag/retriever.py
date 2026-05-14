"""
ChromaDB-backed retriever for FinBot's personal-finance knowledge base.

Responsibilities:
  1. Manage a persistent ChromaDB collection of document chunks.
  2. Accept a natural-language query and return the most relevant chunks.
  3. Provide helpers for ingestion (add/reset) used by ``rag.ingest``.
"""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from rag.embeddings import EmbeddingModel, get_embedding_model

# ── defaults ────────────────────────────────────────────────────
CHROMA_DIR = os.getenv(
    "FINBOT_CHROMA_DIR",
    str(Path(__file__).resolve().parent.parent / "chroma_db"),
)
COLLECTION_NAME = os.getenv("FINBOT_CHROMA_COLLECTION", "finance_knowledge")
DEFAULT_TOP_K = 4


class FinanceRetriever:
    """
    Retrieve relevant personal-finance knowledge chunks for a user query.

    Parameters
    ----------
    persist_dir : str
        Path to the ChromaDB persistent storage directory.
    collection_name : str
        Name of the ChromaDB collection.
    embedding_model : EmbeddingModel | None
        Shared embedding model instance. If *None*, the module-level
        singleton from ``rag.embeddings`` is used.
    """

    def __init__(
        self,
        persist_dir: str = CHROMA_DIR,
        collection_name: str = COLLECTION_NAME,
        embedding_model: EmbeddingModel | None = None,
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedder = embedding_model or get_embedding_model()

        # Persistent ChromaDB client — data survives restarts
        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── retrieval ───────────────────────────────────────────────
    def query(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = 0.25,
    ) -> list[dict]:
        """
        Return the top-k most relevant chunks for *query_text*.

        Parameters
        ----------
        query_text : str
            The user's question or topic.
        top_k : int
            Maximum number of results to return.
        min_score : float
            Minimum similarity score (0–1). Chunks below this threshold
            are discarded so the LLM does not receive low-quality context.

        Returns
        -------
        list[dict]
            Each dict has keys: ``text``, ``source``, ``score``.
            Sorted by descending relevance.
        """
        if self._collection.count() == 0:
            return []

        query_embedding = self.embedder.embed_query(query_text)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[dict] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score: 1 - (distance / 2)
            score = 1.0 - (dist / 2.0)
            if score >= min_score:
                chunks.append({
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "score": round(score, 4),
                })

        return chunks

    def format_context(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> str:
        """
        Retrieve chunks and format them into a single context string
        ready to inject into the LLM prompt.

        Returns an empty string if no relevant chunks are found.
        """
        chunks = self.query(query_text, top_k=top_k)
        if not chunks:
            return ""

        parts = ["RELEVANT FINANCIAL KNOWLEDGE:"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"\n--- Source: {chunk['source']} "
                f"(relevance: {chunk['score']:.0%}) ---\n"
                f"{chunk['text']}"
            )
        parts.append(
            "\nUse the knowledge above to give accurate, helpful advice. "
            "If the user's question is not covered, rely on your general knowledge."
        )
        return "\n".join(parts)

    # ── ingestion helpers ───────────────────────────────────────
    def add_chunks(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> int:
        """
        Add document chunks to the collection.

        Parameters
        ----------
        ids : list[str]
            Unique ID for each chunk (e.g. ``"budgeting_basics_chunk_0"``).
        documents : list[str]
            The text content of each chunk.
        metadatas : list[dict]
            Metadata dict per chunk (must include ``"source"``).

        Returns
        -------
        int
            Number of chunks added.
        """
        if not documents:
            return 0

        embeddings = self.embedder.embed_texts(documents)

        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(documents)

    def reset_collection(self):
        """Delete and re-create the collection (used during re-ingestion)."""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def chunk_count(self) -> int:
        """Return the number of chunks currently stored."""
        return self._collection.count()

    @property
    def is_empty(self) -> bool:
        """True if the collection has no chunks."""
        return self._collection.count() == 0
