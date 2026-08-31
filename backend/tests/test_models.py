import pytest
from pydantic import ValidationError

from app.models.quiz import Option, Question, QuizGenerateRequest
from app.models.quiz import QuizDraft
from app.models.report import AnswerRecord, LearningReport, ReportGenerateRequest
from tests.factories import make_questions


def test_quiz_request_rejects_short_input() -> None:
    with pytest.raises(ValidationError):
        QuizGenerateRequest(user_input="RAG")


def test_question_rejects_answer_not_present_in_options() -> None:
    with pytest.raises(ValidationError):
        Question(
            id="q1",
            type="single",
            stem="测试题目",
            options=[Option(key="A", text="甲"), Option(key="B", text="乙")],
            answer=["C"],
            explanation="测试解析",
            knowledge_point="测试",
            difficulty="easy",
        )


def test_single_question_rejects_multiple_answers() -> None:
    with pytest.raises(ValidationError):
        Question(
            id="q1",
            type="single",
            stem="测试题目",
            options=[Option(key="A", text="甲"), Option(key="B", text="乙")],
            answer=["A", "B"],
            explanation="测试解析",
            knowledge_point="测试",
            difficulty="easy",
        )


def test_report_requires_exactly_three_summary_lines() -> None:
    with pytest.raises(ValidationError):
        LearningReport(
            accuracy=100,
            correct_count=3,
            total_count=3,
            xp_earned=40,
            mastered_points=["定义"],
            weak_points=[],
            three_line_summary=["只有一句"],
            advice=["继续练习"],
            share_quote="把知识做成关卡。",
        )


@pytest.mark.parametrize(
    ("question_type", "options", "answer"),
    [
        ("multiple", [Option(key="A", text="甲"), Option(key="B", text="乙")], ["A"]),
        (
            "judge",
            [
                Option(key="A", text="甲"),
                Option(key="B", text="乙"),
                Option(key="C", text="丙"),
            ],
            ["A"],
        ),
    ],
)
def test_question_type_specific_contracts(question_type, options, answer) -> None:
    with pytest.raises(ValidationError):
        Question(
            id="q1",
            type=question_type,
            stem="测试题目",
            options=options,
            answer=answer,
            explanation="测试解析",
            knowledge_point="测试",
            difficulty="easy",
        )


def test_question_rejects_duplicate_option_keys() -> None:
    with pytest.raises(ValidationError):
        Question(
            id="q1",
            type="single",
            stem="测试题目",
            options=[Option(key="A", text="甲"), Option(key="A", text="乙")],
            answer=["A"],
            explanation="测试解析",
            knowledge_point="测试",
            difficulty="easy",
        )


def test_quiz_draft_rejects_duplicate_question_ids() -> None:
    questions = make_questions()
    questions[1] = questions[1].model_copy(update={"id": "q1"})
    with pytest.raises(ValidationError):
        QuizDraft(title="测试题库", summary="测试摘要", questions=questions)


def test_report_request_requires_all_question_records() -> None:
    with pytest.raises(ValidationError):
        ReportGenerateRequest(
            quiz_id="quiz_test",
            topic="RAG 入门",
            questions=make_questions(),
            answer_records=[
                AnswerRecord(question_id="q1", selected_answers=["B"]),
                AnswerRecord(question_id="q2", selected_answers=["A", "C"]),
                AnswerRecord(question_id="other", selected_answers=["B"]),
            ],
        )
