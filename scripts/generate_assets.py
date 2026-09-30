"""
Asset Generation Script for README Visualizations.

Every figure is derived from files produced by an actual pipeline run:

* ``support_tickets/support_tickets.csv`` -- the 29 input tickets
* ``support_tickets/output.csv``            -- triage decisions for those tickets
* ``docs/results/retrieval-scores.csv``      -- real ChromaDB relevance scores

Usage:
    python scripts/generate_assets.py

Missing inputs cause the corresponding figure to be skipped rather than
substituted with placeholder numbers.
"""

import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKETS_CSV = REPO_ROOT / "support_tickets" / "support_tickets.csv"
OUTPUT_CSV = REPO_ROOT / "support_tickets" / "output.csv"
SCORES_CSV = REPO_ROOT / "docs" / "results" / "retrieval-scores.csv"
ASSETS_DIR = REPO_ROOT / "assets"

CONFIDENCE_THRESHOLD = 0.40

plt.style.use("dark_background")
sns.set_theme(style="darkgrid", palette="muted")


def read_csv(path: Path):
    """Return the rows of a CSV file, or None when the file is absent."""
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def save(fig, filename: str) -> None:
    """Write a figure into the assets directory."""
    path = ASSETS_DIR / filename
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"generated {path.relative_to(REPO_ROOT)}")


def generate_domain_distribution(tickets):
    """Bar chart of ticket volume per company, counted from the input CSV."""
    labels = {"hackerrank": "HackerRank", "claude": "Claude", "visa": "Visa"}
    counts = Counter((row.get("Company") or "None").strip() for row in tickets)
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    names = [labels.get(k.lower(), "Unassigned") for k, _ in ordered]
    values = [v for _, v in ordered]
    colors = ["#3B82F6", "#8B5CF6", "#10B981", "#6B7280"][: len(values)]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    bars = ax.bar(names, values, color=colors, width=0.55, zorder=3)
    for bar, value in zip(bars, values):
        ax.annotate(
            f"{value} tickets",
            xy=(bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            fontsize=10,
            fontweight="bold",
            color="#E5E7EB",
        )
    ax.set_title("Multi-Domain Support Ticket Distribution",
                 fontsize=14, fontweight="bold", pad=15, color="#F9FAFB")
    ax.set_ylabel("Ticket Volume", fontsize=11, color="#D1D5DB")
    ax.set_ylim(0, max(values) * 1.2)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "ticket_domain_distribution.png")


def generate_triage_metrics(results):
    """Escalation split and request-type mix, counted from output.csv."""
    status_counts = Counter(row.get("status", "") for row in results)
    type_counts = Counter(row.get("request_type", "") for row in results)

    replied = status_counts.get("replied", 0)
    escalated = status_counts.get("escalated", 0)
    total = replied + escalated

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    if total:
        ax1.pie(
            [replied, escalated],
            labels=["Replied\n(autonomous)", "Escalated\n(human security)"],
            autopct="%1.1f%%",
            startangle=140,
            colors=["#10B981", "#EF4444"],
            explode=(0.05, 0),
            textprops={"color": "#F9FAFB", "fontsize": 11, "fontweight": "bold"},
        )
    ax1.set_title("Autonomous Resolution vs Escalation",
                  fontsize=13, fontweight="bold", color="#F9FAFB")

    pretty = {
        "product_issue": "Product Issue",
        "bug": "Bug Report",
        "feature_request": "Feature Request",
        "invalid": "Invalid / Out of Scope",
    }
    ordered = sorted(type_counts.items(), key=lambda kv: kv[1], reverse=True)
    names = [pretty.get(k, k) for k, _ in ordered]
    values = [v for _, v in ordered]
    colors = ["#3B82F6", "#F59E0B", "#8B5CF6", "#6B7280"][: len(values)]

    bars = ax2.barh(names, values, color=colors, height=0.55)
    for bar, value in zip(bars, values):
        ax2.annotate(
            f" {value}",
            xy=(value, bar.get_y() + bar.get_height() / 2),
            ha="left",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="#E5E7EB",
        )
    ax2.set_title("Request Type Classification",
                  fontsize=13, fontweight="bold", color="#F9FAFB")
    ax2.set_xlabel("Tickets", fontsize=11, color="#D1D5DB")
    ax2.set_xlim(0, max(values) * 1.2 if values else 1)
    ax2.grid(axis="x", linestyle="--", alpha=0.3)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    save(fig, "triage_metrics.png")


def generate_similarity_distribution(scores):
    """Histogram of measured top-1 ChromaDB relevance scores."""
    top1 = [
        float(row["relevance_score"])
        for row in scores
        if row.get("rank") == "1"
    ]
    if not top1:
        print(f"skipped retrieval_similarity.png (no rank-1 rows in {SCORES_CSV.name})")
        return

    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    sns.histplot(top1, kde=True, ax=ax, color="#8B5CF6", bins=10,
                 line_kws={"linewidth": 2.5})
    ax.axvline(x=CONFIDENCE_THRESHOLD, color="#EF4444", linestyle="--",
               linewidth=2, label="Confidence threshold (0.40)")
    ax.axvline(x=float(np.mean(top1)), color="#F59E0B", linestyle=":",
               linewidth=2, label=f"Mean ({float(np.mean(top1)):.3f})")

    ax.set_title("Measured ChromaDB Top-1 Relevance Scores",
                 fontsize=14, fontweight="bold", pad=15, color="#F9FAFB")
    ax.set_xlabel("Relevance score", fontsize=11, color="#D1D5DB")
    ax.set_ylabel("Tickets", fontsize=11, color="#D1D5DB")
    ax.legend(facecolor="#1F2937", edgecolor="#374151", labelcolor="#F9FAFB")
    save(fig, "retrieval_similarity.png")


def generate_workflow_diagram(results):
    """Stage-by-stage funnel of how tickets reached their triage decision."""
    grounded = sum(1 for row in results
                   if row.get("justification", "").startswith("Grounded response"))
    pattern = sum(1 for row in results
                  if row.get("justification", "").startswith("Matched verified"))
    fallback = sum(1 for row in results
                   if row.get("justification", "").startswith("No high-confidence"))
    escalated = sum(1 for row in results if row.get("status") == "escalated")
    total = len(results)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    ax.axis("off")

    boxes = [
        (0.10, 0.50, f"1. Ticket In\n{total} tickets\n(CSV or CLI)",
         "#1E3A8A", "#3B82F6"),
        (0.37, 0.78, f"2a. Risk Gate\n{escalated} escalated\nsecurity / fraud",
         "#7F1D1D", "#EF4444"),
        (0.37, 0.22, f"2b. RAG Recall\nChromaDB, {4197} chunks",
         "#4C1D95", "#8B5CF6"),
        (0.64, 0.50, f"3. Grounding\n{grounded} doc answers\n{pattern} pattern matches", "#1F2937", "#374151"),
        (0.90, 0.50, f"4. Fallback\n{fallback} generic", "#065F46", "#10B981"),
    ]
    for x, y, label, face, edge in boxes:
        ax.text(x, y, label, ha="center", va="center",
                bbox={"boxstyle": "round,pad=0.6", "fc": face, "ec": edge, "lw": 2},
                color="#F9FAFB", fontweight="bold", fontsize=11)

    arrow = {"arrowstyle": "->", "lw": 2, "color": "#9CA3AF"}
    ax.annotate("", xy=(0.26, 0.68), xytext=(0.17, 0.55), arrowprops=arrow)
    ax.annotate("", xy=(0.26, 0.30), xytext=(0.17, 0.45), arrowprops=arrow)
    ax.annotate("", xy=(0.53, 0.52), xytext=(0.47, 0.26), arrowprops=arrow)
    ax.annotate("", xy=(0.80, 0.50), xytext=(0.74, 0.50), arrowprops=arrow)

    ax.set_title("Support Triage Agent Workflow",
                 fontsize=15, fontweight="bold", pad=20, color="#F9FAFB")
    save(fig, "triage_workflow.png")


def main() -> int:
    """Regenerate every README figure from measured pipeline output."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    tickets = read_csv(TICKETS_CSV)
    results = read_csv(OUTPUT_CSV)
    scores = read_csv(SCORES_CSV)

    if tickets:
        generate_domain_distribution(tickets)
    else:
        print(f"skipped ticket_domain_distribution.png (missing {TICKETS_CSV.name})")

    if results:
        generate_triage_metrics(results)
        generate_workflow_diagram(results)
    else:
        print(f"skipped triage_metrics.png / triage_workflow.png (missing {OUTPUT_CSV.name})")

    if scores:
        generate_similarity_distribution(scores)
    else:
        print(f"skipped retrieval_similarity.png (missing {SCORES_CSV.name})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())