import pytest

from app.core.exceptions import ModelGenerationError
from app.models.quiz import QuizGenerateRequest
from app.models.report import AnswerRecord, ReportGenerateRequest
from app.services.quiz_service import QuizService
from app.services.report_service import ReportService
from tests.factories import make_questions, make_quiz


class FakeGateway:
    def __init__(self, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.quiz_calls = 0
        self.report_calls = 0

    async def generate_quiz(self, **_: object) -> dict:
        self.quiz_calls += 1
        if self.quiz_calls <= self.fail_times:
            raise ModelGenerationError("temporary model failure")
        return {
            "title": "RAG 入门闯关",
            "summary": "认识 RAG 的定义、场景和边界。",
            "questions": [question.model_dump() for question in make_questions()],
        }

    async def generate_report(self, **_: object) -> dict:
        self.report_calls += 1
        if self.report_calls <= self.fail_times:
            raise ModelGenerationError("temporary model failure")
        return {
            "three_line_summary": [
                "RAG 先检索再生成。",
                "外部资料可以补充模型知识。",
                "有依据不等于绝对正确。",
            ],
            "advice": ["重点复习能力边界。"],
            "share_quote": "把知识做成关卡，记得更牢。",
        }


@pytest.mark.anyio
async def test_quiz_service_retries_once_and_returns_valid_quiz() -> None:
    gateway = FakeGateway(fail_times=1)
    service = QuizService(gateway=gateway, max_attempts=2)

    quiz = await service.generate(
        QuizGenerateRequest(user_input="我想学习什么是 RAG", question_count=3)
    )

    assert gateway.quiz_calls == 2
    assert quiz.source_type == "text"
    assert len(quiz.questions) == 3


@pytest.mark.anyio
async def test_quiz_service_raises_after_retry_budget_is_exhausted() -> None:
    service = QuizService(gateway=FakeGateway(fail_times=2), max_attempts=2)
    with pytest.raises(ModelGenerationError):
        await service.generate(QuizGenerateRequest(user_input="我想学习什么是 RAG"))


@pytest.mark.anyio
async def test_report_service_combines_deterministic_score_and_ai_narrative() -> None:
    quiz = make_quiz()
    request = ReportGenerateRequest(
        quiz_id=quiz.quiz_id,
        topic=quiz.title,
        questions=quiz.questions,
        answer_records=[
            AnswerRecord(question_id="q1", selected_answers=["B"], duration_ms=1000),
            AnswerRecord(question_id="q2", selected_answers=["A", "C"], duration_ms=2000),
            AnswerRecord(question_id="q3", selected_answers=["A"], duration_ms=1000),
        ],
    )

    report = await ReportService(FakeGateway()).generate(request)

    assert report.accuracy == 67
    assert report.correct_count == 2
    assert report.xp_earned == 30
    assert report.weak_points == ["RAG 能力边界"]
    assert len(report.three_line_summary) == 3


@pytest.mark.anyio
async def test_report_service_raises_after_retry_budget_is_exhausted() -> None:
    quiz = make_quiz()
    request = ReportGenerateRequest(
        quiz_id=quiz.quiz_id,
        topic=quiz.title,
        questions=quiz.questions,
        answer_records=[
            AnswerRecord(question_id="q1", selected_answers=["B"]),
            AnswerRecord(question_id="q2", selected_answers=["A", "C"]),
            AnswerRecord(question_id="q3", selected_answers=["B"]),
        ],
    )
    gateway = FakeGateway(fail_times=2)
    with pytest.raises(ModelGenerationError):
        await ReportService(gateway, max_attempts=2).generate(request)
    assert gateway.report_calls == 2
