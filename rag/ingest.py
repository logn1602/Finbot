"""
Ingestion pipeline for FinBot's personal-finance knowledge base.

Reads markdown files from ``knowledge/``, splits them into overlapping
chunks, embeds them, and stores them in the ChromaDB collection.

Usage
-----
    # From project root:
    python -m rag.ingest              # ingest (skip if collection non-empty)
    python -m rag.ingest --force      # wipe collection and re-ingest

Can also be called programmatically::

    from rag.ingest import ingest_knowledge_base
    stats = ingest_knowledge_base(force=True)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from rag.retriever import FinanceRetriever

# ── defaults ────────────────────────────────────────────────────
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
CHUNK_SIZE = 600          # target chunk size in characters
CHUNK_OVERLAP = 100       # overlap between consecutive chunks


# ── chunking ────────────────────────────────────────────────────

def _split_into_sections(text: str) -> list[str]:
    """
    Split a markdown document at ``## `` headings.

    Each section keeps its heading so the chunk retains topic context.
    """
    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


def _chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """
    Split *text* into overlapping character-level chunks.

    The algorithm first tries to split on section headings (``## ``).
    Sections that are still longer than *chunk_size* are further split
    on paragraph boundaries, then on sentence boundaries.
    """
    sections = _split_into_sections(text)
    chunks: list[str] = []

    for section in sections:
        if len(section) <= chunk_size:
            chunks.append(section)
            continue

        # Split long sections on paragraph boundaries
        paragraphs = re.split(r"\n{2,}", section)
        buffer = ""
        for para in paragraphs:
            candidate = (buffer + "\n\n" + para).strip() if buffer else para
            if len(candidate) <= chunk_size:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer)
                # If a single paragraph exceeds chunk_size, split on sentences
                if len(para) > chunk_size:
                    sentences = re.split(r"(?<=[.!?])\s+", para)
                    sent_buf = ""
                    for sent in sentences:
                        cand = (sent_buf + " " + sent).strip() if sent_buf else sent
                        if len(cand) <= chunk_size:
                            sent_buf = cand
                        else:
                            if sent_buf:
                                chunks.append(sent_buf)
                            sent_buf = sent
                    if sent_buf:
                        buffer = sent_buf
                else:
                    buffer = para
        if buffer:
            chunks.append(buffer)

    # Add overlap between consecutive chunks for better retrieval
    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            # Find a clean word boundary for the overlap
            space_idx = prev_tail.find(" ")
            if space_idx != -1:
                prev_tail = prev_tail[space_idx + 1:]
            overlapped.append(prev_tail + " " + chunks[i])
        chunks = overlapped

    return [c.strip() for c in chunks if c.strip()]


# ── ingestion ───────────────────────────────────────────────────

def ingest_knowledge_base(
    knowledge_dir: Path = KNOWLEDGE_DIR,
    force: bool = False,
) -> dict:
    """
    Read all ``.md`` files in *knowledge_dir*, chunk them, and load
    into ChromaDB via :class:`FinanceRetriever`.

    Parameters
    ----------
    knowledge_dir : Path
        Directory containing the markdown knowledge files.
    force : bool
        If True, wipe the existing collection before ingesting.

    Returns
    -------
    dict
        Stats: ``files``, ``total_chunks``, ``per_file`` breakdown.
    """
    retriever = FinanceRetriever()

    # Skip if collection already populated (unless forced)
    if not force and not retriever.is_empty:
        return {
            "status": "skipped",
            "reason": "Collection already has chunks. Use --force to re-ingest.",
            "chunk_count": retriever.chunk_count,
        }

    if force:
        retriever.reset_collection()

    md_files = sorted(knowledge_dir.glob("*.md"))
    if not md_files:
        return {"status": "error", "reason": f"No .md files found in {knowledge_dir}"}

    all_ids: list[str] = []
    all_docs: list[str] = []
    all_metas: list[dict] = []
    per_file: list[dict] = []

    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")

        # Extract document title from first H1
        title_match = re.match(r"^#\s+(.+)", text)
        title = title_match.group(1).strip() if title_match else md_path.stem

        chunks = _chunk_text(text)
        slug = md_path.stem  # e.g. "01_budgeting_basics"

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{slug}_chunk_{idx:03d}"
            all_ids.append(chunk_id)
            all_docs.append(chunk)
            all_metas.append({
                "source": title,
                "file": md_path.name,
                "chunk_index": idx,
            })

        per_file.append({
            "file": md_path.name,
            "title": title,
            "chunks": len(chunks),
            "chars": len(text),
        })

    added = retriever.add_chunks(all_ids, all_docs, all_metas)

    return {
        "status": "success",
        "files": len(md_files),
        "total_chunks": added,
        "per_file": per_file,
    }


# ── CLI entry point ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ingest personal-finance knowledge base into ChromaDB",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Wipe existing collection and re-ingest from scratch",
    )
    parser.add_argument(
        "--knowledge-dir",
        type=Path,
        default=KNOWLEDGE_DIR,
        help=f"Path to knowledge markdown files (default: {KNOWLEDGE_DIR})",
    )
    args = parser.parse_args()

    print(f"Knowledge dir : {args.knowledge_dir}")
    print(f"Force re-ingest: {args.force}\n")

    stats = ingest_knowledge_base(
        knowledge_dir=args.knowledge_dir,
        force=args.force,
    )

    if stats["status"] == "skipped":
        print(f"[SKIP] {stats['reason']}")
        print(f"   Existing chunks: {stats['chunk_count']}")
        return

    if stats["status"] == "error":
        print(f"[ERROR] {stats['reason']}")
        sys.exit(1)

    print(f"[OK] Ingested {stats['files']} files -> {stats['total_chunks']} chunks\n")
    for f in stats["per_file"]:
        print(f"   {f['file']:40s}  {f['chunks']:3d} chunks  ({f['chars']:,} chars)")

    print(f"\nCollection ready with {stats['total_chunks']} chunks.")


if __name__ == "__main__":
    main()
