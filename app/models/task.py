import uuid
from enum import Enum as PyEnum
from typing import Any, Dict, Optional
from datetime import datetime
from sqlalchemy import String, Enum, JSON, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.models.base import Base

class TaskStatus(str, PyEnum):
    QUEUED = "QUEUED"
    ANALYZING = "ANALYZING"
    GENERATING = "GENERATING"
    DEPLOYING = "DEPLOYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.QUEUED, nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, index=True, nullable=False)
    round_index: Mapped[int] = mapped_column(default=0, nullable=False)
    nonce: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    pages_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    repo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evaluation_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    llm_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
