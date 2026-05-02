# Vector DB + search over data

import os
import glob
from pathlib import Path
from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions
import hashlib

class SupportCorpusRetriever:
    def __init__(self, data_path: str = "../data/"):
        self.data_path = Path(data_path)
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = None
        self._initialize_or_load()
    
    def _initialize_or_load(self):
        """Load existing collection or create from scratch"""
        try:
            self.collection = self.chroma_client.get_collection(
                name="support_docs",
                embedding_function=self.embedding_fn
            )
            print(f"Loaded existing collection with {self.collection.count()} documents")
        except:
            print("Creating new collection from support docs...")
            self.collection = self.chroma_client.create_collection(
                name="support_docs",
                embedding_function=self.embedding_fn
            )
            self._index_documents()
    
    def _read_markdown_files(self) -> List[Dict]:
        """Read all markdown files from data/ folder"""
        documents = []
        doc_id = 0
        
        # Walk through all subdirectories
        for company_dir in self.data_path.iterdir():
            if not company_dir.is_dir():
                continue
            
            company = company_dir.name
            
            for md_file in glob.glob(str(company_dir / "**/*.md"), recursive=True):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Skip empty files
                    if not content.strip():
                        continue
                    
                    # Chunk long documents (simple chunking by paragraphs)
                    chunks = self._chunk_document(content, md_file)
                    
                    for chunk in chunks:
                        documents.append({
                            "id": f"doc_{doc_id}",
                            "company": company,
                            "file": os.path.basename(md_file),
                            "path": str(md_file),
                            "content": chunk,
                            "metadata": {
                                "company": company,
                                "source_file": os.path.basename(md_file),
                                "chunk_id": doc_id
                            }
                        })
                        doc_id += 1
                        
                except Exception as e:
                    print(f"Error reading {md_file}: {e}")
        
        print(f"Loaded {len(documents)} document chunks")
        return documents
    
    def _chunk_document(self, content: str, filepath: str, max_chars: int = 2000) -> List[str]:
        """Split document into chunks by paragraphs"""
        paragraphs = content.split('\n\n')
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
        
        # If still too big or no chunks, fallback to truncation
        if not chunks:
            chunks = [content[:max_chars]]
        
        return chunks
    
    def _index_documents(self):
        """Index documents in ChromaDB"""
        documents = self._read_markdown_files()
        
        if not documents:
            print("No documents found to index!")
            return
        
        # Prepare for batch insertion
        ids = [doc["id"] for doc in documents]
        contents = [doc["content"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]
        
        # Add to collection
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            self.collection.add(
                ids=ids[i:i+batch_size],
                documents=contents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size]
            )
        
        print(f"Indexed {len(documents)} chunks")
    
    def retrieve(self, query: str, company: str = None, top_k: int = 5) -> List[Dict]:
        """Retrieve most relevant documents for a query"""
        where_filter = {"company": company} if company and company != "None" else None
        
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter
        )
        
        retrieved = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                retrieved.append({
                    "content": doc,
                    "company": results['metadatas'][0][i].get('company', 'unknown'),
                    "source": results['metadatas'][0][i].get('source_file', 'unknown'),
                    "relevance_score": 1 - (results['distances'][0][i] if results['distances'] else 0)
                })
        
        return retrieved