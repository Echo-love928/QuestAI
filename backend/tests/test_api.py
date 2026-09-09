import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import (
    EvidenceInsufficient,
    ExtractUnavailable,
    ModelGenerationError,
    ResearchBudgetExceeded,
    ResearchUnavailable,
    SearchUnavailable,
    TopicAmbiguous,
)
from app.main import create_app
from app.research.safety import UnsafeUrlError
from tests.factories import make_questions


class ApiGateway:
    def __init__(self) -> None:
        self.quiz_calls = 0

    async def generate_quiz(self, **_: object) -> dict:
        self.quiz_calls += 1
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


class FailingResearcher:
    def __init__(self, error) -> None:
        self.error = error

    async def research(self, _request):
        raise self.error


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
async def test_generate_quiz_preserves_url_source_type_without_researcher() -> None:
    response = await request(
        create_app(gateway=ApiGateway()),
        "POST",
        "/api/v1/quiz/generate",
        json={
            "user_input": "https://example.com/guide",
            "source_type": "url",
            "question_count": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["source_type"] == "url"


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
@pytest.mark.parametrize(
    ("error", "status_code", "business_code"),
    [
        (SearchUnavailable("search down"), 503, 5101),
        (ExtractUnavailable("extract down"), 503, 5102),
        (EvidenceInsufficient("insufficient"), 422, 4102),
        (TopicAmbiguous("ambiguous"), 409, 4103),
        (ResearchBudgetExceeded("budget"), 503, 4104),
        (ResearchUnavailable("research down"), 503, 5100),
        (UnsafeUrlError("unsafe internal url"), 400, 4101),
    ],
)
async def test_research_errors_have_stable_safe_api_codes(
    error, status_code, business_code
) -> None:
    response = await request(
        create_app(gateway=ApiGateway(), researcher=FailingResearcher(error)),
        "POST",
        "/api/v1/quiz/generate",
        json={"user_input": "Harness Engineering 是什么"},
    )

    assert response.status_code == status_code
    assert response.json()["code"] == business_code
    assert str(error) not in response.json()["message"]


@pytest.mark.anyio
async def test_quiz_rate_limit_blocks_before_gateway() -> None:
    gateway = ApiGateway()
    app = create_app(gateway=gateway)
    app.state.quiz_rate_limiter.limit = 1

    first = await request(
        app,
        "POST",
        "/api/v1/quiz/generate",
        json={"user_input": "我想学习什么是 RAG", "question_count": 3},
    )
    second = await request(
        app,
        "POST",
        "/api/v1/quiz/generate",
        json={"user_input": "我想学习什么是 RAG", "question_count": 3},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == 4290
    assert gateway.quiz_calls == 1


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
