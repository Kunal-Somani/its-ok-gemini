"""
RAG (Retrieval-Augmented Generation) Service for context retrieval.

Provides vector-based retrieval of:
- Repository boilerplate patterns
- Official library documentation (Tailwind, React)
- Best practice code snippets

Uses local embedding model (all-MiniLM-L6-v2) for 100% data sovereignty.
"""

import asyncio
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib

import structlog
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

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
        self.embedding_model: Optional[SentenceTransformer] = None
        self.qdrant_client: Optional[AsyncQdrantClient] = None
        self.collection_name = "code_context"
        self.embedding_dim = settings.RAG_VECTOR_DIMENSION
        self.chunk_size = settings.RAG_CHUNK_SIZE
        self.chunk_overlap = settings.RAG_CHUNK_OVERLAP
        self.top_k = settings.RAG_TOP_K
        self._initialized = False

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
            # Load embedding model on a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.embedding_model = await loop.run_in_executor(
                None,
                lambda: SentenceTransformer(settings.EMBEDDING_MODEL)
            )
            logger.info(
                "embedding_model_loaded",
                model=settings.EMBEDDING_MODEL,
                dimension=self.embedding_dim
            )
        except Exception as e:
            logger.warning(
                "embedding_model_load_failed_graceful_fallback",
                model=settings.EMBEDDING_MODEL,
                error=str(e),
                fallback="simple_prompt_mode"
            )
            self.embedding_model = None
            initialization_failed = True

        try:
            # Initialize Qdrant client
            self.qdrant_client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None
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
                fallback="simple_prompt_mode"
            )
            self.qdrant_client = None
            initialization_failed = True

        # Mark as initialized even if dependencies failed
        # The orchestrator will work with degraded RAG capabilities
        self._initialized = True

        if initialization_failed:
            logger.warning(
                "rag_service_degraded_mode",
                embedding_model_available=self.embedding_model is not None,
                qdrant_available=self.qdrant_client is not None,
                message="RAG service operating in degraded mode. Retrieval operations will return empty results."
            )
        else:
            logger.info("rag_service_initialized_successfully")

    async def _ensure_collection(self) -> None:
        """Ensure Qdrant collection exists."""
        try:
            await self.qdrant_client.get_collection(self.collection_name)
            logger.info("collection_exists", name=self.collection_name)
        except Exception:
            logger.info("creating_collection", name=self.collection_name)
            await self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
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
        """
        Embed a list of texts using the embedding model.

        If embedding model is unavailable, returns empty embeddings.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (empty list if model unavailable)
        """
        if not self.embedding_model:
            logger.warning("embedding_model_unavailable_returning_empty_embeddings", text_count=len(texts))
            return [[] for _ in texts]

        try:
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self.embedding_model.encode(texts, convert_to_tensor=False)
            )
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error("embedding_failed_returning_empty", error=str(e), text_count=len(texts))
            return [[] for _ in texts]

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
                "boilerplate_indexing_skipped_qdrant_unavailable",
                repo_path=repo_path
            )
            return 0

        logger.info("indexing_boilerplate", repo_path=repo_path)
        chunks: List[DocumentChunk] = []

        # Index HTML templates
        html_files = [
            os.path.join(repo_path, "index.html"),
            os.path.join(repo_path, "frontend/index.html")
        ]

        for html_file in html_files:
            if os.path.exists(html_file):
                try:
                    with open(html_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    text_chunks = self._chunk_text(content)
                    for idx, chunk in enumerate(text_chunks):
                        chunk_id = self._generate_chunk_id("boilerplate_html", idx, chunk)
                        chunks.append(
                            DocumentChunk(
                                id=chunk_id,
                                text=chunk,
                                source="boilerplate",
                                metadata={
                                    "file": html_file,
                                    "type": "html_template",
                                    "chunk_index": idx,
                                    "indexed_at": datetime.utcnow().isoformat()
                                }
                            )
                        )
                    logger.info("indexed_html_file", file=html_file, chunks=len(text_chunks))
                except Exception as e:
                    logger.error("boilerplate_indexing_failed", file=html_file, error=str(e))

        # Index CSS patterns if exists
        css_files = [
            os.path.join(repo_path, "src/style.css"),
            os.path.join(repo_path, "frontend/src/App.css")
        ]

        for css_file in css_files:
            if os.path.exists(css_file):
                try:
                    with open(css_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    text_chunks = self._chunk_text(content)
                    for idx, chunk in enumerate(text_chunks):
                        chunk_id = self._generate_chunk_id("boilerplate_css", idx, chunk)
                        chunks.append(
                            DocumentChunk(
                                id=chunk_id,
                                text=chunk,
                                source="boilerplate",
                                metadata={
                                    "file": css_file,
                                    "type": "css_patterns",
                                    "chunk_index": idx,
                                    "indexed_at": datetime.utcnow().isoformat()
                                }
                            )
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
                "documentation_indexing_skipped_qdrant_unavailable",
                doc_type=doc_type
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
                        "indexed_at": datetime.utcnow().isoformat()
                    }
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
            logger.warning("qdrant_unavailable_skipping_chunk_insertion", chunk_count=len(chunks))
            return 0

        if not self.embedding_model:
            logger.warning("embedding_model_unavailable_skipping_chunk_insertion", chunk_count=len(chunks))
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
                chunk_numeric_id = int(hashlib.md5(chunk.id.encode()).hexdigest(), 16) % (10 ** 8)
                points.append(
                    PointStruct(
                        id=chunk_numeric_id,
                        vector=embedding,
                        payload={
                            "chunk_id": chunk.id,
                            "text": chunk.text,
                            "source": chunk.source,
                            "metadata": chunk.metadata
                        }
                    )
                )

            # Upsert to Qdrant
            await self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points
            )

            logger.info("chunks_added_to_qdrant", count=len(points))
            return len(points)

        except Exception as e:
            logger.error("chunk_insertion_to_qdrant_failed", error=str(e), chunk_count=len(chunks))
            return 0

    async def retrieve_best_practices(self, query: str, source_filter: Optional[str] = None) -> List[RetrievalResult]:
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
        if not self.embedding_model or not self.qdrant_client:
            logger.warning(
                "rag_degraded_skipping_retrieval",
                query=query,
                embedding_available=self.embedding_model is not None,
                qdrant_available=self.qdrant_client is not None
            )
            return []

        try:
            logger.info("retrieving_best_practices", query=query, source=source_filter)

            # Embed the query
            query_embedding = await self._embed_texts([query])
            query_vector = query_embedding[0]

            # Build filter if needed
            query_filter = None
            if source_filter:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="source",
                            match=MatchValue(value=source_filter)
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
                with_vectors=False
            )

            # Convert to RetrievalResult
            results = []
            for scored_point in search_results:
                results.append(
                    RetrievalResult(
                        text=scored_point.payload["text"],
                        source=scored_point.payload["source"],
                        score=scored_point.score,
                        metadata=scored_point.payload.get("metadata", {})
                    )
                )

            logger.info("best_practices_retrieved", count=len(results))
            return results

        except Exception as e:
            logger.warning(
                "best_practices_retrieval_failed_returning_empty",
                error=str(e),
                query=query
            )
            return []

    async def retrieve_relevant_code_chunks(
        self,
        instruction: str,
        existing_code: str,
        max_chars: int = 3000
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
        relevant_code = self._extract_relevant_sections(existing_code, instruction, max_chars)

        logger.info("relevant_chunks_retrieved", result_count=len(results), code_chars=len(relevant_code))
        return results, relevant_code

    def _extract_relevant_sections(self, code: str, instruction: str, max_chars: int) -> str:
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


# ============================================================================
# Singleton Instance
# ============================================================================

rag_service = RAGService()
