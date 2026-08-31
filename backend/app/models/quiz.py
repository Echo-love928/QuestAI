from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


QuestionType = Literal["single", "multiple", "judge"]
Difficulty = Literal["easy", "medium", "hard"]
RequestedDifficulty = Literal["easy", "medium", "hard", "mixed"]


class QuizGenerateRequest(BaseModel):
    user_input: str = Field(min_length=4, max_length=2000)
    question_count: int = Field(default=5, ge=3, le=5)
    difficulty: RequestedDifficulty = "mixed"

    @field_validator("user_input")
    @classmethod
    def normalize_input(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 4:
            raise ValueError("学习内容至少需要 4 个字符")
        return cleaned


class Option(BaseModel):
    key: str = Field(pattern=r"^[A-F]$")
    text: str = Field(min_length=1, max_length=240)


class Question(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    type: QuestionType
    stem: str = Field(min_length=2, max_length=500)
    options: list[Option] = Field(min_length=2, max_length=6)
    answer: list[str] = Field(min_length=1, max_length=6)
    explanation: str = Field(min_length=2, max_length=1000)
    knowledge_point: str = Field(min_length=1, max_length=100)
    difficulty: Difficulty

    @model_validator(mode="after")
    def validate_answer_contract(self) -> "Question":
        option_keys = [option.key for option in self.options]
        if len(option_keys) != len(set(option_keys)):
            raise ValueError("选项 key 不能重复")
        if not set(self.answer).issubset(set(option_keys)):
            raise ValueError("正确答案必须存在于选项中")
        if len(self.answer) != len(set(self.answer)):
            raise ValueError("正确答案不能重复")
        if self.type in {"single", "judge"} and len(self.answer) != 1:
            raise ValueError("单选题和判断题只能有一个正确答案")
        if self.type == "multiple" and len(self.answer) < 2:
            raise ValueError("多选题至少需要两个正确答案")
        if self.type == "judge" and len(self.options) != 2:
            raise ValueError("判断题必须有两个选项")
        return self


class QuizDraft(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    summary: str = Field(min_length=2, max_length=300)
    questions: list[Question] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def unique_question_ids(self) -> "QuizDraft":
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("题目 ID 不能重复")
        return self


class Quiz(QuizDraft):
    quiz_id: str
    source_type: Literal["text"] = "text"
    user_input: str

