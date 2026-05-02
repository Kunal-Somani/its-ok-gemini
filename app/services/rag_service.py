"""
RAG (Retrieval-Augmented Generation) Service for context retrieval.

Provides vector-based retrieval of:
- Repository boilerplate patterns
- Official library documentation (Tailwind, React)
- Best practice code snippets

Uses local embedding model (all-MiniLM-L6-v2) for 100% data sovereignty.
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib

import structlog
import cohere
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from rank_bm25 import BM25Okapi

from app.core.config import settings

logger = structlog.get_logger(__name__)


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class DocumentChunk:
    """Represents a chunk of indexed text."""

    id: str
    text: str
    source: str  # "boilerplate", "react_docs", "tailwind_docs"
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass
class RetrievalResult:
    """Result from vector retrieval."""

    text: str
    source: str
    score: float
    metadata: Dict[str, Any]


class BM25Index:
    def __init__(self):
        self.corpus: List[str] = []
        self.doc_ids: List[str] = []
        self.bm25: Optional[BM25Okapi] = None

    def add_documents(self, texts: List[str], ids: List[str]):
        self.corpus.extend(texts)
        self.doc_ids.extend(ids)
        tokenized = [t.lower().split() for t in self.corpus]
        self.bm25 = BM25Okapi(tokenized)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        if not self.bm25:
            return []
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
            :top_k
        ]
        return [(self.doc_ids[i], float(scores[i])) for i in top_indices]


# ============================================================================
# RAG Service
# ============================================================================


class RAGService:
    """
    Vector-based context retrieval system for code generation.

    Manages:
    - Local embedding model initialization
    - Qdrant vector database connections
    - Document indexing and chunking
    - Semantic retrieval of relevant context
    """

    def __init__(self):
        """Initialize RAG service with embeddings and Qdrant client."""
        self.cohere_client: Optional[cohere.AsyncClient] = None
        self.qdrant_client: Optional[AsyncQdrantClient] = None
        self.collection_name = "code_context"
        self.embedding_dim = settings.RAG_VECTOR_DIMENSION
        self.chunk_size = settings.RAG_CHUNK_SIZE
        self.chunk_overlap = settings.RAG_CHUNK_OVERLAP
        self.top_k = settings.RAG_TOP_K
        self._initialized = False
        self.bm25_index = BM25Index()

    async def initialize(self) -> None:
        """
        Initialize embedding model and Qdrant client with graceful degradation.

        If Qdrant is unreachable or embedding model fails to load, logs a warning
        and allows the orchestrator to proceed with a "Simple Prompt" mode rather
        than crashing the entire task.
        """
        if self._initialized:
            return

        logger.info("initializing_rag_service")
        initialization_failed = False

        try:
            self.cohere_client = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)
            logger.info("cohere_client_initialized", model=settings.EMBEDDING_MODEL)
        except Exception as e:
            logger.warning(
                "cohere_initialization_failed_graceful_fallback",
                model=settings.EMBEDDING_MODEL,
                error=str(e),
                fallback="simple_prompt_mode",
            )
            self.cohere_client = None
            initialization_failed = True

        try:
            # Initialize Qdrant client
            self.qdrant_client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
            )

            # Verify Qdrant connection
            health = await self.qdrant_client.get_collections()
            logger.info("qdrant_connected", collections_count=len(health.collections))

            # Ensure collection exists
            await self._ensure_collection()

        except Exception as e:
            logger.warning(
                "qdrant_connection_failed_graceful_fallback",
                url=settings.QDRANT_URL,
                error=str(e),
                fallback="simple_prompt_mode",
            )
            self.qdrant_client = None
            initialization_failed = True

        # Mark as initialized even if dependencies failed
        # The orchestrator will work with degraded RAG capabilities
        self._initialized = True

        if initialization_failed:
            logger.warning(
                "rag_service_degraded_mode",
                embedding_model_available=self.cohere_client is not None,
                qdrant_available=self.qdrant_client is not None,
                message="RAG service operating in degraded mode. Retrieval operations will return empty results.",
            )
        else:
            logger.info("rag_service_initialized_successfully")

    async def _ensure_collection(self) -> None:
        """
        Ensure Qdrant collection exists.
        MIGRATION NOTE: Existing Qdrant collections must be deleted and recreated when switching embedding models.
        """
        try:
            await self.qdrant_client.get_collection(self.collection_name)
            logger.info("collection_exists", name=self.collection_name)
        except Exception:
            logger.info("creating_collection", name=self.collection_name)
            await self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim, distance=Distance.COSINE
                ),
            )
            logger.info("collection_created", name=self.collection_name)

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk = text[start:end]
            chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap

        return chunks

    def _generate_chunk_id(self, source: str, chunk_index: int, content: str) -> str:
        """Generate deterministic chunk ID."""
        hash_obj = hashlib.md5(f"{source}_{chunk_index}_{content}".encode())
        return f"{source}_{chunk_index}_{hash_obj.hexdigest()[:8]}"

    async def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if not self.cohere_client:
            logger.warning("cohere_client_unavailable_returning_empty")
            return [[] for _ in texts]

        try:
            response = await self.cohere_client.embed(
                texts=texts,
                model=settings.EMBEDDING_MODEL,
                input_type="search_document",
            )
            return response.embeddings
        except Exception as e:
            logger.error("cohere_embed_failed", error=str(e))
            return [[] for _ in texts]

    async def _embed_query(self, query: str) -> List[float]:
        if not self.cohere_client:
            return []

        try:
            response = await self.cohere_client.embed(
                texts=[query], model=settings.EMBEDDING_MODEL, input_type="search_query"
            )
            return response.embeddings[0] if response.embeddings else []
        except Exception as e:
            logger.error("cohere_query_embed_failed", error=str(e))
            return []

    async def index_repository_boilerplate(self, repo_path: str) -> int:
        """
        Index boilerplate patterns from the repository.

        If Qdrant is unavailable, logs a warning and returns 0.

        Indexes patterns like:
        - HTML structure templates
        - CSS patterns
        - JS utilities

        Args:
            repo_path: Path to the repository root

        Returns:
            Number of chunks indexed (0 if RAG unavailable)
        """
        if not self._initialized:
            await self.initialize()

        # Graceful degradation: skip indexing if Qdrant is unavailable
        if not self.qdrant_client:
            logger.warning(
                "boilerplate_indexing_skipped_qdrant_unavailable", repo_path=repo_path
            )
            return 0

        logger.info("indexing_boilerplate", repo_path=repo_path)
        chunks: List[DocumentChunk] = []

        # Index HTML templates
        html_files = [
            os.path.join(repo_path, "index.html"),
            os.path.join(repo_path, "frontend/index.html"),
        ]

        for html_file in html_files:
            if os.path.exists(html_file):
                try:
                    with open(html_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    text_chunks = self._chunk_text(content)
                    for idx, chunk in enumerate(text_chunks):
                        chunk_id = self._generate_chunk_id(
                            "boilerplate_html", idx, chunk
                        )
                        chunks.append(
                            DocumentChunk(
                                id=chunk_id,
                                text=chunk,
                                source="boilerplate",
                                metadata={
                                    "file": html_file,
                                    "type": "html_template",
                                    "chunk_index": idx,
                                    "indexed_at": datetime.utcnow().isoformat(),
                                },
                            )
                        )
                    logger.info(
                        "indexed_html_file", file=html_file, chunks=len(text_chunks)
                    )
                except Exception as e:
                    logger.error(
                        "boilerplate_indexing_failed", file=html_file, error=str(e)
                    )

        # Index CSS patterns if exists
        css_files = [
            os.path.join(repo_path, "src/style.css"),
            os.path.join(repo_path, "frontend/src/App.css"),
        ]

        for css_file in css_files:
            if os.path.exists(css_file):
                try:
                    with open(css_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    text_chunks = self._chunk_text(content)
                    for idx, chunk in enumerate(text_chunks):
                        chunk_id = self._generate_chunk_id(
                            "boilerplate_css", idx, chunk
                        )
                        chunks.append(
                            DocumentChunk(
                                id=chunk_id,
                                text=chunk,
                                source="boilerplate",
                                metadata={
                                    "file": css_file,
                                    "type": "css_patterns",
                                    "chunk_index": idx,
                                    "indexed_at": datetime.utcnow().isoformat(),
                                },
                            )
                        )
                except Exception as e:
                    logger.error(
                        "boilerplate_indexing_failed", file=css_file, error=str(e)
                    )

        chunk_count = await self._add_chunks_to_qdrant(chunks)
        logger.info("boilerplate_indexed", chunk_count=chunk_count)
        return chunk_count

    async def index_documentation(self, doc_type: str, content: str) -> int:
        """
        Index official library documentation.

        If Qdrant is unavailable, logs a warning and returns 0.

        Args:
            doc_type: Type of documentation ("react_docs", "tailwind_docs")
            content: Documentation content

        Returns:
            Number of chunks indexed (0 if RAG unavailable)
        """
        if not self._initialized:
            await self.initialize()

        # Graceful degradation: skip indexing if Qdrant is unavailable
        if not self.qdrant_client:
            logger.warning(
                "documentation_indexing_skipped_qdrant_unavailable", doc_type=doc_type
            )
            return 0

        logger.info("indexing_documentation", doc_type=doc_type)
        chunks: List[DocumentChunk] = []

        text_chunks = self._chunk_text(content)
        for idx, chunk in enumerate(text_chunks):
            chunk_id = self._generate_chunk_id(doc_type, idx, chunk)
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    text=chunk,
                    source=doc_type,
                    metadata={
                        "type": doc_type,
                        "chunk_index": idx,
                        "indexed_at": datetime.utcnow().isoformat(),
                    },
                )
            )

        chunk_count = await self._add_chunks_to_qdrant(chunks)
        logger.info("documentation_indexed", doc_type=doc_type, chunk_count=chunk_count)
        return chunk_count

    async def _add_chunks_to_qdrant(self, chunks: List[DocumentChunk]) -> int:
        """
        Add document chunks to Qdrant.

        If Qdrant is unavailable, logs a warning and returns 0 without crashing.

        Args:
            chunks: List of document chunks

        Returns:
            Number of chunks added (0 if Qdrant unavailable)
        """
        if not self.qdrant_client:
            logger.warning(
                "qdrant_unavailable_skipping_chunk_insertion", chunk_count=len(chunks)
            )
            return 0

        if not self.cohere_client:
            logger.warning(
                "cohere_client_unavailable_skipping_chunk_insertion",
                chunk_count=len(chunks),
            )
            return 0

        if not chunks:
            return 0

        try:
            # Embed all chunks
            texts = [chunk.text for chunk in chunks]
            embeddings = await self._embed_texts(texts)

            # Prepare points for Qdrant
            points = []
            for chunk, embedding in zip(chunks, embeddings):
                # Use hash of chunk ID to create a numeric ID
                chunk_numeric_id = int(
                    hashlib.md5(chunk.id.encode()).hexdigest(), 16
                ) % (10**8)
                points.append(
                    PointStruct(
                        id=chunk_numeric_id,
                        vector=embedding,
                        payload={
                            "chunk_id": chunk.id,
                            "text": chunk.text,
                            "source": chunk.source,
                            "metadata": chunk.metadata,
                        },
                    )
                )

            # Upsert to Qdrant
            await self.qdrant_client.upsert(
                collection_name=self.collection_name, points=points
            )

            texts = [chunk.text for chunk in chunks]
            ids = [chunk.id for chunk in chunks]
            self.bm25_index.add_documents(texts, ids)

            logger.info("chunks_added_to_qdrant", count=len(points))
            return len(points)

        except Exception as e:
            logger.error(
                "chunk_insertion_to_qdrant_failed",
                error=str(e),
                chunk_count=len(chunks),
            )
            return 0

    @staticmethod
    def _reciprocal_rank_fusion(
        dense_results: List[RetrievalResult],
        sparse_results: List[Tuple[str, float]],
        k: int = 60,
    ) -> List[RetrievalResult]:
        """Merge dense and sparse results using RRF."""
        scores: Dict[str, float] = {}

        # Build lookup from chunk_id -> RetrievalResult for dense
        dense_map = {r.metadata.get("chunk_id", r.text[:50]): r for r in dense_results}

        for rank, result in enumerate(dense_results):
            doc_id = result.metadata.get("chunk_id", result.text[:50])
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

        for rank, (doc_id, _) in enumerate(sparse_results):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

        # Sort by RRF score
        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)

        # Return RetrievalResults in RRF order, only those we have full data for
        fused = []
        for doc_id in sorted_ids:
            if doc_id in dense_map:
                result = dense_map[doc_id]
                result.score = scores[doc_id]  # overwrite with RRF score
                fused.append(result)
        return fused

    async def retrieve_best_practices(
        self, query: str, source_filter: Optional[str] = None
    ) -> List[RetrievalResult]:
        # 1. Dense retrieval via Qdrant
        dense_results = await self._dense_search(query, source_filter)

        # 2. Sparse retrieval via BM25
        sparse_results = self.bm25_index.search(query, top_k=self.top_k * 2)

        # 3. Fuse via RRF
        if dense_results and sparse_results:
            return self._reciprocal_rank_fusion(dense_results, sparse_results)[
                : self.top_k
            ]
        return dense_results or []

    async def _dense_search(
        self, query: str, source_filter: Optional[str] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve best practice snippets based on user brief.

        Used in Round 1 to provide context for initial generation.

        If Qdrant or embedding model are unavailable, returns empty list
        to allow orchestrator to proceed with simple prompt.

        Args:
            query: User's brief or query
            source_filter: Optional filter by source ("boilerplate", "react_docs", etc.)

        Returns:
            List of relevant chunks ranked by relevance (empty if RAG unavailable)
        """
        if not self._initialized:
            await self.initialize()

        # Graceful degradation: return empty results if RAG is unavailable
        if not self.cohere_client or not self.qdrant_client:
            logger.warning(
                "rag_degraded_skipping_retrieval",
                query=query,
                embedding_available=self.cohere_client is not None,
                qdrant_available=self.qdrant_client is not None,
            )
            return []

        try:
            logger.info("retrieving_best_practices", query=query, source=source_filter)

            # Embed the query
            query_vector = await self._embed_query(query)
            if not query_vector:
                return []

            # Build filter if needed
            query_filter = None
            if source_filter:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="source", match=MatchValue(value=source_filter)
                        )
                    ]
                )

            # Search in Qdrant
            search_results = await self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=self.top_k,
                with_payload=True,
                with_vectors=False,
            )

            # Convert to RetrievalResult
            results = []
            for scored_point in search_results:
                results.append(
                    RetrievalResult(
                        text=scored_point.payload["text"],
                        source=scored_point.payload["source"],
                        score=scored_point.score,
                        metadata=scored_point.payload.get("metadata", {}),
                    )
                )

            logger.info("best_practices_retrieved", count=len(results))
            return results

        except Exception as e:
            logger.warning(
                "best_practices_retrieval_failed_returning_empty",
                error=str(e),
                query=query,
            )
            return []

    async def retrieve_relevant_code_chunks(
        self, instruction: str, existing_code: str, max_chars: int = 3000
    ) -> Tuple[List[RetrievalResult], str]:
        """
        Retrieve most relevant chunks of existing code for Round 2 "Surgical Updates".

        If RAG is unavailable, returns empty results list but still processes existing_code.

        Focuses on:
        1. Boilerplate patterns similar to existing code
        2. Relevant documentation
        3. Code sections semantically similar to the instruction

        Args:
            instruction: The update instruction
            existing_code: The existing codebase
            max_chars: Maximum characters of existing code to return

        Returns:
            Tuple of (retrieval results, relevant code excerpt)
        """
        if not self._initialized:
            await self.initialize()

        logger.info("retrieving_relevant_code_chunks", max_chars=max_chars)

        # Combine instruction with a sample of existing code for context
        query = f"{instruction}\n\n{existing_code[:1000]}"

        # Retrieve best practices (returns empty list if RAG unavailable)
        results = await self.retrieve_best_practices(query, source_filter="boilerplate")

        # Extract the most relevant sections from existing code
        # This works regardless of RAG availability
        relevant_code = self._extract_relevant_sections(
            existing_code, instruction, max_chars
        )

        logger.info(
            "relevant_chunks_retrieved",
            result_count=len(results),
            code_chars=len(relevant_code),
        )
        return results, relevant_code

    def _extract_relevant_sections(
        self, code: str, instruction: str, max_chars: int
    ) -> str:
        """
        Extract relevant sections from code based on instruction.

        Simple heuristic: prioritize sections that likely relate to the instruction.
        """
        # Split by common HTML/CSS sections
        sections = code.split("\n\n")

        # Keywords from instruction
        keywords = instruction.lower().split()

        # Score sections by keyword matches
        scored_sections = []
        for section in sections:
            score = sum(1 for kw in keywords if kw in section.lower())
            if score > 0:
                scored_sections.append((score, section))

        # Sort by score and concatenate until max_chars
        scored_sections.sort(reverse=True, key=lambda x: x[0])

        result = []
        current_len = 0
        for score, section in scored_sections:
            if current_len + len(section) <= max_chars:
                result.append(section)
                current_len += len(section)
            else:
                break

        return "\n\n".join(result)

    async def clear_collection(self) -> None:
        """
        Clear all documents from the collection.

        If Qdrant is unavailable, logs a warning and returns gracefully.
        """
        if not self._initialized:
            await self.initialize()

        if not self.qdrant_client:
            logger.warning("qdrant_unavailable_skipping_collection_clear")
            return

        logger.info("clearing_qdrant_collection")

        try:
            # Delete and recreate the collection
            try:
                await self.qdrant_client.delete_collection(self.collection_name)
            except Exception as e:
                logger.warning("collection_not_found", error=str(e))

            await self._ensure_collection()
            logger.info("collection_cleared")

        except Exception as e:
            logger.error("collection_clear_failed", error=str(e))

    async def index_code_example(
        self, source_name: str, code: str, metadata: dict
    ) -> int:
        """
        Indexes code snippets (split by functions/classes) into a separate Qdrant collection "code_examples".
        """
        if not self._initialized:
            await self.initialize()

        if not self.qdrant_client:
            logger.warning("index_code_example_skipped_qdrant_unavailable")
            return 0

        # Ensure collection exists
        collection_name = "code_examples"
        try:
            await self.qdrant_client.get_collection(collection_name)
        except Exception:
            await self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim, distance=Distance.COSINE
                ),
            )

        # Chunk code by functions/classes
        chunks = []
        import re

        splits = re.split(r"(?=\n(?:def|class)\s+)", "\n" + code)
        splits = [s.strip() for s in splits if s.strip()]

        for idx, split_code in enumerate(splits):
            chunk_id = self._generate_chunk_id(f"code_{source_name}", idx, split_code)
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    text=split_code,
                    source=source_name,
                    metadata={"chunk_index": idx, **metadata},
                )
            )

        if not self.cohere_client or not chunks:
            return 0

        try:
            texts = [chunk.text for chunk in chunks]
            embeddings = await self._embed_texts(texts)

            points = []
            for chunk, embedding in zip(chunks, embeddings):
                if not embedding:
                    continue
                chunk_numeric_id = int(
                    hashlib.md5(chunk.id.encode()).hexdigest(), 16
                ) % (10**8)
                points.append(
                    PointStruct(
                        id=chunk_numeric_id,
                        vector=embedding,
                        payload={
                            "chunk_id": chunk.id,
                            "text": chunk.text,
                            "source": chunk.source,
                            "metadata": chunk.metadata,
                        },
                    )
                )

            if points:
                await self.qdrant_client.upsert(
                    collection_name=collection_name, points=points
                )
            return len(points)
        except Exception as e:
            logger.error("index_code_example_failed", error=str(e))
            return 0


# ============================================================================
# Singleton Instance
# ============================================================================

rag_service = RAGService()
