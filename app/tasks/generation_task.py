import asyncio
import uuid
from app.core.celery_app import celery_app

@celery_app.task(
    bind=True,
    name="app.tasks.generation_task.run_generation",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def run_generation(self, task_id: str, instruction: str, attachments: list = None):
    """
    Celery task that runs the full generation pipeline.
    Runs the async orchestrator inside a new event loop.
    """
    from app.workers.orchestrator import orchestrator
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            orchestrator.process_task(
                task_id=uuid.UUID(task_id),
                instruction=instruction,
                attachments=attachments or []
            )
        )
    finally:
        loop.close()
