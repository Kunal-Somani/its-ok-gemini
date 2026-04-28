import httpx
import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import structlog

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

class ContextWindowExceededError(Exception):
    """Raised when the token count exceeds the model's context window."""
    pass

# ============================================================================
# Token Counter - Uses transformers library for local token counting
# ============================================================================

class TokenCounter:
    """
    Manages tokenization for DeepSeek-Coder and other models.
    Uses the transformers library to calculate token counts locally,
    ensuring we don't exceed the context window before making API calls.
    """
    
    _tokenizers: Dict[str, Any] = {}
    
    # Tokenizer model mappings
    TOKENIZER_MODELS = {
        "deepseek-coder-v2": "deepseek-ai/deepseek-coder-6.7b-base",
        "codellama-70b": "codellama/CodeLlama-70b-hf",
    }
    
    @classmethod
    async def get_tokenizer(cls, model: str):
        """Lazy-load the appropriate tokenizer for the model."""
        if model not in cls._tokenizers:
            try:
                from transformers import AutoTokenizer
                
                tokenizer_model = cls.TOKENIZER_MODELS.get(
                    model, 
                    "deepseek-ai/deepseek-coder-6.7b-base"  # Default to DeepSeek
                )
                
                # Load tokenizer asynchronously
                loop = asyncio.get_event_loop()
                tokenizer = await loop.run_in_executor(
                    None,
                    lambda: AutoTokenizer.from_pretrained(tokenizer_model, trust_remote_code=True)
                )
                cls._tokenizers[model] = tokenizer
                logger.info("tokenizer_loaded", model=model, tokenizer_model=tokenizer_model)
            except Exception as e:
                logger.error("tokenizer_load_failed", model=model, error=str(e))
                raise APIError(f"Failed to load tokenizer for {model}: {str(e)}")
        
        return cls._tokenizers[model]
    
    @classmethod
    async def count_tokens(cls, text: str, model: str) -> int:
        """Count tokens in text using the appropriate tokenizer."""
        tokenizer = await cls.get_tokenizer(model)
        
        try:
            tokens = tokenizer.encode(text, add_special_tokens=True)
            return len(tokens)
        except Exception as e:
            logger.error("token_counting_failed", model=model, error=str(e))
            # Fallback: rough estimation (1 token ≈ 4 characters)
            return len(text) // 4

# ============================================================================
# Prompt Builder
# ============================================================================

class PromptBuilder:
    """Constructs prompts for code generation with strict formatting."""
    
    @staticmethod
    def base_prompt(instruction: str) -> str:
        """Base prompt for initial code generation."""
        return (
            "You are an expert full-stack developer specialized in code generation. "
            "Generate clean, well-formatted, production-ready code.\n\n"
            "User Instruction:\n"
            f"{instruction}\n\n"
            "Return ONLY valid JSON with the following structure: "
            '{"index.html": "...", "README.md": "...", "LICENSE": "..."}'
        )

    @staticmethod
    def surgical_update_prompt(existing_code: str, instruction: str) -> str:
        """Prompt for surgical updates to existing code."""
        return (
            "You are an expert developer making a surgical update to an existing codebase.\n"
            "Preserve all existing functionality while applying the new instruction.\n\n"
            "--- EXISTING CODE ---\n"
            f"{existing_code}\n\n"
            "--- UPDATE INSTRUCTION ---\n"
            f"{instruction}\n\n"
            "Return ONLY valid JSON with the following structure: "
            '{"index.html": "...", "README.md": "...", "LICENSE": "..."}'
        )

# ============================================================================
# vLLM Service - OpenAI-Compatible Backend
# ============================================================================

class vLLMService:
    """
    Uses vLLM for local/self-hosted inference with OpenAI-compatible API.
    Supports DeepSeek-Coder-V2 and CodeLlama-70B models.
    
    Sampling parameters optimized for code generation:
    - temperature: 0.1 (low for strict syntax adherence)
    - top_p: 0.95 (nucleus sampling for diversity)
    - frequency_penalty: 0.2 (reduce repetition)
    """
    
    # Enterprise-standard sampling parameters
    SAMPLING_PARAMS = {
        "temperature": 0.1,      # Low temperature for strict code generation
        "top_p": 0.95,           # Nucleus sampling cutoff
        "frequency_penalty": 0.2, # Reduce repetitive token generation
        "max_tokens": 8192,      # Max output tokens
    }
    
    def __init__(self):
        self.endpoint = settings.VLLM_ENDPOINT
        self.model = settings.VLLM_MODEL
        self.context_window = settings.VLLM_CONTEXT_WINDOW
        self.timeout = settings.VLLM_TIMEOUT
        
        logger.info(
            "vllm_service_initialized",
            endpoint=self.endpoint,
            model=self.model,
            context_window=self.context_window
        )
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True
    )
    async def _call_vllm_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call vLLM OpenAI-compatible API with exponential backoff for rate limits.
        """
        url = f"{self.endpoint}/chat/completions"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=float(self.timeout)
                )
            except httpx.RequestError as e:
                logger.error("vllm_request_error", error=str(e))
                raise APIError(f"Request failed: {str(e)}")
            
            if response.status_code == 429:
                logger.warning("vllm_rate_limit_encountered")
                raise RateLimitError("vLLM rate limit exceeded")
            
            if response.status_code != 200:
                logger.error("vllm_api_error", status=response.status_code, body=response.text)
                raise APIError(f"API Error {response.status_code}: {response.text}")
            
            return response.json()
    
    async def _validate_context_window(self, prompt: str) -> int:
        """
        Validate that the prompt doesn't exceed context window.
        Returns token count if valid.
        """
        token_count = await TokenCounter.count_tokens(prompt, self.model)
        
        # Reserve tokens for response + safety margin
        reserved_tokens = self.SAMPLING_PARAMS["max_tokens"] + 500
        available_tokens = self.context_window - reserved_tokens
        
        if token_count > available_tokens:
            logger.error(
                "context_window_exceeded",
                token_count=token_count,
                available_tokens=available_tokens,
                context_window=self.context_window
            )
            raise ContextWindowExceededError(
                f"Prompt exceeds context window. "
                f"Tokens: {token_count}, Available: {available_tokens}"
            )
        
        return token_count
    
    async def generate_code(
        self,
        instruction: str,
        round_index: int = 1,
        existing_code: Optional[str] = None,
        images: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate or update code using vLLM backend.
        
        Args:
            instruction: User's code generation instruction
            round_index: Iteration number (>1 triggers surgical updates)
            existing_code: Previous version for updates
            images: Unused for vLLM (no vision support yet)
        
        Returns:
            Dict with 'files' (parsed JSON) and 'metadata' (token usage)
        """
        
        # 1. Build appropriate prompt
        if round_index > 1 and existing_code:
            prompt_text = PromptBuilder.surgical_update_prompt(existing_code, instruction)
        else:
            prompt_text = PromptBuilder.base_prompt(instruction)
        
        # 2. Validate context window
        prompt_tokens = await self._validate_context_window(prompt_text)
        logger.info("prompt_validated", tokens=prompt_tokens, round=round_index)
        
        # 3. Build OpenAI-compatible payload
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert code generator. Always respond with valid JSON. "
                        "Never include markdown code blocks or backticks."
                    )
                },
                {
                    "role": "user",
                    "content": prompt_text
                }
            ],
            **self.SAMPLING_PARAMS  # Include sampling parameters
        }
        
        # 4. Call vLLM API
        try:
            logger.info("calling_vllm", model=self.model, endpoint=self.endpoint)
            result = await self._call_vllm_api(payload)
            
            # 5. Extract and parse response
            try:
                # OpenAI-compatible response format
                message_content = result["choices"][0]["message"]["content"]
                
                # Clean JSON extraction (handle potential markdown wrapping)
                json_str = message_content.strip()
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                if json_str.startswith("```"):
                    json_str = json_str[3:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
                json_str = json_str.strip()
                
                parsed_json = json.loads(json_str)
                
                # Extract token usage from OpenAI-compatible response
                usage = result.get("usage", {})
                
                return {
                    "files": parsed_json,
                    "metadata": {
                        "model": self.model,
                        "prompt_token_count": usage.get("prompt_tokens", prompt_tokens),
                        "completion_token_count": usage.get("completion_tokens", 0),
                        "total_token_count": usage.get("total_tokens", prompt_tokens),
                        "context_window": self.context_window,
                        "backend": "vllm"
                    }
                }
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                logger.error("response_parsing_failed", error=str(e), response=message_content)
                raise APIError(f"Failed to parse vLLM response: {str(e)}")
        
        except (RateLimitError, APIError, ContextWindowExceededError) as e:
            logger.error("generation_failed", error=str(e))
            raise

# ============================================================================
# Gemini Service - Google Gemini API Backend (Fallback)
# ============================================================================

class GeminiService:
    """
    Uses Google Gemini API for code generation.
    Serves as fallback when vLLM is unavailable.
    """

    def __init__(self):
        try:
            import google.generativeai as genai
            self.genai = genai
        except ImportError:
            raise ImportError("google-generativeai package not installed. Install with: pip install google-generativeai")

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured in environment")

        self.genai.configure(api_key=api_key)
        self.model = self.genai.GenerativeModel("gemini-2.0-flash")
        self.context_window = 1000000  # Gemini has a large context window

        logger.info(
            "gemini_service_initialized",
            model="gemini-2.0-flash",
            context_window=self.context_window
        )

    async def generate_code(
        self,
        instruction: str,
        round_index: int = 1,
        existing_code: Optional[str] = None,
        images: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate or update code using Google Gemini API.

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

        # 2. Build content with images if provided
        content = [prompt_text]
        if images:
            try:
                from PIL import Image
                from io import BytesIO

                for img_data in images:
                    image_bytes = img_data.get("data")
                    if image_bytes:
                        img = Image.open(BytesIO(image_bytes))
                        content.append(img)
            except ImportError:
                logger.warning("PIL_not_installed_skipping_images")

        # 3. Call Gemini API with retry
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(content)
            )

            # 4. Extract and parse response
            message_content = response.text

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

            logger.info("gemini_generation_successful", round=round_index)

            return {
                "files": parsed_json,
                "metadata": {
                    "model": "gemini-2.0-flash",
                    "backend": "gemini",
                    "round": round_index
                }
            }

        except Exception as e:
            logger.error("gemini_generation_failed", error=str(e))
            raise APIError(f"Failed to generate code with Gemini: {str(e)}")

# ============================================================================
# Service Factory - Route to appropriate backend with fallback
# ============================================================================

async def _check_vllm_availability() -> bool:
    """Check if vLLM service is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.VLLM_ENDPOINT}/models",
                timeout=5.0
            )
            is_available = response.status_code == 200
            if is_available:
                logger.info("vllm_available")
            else:
                logger.warning("vllm_unavailable", status=response.status_code)
            return is_available
    except Exception as e:
        logger.warning("vllm_check_failed", error=str(e))
        return False

def get_llm_service():
    """
    Factory function to get the appropriate LLM service based on configuration.
    - Tries vLLM first if configured as backend
    - Falls back to Gemini if vLLM is unavailable
    - Raises error if Gemini is not configured
    """
    backend = settings.LLM_BACKEND.lower()

    if backend == "vllm":
        try:
            # Create vLLM service without full availability check at startup
            # It will be validated on first request
            service = vLLMService()
            logger.info("using_vllm_backend")
            return service
        except Exception as e:
            logger.warning("vllm_initialization_failed_trying_gemini", error=str(e))
            try:
                service = GeminiService()
                logger.info("fallback_to_gemini_backend")
                return service
            except Exception as gemini_error:
                logger.error("all_backends_failed", vllm_error=str(e), gemini_error=str(gemini_error))
                raise

    elif backend == "gemini":
        try:
            service = GeminiService()
            logger.info("using_gemini_backend")
            return service
        except Exception as e:
            logger.error("gemini_initialization_failed", error=str(e))
            raise

    else:
        logger.error("unknown_backend", backend=backend)
        raise ValueError(f"Unknown LLM backend: {backend}")

# Default instance
llm_service = get_llm_service()
