import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.models.task import TaskRecord, TaskStatus
from app.core.security import get_api_key, limiter

router = APIRouter()


class TaskCreate(BaseModel):
    task_name: str = Field(..., min_length=3, max_length=100)
    email: str = Field(
        ..., pattern=r"^\S+@\S+\.\S+$", description="User's email address"
    )
    round_index: int = Field(default=1, ge=1)
    nonce: str = Field(
        ...,
        min_length=5,
        description="Idempotency key to prevent duplicate submissions",
    )
    instruction: str = Field(..., min_length=5)
    attachments: Optional[List[Dict[str, Any]]] = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    status: TaskStatus
    task_name: str
    email: str
    round_index: int
    nonce: str
    pages_url: Optional[str] = None
    repo_url: Optional[str] = None
    commit_sha: Optional[str] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    model_config = {"from_attributes": True}


@router.post(
    "/tasks/ready", response_model=TaskResponse, status_code=201, tags=["tasks"]
)
@limiter.limit("10/minute")
async def create_task(
    request: Request,
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """
    Create a new autonomous task.
    Returns 201 if a new task is created, or 200 with the existing task if the nonce matches.
    """
    # 1. Idempotency Check
    stmt = select(TaskRecord).where(TaskRecord.nonce == task_in.nonce)
    result = await db.execute(stmt)
    existing_task = result.scalar_one_or_none()

    if existing_task:
        return existing_task

    # 2. Database Write
    new_task = TaskRecord(
        task_name=task_in.task_name,
        email=task_in.email,
        round_index=task_in.round_index,
        nonce=task_in.nonce,
        status=TaskStatus.QUEUED,
    )
    db.add(new_task)
    try:
        await db.commit()
        await db.refresh(new_task)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Task with this nonce already exists"
        )

    # 3. Offload to Celery Task
    from app.tasks.generation_task import run_generation
    run_generation.delay(str(new_task.id), task_in.instruction, task_in.attachments)

    return new_task


@router.get("/tasks", response_model=List[TaskResponse], tags=["tasks"])
async def get_tasks(
    status: Optional[TaskStatus] = Query(None, description="Filter tasks by status"),
    task_name_contains: Optional[str] = Query(None, description="Search task name"),
    after_id: Optional[uuid.UUID] = Query(None, description="Cursor pagination"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """Retrieve historical tasks with pagination and status filtering."""
    stmt = select(TaskRecord).order_by(TaskRecord.created_at.desc())
    if status:
        stmt = stmt.where(TaskRecord.status == status)
    if task_name_contains:
        stmt = stmt.where(TaskRecord.task_name.ilike(f"%{task_name_contains}%"))

    if after_id:
        cursor_task = await db.get(TaskRecord, after_id)
        if cursor_task:
            stmt = stmt.where(TaskRecord.created_at < cursor_task.created_at)
    else:
        stmt = stmt.offset(offset)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=TaskResponse, tags=["tasks"])
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """Retrieve details for a specific task by ID."""
    task = await db.get(TaskRecord, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/tasks/{task_id}", status_code=204, tags=["tasks"])
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """Cancel an ongoing task or mark it as FAILED."""
    task = await db.get(TaskRecord, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in (TaskStatus.SUCCESS, TaskStatus.FAILED):
        task.status = TaskStatus.FAILED
        task.error_log = "Cancelled by user"
        await db.commit()
    return None
