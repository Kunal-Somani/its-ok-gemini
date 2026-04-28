from fastapi import APIRouter, Depends
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.task import TaskRecord
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()

# ============================================================================
# Global Metrics Registry - All metrics registered to REGISTRY
# ============================================================================

# Task status counter
task_status_counter = Counter(
    'task_status_total',
    'Total count of tasks by status',
    ['status'],
    registry=REGISTRY
)

# Task success/failure rates
task_success_gauge = Gauge(
    'task_status_count',
    'Count of tasks by status',
    ['status'],
    registry=REGISTRY
)

# LLM token usage metrics
llm_prompt_tokens = Gauge(
    'llm_tokens_prompt_total',
    'Total prompt tokens used by LLM',
    registry=REGISTRY
)

llm_completion_tokens = Gauge(
    'llm_tokens_completion_total',
    'Total completion tokens used by LLM',
    registry=REGISTRY
)

llm_tokens_total = Gauge(
    'llm_tokens_total',
    'Total tokens used by LLM (prompt + completion)',
    registry=REGISTRY
)

# Task processing histogram (by duration)
task_processing_duration = Histogram(
    'task_processing_duration_seconds',
    'Task processing duration in seconds',
    ['status'],
    registry=REGISTRY
)

logger.info("metrics_registry_initialized", registry="global_prometheus_registry")

@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """
    Exports Prometheus-compatible metrics for task success rates and LLM token usage.

    Returns metrics from the global REGISTRY, which contains all metrics
    registered throughout the application lifecycle.
    """

    # 1. Update Task Status Counts
    try:
        stmt = select(TaskRecord.status, func.count(TaskRecord.id)).group_by(TaskRecord.status)
        result = await db.execute(stmt)

        for status, count in result.all():
            task_success_gauge.labels(status=status.value).set(count)
            task_status_counter.labels(status=status.value).inc(count)

        logger.info("task_metrics_updated")
    except Exception as e:
        logger.error("task_metrics_update_failed", error=str(e))

    # 2. Update LLM Token Usage Metrics
    try:
        stmt = select(TaskRecord.llm_metadata).where(TaskRecord.llm_metadata != None)
        result = await db.execute(stmt)

        total_prompt = 0
        total_completion = 0

        for row in result.all():
            meta = row[0]
            if meta:
                total_prompt += meta.get("prompt_token_count", 0)
                total_completion += meta.get("completion_token_count", 0)

        # Update gauge metrics
        llm_prompt_tokens.set(total_prompt)
        llm_completion_tokens.set(total_completion)
        llm_tokens_total.set(total_prompt + total_completion)

        logger.info(
            "llm_metrics_updated",
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_prompt + total_completion
        )
    except Exception as e:
        logger.error("llm_metrics_update_failed", error=str(e))

    # Return metrics from the global registry
    return Response(generate_latest(REGISTRY), media_type="text/plain")
