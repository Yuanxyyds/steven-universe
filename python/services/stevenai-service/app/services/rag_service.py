"""
RAG Service - Retrieval-Augmented Generation using FAISS.

Loads FAISS indexes for documents and QA pairs, performs semantic search.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """
    Manages RAG retrieval using FAISS indexes.

    Loads two separate indexes:
    1. Documents (from rag_document.json)
    2. QA pairs (from rag_qa.json)
    """

    def __init__(self):
        self.encoder: Optional[SentenceTransformer] = None
        self.document_index: Optional[faiss.IndexFlatIP] = None
        self.qa_index: Optional[faiss.IndexFlatIP] = None
        self.document_texts: List[Dict[str, Any]] = []
        self.qa_texts: List[Dict[str, Any]] = []
        self._initialized = False

    async def initialize(self):
        """
        Initialize RAG service:
        1. Load sentence transformer model
        2. Load text data
        3. Build or load FAISS indexes
        """
        if self._initialized:
            logger.info("RAG service already initialized")
            return

        logger.info("Initializing RAG service...")

        # Load encoder
        logger.info(f"Loading embedding model: {settings.RAG_EMBEDDING_MODEL}")
        self.encoder = SentenceTransformer(settings.RAG_EMBEDDING_MODEL)

        # Load data
        self._load_documents()
        self._load_qa_pairs()

        # Build or load indexes
        index_path = Path(settings.RAG_INDEX_PATH)
        index_path.mkdir(parents=True, exist_ok=True)

        doc_index_file = index_path / "documents.faiss"
        qa_index_file = index_path / "qa.faiss"

        # Document index
        if doc_index_file.exists():
            logger.info("Loading existing document FAISS index")
            self.document_index = faiss.read_index(str(doc_index_file))
        else:
            logger.info("Building document FAISS index")
            self.document_index = self._build_index(
                [doc["content"] for doc in self.document_texts]
            )
            faiss.write_index(self.document_index, str(doc_index_file))
            logger.info(f"Saved document index to {doc_index_file}")

        # QA index
        if qa_index_file.exists():
            logger.info("Loading existing QA FAISS index")
            self.qa_index = faiss.read_index(str(qa_index_file))
        else:
            logger.info("Building QA FAISS index")
            self.qa_index = self._build_index(
                [qa["content"] for qa in self.qa_texts]
            )
            faiss.write_index(self.qa_index, str(qa_index_file))
            logger.info(f"Saved QA index to {qa_index_file}")

        self._initialized = True
        logger.info("✅ RAG service initialized successfully")

    def _load_documents(self):
        """Load rag_document.json."""
        doc_path = Path(settings.RAG_DOCUMENT_PATH)
        if not doc_path.exists():
            raise FileNotFoundError(f"Document file not found: {doc_path}")

        with open(doc_path, 'r', encoding='utf-8') as f:
            self.document_texts = json.load(f)
        logger.info(f"Loaded {len(self.document_texts)} documents")

    def _load_qa_pairs(self):
        """Load rag_qa.json."""
        qa_path = Path(settings.RAG_QA_PATH)
        if not qa_path.exists():
            raise FileNotFoundError(f"QA file not found: {qa_path}")

        with open(qa_path, 'r', encoding='utf-8') as f:
            self.qa_texts = json.load(f)
        logger.info(f"Loaded {len(self.qa_texts)} QA pairs")

    def _build_index(self, texts: List[str]) -> faiss.IndexFlatIP:
        """
        Build FAISS index from texts.

        Uses IndexFlatIP with normalized vectors for cosine similarity.
        """
        logger.info(f"Encoding {len(texts)} texts...")
        embeddings = self.encoder.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=True
        )

        # Normalize for cosine similarity (IndexFlatIP uses inner product)
        faiss.normalize_L2(embeddings)

        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings)

        logger.info(f"Built FAISS index with {index.ntotal} vectors, dim={dimension}")
        return index

    def search(
        self,
        query: str,
        use_docs: bool = False,
        use_qa: bool = False,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Search RAG datasets for relevant contexts.

        Args:
            query: User query
            use_docs: Include documents dataset
            use_qa: Include QA pairs dataset
            top_k: Number of results per dataset (default: settings.RAG_TOP_K)

        Returns:
            List of retrieved contexts with scores and metadata
        """
        if not self._initialized:
            raise RuntimeError("RAG service not initialized. Call initialize() first.")

        if not use_docs and not use_qa:
            logger.info("No RAG datasets enabled, returning empty results")
            return []

        if top_k is None:
            top_k = settings.RAG_TOP_K

        results = []

        # Encode query
        query_embedding = self.encoder.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_embedding)

        # Search documents
        if use_docs and self.document_index:
            logger.info(f"Searching documents with top_k={top_k}")
            scores, indices = self.document_index.search(query_embedding, top_k)
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx < len(self.document_texts):
                    doc = self.document_texts[idx]
                    results.append({
                        "content": doc["content"],
                        "score": float(score),
                        "metadata": {
                            **doc.get("metadata", {}),
                            "source": "document"
                        }
                    })

        # Search QA pairs
        if use_qa and self.qa_index:
            logger.info(f"Searching QA pairs with top_k={top_k}")
            scores, indices = self.qa_index.search(query_embedding, top_k)
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx < len(self.qa_texts):
                    qa_item = self.qa_texts[idx]
                    # Use the answer as content (from metadata)
                    answer = qa_item.get("metadata", {}).get("answer", "")
                    results.append({
                        "content": answer,
                        "score": float(score),
                        "metadata": {
                            **qa_item.get("metadata", {}),
                            "source": "qa",
                            "question": qa_item["content"]
                        }
                    })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        logger.info(f"Retrieved {len(results)} contexts (docs={use_docs}, qa={use_qa})")
        return results


# Global instance
rag_service = RAGService()
