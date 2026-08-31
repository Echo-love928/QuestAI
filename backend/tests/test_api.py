import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import ModelGenerationError
from app.main import create_app
from tests.factories import make_questions


class ApiGateway:
    async def generate_quiz(self, **_: object) -> dict:
        return {
            "title": "RAG 入门闯关",
            "summary": "认识 RAG 的定义、场景和边界。",
            "questions": [question.model_dump() for question in make_questions()],
        }

    async def generate_report(self, **_: object) -> dict:
        return {
            "three_line_summary": [
                "RAG 先检索再生成。",
                "外部资料可以补充模型知识。",
                "有依据不等于绝对正确。",
            ],
            "advice": ["重点复习能力边界。"],
            "share_quote": "把知识做成关卡，记得更牢。",
        }


class FailingGateway(ApiGateway):
    async def generate_quiz(self, **_: object) -> dict:
        raise ModelGenerationError("upstream unavailable")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def request(app, method: str, path: str, **kwargs):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.anyio
async def test_health_endpoint() -> None:
    response = await request(create_app(gateway=ApiGateway()), "GET", "/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {"status": "healthy"},
    }


@pytest.mark.anyio
async def test_generate_quiz_endpoint() -> None:
    response = await request(
        create_app(gateway=ApiGateway()),
        "POST",
        "/api/v1/quiz/generate",
        json={"user_input": "我想学习什么是 RAG", "question_count": 3},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["title"] == "RAG 入门闯关"
    assert len(body["data"]["questions"]) == 3


@pytest.mark.anyio
async def test_validation_error_uses_unified_response() -> None:
    response = await request(
        create_app(gateway=ApiGateway()),
        "POST",
        "/api/v1/quiz/generate",
        json={"user_input": "短"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == 4000
    assert response.json()["data"] is None


@pytest.mark.anyio
async def test_model_failure_returns_service_unavailable() -> None:
    response = await request(
        create_app(gateway=FailingGateway()),
        "POST",
        "/api/v1/quiz/generate",
        json={"user_input": "我想学习什么是 RAG"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == 5001
    assert "重试" in response.json()["message"]


@pytest.mark.anyio
async def test_generate_report_endpoint() -> None:
    questions = [question.model_dump() for question in make_questions()]
    response = await request(
        create_app(gateway=ApiGateway()),
        "POST",
        "/api/v1/report/generate",
        json={
            "quiz_id": "quiz_test",
            "topic": "RAG 入门",
            "questions": questions,
            "answer_records": [
                {"question_id": "q1", "selected_answers": ["B"], "duration_ms": 1000},
                {"question_id": "q2", "selected_answers": ["A", "C"], "duration_ms": 2000},
                {"question_id": "q3", "selected_answers": ["A"], "duration_ms": 1000},
            ],
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["data"]["accuracy"] == 67
    assert body["data"]["weak_points"] == ["RAG 能力边界"]

