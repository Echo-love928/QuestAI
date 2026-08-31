from pydantic import BaseModel, Field, model_validator

from app.models.quiz import Question


class AnswerRecord(BaseModel):
    question_id: str = Field(min_length=1, max_length=40)
    selected_answers: list[str] = Field(min_length=1, max_length=6)
    duration_ms: int = Field(default=0, ge=0, le=3_600_000)


class AnswerResult(AnswerRecord):
    correct_answers: list[str]
    is_correct: bool


class ScoreSummary(BaseModel):
    accuracy: int = Field(ge=0, le=100)
    correct_count: int = Field(ge=0)
    total_count: int = Field(ge=1)
    xp_earned: int = Field(ge=0)
    mastered_points: list[str]
    weak_points: list[str]
    answer_results: list[AnswerResult]


class ReportNarrative(BaseModel):
    three_line_summary: list[str] = Field(min_length=3, max_length=3)
    advice: list[str] = Field(min_length=1, max_length=3)
    share_quote: str = Field(min_length=2, max_length=80)


class LearningReport(ScoreSummary, ReportNarrative):
    pass


class ReportGenerateRequest(BaseModel):
    quiz_id: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=2, max_length=100)
    questions: list[Question] = Field(min_length=3, max_length=5)
    answer_records: list[AnswerRecord] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_record_ids(self) -> "ReportGenerateRequest":
        question_ids = [question.id for question in self.questions]
        record_ids = [record.question_id for record in self.answer_records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("同一道题不能重复提交")
        if set(question_ids) != set(record_ids):
            raise ValueError("必须提交每道题的答题记录")
        return self

