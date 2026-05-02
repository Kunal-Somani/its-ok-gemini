"""
LLM Service — Qwen2.5-Coder-7B-Instruct via llama-cpp-python
GBNF grammar-constrained sampling guarantees schema-valid JSON output.
No external API. No network calls. Fully local inference.
"""

import json
import textwrap
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import structlog
from llama_cpp import Llama, LlamaGrammar

from app.core.config import settings

logger = structlog.get_logger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================


class ModelNotLoadedError(Exception):
    """Raised when inference is attempted before the model is loaded."""

    pass


class GenerationError(Exception):
    """Raised when model output cannot be parsed into the expected schema."""

    pass


# Keep these names for backwards compatibility with orchestrator error handling
RateLimitError = GenerationError
APIError = GenerationError


# ============================================================================
# GBNF Grammar — constrains token sampling to valid JSON with required keys
# ============================================================================

# This grammar forces the model to output ONLY a JSON object with exactly
# three string fields: index_html, readme_md, license.
# The token sampler physically cannot produce any other token sequence.
PROJECT_FILES_GRAMMAR_STR = r"""
root   ::= "{" ws "\"index_html\"" ws ":" ws string "," ws "\"readme_md\"" ws ":" ws string "," ws "\"license\"" ws ":" ws string ws "}"
string ::= "\"" ( [^"\\] | "\\" ( ["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] ) )* "\""
ws     ::= ([ \t\n\r])*
"""


# ============================================================================
# Prompt Builder
# ============================================================================


class PromptBuilder:
    """Constructs Qwen2.5-Coder chat-format prompts."""

    SYSTEM_PROMPT = textwrap.dedent("""\
        You are an expert full-stack developer. Generate production-ready web applications.
        You must respond with a single JSON object containing exactly these keys:
        - index_html: complete single-file HTML application using Tailwind CDN
        - readme_md: professional README.md for the project
        - license: MIT License text with current year
        Do not include any text outside the JSON object.
    """)

    @staticmethod
    def _wrap_chat(system: str, user: str) -> str:
        """Format prompt in Qwen2.5-Instruct chat template."""
        return (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

    @staticmethod
    def base_prompt(instruction: str) -> str:
        user = f"User Instruction:\n{instruction}"
        return PromptBuilder._wrap_chat(PromptBuilder.SYSTEM_PROMPT, user)

    @staticmethod
    def surgical_update_prompt(existing_code: str, instruction: str) -> str:
        user = (
            "You are making a surgical update to an existing codebase.\n"
            "Preserve all existing functionality while applying the new instruction.\n\n"
            f"--- EXISTING CODE ---\n{existing_code}\n\n"
            f"--- UPDATE INSTRUCTION ---\n{instruction}"
        )
        return PromptBuilder._wrap_chat(PromptBuilder.SYSTEM_PROMPT, user)

    @staticmethod
    def vision_prompt(
        instruction: str,
        base64_images: List[str],
        mime_type: str = "image/png",
    ) -> str:
        """
        Vision is not supported in GGUF text models.
        Falls back to text-only prompt and logs a warning.
        """
        logger.warning(
            "vision_prompt_called_on_text_model",
            detail="Qwen2.5-Coder GGUF does not support image input. Using text-only prompt.",
        )
        return PromptBuilder.base_prompt(instruction)


# ============================================================================
# Qwen2.5-Coder LLM Service
# ============================================================================


class QwenCoderService:
    """
    Local inference service using Qwen2.5-Coder-7B-Instruct Q4_K_M GGUF.
    Uses GBNF grammar to constrain output to a schema-valid JSON object.
    The grammar is compiled once at startup and reused across all requests.
    """

    def __init__(self) -> None:
        self._llm: Optional[Llama] = None
        self._grammar: Optional[LlamaGrammar] = None
        self._model_path = Path(settings.MODEL_PATH)

    def _ensure_loaded(self) -> None:
        """Lazy-load the model on first use. Thread-safe via GIL."""
        if self._llm is not None:
            return

        if not self._model_path.exists():
            raise ModelNotLoadedError(
                f"Model file not found at {self._model_path}. "
                "Run: bash scripts/download_model.sh"
            )

        logger.info(
            "loading_model",
            path=str(self._model_path),
            n_ctx=settings.MODEL_N_CTX,
            n_gpu_layers=settings.MODEL_N_GPU_LAYERS,
            n_threads=settings.MODEL_N_THREADS,
        )

        self._llm = Llama(
            model_path=str(self._model_path),
            n_ctx=settings.MODEL_N_CTX,
            n_gpu_layers=settings.MODEL_N_GPU_LAYERS,
            n_threads=settings.MODEL_N_THREADS,
            verbose=False,
        )
        self._grammar = LlamaGrammar.from_string(PROJECT_FILES_GRAMMAR_STR)

        logger.info("model_loaded_successfully", path=str(self._model_path))

    def _run_inference(self, prompt: str) -> str:
        """
        Run synchronous GBNF-constrained completion.
        llama-cpp-python is synchronous — called from async context via
        Celery worker (already a separate process), so blocking is acceptable.
        """
        self._ensure_loaded()

        output = self._llm(
            prompt,
            max_tokens=settings.MODEL_MAX_TOKENS,
            grammar=self._grammar,
            temperature=0.2,
            top_p=0.95,
            repeat_penalty=1.1,
            stop=["<|im_end|>", "<|endoftext|>"],
            echo=False,
        )

        raw_text: str = output["choices"][0]["text"].strip()
        prompt_tokens: int = output["usage"]["prompt_tokens"]
        completion_tokens: int = output["usage"]["completion_tokens"]

        return raw_text, prompt_tokens, completion_tokens

    def _parse_output(self, raw_text: str) -> Dict[str, str]:
        """
        Parse GBNF-constrained output into file dict.
        Grammar guarantees valid JSON so this should never fail,
        but we handle edge cases defensively.
        """
        try:
            parsed = json.loads(raw_text)
            return {
                "index.html": parsed["index_html"],
                "README.md": parsed["readme_md"],
                "LICENSE": parsed["license"],
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("output_parse_failed", raw=raw_text[:200], error=str(e))
            raise GenerationError(f"Failed to parse model output: {e}")

    async def generate_code(
        self,
        instruction: str,
        round_index: int = 1,
        existing_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate or surgically update project files.
        Returns same dict shape as the previous LLM service for
        full orchestrator compatibility.
        """
        if round_index > 1 and existing_code:
            prompt = PromptBuilder.surgical_update_prompt(existing_code, instruction)
        else:
            prompt = PromptBuilder.base_prompt(instruction)

        logger.info("starting_local_inference", round_index=round_index)

        try:
            raw_text, prompt_tokens, completion_tokens = self._run_inference(prompt)
        except ModelNotLoadedError:
            raise
        except Exception as e:
            logger.error("inference_failed", error=str(e))
            raise GenerationError(f"Inference failed: {e}")

        files = self._parse_output(raw_text)

        logger.info(
            "inference_complete",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        return {
            "files": files,
            "metadata": {
                "model": self._model_path.name,
                "prompt_token_count": prompt_tokens,
                "completion_token_count": completion_tokens,
                "total_token_count": prompt_tokens + completion_tokens,
                "backend": "llama_cpp_gbnf",
            },
        }

    async def stream_generation(
        self,
        instruction: str,
        round_index: int = 1,
        existing_code: Optional[str] = None,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """
        Streaming generation — yields token chunks then final dict.
        llama-cpp-python supports streaming via stream=True.
        """
        self._ensure_loaded()

        if round_index > 1 and existing_code:
            prompt = PromptBuilder.surgical_update_prompt(existing_code, instruction)
        else:
            prompt = PromptBuilder.base_prompt(instruction)

        accumulated = ""
        prompt_tokens = 0
        completion_tokens = 0

        stream = self._llm(
            prompt,
            max_tokens=settings.MODEL_MAX_TOKENS,
            grammar=self._grammar,
            temperature=0.2,
            top_p=0.95,
            repeat_penalty=1.1,
            stop=["<|im_end|>", "<|endoftext|>"],
            echo=False,
            stream=True,
        )

        for chunk in stream:
            delta = chunk["choices"][0]["text"]
            accumulated += delta
            completion_tokens += 1
            yield delta

        files = self._parse_output(accumulated)
        yield {
            "files": files,
            "metadata": {
                "model": self._model_path.name,
                "prompt_token_count": prompt_tokens,
                "completion_token_count": completion_tokens,
                "total_token_count": completion_tokens,
                "backend": "llama_cpp_gbnf_stream",
            },
        }

    async def generate_code_with_vision(
        self,
        instruction: str,
        base64_images: List[str],
        round_index: int = 1,
        existing_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        GGUF text models do not support image input.
        Logs a warning and falls back to text-only generation.
        """
        logger.warning(
            "vision_input_ignored",
            detail="Qwen2.5-Coder GGUF text model cannot process images. Falling back to text-only.",
        )
        return await self.generate_code(instruction, round_index, existing_code)


# ============================================================================
# Singleton export — same name as before so orchestrator import is unchanged
# ============================================================================

llm_service = QwenCoderService()
