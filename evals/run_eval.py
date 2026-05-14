"""
RAG Evaluation Pipeline for FinBot.

Measures retrieval quality across 50+ test cases without requiring
any paid API calls — evaluation is purely on the retrieval side
(embedding + ChromaDB), not on LLM generation.

Metrics
-------
- **Hit Rate (Recall@K)**: Did at least one retrieved chunk come from
  an expected source file?
- **Topic Coverage**: What fraction of expected topic keywords appear
  in the retrieved chunks?
- **Mean Relevance Score**: Average cosine similarity of retrieved chunks.
- **MRR (Mean Reciprocal Rank)**: How high does the first relevant
  result appear in the ranked list?

Usage
-----
    python -m evals.run_eval                 # run all test cases
    python -m evals.run_eval --category debt # run only "debt" cases
    python -m evals.run_eval --verbose       # show per-case details
    python -m evals.run_eval --top-k 5       # test with top_k=5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rag.retriever import FinanceRetriever

EVAL_DIR = Path(__file__).resolve().parent
TEST_CASES_PATH = EVAL_DIR / "test_cases.json"


# ── Metric helpers ──────────────────────────────────────────────

def _check_hit(results: list[dict], expected_sources: list[str]) -> bool:
    """True if any retrieved chunk's file matches an expected source."""
    retrieved_files = set()
    for r in results:
        retrieved_files.add(r.get("file", ""))
        retrieved_files.add(r.get("source", ""))
    for exp in expected_sources:
        if exp in retrieved_files:
            return True
        # Also match by stem (e.g. "01_budgeting_basics" in title)
        stem = exp.replace(".md", "")
        for ret in retrieved_files:
            if stem in ret or exp in ret:
                return True
    return False


def _topic_coverage(results: list[dict], expected_topics: list[str]) -> float:
    """Fraction of expected topic keywords found in retrieved text."""
    if not expected_topics:
        return 1.0
    combined_text = " ".join(r["text"] for r in results).lower()
    hits = sum(1 for topic in expected_topics if topic.lower() in combined_text)
    return hits / len(expected_topics)


def _mean_score(results: list[dict]) -> float:
    """Average relevance score across retrieved chunks."""
    if not results:
        return 0.0
    return sum(r["score"] for r in results) / len(results)


def _reciprocal_rank(results: list[dict], expected_sources: list[str]) -> float:
    """1/rank of the first relevant result. 0 if none found."""
    for i, r in enumerate(results):
        src = r.get("source", "")
        fname = r.get("file", "")
        for exp in expected_sources:
            stem = exp.replace(".md", "")
            if exp in (src, fname) or stem in src or stem in fname:
                return 1.0 / (i + 1)
    return 0.0


# ── Evaluation runner ───────────────────────────────────────────

def load_test_cases(category: str | None = None) -> list[dict]:
    """Load test cases, optionally filtered by category."""
    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)
    if category:
        cases = [c for c in cases if c.get("category") == category]
    return cases


def evaluate(
    top_k: int = 4,
    category: str | None = None,
    verbose: bool = False,
) -> dict:
    """
    Run the full evaluation pipeline.

    Returns
    -------
    dict
        Overall metrics and per-case results.
    """
    retriever = FinanceRetriever()
    cases = load_test_cases(category)

    if not cases:
        return {"error": f"No test cases found for category={category}"}

    if retriever.is_empty:
        return {"error": "ChromaDB collection is empty. Run: python -m rag.ingest"}

    results_list: list[dict] = []
    total_hit = 0
    total_topic_cov = 0.0
    total_score = 0.0
    total_mrr = 0.0

    for case in cases:
        query = case["query"]
        expected_sources = case.get("expected_sources", [])
        expected_topics = case.get("expected_topics", [])

        chunks = retriever.query(query, top_k=top_k)

        hit = _check_hit(chunks, expected_sources)
        topic_cov = _topic_coverage(chunks, expected_topics)
        avg_score = _mean_score(chunks)
        rr = _reciprocal_rank(chunks, expected_sources)

        total_hit += int(hit)
        total_topic_cov += topic_cov
        total_score += avg_score
        total_mrr += rr

        case_result = {
            "id": case["id"],
            "query": query,
            "category": case.get("category", ""),
            "hit": hit,
            "topic_coverage": round(topic_cov, 3),
            "mean_score": round(avg_score, 4),
            "reciprocal_rank": round(rr, 4),
            "num_results": len(chunks),
        }

        if verbose:
            case_result["retrieved_sources"] = [
                {"source": c["source"], "score": c["score"]}
                for c in chunks
            ]
            case_result["expected_sources"] = expected_sources
            # Show which topics were found/missed
            combined_text = " ".join(c["text"] for c in chunks).lower()
            case_result["topics_found"] = [
                t for t in expected_topics if t.lower() in combined_text
            ]
            case_result["topics_missed"] = [
                t for t in expected_topics if t.lower() not in combined_text
            ]

        results_list.append(case_result)

    n = len(cases)
    summary = {
        "total_cases": n,
        "top_k": top_k,
        "category_filter": category or "all",
        "hit_rate": round(total_hit / n * 100, 1),
        "mean_topic_coverage": round(total_topic_cov / n * 100, 1),
        "mean_relevance_score": round(total_score / n, 4),
        "mrr": round(total_mrr / n, 4),
        "hits": total_hit,
        "misses": n - total_hit,
    }

    return {"summary": summary, "results": results_list}


# ── CLI ─────────────────────────────────────────────────────────

def _print_report(report: dict):
    """Pretty-print the evaluation report."""
    if "error" in report:
        print(f"[ERROR] {report['error']}")
        sys.exit(1)

    s = report["summary"]
    print("=" * 60)
    print("  FinBot RAG Evaluation Report")
    print("=" * 60)
    print(f"  Test cases   : {s['total_cases']}")
    print(f"  Category     : {s['category_filter']}")
    print(f"  Top-K        : {s['top_k']}")
    print()
    print(f"  Hit Rate     : {s['hit_rate']}%  ({s['hits']}/{s['total_cases']})")
    print(f"  Topic Coverage: {s['mean_topic_coverage']}%")
    print(f"  Mean Score   : {s['mean_relevance_score']:.4f}")
    print(f"  MRR          : {s['mrr']:.4f}")
    print("=" * 60)

    # Per-category breakdown
    categories: dict[str, list] = {}
    for r in report["results"]:
        cat = r.get("category", "other")
        categories.setdefault(cat, []).append(r)

    print("\n  Per-Category Breakdown:")
    print(f"  {'Category':<15s} {'Cases':>5s} {'Hits':>5s} {'Hit%':>6s} {'TopicCov':>9s} {'MeanScr':>8s}")
    print("  " + "-" * 52)
    for cat, cases_in_cat in sorted(categories.items()):
        n_cat = len(cases_in_cat)
        hits_cat = sum(1 for c in cases_in_cat if c["hit"])
        hit_pct = hits_cat / n_cat * 100
        tc_avg = sum(c["topic_coverage"] for c in cases_in_cat) / n_cat * 100
        sc_avg = sum(c["mean_score"] for c in cases_in_cat) / n_cat
        print(f"  {cat:<15s} {n_cat:>5d} {hits_cat:>5d} {hit_pct:>5.1f}% {tc_avg:>8.1f}% {sc_avg:>8.4f}")

    # Show failures
    failures = [r for r in report["results"] if not r["hit"]]
    if failures:
        print(f"\n  Failed Cases ({len(failures)}):")
        for f in failures:
            print(f"    - [{f['id']}] {f['query']}")

    # Verbose per-case detail
    verbose_cases = [r for r in report["results"] if "topics_missed" in r]
    if verbose_cases:
        print("\n  Detailed Results:")
        print("  " + "-" * 56)
        for r in verbose_cases:
            status = "HIT" if r["hit"] else "MISS"
            print(f"\n  [{r['id']}] {r['query']}")
            print(f"    Status: {status} | TopicCov: {r['topic_coverage']:.0%} | Score: {r['mean_score']:.4f}")
            if r.get("retrieved_sources"):
                for rs in r["retrieved_sources"]:
                    print(f"      -> {rs['source']} ({rs['score']:.4f})")
            if r.get("topics_missed"):
                print(f"    Missed topics: {', '.join(r['topics_missed'])}")


def main():
    parser = argparse.ArgumentParser(description="Run FinBot RAG evaluation pipeline")
    parser.add_argument("--category", type=str, default=None,
                        help="Filter by category (budgeting, saving, debt, investing, tax, insurance, planning, mistakes, cross-topic)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show per-case details including retrieved sources and missed topics")
    parser.add_argument("--top-k", type=int, default=4,
                        help="Number of chunks to retrieve per query (default: 4)")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON instead of formatted report")
    args = parser.parse_args()

    report = evaluate(top_k=args.top_k, category=args.category, verbose=args.verbose)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_report(report)


if __name__ == "__main__":
    main()
