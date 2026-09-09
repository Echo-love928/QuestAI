import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import (
    ExtractUnavailable,
    ModelGenerationError,
    ResearchUnavailable,
    SearchUnavailable,
)
from app.models.quiz import QuizGenerateRequest
from app.models.quiz_task import QuizTaskStatus
from app.services.quiz_task_service import QuizTaskService
from app.main import create_app
from tests.factories import make_questions


class TaskGateway:
    async def generate_quiz(self, **_: object) -> dict:
        return {
            "title": "异步 RAG 闯关",
            "summary": "异步生成成功",
            "questions": [question.model_dump() for question in make_questions()],
        }

    async def generate_report(self, **_: object) -> dict:
        raise NotImplementedError


class FailingTaskGateway(TaskGateway):
    async def generate_quiz(self, **_: object) -> dict:
        raise ModelGenerationError("upstream secret detail")


class MemoryTaskRepository:
    def __init__(self) -> None:
        self.tasks = {}
        self.saved_quizzes = []

    async def create_quiz_task(self, task_id, user_id, request):
        task = QuizTaskStatus(task_id=task_id, status="pending")
        self.tasks[task_id] = {"public": task, "user_id": user_id, "request": request}
        return task

    async def get_quiz_task(self, task_id):
        item = self.tasks.get(task_id)
        return (item["public"], item["user_id"]) if item else None

    async def mark_quiz_task_processing(self, task_id):
        self.tasks[task_id]["public"] = QuizTaskStatus(
            task_id=task_id, status="processing"
        )

    async def complete_quiz_task(self, task_id, quiz):
        self.tasks[task_id]["public"] = QuizTaskStatus(
            task_id=task_id, status="completed", quiz=quiz
        )

    async def fail_quiz_task(self, task_id, error_code, error_message):
        self.tasks[task_id]["public"] = QuizTaskStatus(
            task_id=task_id,
            status="failed",
            error_code=error_code,
            error_message=error_message,
        )

    async def save_quiz(self, user_id, quiz):
        self.saved_quizzes.append((user_id, quiz.quiz_id))


@pytest.mark.anyio
async def test_task_is_persisted_before_generation_and_completes() -> None:
    repository = MemoryTaskRepository()
    service = QuizTaskService(TaskGateway(), repository)
    request = QuizGenerateRequest(user_input="我想学习什么是 RAG", question_count=3)

    task = await service.create(request, user_id=7)
    assert task.status == "pending"
    assert (await service.get(task.task_id, user_id=7)).status == "pending"

    await service.run(task.task_id, request, user_id=7)
    completed = await service.get(task.task_id, user_id=7)
    assert completed.status == "completed"
    assert completed.quiz is not None
    assert repository.saved_quizzes == [(7, completed.quiz.quiz_id)]


@pytest.mark.anyio
async def test_failed_task_exposes_safe_retryable_error() -> None:
    repository = MemoryTaskRepository()
    service = QuizTaskService(FailingTaskGateway(), repository)
    request = QuizGenerateRequest(user_input="我想学习什么是 RAG", question_count=3)
    task = await service.create(request, user_id=None)

    await service.run(task.task_id, request, user_id=None)

    failed = await service.get(task.task_id, user_id=None)
    assert failed.status == "failed"
    assert failed.error_code == 5001
    assert failed.error_message == "AI 生成失败，请稍后重试"
    assert "secret" not in failed.error_message


@pytest.mark.anyio
async def test_logged_in_task_cannot_be_read_by_another_user() -> None:
    repository = MemoryTaskRepository()
    service = QuizTaskService(TaskGateway(), repository)
    request = QuizGenerateRequest(user_input="我想学习什么是 RAG", question_count=3)
    task = await service.create(request, user_id=7)

    assert await service.get(task.task_id, user_id=8) is None
    assert await service.get(task.task_id, user_id=None) is None


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (SearchUnavailable(), 5101),
        (ExtractUnavailable(), 5102),
        (ResearchUnavailable(), 5100),
    ],
)
def test_specific_research_task_error_codes_are_preserved(
    error: Exception, expected_code: int
) -> None:
    assert QuizTaskService._safe_error(error)[0] == expected_code


@pytest.mark.anyio
async def test_async_task_api_returns_immediately_then_can_be_polled() -> None:
    repository = MemoryTaskRepository()
    app = create_app(gateway=TaskGateway(), learning_repository=repository)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/quiz/tasks",
            json={"user_input": "我想学习什么是 RAG", "question_count": 3},
        )
        task_id = created.json()["data"]["task_id"]
        polled = await client.get(f"/api/v1/quiz/tasks/{task_id}")

    assert created.status_code == 202
    assert created.json()["data"]["status"] == "pending"
    assert polled.status_code == 200
    assert polled.json()["data"]["status"] == "completed"
    assert len(polled.json()["data"]["quiz"]["questions"]) == 3
