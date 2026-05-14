"""
Unit tests for the FinBot RAG pipeline.

Covers:
  - EmbeddingModel: dimensionality, normalization, determinism, empty input
  - FinanceRetriever: add/query/reset lifecycle, min_score filtering,
    empty collection, format_context output
  - Ingestion: chunking logic, full ingest cycle, idempotent skip

All tests use a temporary ChromaDB directory so they never touch the
production collection.

Run:
    python -m pytest tests/test_rag.py -v
"""

import json
import math
import shutil
import tempfile
from pathlib import Path

import pytest

from rag.embeddings import EmbeddingModel, get_embedding_model, EMBEDDING_DIM
from rag.retriever import FinanceRetriever
from rag.ingest import _chunk_text, _split_into_sections, ingest_knowledge_base


# ════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def embed_model():
    """Shared embedding model for the entire test module (slow to load)."""
    return EmbeddingModel()


@pytest.fixture()
def tmp_chroma(tmp_path):
    """Provide a fresh temporary ChromaDB directory per test."""
    chroma_dir = tmp_path / "chroma_test"
    chroma_dir.mkdir()
    yield str(chroma_dir)


@pytest.fixture()
def retriever(tmp_chroma, embed_model):
    """Retriever backed by a temporary ChromaDB collection."""
    return FinanceRetriever(
        persist_dir=tmp_chroma,
        collection_name="test_collection",
        embedding_model=embed_model,
    )


@pytest.fixture()
def tmp_knowledge(tmp_path):
    """Create a small temporary knowledge directory with two markdown files."""
    kdir = tmp_path / "knowledge"
    kdir.mkdir()

    (kdir / "topic_a.md").write_text(
        "# Topic A Title\n\n"
        "## Section One\n\n"
        "This is the first section about saving money. "
        "Emergency funds are important for financial security.\n\n"
        "## Section Two\n\n"
        "This section covers budgeting basics and the 50/30/20 rule. "
        "Needs, wants, and savings should be balanced carefully.\n",
        encoding="utf-8",
    )

    (kdir / "topic_b.md").write_text(
        "# Topic B Title\n\n"
        "## Investing\n\n"
        "Index funds offer broad diversification at low cost. "
        "Dollar-cost averaging removes emotion from investing.\n\n"
        "## Debt\n\n"
        "The avalanche method targets the highest interest rate first. "
        "The snowball method targets the smallest balance first.\n",
        encoding="utf-8",
    )

    return kdir


# ════════════════════════════════════════════════════════════════
# EmbeddingModel Tests
# ════════════════════════════════════════════════════════════════

class TestEmbeddingModel:

    def test_dimension(self, embed_model):
        """Embedding dimension matches the expected constant."""
        assert embed_model.dimension == EMBEDDING_DIM

    def test_embed_single_query(self, embed_model):
        """embed_query returns a flat list of the correct length."""
        vec = embed_model.embed_query("hello world")
        assert isinstance(vec, list)
        assert len(vec) == EMBEDDING_DIM

    def test_embed_multiple_texts(self, embed_model):
        """embed_texts returns one vector per input."""
        texts = ["first", "second", "third"]
        vecs = embed_model.embed_texts(texts)
        assert len(vecs) == 3
        for v in vecs:
            assert len(v) == EMBEDDING_DIM

    def test_embed_empty_list(self, embed_model):
        """Empty input returns empty output."""
        assert embed_model.embed_texts([]) == []

    def test_normalization(self, embed_model):
        """Vectors should be unit-length (normalized)."""
        vec = embed_model.embed_query("test normalization")
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 0.01, f"Expected unit vector, got norm={norm}"

    def test_determinism(self, embed_model):
        """Same input produces identical embeddings."""
        text = "deterministic test input"
        v1 = embed_model.embed_query(text)
        v2 = embed_model.embed_query(text)
        for a, b in zip(v1, v2):
            assert abs(a - b) < 1e-6

    def test_similar_texts_closer(self, embed_model):
        """Semantically similar texts should have higher cosine similarity."""
        v_budget = embed_model.embed_query("how to create a monthly budget")
        v_saving = embed_model.embed_query("ways to save money each month")
        v_unrelated = embed_model.embed_query("the weather forecast for tomorrow")

        def cosine(a, b):
            return sum(x * y for x, y in zip(a, b))

        sim_related = cosine(v_budget, v_saving)
        sim_unrelated = cosine(v_budget, v_unrelated)
        assert sim_related > sim_unrelated, (
            f"Related similarity ({sim_related:.4f}) should exceed "
            f"unrelated similarity ({sim_unrelated:.4f})"
        )

    def test_singleton(self):
        """get_embedding_model returns the same cached instance."""
        m1 = get_embedding_model()
        m2 = get_embedding_model()
        assert m1 is m2


# ════════════════════════════════════════════════════════════════
# FinanceRetriever Tests
# ════════════════════════════════════════════════════════════════

class TestFinanceRetriever:

    def test_empty_collection(self, retriever):
        """Querying an empty collection returns no results."""
        assert retriever.is_empty
        assert retriever.chunk_count == 0
        assert retriever.query("anything") == []

    def test_add_and_query(self, retriever):
        """Added chunks should be retrievable."""
        retriever.add_chunks(
            ids=["c1", "c2"],
            documents=[
                "Emergency funds should cover three to six months of expenses.",
                "Index funds track the stock market at very low cost.",
            ],
            metadatas=[
                {"source": "Saving Strategies", "file": "02_saving.md"},
                {"source": "Investing Basics", "file": "04_investing.md"},
            ],
        )
        assert retriever.chunk_count == 2
        assert not retriever.is_empty

        results = retriever.query("how much emergency savings do I need", top_k=2)
        assert len(results) > 0
        # The emergency fund chunk should rank first
        assert "emergency" in results[0]["text"].lower()

    def test_top_k_limits_results(self, retriever):
        """top_k should cap the number of results."""
        retriever.add_chunks(
            ids=["a", "b", "c", "d", "e"],
            documents=[
                "Budgeting helps you plan.",
                "Saving builds security.",
                "Debt management is crucial.",
                "Investing grows wealth.",
                "Tax planning saves money.",
            ],
            metadatas=[{"source": f"src_{i}", "file": f"f{i}.md"} for i in range(5)],
        )
        results = retriever.query("financial planning", top_k=2)
        assert len(results) <= 2

    def test_min_score_filtering(self, retriever):
        """Results below min_score should be excluded."""
        retriever.add_chunks(
            ids=["x1"],
            documents=["Photosynthesis is the process by which plants convert sunlight."],
            metadatas=[{"source": "Biology", "file": "biology.md"}],
        )
        # A finance query against a biology chunk should score low
        results = retriever.query("how to budget my salary", top_k=1, min_score=0.8)
        assert len(results) == 0

    def test_file_field_in_results(self, retriever):
        """Results should include the file metadata field."""
        retriever.add_chunks(
            ids=["f1"],
            documents=["The 50/30/20 rule splits income into needs, wants, and savings."],
            metadatas=[{"source": "Budgeting", "file": "01_budgeting.md"}],
        )
        results = retriever.query("50/30/20 rule", top_k=1)
        assert len(results) == 1
        assert results[0]["file"] == "01_budgeting.md"

    def test_reset_collection(self, retriever):
        """reset_collection should wipe all chunks."""
        retriever.add_chunks(
            ids=["r1"],
            documents=["Some content."],
            metadatas=[{"source": "test", "file": "test.md"}],
        )
        assert retriever.chunk_count == 1
        retriever.reset_collection()
        assert retriever.is_empty
        assert retriever.chunk_count == 0

    def test_format_context_empty(self, retriever):
        """format_context on empty collection returns empty string."""
        assert retriever.format_context("anything") == ""

    def test_format_context_with_data(self, retriever):
        """format_context should return a formatted string with source info."""
        retriever.add_chunks(
            ids=["fc1"],
            documents=["Pay yourself first by automating savings transfers."],
            metadatas=[{"source": "Saving Tips", "file": "02_saving.md"}],
        )
        ctx = retriever.format_context("how to save money")
        assert "RELEVANT FINANCIAL KNOWLEDGE" in ctx
        assert "Saving Tips" in ctx
        assert "Pay yourself first" in ctx


# ════════════════════════════════════════════════════════════════
# Chunking Tests
# ════════════════════════════════════════════════════════════════

class TestChunking:

    def test_split_into_sections(self):
        """Sections should split on ## headings."""
        text = "# Title\n\nIntro paragraph.\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B."
        sections = _split_into_sections(text)
        assert len(sections) >= 2
        assert any("Section A" in s for s in sections)
        assert any("Section B" in s for s in sections)

    def test_chunk_text_basic(self):
        """Short text should produce at least one chunk."""
        text = "## Budgeting\n\nBudgeting is important for financial health."
        chunks = _chunk_text(text, chunk_size=600, overlap=100)
        assert len(chunks) >= 1
        assert "Budgeting" in chunks[0]

    def test_chunk_text_long_splits(self):
        """Long text should be split into multiple chunks."""
        # Create text longer than one chunk
        text = "## Long Section\n\n" + "This is a sentence about money. " * 100
        chunks = _chunk_text(text, chunk_size=200, overlap=50)
        assert len(chunks) > 1

    def test_chunk_overlap(self):
        """Consecutive chunks should share overlapping content."""
        text = "## Section\n\n" + "Sentence about finance number one. " * 50
        chunks = _chunk_text(text, chunk_size=200, overlap=80)
        if len(chunks) >= 2:
            # Some text from end of chunk 0 should appear at start of chunk 1
            tail_of_first = chunks[0][-40:]
            # Check that at least some words overlap
            tail_words = set(tail_of_first.lower().split())
            head_words = set(chunks[1][:80].lower().split())
            overlap_words = tail_words & head_words
            assert len(overlap_words) > 0, "Expected overlapping words between chunks"

    def test_empty_text(self):
        """Empty text should produce no chunks."""
        assert _chunk_text("") == []
        assert _chunk_text("   ") == []


# ════════════════════════════════════════════════════════════════
# Ingestion Tests
# ════════════════════════════════════════════════════════════════

class TestIngestion:

    def test_ingest_from_directory(self, tmp_knowledge, tmp_chroma, embed_model):
        """Ingesting a knowledge directory should populate ChromaDB."""
        # Patch the retriever to use temp dir
        import rag.retriever as ret_mod
        orig_dir = ret_mod.CHROMA_DIR
        orig_col = ret_mod.COLLECTION_NAME
        ret_mod.CHROMA_DIR = tmp_chroma
        ret_mod.COLLECTION_NAME = "test_ingest"

        try:
            stats = ingest_knowledge_base(knowledge_dir=tmp_knowledge, force=True)
            assert stats["status"] == "success"
            assert stats["files"] == 2
            assert stats["total_chunks"] > 0
            assert len(stats["per_file"]) == 2
        finally:
            ret_mod.CHROMA_DIR = orig_dir
            ret_mod.COLLECTION_NAME = orig_col

    def test_ingest_skip_when_populated(self, tmp_knowledge, tmp_chroma):
        """Second ingest without --force should skip."""
        import rag.retriever as ret_mod
        orig_dir = ret_mod.CHROMA_DIR
        orig_col = ret_mod.COLLECTION_NAME
        ret_mod.CHROMA_DIR = tmp_chroma
        ret_mod.COLLECTION_NAME = "test_skip"

        try:
            # First ingest
            stats1 = ingest_knowledge_base(knowledge_dir=tmp_knowledge, force=True)
            assert stats1["status"] == "success"

            # Second ingest — should skip
            stats2 = ingest_knowledge_base(knowledge_dir=tmp_knowledge, force=False)
            assert stats2["status"] == "skipped"
            assert "chunk_count" in stats2
        finally:
            ret_mod.CHROMA_DIR = orig_dir
            ret_mod.COLLECTION_NAME = orig_col

    def test_ingest_empty_directory(self, tmp_path):
        """Ingesting from an empty directory should return an error."""
        empty_dir = tmp_path / "empty_knowledge"
        empty_dir.mkdir()
        import rag.retriever as ret_mod
        orig_dir = ret_mod.CHROMA_DIR
        orig_col = ret_mod.COLLECTION_NAME
        ret_mod.CHROMA_DIR = str(tmp_path / "chroma_empty")
        ret_mod.COLLECTION_NAME = "test_empty"

        try:
            stats = ingest_knowledge_base(knowledge_dir=empty_dir, force=True)
            assert stats["status"] == "error"
        finally:
            ret_mod.CHROMA_DIR = orig_dir
            ret_mod.COLLECTION_NAME = orig_col

    def test_ingest_force_resets(self, tmp_knowledge, tmp_chroma):
        """Force ingest should wipe and repopulate."""
        import rag.retriever as ret_mod
        orig_dir = ret_mod.CHROMA_DIR
        orig_col = ret_mod.COLLECTION_NAME
        ret_mod.CHROMA_DIR = tmp_chroma
        ret_mod.COLLECTION_NAME = "test_force"

        try:
            stats1 = ingest_knowledge_base(knowledge_dir=tmp_knowledge, force=True)
            count1 = stats1["total_chunks"]

            stats2 = ingest_knowledge_base(knowledge_dir=tmp_knowledge, force=True)
            count2 = stats2["total_chunks"]

            # Same content should produce same chunk count
            assert count1 == count2
            assert stats2["status"] == "success"
        finally:
            ret_mod.CHROMA_DIR = orig_dir
            ret_mod.COLLECTION_NAME = orig_col
