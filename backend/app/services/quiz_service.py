import asyncio
from uuid import uuid4

from pydantic import ValidationError

from app.core.exceptions import ModelGenerationError
from app.llm.base import LearningModelGateway
from app.models.quiz import Quiz, QuizDraft, QuizGenerateRequest


class QuizService:
    def __init__(
        self, gateway: LearningModelGateway, max_attempts: int = 2
    ) -> None:
        self.gateway = gateway
        self.max_attempts = max_attempts

    async def generate(self, request: QuizGenerateRequest) -> Quiz:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                raw = await self.gateway.generate_quiz(
                    user_input=request.user_input,
                    question_count=request.question_count,
                    difficulty=request.difficulty,
                )
                draft = QuizDraft.model_validate(raw)
                if len(draft.questions) != request.question_count:
                    raise ValueError("模型返回的题目数量不正确")
                return Quiz(
                    quiz_id=f"quiz_{uuid4().hex[:12]}",
                    source_type="text",
                    user_input=request.user_input,
                    **draft.model_dump(),
                )
            except (ModelGenerationError, ValidationError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < self.max_attempts:
                    await asyncio.sleep(0)
        raise ModelGenerationError("题库生成失败，请重试") from last_error

