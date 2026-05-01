import json
from typing import List, Dict, Any, Optional
import structlog
import anthropic
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

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
# Prompt Builder
# ============================================================================

class PromptBuilder:
    """Constructs prompts for code generation with strict formatting."""
    
    @staticmethod
    def base_prompt(instruction: str) -> str:
        """Base prompt for initial code generation."""
        return (
            "User Instruction:\n"
            f"{instruction}\n"
        )

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
            max_tokens=self.max_tokens
        )
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(anthropic.RateLimitError),
        reraise=True
    )
    async def _call_anthropic_api(self, **kwargs) -> Any:
        """
        Call Anthropic API with exponential backoff for rate limits.
        """
        try:
            return await self.client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
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
        images: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate or update code using Anthropic backend.
        
        Args:
            instruction: User's code generation instruction
            round_index: Iteration number (>1 triggers surgical updates)
            existing_code: Previous version for updates
            images: Image attachments for vision-based generation
        
        Returns:
            Dict with 'files' (parsed JSON) and 'metadata' (token usage)
        """
        
        # 1. Build appropriate prompt
        if round_index > 1 and existing_code:
            prompt_text = PromptBuilder.surgical_update_prompt(existing_code, instruction)
        else:
            prompt_text = PromptBuilder.base_prompt(instruction)
        
        # System prompt as instructed
        system_prompt = (
            "You are an expert full-stack developer. Always return ONLY valid JSON: "
            '{"index.html": "...", "README.md": "...", "LICENSE": "..."}'
        )

        content = []
        
        # Add images if provided (Anthropic SDK format)
        if images:
            for img_data in images:
                image_bytes = img_data.get("data")
                mime_type = img_data.get("mime_type", "image/png")
                import base64
                if image_bytes:
                    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": encoded_image
                        }
                    })

        content.append({
            "type": "text",
            "text": prompt_text
        })
        
        # 2. Call Anthropic API
        try:
            logger.info("calling_anthropic", model=self.model)
            
            try:
                response = await self._call_anthropic_api(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": content
                        }
                    ]
                )
            except anthropic.RateLimitError as e:
                raise RateLimitError(str(e))
            
            # 3. Extract and parse response
            try:
                # Get text block from response content
                message_content = response.content[0].text
                
                # Clean JSON extraction
                json_str = message_content.strip()
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                if json_str.startswith("```"):
                    json_str = json_str[3:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
                json_str = json_str.strip()
                
                parsed_json = json.loads(json_str)
                
                # Extract token usage
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                
                return {
                    "files": parsed_json,
                    "metadata": {
                        "model": self.model,
                        "prompt_token_count": input_tokens,
                        "completion_token_count": output_tokens,
                        "total_token_count": input_tokens + output_tokens,
                        "backend": "anthropic"
                    }
                }
            except (KeyError, IndexError, json.JSONDecodeError, AttributeError) as e:
                logger.error("response_parsing_failed", error=str(e), response=getattr(response, "content", ""))
                raise APIError(f"Failed to parse Anthropic response: {str(e)}")
        
        except (RateLimitError, APIError) as e:
            logger.error("generation_failed", error=str(e))
            raise

# Default instance
llm_service = AnthropicService()
