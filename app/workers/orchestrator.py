import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.api.v1.metrics import task_status_counter, task_processing_duration

import httpx
import structlog
from opentelemetry import trace
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.db.session import AsyncSessionLocal
from app.models.task import TaskRecord, TaskStatus
from app.services.github_service import github_service, GitManager, temporary_clone_dir
from app.services.llm_service import llm_service
from app.core.config import settings

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)

class SafetyGateError(Exception):
    """Raised when a generation fails a safety threshold."""
    pass

class TaskOrchestrator:

    def _read_existing_code(self, temp_dir: str) -> str:
        files_to_read = ["index.html", "README.md", "LICENSE"]
        existing = []
        for filename in files_to_read:
            file_path = os.path.join(temp_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    existing.append(f"--- {filename} ---\n{content}")
        return "\n\n".join(existing)

    def _run_safety_gate(self, existing_code: str, generated_files: Dict[str, str], instruction: str) -> None:
        """Compares character counts and throws an error if >50% shrink without 'refactor' keyword."""
        existing_len = len(existing_code)
        if existing_len == 0:
            return
            
        new_len = sum(len(content) for content in generated_files.values())
        shrinkage = (existing_len - new_len) / existing_len
        
        if shrinkage > 0.5 and "refactor" not in instruction.lower():
            logger.error(
                "safety_gate_triggered", 
                shrinkage=shrinkage, 
                existing_len=existing_len, 
                new_len=new_len
            )
            raise SafetyGateError(
                f"Destructive rewrite detected: code shrank by {shrinkage*100:.1f}%. "
                "Include 'refactor' in the prompt to allow this."
            )

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True
    )
    async def _notify_evaluator(self, task: TaskRecord) -> None:
        """
        Notify the external evaluator about task completion.

        POSTs task results to the evaluation_url with:
        - repo_url: GitHub repository URL
        - pages_url: GitHub Pages URL
        - commit_sha: Latest commit SHA
        - task_id: Task identifier
        - status: Task completion status

        Implements exponential backoff retry logic (3 attempts max).
        """
        if not task.evaluation_url:
            logger.warning("evaluator_notification_skipped_no_url", task_id=str(task.id))
            return

        # Prepare payload with task results
        payload = {
            "task_id": str(task.id),
            "repo_url": task.repo_url,
            "pages_url": task.pages_url,
            "commit_sha": task.commit_sha,
            "status": task.status.value,
            "round_index": task.round_index,
            "llm_metadata": task.llm_metadata or {}
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(
                    "notifying_evaluator",
                    task_id=str(task.id),
                    evaluation_url=task.evaluation_url
                )

                response = await client.post(
                    task.evaluation_url,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code not in (200, 201, 202):
                    logger.error(
                        "evaluator_notification_failed",
                        task_id=str(task.id),
                        status=response.status_code,
                        response=response.text
                    )
                    raise httpx.RequestError(
                        f"Evaluator returned {response.status_code}: {response.text}"
                    )

                logger.info(
                    "evaluator_notified_successfully",
                    task_id=str(task.id),
                    status_code=response.status_code
                )

        except httpx.RequestError as e:
            logger.warning(
                "evaluator_notification_request_error",
                task_id=str(task.id),
                error=str(e),
                attempt=self._notify_evaluator.retry.statistics.get('attempt_number', 1)
            )
            raise

    async def process_task(
        self, 
        task_id: uuid.UUID, 
        instruction: str, 
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Main orchestrator lifecycle."""
        structlog.contextvars.bind_contextvars(task_id=str(task_id))
        with tracer.start_as_current_span("orchestrator_pipeline") as pipeline_span:
            pipeline_span.set_attribute("task.id", str(task_id))
            
            async with AsyncSessionLocal() as session:
                # 1. Fetch Task
                with tracer.start_as_current_span("task.analyze") as analyze_span:
                    task = await session.get(TaskRecord, task_id)
                    if not task:
                        logger.error("task_not_found", task_id=str(task_id))
                        return
                    analyze_span.set_attribute("task.id", str(task_id))
                    analyze_span.set_attribute("task.name", task.task_name)
                    analyze_span.set_attribute("task.round_index", task.round_index)
                    analyze_span.add_event("status_transition", {"status": "ANALYZING"})
                    
                    # Update Status
                    task.status = TaskStatus.ANALYZING
                    await session.commit()
                    task_status_counter.labels(status=task.status.value).inc()
                    
                repo_name = f"gen-{task.nonce}"
                
                try:
                    with tracer.start_as_current_span("setup_github"):
                        token = await github_service.get_installation_access_token()
                        await github_service.create_repo_if_not_exists(repo_name, token)
                        
                    with temporary_clone_dir() as temp_dir:
                        with tracer.start_as_current_span("git_clone"):
                            repo_url = f"https://github.com/{settings.GITHUB_USERNAME}/{repo_name}.git"
                            git_manager = GitManager(repo_url, token, temp_dir)
                            git_manager.clone()
                            
                        existing_code = None
                        if task.round_index > 1:
                            with tracer.start_as_current_span("read_existing_code"):
                                existing_code = self._read_existing_code(temp_dir)
                                
                        # 2. Save Attachments
                        with tracer.start_as_current_span("save_attachments"):
                            if attachments:
                                os.makedirs(os.path.join(temp_dir, "assets"), exist_ok=True)
                                for idx, att in enumerate(attachments):
                                    ext = att.get("mime_type", "image/png").split("/")[-1]
                                    att_path = os.path.join(temp_dir, "assets", f"attachment_{idx}.{ext}")
                                    with open(att_path, "wb") as f:
                                        f.write(att["data"])
                                        
                        # 3. Call LLM
                        task.status = TaskStatus.GENERATING
                        await session.commit()
                        task_status_counter.labels(status=task.status.value).inc()
                        
                        with tracer.start_as_current_span("task.generate") as generate_span:
                            generate_span.set_attribute("task.id", str(task_id))
                            generate_span.set_attribute("task.name", task.task_name)
                            generate_span.set_attribute("task.round_index", task.round_index)
                            generate_span.add_event("status_transition", {"status": "GENERATING"})
                            llm_result = await llm_service.generate_code(
                                instruction=instruction,
                                round_index=task.round_index,
                                existing_code=existing_code,
                                images=attachments
                            )
                            # Persist token counts to metadata
                            task.llm_metadata = llm_result.get("metadata", {})
                            await session.commit()
                            generated_files = llm_result.get("files", {})
                            
                        # 4. Safety Gates
                        if task.round_index > 1 and existing_code:
                            with tracer.start_as_current_span("safety_gate"):
                                self._run_safety_gate(existing_code, generated_files, instruction)
                                
                        # 5. Save Files
                        with tracer.start_as_current_span("save_files"):
                            for filename, content in generated_files.items():
                                file_path = os.path.join(temp_dir, filename)
                                with open(file_path, "w", encoding="utf-8") as f:
                                    f.write(content)
                                    
                        # 6. Push to Git
                        task.status = TaskStatus.DEPLOYING
                        await session.commit()
                        task_status_counter.labels(status=task.status.value).inc()

                        with tracer.start_as_current_span("task.deploy") as deploy_span:
                            deploy_span.set_attribute("task.id", str(task_id))
                            deploy_span.set_attribute("task.name", task.task_name)
                            deploy_span.add_event("status_transition", {"status": "DEPLOYING"})
                            git_manager.add_all()
                            git_manager.commit(message=f"feat: Round {task.round_index} automated updates")
                            git_manager.push()

                            # Capture the commit SHA for evaluator notification
                            task.commit_sha = git_manager.repo.head.commit.hexsha
                            task.repo_url = f"https://github.com/{settings.GITHUB_USERNAME}/{repo_name}"
                            task.pages_url = f"{settings.GITHUB_PAGES_BASE}/{repo_name}"
                            await session.commit()

                        with tracer.start_as_current_span("enable_pages"):
                            await github_service.enable_pages_via_api(repo_name, token)
                            
                        # 7. Notify Evaluator
                        with tracer.start_as_current_span("notify_evaluator"):
                            await self._notify_evaluator(task)
                            
                        # Complete
                        task.status = TaskStatus.SUCCESS
                        task.completed_at = datetime.now(timezone.utc)
                        if task.created_at:
                            task.duration_seconds = (task.completed_at - task.created_at).total_seconds()
                            task_processing_duration.labels(status=task.status.value).observe(task.duration_seconds)
                        await session.commit()
                        task_status_counter.labels(status=task.status.value).inc()
                        logger.info("task_completed_successfully", task_id=str(task_id))
                        
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error_log = str(e)
                    task.completed_at = datetime.now(timezone.utc)
                    if task.created_at:
                        task.duration_seconds = (task.completed_at - task.created_at).total_seconds()
                        task_processing_duration.labels(status=task.status.value).observe(task.duration_seconds)
                    await session.commit()
                    task_status_counter.labels(status=task.status.value).inc()
                    logger.error("task_failed", task_id=str(task_id), error=str(e))
                    raise

orchestrator = TaskOrchestrator()
