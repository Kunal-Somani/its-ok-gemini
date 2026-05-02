import pytest
from unittest.mock import AsyncMock, patch
from app.services.rag_service import RAGService


@pytest.fixture
def rag_service():
    return RAGService()


def test_chunk_text(rag_service):
    text = "A" * 1000
    chunks = rag_service._chunk_text(text, chunk_size=500, overlap=100)
    assert len(chunks) > 1
    assert len(chunks[0]) == 500


@patch("app.services.rag_service.cohere.AsyncClient")
@pytest.mark.asyncio
async def test_embed_texts(mock_cohere, rag_service):
    mock_instance = AsyncMock()
    mock_instance.embed.return_value.embeddings = [[0.1] * 1024, [0.2] * 1024]
    rag_service.cohere_client = mock_instance
    embeddings = await rag_service._embed_texts(["test1", "test2"])
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1024


@patch("app.services.rag_service.AsyncQdrantClient")
@pytest.mark.asyncio
async def test_retrieve_best_practices(mock_qdrant, rag_service):
    mock_instance = AsyncMock()
    mock_point = AsyncMock()
    mock_point.payload = {"content": "good code", "source": "test.py"}
    mock_point.score = 0.9
    mock_instance.search.return_value = [mock_point]
    rag_service.qdrant_client = mock_instance

    with patch.object(rag_service, "_embed_query", return_value=[0.1] * 1024):
        results = await rag_service._dense_search("how to test")
        assert len(results) == 1
        assert results[0].text == "good code"
        assert results[0].source == "test.py"


@pytest.mark.asyncio
async def test_retrieve_best_practices_unavailable(rag_service):
    rag_service.qdrant_client = None
    results = await rag_service.retrieve_best_practices("test")
    assert results == []


def test_bm25_search():
    from app.services.rag_service import BM25Index

    idx = BM25Index()
    idx.add_documents(
        [
            "import React from 'react'",
            "fastapi background tasks",
            "qdrant dense retrieval",
        ],
        ["id1", "id2", "id3"],
    )
    res = idx.search("fastapi", top_k=2)
    assert len(res) == 2
    assert res[0][0] == "id2"


def test_rrf_fusion():
    from app.services.rag_service import RAGService, RetrievalResult

    dense = [
        RetrievalResult(
            text="text1", source="src", score=0.9, metadata={"chunk_id": "id1"}
        ),
        RetrievalResult(
            text="text2", source="src", score=0.8, metadata={"chunk_id": "id2"}
        ),
    ]
    sparse = [("id2", 1.5), ("id3", 1.2)]

    fused = RAGService._reciprocal_rank_fusion(dense, sparse, k=60)
    assert len(fused) == 2
    assert fused[0].metadata["chunk_id"] == "id2"
    assert fused[1].metadata["chunk_id"] == "id1"


@patch("app.services.rag_service.RAGService._dense_search")
@pytest.mark.asyncio
async def test_hybrid_retrieve(mock_dense, rag_service):
    from app.services.rag_service import RetrievalResult

    mock_dense.return_value = [
        RetrievalResult(
            text="text1", source="src", score=0.9, metadata={"chunk_id": "id1"}
        ),
        RetrievalResult(
            text="text2", source="src", score=0.8, metadata={"chunk_id": "id2"}
        ),
    ]
    rag_service.top_k = 1

    rag_service.bm25_index.search = lambda q, top_k: [("id2", 1.5)]

    results = await rag_service.retrieve_best_practices("test")
    assert len(results) == 1
    assert results[0].metadata["chunk_id"] == "id2"
