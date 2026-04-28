from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field

class Settings(BaseSettings):
    # Environment mode
    ENVIRONMENT: str = Field(default="development")

    # GitHub Settings
    GITHUB_USERNAME: str = Field(..., description="GitHub username used for Pages computation")
    GITHUB_APP_ID: str = Field(..., description="GitHub App ID")
    GITHUB_PRIVATE_KEY_B64: str = Field(..., description="Base64 encoded GitHub Private Key")
    
    # LLM Settings: vLLM OpenAI-compatible endpoint (new)
    LLM_BACKEND: str = Field(default="vllm", description="LLM backend: 'vllm' or 'gemini'")
    VLLM_ENDPOINT: str = Field(default="http://localhost:8001/v1", description="vLLM OpenAI-compatible endpoint")
    VLLM_MODEL: str = Field(default="deepseek-coder-v2", description="Model name: 'deepseek-coder-v2' or 'codellama-70b'")
    VLLM_CONTEXT_WINDOW: int = Field(default=128000, description="Model context window size in tokens")
    VLLM_TIMEOUT: int = Field(default=300, description="vLLM request timeout in seconds")
    
    # Legacy: Gemini API Settings (deprecated, kept for backwards compatibility)
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key (deprecated)")
    
    # RAG & Vector Database Settings
    QDRANT_URL: str = Field(default="http://localhost:6333", description="Qdrant Vector Database URL")
    QDRANT_API_KEY: str = Field(default="", description="Optional API key for Qdrant")
    EMBEDDING_MODEL: str = Field(default="all-MiniLM-L6-v2", description="Sentence-transformers embedding model for RAG")
    RAG_VECTOR_DIMENSION: int = Field(default=384, description="Embedding vector dimension (all-MiniLM-L6-v2 uses 384)")
    RAG_CHUNK_SIZE: int = Field(default=500, description="Text chunk size for document indexing")
    RAG_CHUNK_OVERLAP: int = Field(default=50, description="Overlap between chunks for better context")
    RAG_TOP_K: int = Field(default=5, description="Number of top relevant chunks to retrieve")
    
    # Database Settings
    DATABASE_URL: str = Field(..., description="Async Database URL for SQLAlchemy")
    DATABASE_SYNC_URL: str = Field(..., description="Synchronous Database URL for Alembic migrations")

    # Security Settings
    STUDENT_SECRET: str = Field(..., description="Secret key for authenticating student task submissions")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)

    @computed_field
    def GITHUB_PAGES_BASE(self) -> str:
        return f"https://{self.GITHUB_USERNAME}.github.io"

settings = Settings()
