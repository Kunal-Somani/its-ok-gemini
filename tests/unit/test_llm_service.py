"""
Unit tests for QwenCoderService (llama-cpp-python + GBNF backend).
The Llama model is mocked — no model file required to run tests.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from app.services.llm_service import (
    QwenCoderService,
    PromptBuilder,
    GenerationError,
    ModelNotLoadedError,
    PROJECT_FILES_GRAMMAR_STR,
)


VALID_JSON_OUTPUT = json.dumps(
    {
        "index_html": "<html><body>Hello</body></html>",
        "readme_md": "# Test Project",
        "license": "MIT License 2025",
    }
)


def make_mock_llm_output(
    text: str, prompt_tokens: int = 10, completion_tokens: int = 20
):
    return {
        "choices": [{"text": text}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


@pytest.fixture
def service():
    svc = QwenCoderService()
    mock_llm = MagicMock()
    mock_llm.return_value = make_mock_llm_output(VALID_JSON_OUTPUT)
    svc._llm = mock_llm
    svc._grammar = MagicMock()
    return svc


def test_grammar_string_is_valid():
    """GBNF grammar string must be non-empty and contain required keys."""
    assert "index_html" in PROJECT_FILES_GRAMMAR_STR
    assert "readme_md" in PROJECT_FILES_GRAMMAR_STR
    assert "license" in PROJECT_FILES_GRAMMAR_STR


def test_parse_output_valid(service):
    files = service._parse_output(VALID_JSON_OUTPUT)
    assert "index.html" in files
    assert "README.md" in files
    assert "LICENSE" in files
    assert files["index.html"] == "<html><body>Hello</body></html>"


def test_parse_output_invalid_json_raises(service):
    with pytest.raises(GenerationError):
        service._parse_output("not json at all {{{")


def test_parse_output_missing_key_raises(service):
    bad = json.dumps({"index_html": "<html/>", "readme_md": "# hi"})  # license missing
    with pytest.raises(GenerationError):
        service._parse_output(bad)


@pytest.mark.asyncio
async def test_generate_code_returns_expected_shape(service):
    result = await service.generate_code("Build a portfolio site", round_index=1)
    assert "files" in result
    assert "metadata" in result
    assert result["metadata"]["backend"] == "llama_cpp_gbnf"
    assert "index.html" in result["files"]


@pytest.mark.asyncio
async def test_generate_code_surgical_update_uses_existing_code(service):
    result = await service.generate_code(
        "Add a dark mode toggle",
        round_index=2,
        existing_code="<html>old</html>",
    )
    assert result["files"]["index.html"] is not None
    # Verify surgical prompt was used (prompt contains existing code marker)
    call_args = service._llm.call_args[0][0]
    assert "EXISTING CODE" in call_args


@pytest.mark.asyncio
async def test_generate_code_raises_when_model_not_loaded():
    svc = QwenCoderService()
    # _llm is None and model file doesn't exist
    with patch.object(
        svc, "_ensure_loaded", side_effect=ModelNotLoadedError("no file")
    ):
        with pytest.raises(ModelNotLoadedError):
            await svc.generate_code("test")


def test_prompt_builder_base_contains_system_prompt():
    prompt = PromptBuilder.base_prompt("Build a calculator")
    assert "<|im_start|>system" in prompt
    assert "Build a calculator" in prompt
    assert "<|im_start|>assistant" in prompt


def test_prompt_builder_surgical_contains_existing_code():
    prompt = PromptBuilder.surgical_update_prompt("<html>old</html>", "add nav bar")
    assert "EXISTING CODE" in prompt
    assert "add nav bar" in prompt
