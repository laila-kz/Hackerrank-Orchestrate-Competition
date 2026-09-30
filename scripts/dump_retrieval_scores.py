"""
Dump real ChromaDB retrieval relevance scores for every support ticket.

Usage:
    python scripts/dump_retrieval_scores.py
    -> docs/results/retrieval-scores.csv

Every row is an actual query against the persisted index. No synthetic values.
"""

import csv
import os
import sys
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault(
    "CHROMA_TELEMETRY_IMPL",
    "chromadb.telemetry.product.posthog.NoopProductTelemetryClient",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "code"))

from retriever import SupportCorpusRetriever

TICKETS = REPO_ROOT / "support_tickets" / "support_tickets.csv"
OUTPUT = REPO_ROOT / "docs" / "results" / "retrieval-scores.csv"


def main() -> int:
    """Query the index once per ticket and record the real similarity scores."""
    retriever = SupportCorpusRetriever(data_path=str(REPO_ROOT / "data"))

    with open(TICKETS, encoding="utf-8") as handle:
        tickets = list(csv.DictReader(handle))

    rows = []
    for ticket in tickets:
        issue = ticket.get("Issue", "")
        company = ticket.get("Company", "None")
        subject = ticket.get("Subject", "")
        hits = retriever.retrieve(issue, company=company, top_k=5)
        for rank, hit in enumerate(hits, 1):
            rows.append({
                "issue": issue,
                "subject": subject,
                "company": company,
                "rank": rank,
                "relevance_score": hit["relevance_score"],
                "hit_company": hit["company"],
                "source": hit["source"],
            })
        if not hits:
            rows.append({
                "issue": issue,
                "subject": subject,
                "company": company,
                "rank": 0,
                "relevance_score": 0.0,
                "hit_company": "",
                "source": "",
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    top1 = [r["relevance_score"] for r in rows if r["rank"] == 1]
    print(f"tickets queried:      {len(tickets)}")
    print(f"score rows written:   {len(rows)}")
    print(f"top-1 score:          min={min(top1):.4f} max={max(top1):.4f} mean={sum(top1) / len(top1):.4f}")
    print(f"top-1 >= 0.40:        {sum(1 for s in top1 if s >= 0.40)}/{len(top1)}")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())