from app.models.quiz import Question
from app.models.report import AnswerRecord, AnswerResult, ScoreSummary


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def score_quiz(
    questions: list[Question], answer_records: list[AnswerRecord]
) -> ScoreSummary:
    question_by_id = {question.id: question for question in questions}
    record_by_id = {record.question_id: record for record in answer_records}
    if set(question_by_id) != set(record_by_id):
        raise ValueError("必须提交每道题的答题记录")

    results: list[AnswerResult] = []
    mastered: list[str] = []
    weak: list[str] = []

    for question in questions:
        record = record_by_id[question.id]
        is_correct = set(record.selected_answers) == set(question.answer)
        results.append(
            AnswerResult(
                **record.model_dump(),
                correct_answers=question.answer,
                is_correct=is_correct,
            )
        )
        (mastered if is_correct else weak).append(question.knowledge_point)

    correct_count = sum(result.is_correct for result in results)
    total_count = len(questions)
    completion_bonus = 10
    return ScoreSummary(
        accuracy=round(correct_count / total_count * 100),
        correct_count=correct_count,
        total_count=total_count,
        xp_earned=correct_count * 10 + completion_bonus,
        mastered_points=_unique(mastered),
        weak_points=_unique(weak),
        answer_results=results,
    )

