import logging

import pytest
from langchain_core.runnables import RunnableLambda

from app.core.config import Settings
from app.core.exceptions import ConfigurationError, ModelGenerationError
from app.llm.deepseek_gateway import DeepSeekGateway
from app.models.quiz import QuizDraft
from app.models.report import ReportNarrative
from tests.factories import make_questions


class StructuredFakeModel:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.prompts: list[str] = []

    def with_structured_output(self, schema, **_kwargs):
        async def invoke(prompt_value):
            self.prompts.append(prompt_value.to_string())
            if self.should_fail:
                raise RuntimeError("model down")
            if schema is QuizDraft:
                return QuizDraft(
                    title="RAG 入门闯关",
                    summary="认识 RAG 的定义、场景和边界。",
                    questions=make_questions(),
                )
            if schema is ReportNarrative:
                return ReportNarrative(
                    three_line_summary=["第一句", "第二句", "第三句"],
                    advice=["复习能力边界"],
                    share_quote="把知识做成关卡。",
                )
            raise AssertionError("unexpected schema")

        return RunnableLambda(invoke)


def settings(api_key: str = "test-key") -> Settings:
    return Settings(
        deepseek_api_key=api_key,
        deepseek_model="deepseek-v4-flash",
        cors_origins=["http://localhost:10086"],
    )


def test_gateway_requires_api_key_when_building_real_model() -> None:
    with pytest.raises(ConfigurationError):
        DeepSeekGateway(settings(api_key=""))


@pytest.mark.anyio
async def test_gateway_generates_structured_quiz_and_report() -> None:
    model = StructuredFakeModel()
    gateway = DeepSeekGateway(settings(), model=model)

    quiz = await gateway.generate_quiz(
        user_input="我想学习 RAG", question_count=3, difficulty="mixed"
    )
    report = await gateway.generate_report(
        topic="RAG",
        answer_context={"answers": []},
        score_context={"accuracy": 67},
    )

    assert quiz["title"] == "RAG 入门闯关"
    assert len(quiz["questions"]) == 3
    assert report["three_line_summary"] == ["第一句", "第二句", "第三句"]
    assert "请生成 JSON 题库" in model.prompts[0]
    assert '"accuracy": 67' in model.prompts[1]
    assert '"stem"' in model.prompts[0]
    assert '"three_line_summary"' in model.prompts[1]


@pytest.mark.anyio
async def test_gateway_wraps_model_errors() -> None:
    gateway = DeepSeekGateway(settings(), model=StructuredFakeModel(should_fail=True))
    with pytest.raises(ModelGenerationError):
        await gateway.generate_quiz(
            user_input="我想学习 RAG", question_count=3, difficulty="mixed"
        )
    with pytest.raises(ModelGenerationError):
        await gateway.generate_report(
            topic="RAG", answer_context={}, score_context={}
        )


@pytest.mark.anyio
async def test_gateway_logs_underlying_model_error(caplog) -> None:
    gateway = DeepSeekGateway(settings(), model=StructuredFakeModel(should_fail=True))

    with caplog.at_level(logging.ERROR, logger="app.llm.deepseek_gateway"):
        with pytest.raises(ModelGenerationError):
            await gateway.generate_quiz(
                user_input="我想学习 RAG", question_count=3, difficulty="mixed"
            )

    assert "quiz generation failed" in caplog.text
    assert "model down" in caplog.text
