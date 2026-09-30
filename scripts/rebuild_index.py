"""
Rebuild the ChromaDB support-docs index with the deterministic BLAKE2b hash.

Usage:
    python scripts/rebuild_index.py [--log docs/results/rebuild-chroma.txt]

Moving to collection ``support_docs_v3`` forces a cold rebuild: vectors written by
the previous salted-hash embedding function live in a different hash space and are
not comparable against freshly computed query vectors.
"""

import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault(
    "CHROMA_TELEMETRY_IMPL",
    "chromadb.telemetry.product.posthog.NoopProductTelemetryClient",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "code"))

import chromadb
from retriever import (
    COLLECTION_NAME,
    FastLocalEmbeddingFunction,
    SupportCorpusRetriever,
)

STALE_COLLECTION = "support_docs_v2"
BATCH_SIZE = 100


def main() -> int:
    """Rebuild the collection from scratch and write a timing report."""
    parser = argparse.ArgumentParser(description="Rebuild the ChromaDB support-docs index.")
    parser.add_argument("--log", default=str(REPO_ROOT / "docs/results/rebuild-chroma.txt"))
    args = parser.parse_args()

    lines = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    t_start = time.time()
    log("ChromaDB index rebuild")
    log(f"python:     {sys.executable}")
    log(f"chromadb:   {chromadb.__version__}")
    log(f"collection: {COLLECTION_NAME}")
    log("embedding:  FastLocalEmbeddingFunction (BLAKE2b hashed bag-of-terms, dim=128)")
    log("corpus:     {}".format(REPO_ROOT / "data"))
    log("=" * 62)

    db_path = REPO_ROOT / "code" / "chroma_db"

    t_open = time.time()
    client = chromadb.PersistentClient(path=str(db_path))
    log(f"opened persistent store ({time.time() - t_open:.2f}s)")

    names = [c.name for c in client.list_collections()]
    log("existing collections: {}".format(names or "none"))

    for stale in (STALE_COLLECTION, COLLECTION_NAME):
        if stale in names:
            client.delete_collection(name=stale)
            log(f"deleted collection '{stale}'")

    embedding_fn = FastLocalEmbeddingFunction()
    collection = client.create_collection(
        name=COLLECTION_NAME, embedding_function=embedding_fn
    )
    log(f"created collection '{COLLECTION_NAME}'")

    # Reuse the retriever's chunker so the rebuild matches runtime retrieval.
    retriever = SupportCorpusRetriever.__new__(SupportCorpusRetriever)
    retriever.data_path = REPO_ROOT / "data"
    retriever.chroma_db_path = db_path
    retriever.chroma_client = client
    retriever.embedding_fn = embedding_fn
    retriever.collection = collection

    t_read = time.time()
    documents = retriever._read_markdown_files()
    read_s = time.time() - t_read
    log(f"read + chunked {len(documents)} documents ({read_s:.2f}s)")

    per_company = {}
    for doc in documents:
        key = doc["metadata"]["company"]
        per_company[key] = per_company.get(key, 0) + 1
    for company in sorted(per_company):
        log(f"    {company:<12} {per_company[company]:>5} chunks")

    t_index = time.time()
    ids = [d["id"] for d in documents]
    contents = [d["content"] for d in documents]
    metadatas = [d["metadata"] for d in documents]
    for i in range(0, len(ids), BATCH_SIZE):
        collection.add(
            ids=ids[i:i + BATCH_SIZE],
            documents=contents[i:i + BATCH_SIZE],
            metadatas=metadatas[i:i + BATCH_SIZE],
        )
    index_s = time.time() - t_index
    log(f"embedded + added {len(ids)}/{len(ids)} chunks in batches of {BATCH_SIZE} ({index_s:.2f}s)")

    log(f"collection count: {collection.count()}")

    probe_query = "my visa card was stolen and I need a replacement"
    t_q = time.time()
    probe = retriever.retrieve(probe_query, top_k=3)
    query_s = time.time() - t_q
    log("")
    log(f"smoke query ({query_s:.3f}s): {probe_query!r}")
    for i, hit in enumerate(probe, 1):
        log("    {}. score={} company={} source={}".format(
            i, hit["relevance_score"], hit["company"], hit["source"]))

    log("")
    log("determinism fingerprint: {}".format([h["relevance_score"] for h in probe]))
    log(f"total wall clock: {time.time() - t_start:.2f}s")

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())