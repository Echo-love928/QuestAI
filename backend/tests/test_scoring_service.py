from app.models.report import AnswerRecord
from app.services.scoring_service import score_quiz
from tests.factories import make_questions


def test_scoring_handles_single_multiple_and_judge_answers() -> None:
    result = score_quiz(
        make_questions(),
        [
            AnswerRecord(question_id="q1", selected_answers=["B"], duration_ms=1200),
            AnswerRecord(question_id="q2", selected_answers=["C", "A"], duration_ms=2300),
            AnswerRecord(question_id="q3", selected_answers=["A"], duration_ms=900),
        ],
    )

    assert result.correct_count == 2
    assert result.total_count == 3
    assert result.accuracy == 67
    assert result.xp_earned == 30
    assert result.mastered_points == ["RAG 基本定义", "RAG 应用场景"]
    assert result.weak_points == ["RAG 能力边界"]
    assert [item.is_correct for item in result.answer_results] == [True, True, False]


def test_scoring_rejects_missing_answer_record() -> None:
    try:
        score_quiz(
            make_questions(),
            [AnswerRecord(question_id="q1", selected_answers=["B"], duration_ms=1200)],
        )
    except ValueError as exc:
        assert "每道题" in str(exc)
    else:
        raise AssertionError("缺少答题记录时应抛出 ValueError")

