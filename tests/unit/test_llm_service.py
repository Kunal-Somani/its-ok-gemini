import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_service import AnthropicService, APIError

class MockToolUseBlock:
    def __init__(self, input_dict):
        self.type = "tool_use"
        self.input = input_dict

class MockUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

class MockResponse:
    def __init__(self, content, model, input_tokens, output_tokens):
        self.content = content
        self.model = model
        self.usage = MockUsage(input_tokens, output_tokens)

@pytest.fixture
def mock_anthropic_client():
    with patch("app.services.llm_service.anthropic.AsyncAnthropic") as MockClient:
        mock_instance = AsyncMock()
        MockClient.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def service(mock_anthropic_client):
    return AnthropicService()

@pytest.mark.asyncio
async def test_generate_code_tool_use(service, mock_anthropic_client):
    # Setup mock response with a valid tool_use block
    tool_input = {
        "index_html": "<html><body>Hello</body></html>",
        "readme_md": "# Project",
        "license": "MIT"
    }
    mock_block = MockToolUseBlock(tool_input)
    mock_response = MockResponse(content=[mock_block], model="claude-3-opus", input_tokens=10, output_tokens=50)
    
    mock_anthropic_client.messages.create.return_value = mock_response
    
    result = await service.generate_code("Create a simple website")
    
    assert "files" in result
    assert result["files"]["index.html"] == "<html><body>Hello</body></html>"
    assert result["files"]["README.md"] == "# Project"
    assert result["files"]["LICENSE"] == "MIT"
    
    assert "metadata" in result
    assert result["metadata"]["prompt_token_count"] == 10
    assert result["metadata"]["completion_token_count"] == 50
    assert result["metadata"]["backend"] == "anthropic_tool_use"

@pytest.mark.asyncio
async def test_generate_code_tool_use_missing(service, mock_anthropic_client):
    class MockTextBlock:
        def __init__(self):
            self.type = "text"
            self.text = "I failed to use the tool."
            
    mock_response = MockResponse(content=[MockTextBlock()], model="claude-3-opus", input_tokens=10, output_tokens=50)
    mock_anthropic_client.messages.create.return_value = mock_response
    
    with pytest.raises(APIError, match="Failed to parse Anthropic tool_use:"):
        await service.generate_code("Create a simple website")

@pytest.mark.asyncio
async def test_generate_code_tool_use_missing_keys(service, mock_anthropic_client):
    # Setup mock response with a tool_use block missing required keys
    tool_input = {
        "index_html": "<html><body>Hello</body></html>"
    }
    mock_block = MockToolUseBlock(tool_input)
    mock_response = MockResponse(content=[mock_block], model="claude-3-opus", input_tokens=10, output_tokens=50)
    
    mock_anthropic_client.messages.create.return_value = mock_response
    
    with pytest.raises(APIError, match="Failed to parse Anthropic tool_use:"):
        await service.generate_code("Create a simple website")
