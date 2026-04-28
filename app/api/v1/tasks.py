import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.models.task import TaskRecord, TaskStatus
from app.workers.orchestrator import orchestrator
from app.core.config import settings

router = APIRouter()

class TaskCreate(BaseModel):
    task_name: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., pattern=r"^\S+@\S+\.\S+$", description="User's email address")
    round_index: int = Field(default=1, ge=1)
    nonce: str = Field(..., min_length=5, description="Idempotency key to prevent duplicate submissions")
    instruction: str = Field(..., min_length=5)
    secret: str = Field(..., description="Secret key for authentication")
    attachments: Optional[List[Dict[str, Any]]] = None

class TaskResponse(BaseModel):
    id: uuid.UUID
    status: TaskStatus
    task_name: str
    email: str
    round_index: int
    nonce: str

    model_config = {"from_attributes": True}

def _verify_secret(secret: str) -> None:
    """Verify that the provided secret matches the STUDENT_SECRET.

    Args:
        secret: The secret key provided in the request

    Raises:
        HTTPException: If the secret does not match
    """
    if secret != settings.STUDENT_SECRET:
        raise HTTPException(status_code=401, detail="Invalid authentication secret")

@router.post("/tasks/ready", response_model=TaskResponse)
async def create_task(
    task_in: TaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # 0. Verify authentication secret
    _verify_secret(task_in.secret)

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
        status=TaskStatus.QUEUED
    )
    db.add(new_task)
    try:
        await db.commit()
        await db.refresh(new_task)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Task with this nonce already exists")

    # 3. Offload to Background Task
    background_tasks.add_task(
        orchestrator.process_task,
        task_id=new_task.id,
        instruction=task_in.instruction,
        attachments=task_in.attachments
    )

    return new_task

@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(
    status: Optional[TaskStatus] = Query(None, description="Filter tasks by status"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve historical tasks with pagination and status filtering."""
    stmt = select(TaskRecord).order_by(TaskRecord.created_at.desc())
    if status:
        stmt = stmt.where(TaskRecord.status == status)
        
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()
