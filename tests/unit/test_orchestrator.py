import pytest
from unittest.mock import AsyncMock, patch
from app.services.orchestrator import AgentOrchestrator, SafetyGateError
from app.models.task import TaskRecord


@pytest.fixture
def orchestrator():
    return AgentOrchestrator(db_session=AsyncMock())


def test_run_safety_gate_new_code(orchestrator):
    orchestrator._run_safety_gate("add feature", "def foo(): pass", 0)


def test_run_safety_gate_raises_when_shrinks(orchestrator):
    with pytest.raises(SafetyGateError):
        orchestrator._run_safety_gate("add a comment", "def foo(): pass", 1000)


def test_run_safety_gate_refactor_allows_shrink(orchestrator):
    orchestrator._run_safety_gate("refactor the code", "def foo(): pass", 1000)


@patch("app.services.orchestrator.os.path.exists", return_value=True)
def test_read_existing_code(mock_exists, orchestrator):
    with patch("builtins.open", patch.mock_open(read_data="file content")):
        content = orchestrator._read_existing_code(
            "/dummy/path", ["file1.py", "file2.py"]
        )
        assert "file content" in content


@patch("app.services.orchestrator.GithubService")
@patch("app.services.orchestrator.AnthropicService")
@patch("app.services.orchestrator.RAGService")
@pytest.mark.asyncio
async def test_process_task_happy_path(
    mock_rag, mock_anthropic, mock_github, orchestrator
):
    task = TaskRecord(
        id="a1b2c3d4-e5f6-7890-1234-567890abcdef",
        task_name="test",
        email="test@test.com",
        nonce="nonce",
        status="QUEUED",
    )

    mock_gh_instance = AsyncMock()
    mock_gh_instance.create_repo_if_not_exists.return_value = (
        "https://github.com/testuser/test"
    )
    mock_gh_instance.enable_pages_via_api.return_value = (
        "https://testuser.github.io/test"
    )
    mock_github.return_value = mock_gh_instance

    mock_llm_instance = AsyncMock()
    mock_llm_instance.generate_code.return_value = {
        "files": {"test.py": "print('ok')"},
        "metadata": {},
    }
    mock_anthropic.return_value = mock_llm_instance

    mock_rag_instance = AsyncMock()
    mock_rag_instance.retrieve_best_practices.return_value = []
    mock_rag.return_value = mock_rag_instance

    with patch.object(orchestrator, "_read_existing_code", return_value=""):
        with patch.object(orchestrator, "_run_safety_gate", return_value=None):
            with patch("app.services.orchestrator.shutil.rmtree"):
                with patch("app.services.orchestrator.os.makedirs"):
                    with patch(
                        "app.services.orchestrator.os.path.join",
                        return_value="/tmp/test.py",
                    ):
                        with patch("builtins.open", patch.mock_open()):
                            await orchestrator.process_task(
                                task_id=task.id, instruction="instruction"
                            )
