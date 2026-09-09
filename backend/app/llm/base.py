from typing import Protocol

from app.models.quiz import QuizGenerateRequest
from app.research.models import ResearchResult


class LearningModelGateway(Protocol):
    async def generate_quiz(self, **kwargs: object) -> dict: ...

    async def generate_report(self, **kwargs: object) -> dict: ...


class ResearchGateway(Protocol):
    async def research(self, request: QuizGenerateRequest) -> ResearchResult: ...
