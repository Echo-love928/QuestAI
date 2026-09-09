import json

import pytest

from app.core.exceptions import EvidenceInsufficient, ModelGenerationError
from app.models.quiz import QuizGenerateRequest
from app.models.report import AnswerRecord, ReportGenerateRequest
from app.services.quiz_service import QuizService
from app.services.report_service import ReportService
from app.research.models import EvidenceSource, ResearchBrief, ResearchFact, ResearchResult
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


class FakeResearcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def research(self, _request):
        if self.fail:
            raise EvidenceInsufficient("not enough evidence")
        source = EvidenceSource(
            source_id="src_official",
            title="Official guide",
            url="https://example.com/guide",
            site_name="example.com",
            acquisition_method="search_snippet",
            content="Harness Engineering is a current software practice.",
        )
        return ResearchResult(
            grounding_mode="web_search",
            sources=[source],
            brief=ResearchBrief(
                resolved_topic="Harness Engineering",
                domain="software engineering",
                is_ambiguous=False,
                is_sufficient=True,
                summary="Current software practice",
                key_facts=[
                    ResearchFact(text="Current fact", source_ids=[source.source_id])
                ],
                first_party_source_ids=[source.source_id],
            ),
        )


class GroundedGateway(FakeGateway):
    def __init__(self) -> None:
        super().__init__()
        self.last_quiz_kwargs = {}

    async def generate_quiz(self, **kwargs: object) -> dict:
        self.quiz_calls += 1
        self.last_quiz_kwargs = kwargs
        questions = [
            question.model_copy(update={"source_ids": ["src_official"]})
            for question in make_questions()
        ]
        return {
            "title": "Harness Engineering 闯关",
            "summary": "根据当前资料生成。",
            "questions": [question.model_dump() for question in questions],
        }


class InvalidThenGroundedGateway(GroundedGateway):
    async def generate_quiz(self, **kwargs: object) -> dict:
        result = await super().generate_quiz(**kwargs)
        if self.quiz_calls == 1:
            result["questions"][0]["source_ids"] = ["src_unknown"]
        return result


class ManySourceResearcher:
    async def research(self, _request):
        sources = [
            EvidenceSource(
                source_id=f"src_{index}",
                title=f"Source {index}",
                url=f"https://example{index}.com/guide",
                site_name=f"example{index}.com",
                acquisition_method="search_snippet",
                content=f"Verified fact {index}",
            )
            for index in range(10)
        ]
        return ResearchResult(
            grounding_mode="web_search",
            sources=sources,
            brief=ResearchBrief(
                resolved_topic="Current topic",
                domain="software engineering",
                is_ambiguous=False,
                is_sufficient=True,
                summary="Verified summary",
                key_facts=[
                    ResearchFact(
                        text=f"Fact {index}", source_ids=[source.source_id]
                    )
                    for index, source in enumerate(sources)
                ],
                first_party_source_ids=[sources[0].source_id],
            ),
        )


class ContextAwareGateway(FakeGateway):
    async def generate_quiz(self, **kwargs: object) -> dict:
        context = json.loads(str(kwargs["grounding_context"]))
        source_id = context["sources"][0]["source_id"]
        questions = [
            question.model_copy(update={"source_ids": [source_id]})
            for question in make_questions()
        ]
        return {
            "title": "Current topic",
            "summary": "Verified summary",
            "questions": [question.model_dump() for question in questions],
        }


@pytest.mark.anyio
async def test_quiz_service_passes_validated_research_to_grounded_prompt() -> None:
    gateway = GroundedGateway()
    service = QuizService(gateway=gateway, researcher=FakeResearcher())

    quiz = await service.generate(
        QuizGenerateRequest(user_input="Harness Engineering 是什么", question_count=3)
    )

    assert quiz.grounding_mode == "web_search"
    assert quiz.sources[0].source_id == "src_official"
    assert "src_official" in str(gateway.last_quiz_kwargs["grounding_context"])
    assert all(question.source_ids == ["src_official"] for question in quiz.questions)


@pytest.mark.anyio
async def test_research_failure_never_calls_quiz_gateway() -> None:
    gateway = GroundedGateway()
    service = QuizService(gateway=gateway, researcher=FakeResearcher(fail=True))

    with pytest.raises(EvidenceInsufficient):
        await service.generate(
            QuizGenerateRequest(user_input="Harness Engineering 是什么")
        )
    assert gateway.quiz_calls == 0


@pytest.mark.anyio
async def test_quiz_service_retries_unknown_grounding_reference() -> None:
    gateway = InvalidThenGroundedGateway()
    quiz = await QuizService(
        gateway=gateway, researcher=FakeResearcher(), max_attempts=2
    ).generate(
        QuizGenerateRequest(user_input="Harness Engineering 是什么", question_count=3)
    )

    assert gateway.quiz_calls == 2
    assert quiz.questions[0].source_ids == ["src_official"]


@pytest.mark.anyio
async def test_quiz_service_caps_public_sources_and_prompt_to_schema_limit() -> None:
    quiz = await QuizService(
        gateway=ContextAwareGateway(), researcher=ManySourceResearcher()
    ).generate(
        QuizGenerateRequest(user_input="A current software topic", question_count=3)
    )

    assert len(quiz.sources) == 8
    assert all(
        set(question.source_ids).issubset({source.source_id for source in quiz.sources})
        for question in quiz.questions
    )


class UserContentResearcher:
    async def research(self, _request):
        return ResearchResult(grounding_mode="user_content")


@pytest.mark.anyio
async def test_complete_user_material_keeps_original_content_mode() -> None:
    gateway = FakeGateway()
    quiz = await QuizService(
        gateway=gateway, researcher=UserContentResearcher()
    ).generate(
        QuizGenerateRequest(user_input="完整稳定的学习资料。" * 40, question_count=3)
    )

    assert quiz.grounding_mode == "user_content"
    assert quiz.sources == []
    assert gateway.quiz_calls == 1


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
