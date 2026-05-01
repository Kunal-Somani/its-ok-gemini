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
    mock_instance.embed.return_value.embeddings = [[0.1]*1024, [0.2]*1024]
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
    
    with patch.object(rag_service, "_embed_query", return_value=[0.1]*1024):
        results = await rag_service.retrieve_best_practices("how to test")
        assert len(results) == 1
        assert results[0].content == "good code"
        assert results[0].source == "test.py"

@pytest.mark.asyncio
async def test_retrieve_best_practices_unavailable(rag_service):
    rag_service.qdrant_client = None
    results = await rag_service.retrieve_best_practices("test")
    assert results == []
