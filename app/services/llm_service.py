import json
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
import structlog
import anthropic
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ============================================================================
# Custom Exceptions
# ============================================================================


class RateLimitError(Exception):
    """Raised when the API returns a 429 Rate Limit error."""

    pass


class APIError(Exception):
    """Raised when the API returns an unexpected error or parsing fails."""

    pass


# ============================================================================
# Tool Schemas
# ============================================================================

CODE_GENERATION_TOOL = {
    "name": "generate_project_files",
    "description": "Generate the complete set of project files for a web application.",
    "input_schema": {
        "type": "object",
        "properties": {
            "index_html": {
                "type": "string",
                "description": "Complete HTML file content. Must be a single-file app using Tailwind CDN."
            },
            "readme_md": {
                "type": "string",
                "description": "Professional README.md for the project."
            },
            "license": {
                "type": "string",
                "description": "MIT License text with current year."
            }
        },
        "required": ["index_html", "readme_md", "license"]
    }
}


# ============================================================================
# Prompt Builder
# ============================================================================


class PromptBuilder:
    """Constructs prompts for code generation with strict formatting."""

    @staticmethod
    def base_prompt(instruction: str) -> str:
        """Base prompt for initial code generation."""
        return f"User Instruction:\n{instruction}\n"

    @staticmethod
    def surgical_update_prompt(existing_code: str, instruction: str) -> str:
        """Prompt for surgical updates to existing code."""
        return (
            "You are making a surgical update to an existing codebase.\n"
            "Preserve all existing functionality while applying the new instruction.\n\n"
            "--- EXISTING CODE ---\n"
            f"{existing_code}\n\n"
            "--- UPDATE INSTRUCTION ---\n"
            f"{instruction}\n"
        )
        
    @staticmethod
    def vision_prompt(instruction: str, base64_images: List[str], mime_type: str = "image/png") -> List[Dict[str, Any]]:
        """Constructs multimodal message content for vision tasks."""
        content: List[Dict[str, Any]] = []
        for b64 in base64_images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": b64,
                }
            })
        content.append({"type": "text", "text": f"User Instruction:\n{instruction}\n"})
        return content


# ============================================================================
# Anthropic Service - Official SDK Backend
# ============================================================================


class AnthropicService:
    """
    Uses Anthropic official Python SDK for code generation.
    """

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = settings.ANTHROPIC_MODEL
        self.max_tokens = settings.ANTHROPIC_MAX_TOKENS
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

        logger.info(
            "anthropic_service_initialized",
            model=self.model,
            max_tokens=self.max_tokens,
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(anthropic.RateLimitError),
        reraise=True,
    )
    async def _call_anthropic_api(self, **kwargs) -> Any:
        """
        Call Anthropic API with exponential backoff for rate limits.
        """
        try:
            return await self.client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            logger.warning("anthropic_rate_limit_encountered")
            raise  # Will be caught and retried by tenacity
        except Exception as e:
            logger.error("anthropic_api_error", error=str(e))
            raise APIError(f"API Error: {str(e)}")

    async def generate_code(
        self,
        instruction: str,
        round_index: int = 1,
        existing_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate or update code using Anthropic backend.
        """
        if round_index > 1 and existing_code:
            prompt_text = PromptBuilder.surgical_update_prompt(
                existing_code, instruction
            )
        else:
            prompt_text = PromptBuilder.base_prompt(instruction)

        system_prompt = "You are an expert full-stack developer. Generate production-ready web applications."

        try:
            logger.info("calling_anthropic", model=self.model)

            try:
                response = await self._call_anthropic_api(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    tools=[CODE_GENERATION_TOOL],
                    tool_choice={"type": "tool", "name": "generate_project_files"},
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt_text}],
                )
            except anthropic.RateLimitError as e:
                raise RateLimitError(str(e))

            try:
                tool_use_block = next(b for b in response.content if b.type == "tool_use")
                files = {
                    "index.html": tool_use_block.input["index_html"],
                    "README.md": tool_use_block.input["readme_md"],
                    "LICENSE": tool_use_block.input["license"]
                }

                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens

                return {
                    "files": files,
                    "metadata": {
                        "model": response.model,
                        "prompt_token_count": input_tokens,
                        "completion_token_count": output_tokens,
                        "total_token_count": input_tokens + output_tokens,
                        "backend": "anthropic_tool_use",
                    },
                }
            except (StopIteration, KeyError, AttributeError) as e:
                logger.error(
                    "response_parsing_failed",
                    error=str(e),
                    response=getattr(response, "content", ""),
                )
                raise APIError(f"Failed to parse Anthropic response: {str(e)}")

        except (RateLimitError, APIError) as e:
            logger.error("generation_failed", error=str(e))
            raise
            
    async def stream_generation(
        self,
        instruction: str,
        round_index: int = 1,
        existing_code: Optional[str] = None,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """
        Stream generation. Yields partial tokens and returns a final dict.
        """
        if round_index > 1 and existing_code:
            prompt_text = PromptBuilder.surgical_update_prompt(
                existing_code, instruction
            )
        else:
            prompt_text = PromptBuilder.base_prompt(instruction)

        system_prompt = "You are an expert full-stack developer. Generate production-ready web applications."

        logger.info("streaming_anthropic", model=self.model)

        input_tokens = 0
        output_tokens = 0
        tool_input_json = ""

        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                tools=[CODE_GENERATION_TOOL],
                tool_choice={"type": "tool", "name": "generate_project_files"},
                system=system_prompt,
                messages=[{"role": "user", "content": prompt_text}],
            ) as stream:
                async for event in stream:
                    if event.type == "message_start":
                        input_tokens = event.message.usage.input_tokens
                    elif event.type == "content_block_delta" and event.delta.type == "input_json_delta":
                        chunk = event.delta.partial_json
                        tool_input_json += chunk
                        yield chunk
                    elif event.type == "message_delta":
                        output_tokens = event.usage.output_tokens

            parsed_input = json.loads(tool_input_json)
            files = {
                "index.html": parsed_input.get("index_html", ""),
                "README.md": parsed_input.get("readme_md", ""),
                "LICENSE": parsed_input.get("license", "")
            }
            
            yield {
                "files": files,
                "metadata": {
                    "model": self.model,
                    "prompt_token_count": input_tokens,
                    "completion_token_count": output_tokens,
                    "total_token_count": input_tokens + output_tokens,
                    "backend": "anthropic_tool_use_stream",
                },
            }
        except Exception as e:
            logger.error("stream_failed", error=str(e))
            raise APIError(f"Stream generation failed: {str(e)}")

    async def generate_code_with_vision(
        self,
        instruction: str,
        images: List[str],
        mime_type: str = "image/png"
    ) -> Dict[str, Any]:
        """
        Generate code using Anthropic backend with vision support.
        """
        content = PromptBuilder.vision_prompt(instruction, images, mime_type)
        system_prompt = "You are an expert full-stack developer. Generate production-ready web applications."

        try:
            logger.info("calling_anthropic_with_vision", model=self.model)
            response = await self._call_anthropic_api(
                model=self.model,
                max_tokens=self.max_tokens,
                tools=[CODE_GENERATION_TOOL],
                tool_choice={"type": "tool", "name": "generate_project_files"},
                system=system_prompt,
                messages=[{"role": "user", "content": content}],
            )
            
            tool_use_block = next(b for b in response.content if b.type == "tool_use")
            files = {
                "index.html": tool_use_block.input["index_html"],
                "README.md": tool_use_block.input["readme_md"],
                "LICENSE": tool_use_block.input["license"]
            }

            return {
                "files": files,
                "metadata": {
                    "model": response.model,
                    "prompt_token_count": response.usage.input_tokens,
                    "completion_token_count": response.usage.output_tokens,
                    "total_token_count": response.usage.input_tokens + response.usage.output_tokens,
                    "backend": "anthropic_tool_use",
                },
            }
        except (StopIteration, KeyError, AttributeError) as e:
            logger.error("vision_parsing_failed", error=str(e))
            raise APIError(f"Failed to parse Anthropic tool_use: {str(e)}")
        except anthropic.RateLimitError as e:
            raise RateLimitError(str(e))
        except Exception as e:
            raise APIError(str(e))

# Default instance
llm_service = AnthropicService()
