from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field


class Settings(BaseSettings):
    # Environment mode
    ENVIRONMENT: str = Field(default="development")

    # GitHub Settings
    GITHUB_USERNAME: str = Field(
        ..., description="GitHub username used for Pages computation"
    )
    GITHUB_APP_ID: str = Field(..., description="GitHub App ID")
    GITHUB_PRIVATE_KEY_B64: str = Field(
        ..., description="Base64 encoded GitHub Private Key"
    )

    # LLM Settings
    ANTHROPIC_API_KEY: str = Field(..., description="Anthropic API key")
    ANTHROPIC_MODEL: str = Field(
        default="claude-sonnet-4-5", description="claude-sonnet-4-5 or claude-opus-4-5"
    )
    ANTHROPIC_MAX_TOKENS: int = Field(default=8192)

    # RAG & Vector Database Settings
    QDRANT_URL: str = Field(
        default="http://localhost:6333", description="Qdrant Vector Database URL"
    )
    QDRANT_API_KEY: str = Field(default="", description="Optional API key for Qdrant")
    COHERE_API_KEY: str = Field(default="", description="Cohere API key for embeddings")
    EMBEDDING_MODEL: str = Field(
        default="embed-english-v3.0", description="Cohere embedding model for RAG"
    )
    RAG_VECTOR_DIMENSION: int = Field(
        default=1024,
        description="Embedding vector dimension (embed-english-v3.0 uses 1024)",
    )
    RAG_CHUNK_SIZE: int = Field(
        default=500, description="Text chunk size for document indexing"
    )
    RAG_CHUNK_OVERLAP: int = Field(
        default=50, description="Overlap between chunks for better context"
    )
    RAG_TOP_K: int = Field(
        default=5, description="Number of top relevant chunks to retrieve"
    )

    # Database Settings
    DATABASE_URL: str = Field(..., description="Async Database URL for SQLAlchemy")
    DATABASE_SYNC_URL: str = Field(
        ..., description="Synchronous Database URL for Alembic migrations"
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379", description="Redis connection URL"
    )

    # Security Settings
    API_KEY: str = Field(..., description="API key for authenticating requests")
    JWT_SECRET: str = Field(..., description="Secret for signing JWT tokens")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    ALLOWED_ORIGINS: list[str] = Field(default=["http://localhost:5173"])
    OTLP_ENDPOINT: str = Field(default="")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )

    @computed_field
    def GITHUB_PAGES_BASE(self) -> str:
        return f"https://{self.GITHUB_USERNAME}.github.io"


settings = Settings()
