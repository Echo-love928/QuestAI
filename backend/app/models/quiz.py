from typing import Literal

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.research.models import GroundingMode, QuizSource


QuestionType = Literal["single", "multiple", "judge"]
Difficulty = Literal["easy", "medium", "hard"]
RequestedDifficulty = Literal["easy", "medium", "hard", "mixed"]
SourceType = Literal["text", "url"]
SourceScope = Literal["web", "private", "mixed"]


class QuizGenerateRequest(BaseModel):
    user_input: str = Field(min_length=4, max_length=2000)
    source_type: SourceType = "text"
    question_count: int = Field(default=5, ge=3, le=5)
    difficulty: RequestedDifficulty = "mixed"
    source_scope: SourceScope | None = Field(default=None, exclude_if=lambda value: value is None)
    knowledge_base_ids: list[int] = Field(
        default_factory=list, max_length=5, exclude_if=lambda value: not value
    )

    @field_validator("user_input")
    @classmethod
    def normalize_input(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 4:
            raise ValueError("学习内容至少需要 4 个字符")
        return cleaned

    @field_validator("knowledge_base_ids")
    @classmethod
    def unique_knowledge_base_ids(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError("知识库 ID 无效")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_source_scope(self) -> "QuizGenerateRequest":
        if self.source_scope in {"private", "mixed"} and not self.knowledge_base_ids:
            raise ValueError("私有资料出题必须选择知识库")
        if self.source_scope == "web" and self.knowledge_base_ids:
            raise ValueError("联网模式不能携带知识库")
        if self.source_type == "url" and self.source_scope in {"private", "mixed"}:
            raise ValueError("网页 URL 不能作为私有知识库查询")
        return self


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
    source_ids: list[str] = Field(default_factory=list, max_length=8)

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
    source_type: SourceType = "text"
    user_input: str
    grounding_mode: GroundingMode = "user_content"
    sources: list[QuizSource] = Field(default_factory=list, max_length=8)
    researched_at: datetime | None = None

    @model_validator(mode="after")
    def validate_grounding_sources(self) -> "Quiz":
        if self.grounding_mode == "user_content":
            return self
        source_ids = {source.source_id for source in self.sources}
        if not source_ids:
            raise ValueError("联网题库必须包含来源")
        for question in self.questions:
            if not question.source_ids or not set(question.source_ids).issubset(source_ids):
                raise ValueError("每道联网题目必须引用已知来源")
            if self.grounding_mode in {"private", "hybrid"}:
                private_ids = {
                    source.source_id
                    for source in self.sources
                    if source.source_type == "private_document"
                }
                if not set(question.source_ids) & private_ids:
                    raise ValueError("每道私有资料题目必须引用私有文档")
        return self
