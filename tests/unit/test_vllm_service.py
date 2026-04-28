"""
Unit tests for vLLM LLM Service Integration

Tests:
- Token counting functionality
- Context window validation
- API communication with vLLM
- Response parsing
- Error handling
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json
from typing import Dict, Any

from app.services.llm_service import (
    vLLMService,
    TokenCounter,
    PromptBuilder,
    APIError,
    RateLimitError,
    ContextWindowExceededError,
    get_llm_service
)


class TestPromptBuilder:
    """Test prompt construction for different scenarios."""
    
    def test_base_prompt(self):
        """Test base prompt generation."""
        instruction = "Create a React app"
        prompt = PromptBuilder.base_prompt(instruction)
        
        assert "expert code generator" in prompt
        assert instruction in prompt
        assert "JSON" in prompt
    
    def test_surgical_update_prompt(self):
        """Test surgical update prompt with existing code."""
        existing = "original code here"
        instruction = "Add dark mode"
        prompt = PromptBuilder.surgical_update_prompt(existing, instruction)
        
        assert "surgical update" in prompt.lower()
        assert existing in prompt
        assert instruction in prompt
        assert "JSON" in prompt


class TestTokenCounter:
    """Test token counting functionality."""
    
    @pytest.mark.asyncio
    async def test_count_tokens(self):
        """Test token counting for a text."""
        # Mock the tokenizer loading
        with patch('app.services.llm_service.AutoTokenizer') as mock_tokenizer_class:
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = [1] * 10  # 10 tokens
            mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
            
            # Test token counting
            count = await TokenCounter.count_tokens("test text", "deepseek-coder-v2")
            
            assert count == 10
            assert "deepseek-coder-v2" in TokenCounter._tokenizers
    
    @pytest.mark.asyncio
    async def test_tokenizer_caching(self):
        """Test that tokenizers are cached after first load."""
        with patch('app.services.llm_service.AutoTokenizer') as mock_tokenizer_class:
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = [1] * 5
            mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
            
            # First call
            await TokenCounter.count_tokens("text1", "deepseek-coder-v2")
            call_count_1 = mock_tokenizer_class.from_pretrained.call_count
            
            # Second call (should use cache)
            await TokenCounter.count_tokens("text2", "deepseek-coder-v2")
            call_count_2 = mock_tokenizer_class.from_pretrained.call_count
            
            # Should not have called from_pretrained again
            assert call_count_2 == call_count_1


class TestvLLMService:
    """Test vLLM service functionality."""
    
    def test_service_initialization(self):
        """Test service initializes with correct configuration."""
        service = vLLMService()
        
        assert service.endpoint is not None
        assert service.model is not None
        assert service.context_window == 128000
        assert service.SAMPLING_PARAMS["temperature"] == 0.1
    
    @pytest.mark.asyncio
    async def test_context_window_validation_pass(self):
        """Test context window validation passes for small prompt."""
        service = vLLMService()
        service.context_window = 1000
        
        with patch.object(TokenCounter, 'count_tokens', return_value=100):
            # Should not raise
            token_count = await service._validate_context_window("short text")
            assert token_count == 100
    
    @pytest.mark.asyncio
    async def test_context_window_validation_fail(self):
        """Test context window validation fails for large prompt."""
        service = vLLMService()
        service.context_window = 1000
        
        with patch.object(TokenCounter, 'count_tokens', return_value=500):
            # max_tokens=8192 + safety=500 > 1000
            with pytest.raises(ContextWindowExceededError):
                await service._validate_context_window("very long text")
    
    @pytest.mark.asyncio
    async def test_call_vllm_api_success(self):
        """Test successful vLLM API call."""
        service = vLLMService()
        
        expected_response = {
            "choices": [{"message": {"content": "response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected_response
            
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            result = await service._call_vllm_api({"test": "payload"})
            
            assert result == expected_response
    
    @pytest.mark.asyncio
    async def test_call_vllm_api_rate_limit(self):
        """Test rate limit error handling."""
        service = vLLMService()
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 429
            
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            with pytest.raises(RateLimitError):
                await service._call_vllm_api({"test": "payload"})
    
    @pytest.mark.asyncio
    async def test_call_vllm_api_error(self):
        """Test API error handling."""
        service = vLLMService()
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Server error"
            
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            with pytest.raises(APIError):
                await service._call_vllm_api({"test": "payload"})
    
    @pytest.mark.asyncio
    async def test_generate_code_base_prompt(self):
        """Test code generation with base prompt."""
        service = vLLMService()
        
        expected_files = {
            "index.html": "<html>...</html>",
            "README.md": "# Project",
            "LICENSE": "MIT"
        }
        
        expected_response = {
            "choices": [{"message": {"content": json.dumps(expected_files)}}],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 200,
                "total_tokens": 250
            }
        }
        
        with patch.object(service, '_call_vllm_api', return_value=expected_response):
            with patch.object(TokenCounter, 'count_tokens', return_value=50):
                result = await service.generate_code("Create a website")
                
                assert result["files"] == expected_files
                assert result["metadata"]["model"] == service.model
                assert result["metadata"]["total_token_count"] == 250
    
    @pytest.mark.asyncio
    async def test_generate_code_surgical_update(self):
        """Test code generation with surgical update."""
        service = vLLMService()
        existing_code = "old html"
        
        expected_response = {
            "choices": [{"message": {"content": json.dumps({
                "index.html": "updated html",
                "README.md": "...",
                "LICENSE": "..."
            })}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
        }
        
        with patch.object(service, '_call_vllm_api', return_value=expected_response):
            with patch.object(TokenCounter, 'count_tokens', return_value=100):
                result = await service.generate_code(
                    "Add dark mode",
                    round_index=2,
                    existing_code=existing_code
                )
                
                assert "index.html" in result["files"]
                assert result["metadata"]["backend"] == "vllm"
    
    @pytest.mark.asyncio
    async def test_generate_code_json_cleanup(self):
        """Test JSON response cleanup (handles markdown wrapping)."""
        service = vLLMService()
        
        # Response wrapped in markdown code blocks
        messy_response = {
            "choices": [{"message": {"content": """```json
{
  "index.html": "<html></html>",
  "README.md": "readme",
  "LICENSE": "license"
}
```"""}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150}
        }
        
        with patch.object(service, '_call_vllm_api', return_value=messy_response):
            with patch.object(TokenCounter, 'count_tokens', return_value=50):
                result = await service.generate_code("Create site")
                
                # Should successfully parse despite markdown wrapping
                assert "index.html" in result["files"]
                assert result["files"]["index.html"] == "<html></html>"


class TestServiceFactory:
    """Test the LLM service factory."""
    
    def test_get_vllm_service(self):
        """Test getting vLLM service."""
        service = get_llm_service()
        
        assert isinstance(service, vLLMService)


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self):
        """Test handling of invalid JSON in response."""
        service = vLLMService()
        
        bad_response = {
            "choices": [{"message": {"content": "not valid json"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}
        }
        
        with patch.object(service, '_call_vllm_api', return_value=bad_response):
            with patch.object(TokenCounter, 'count_tokens', return_value=50):
                with pytest.raises(APIError):
                    await service.generate_code("test")
    
    @pytest.mark.asyncio
    async def test_missing_response_fields(self):
        """Test handling of missing response fields."""
        service = vLLMService()
        
        incomplete_response = {
            "choices": [{"message": {"content": ""}}],
            # Missing 'usage' field
        }
        
        with patch.object(service, '_call_vllm_api', return_value=incomplete_response):
            with patch.object(TokenCounter, 'count_tokens', return_value=50):
                with pytest.raises(APIError):
                    await service.generate_code("test")


# Integration tests (requires actual vLLM server running)

@pytest.mark.integration
class TestvLLMIntegration:
    """Integration tests with real vLLM server (optional)."""
    
    @pytest.mark.asyncio
    async def test_real_vllm_connection(self):
        """Test connection to real vLLM server.
        
        Requires vLLM running at http://localhost:8001/v1
        """
        service = vLLMService()
        
        try:
            result = await service.generate_code("Hello")
            assert "files" in result
            assert "metadata" in result
            assert result["metadata"]["backend"] == "vllm"
        except APIError as e:
            pytest.skip(f"vLLM server not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
