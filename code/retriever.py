"""
Vector Retrieval Engine for Multi-Domain Support Documentation.

Uses ChromaDB with fast local embedding functionality to chunk, index,
and retrieve grounded knowledge from support documentation.
"""

import glob
import hashlib
import math
import os
from pathlib import Path

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.errors import NotFoundError

COLLECTION_NAME = "support_docs_v3"


class FastLocalEmbeddingFunction(EmbeddingFunction):
    """
    Zero-network local embedding function using hashed term frequency vectors.

    Tokens are mapped to bucket indices with BLAKE2b rather than Python's builtin
    ``hash()``. The builtin is salted per process (PYTHONHASHSEED), which would
    place document vectors and query vectors in different hash spaces and make
    retrieval non-deterministic. BLAKE2b is stable across processes and runs, so
    a given corpus always yields the same index and the same similarity scores.
    """

    def __init__(self, dim: int = 128):
        self.dim = dim

    def name(self) -> str:
        """Stable identifier persisted alongside the ChromaDB collection."""
        return f"fast-local-btf-blake2b-{self.dim}"

    @staticmethod
    def _bucket(token: str, dim: int) -> int:
        """Map a token to a bucket index deterministically."""
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % dim

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            words = text.lower().split()
            vec = [0.0] * self.dim
            if not words:
                embeddings.append(vec)
                continue

            for w in words:
                vec[self._bucket(w, self.dim)] += 1.0

            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]

            embeddings.append(vec)
        return embeddings


class SupportCorpusRetriever:
    """Manages vector embeddings and retrieval over multi-domain markdown docs."""

    def __init__(self, data_path: str | None = None, chroma_db_path: str | None = None):
        base_dir = Path(__file__).resolve().parent

        if data_path:
            self.data_path = Path(data_path).resolve()
        else:
            self.data_path = (base_dir / "../data").resolve()

        if chroma_db_path:
            self.chroma_db_path = Path(chroma_db_path).resolve()
        else:
            self.chroma_db_path = (base_dir / "chroma_db").resolve()

        self.chroma_client = chromadb.PersistentClient(path=str(self.chroma_db_path))
        self.embedding_fn = FastLocalEmbeddingFunction()
        self.collection = None
        self._initialize_or_load()

    def _initialize_or_load(self, force_reindex: bool = False):
        """
        Load existing vector collection or index from scratch.

        ``embedding_function`` is always passed explicitly. Omitting it makes
        ChromaDB fall back to its bundled ONNX MiniLM embedder, which attempts a
        ~79 MB model download and blocks the first query on a network round trip.
        """
        if force_reindex:
            try:
                self.chroma_client.delete_collection(name=COLLECTION_NAME)
            except NotFoundError:
                pass
            self.collection = self.chroma_client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_fn
            )
            self._index_documents()
            return

        try:
            self.collection = self.chroma_client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_fn
            )
            if self.collection.count() == 0:
                self._index_documents()
        except Exception:  # noqa: BLE001 - cold-start path, retried below
            try:
                self.collection = self.chroma_client.create_collection(
                    name=COLLECTION_NAME,
                    embedding_function=self.embedding_fn
                )
                self._index_documents()
            except Exception:  # noqa: BLE001 - concurrent creation, fall back to get
                self.collection = self.chroma_client.get_collection(
                    name=COLLECTION_NAME,
                    embedding_function=self.embedding_fn
                )

    def _read_markdown_files(self) -> list[dict]:
        """Read and chunk all markdown documentation files from data_path."""
        documents = []
        doc_id = 0

        if not self.data_path.exists():
            return documents

        for company_dir in self.data_path.iterdir():
            if not company_dir.is_dir():
                continue

            company = company_dir.name

            for md_file in glob.glob(str(company_dir / "**/*.md"), recursive=True):
                try:
                    with open(md_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    content = self._strip_frontmatter(content)
                    if not content.strip():
                        continue

                    chunks = self._chunk_document(content)
                    filename = os.path.basename(md_file)

                    for chunk in chunks:
                        documents.append({
                            "id": f"doc_{doc_id}",
                            "content": chunk,
                            "metadata": {
                                "company": company.lower(),
                                "company_display": company.capitalize(),
                                "source_file": filename,
                                "chunk_id": doc_id,
                            }
                        })
                        doc_id += 1

                except (OSError, UnicodeDecodeError) as e:
                    print(f"Warning: Error reading {md_file}: {e}")

        return documents

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        """
        Drop a leading YAML front-matter block from a markdown document.

        Scraped articles carry ``---`` delimited metadata (title, source_url,
        last_updated_iso). Left in place it both pollutes the embedding with
        boilerplate tokens and leaks raw YAML into the grounded response body.
        """
        if not content.startswith("---"):
            return content
        parts = content.split("\n---", 1)
        if len(parts) == 2:
            return parts[1].lstrip("-").lstrip("\n")
        return content

    def _chunk_document(self, content: str, max_chars: int = 1500) -> list[str]:
        """Split document content into semantic paragraph chunks."""
        paragraphs = content.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) < max_chars:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        if not chunks and content:
            chunks = [content[:max_chars]]

        return chunks

    def _index_documents(self):
        """Index markdown documents into ChromaDB in batches."""
        documents = self._read_markdown_files()
        if not documents:
            return

        ids = [doc["id"] for doc in documents]
        contents = [doc["content"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            self.collection.add(
                ids=ids[i:i + batch_size],
                documents=contents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size]
            )

    def retrieve(self, query: str, company: str | None = None, top_k: int = 5) -> list[dict]:
        """
        Retrieve top_k most relevant document chunks for a given query.
        Optionally filter by company domain.
        """
        where_filter = None
        if company and company.lower() != "none":
            where_filter = {"company": company.lower()}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter
            )

            retrieved = []
            if results and results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    dist = results["distances"][0][i] if results.get("distances") else 0.5
                    sim_score = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                    retrieved.append({
                        "content": doc,
                        "company": results["metadatas"][0][i].get("company", "unknown"),
                        "source": results["metadatas"][0][i].get("source_file", "unknown"),
                        "relevance_score": round(sim_score, 4),
                    })
            return retrieved

        except Exception as e:  # noqa: BLE001 - degrade to fallback, never crash a batch
            print(f"Retrieval error: {e}")
            return []