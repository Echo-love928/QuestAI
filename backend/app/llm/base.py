from typing import Protocol


class LearningModelGateway(Protocol):
    async def generate_quiz(self, **kwargs: object) -> dict: ...

    async def generate_report(self, **kwargs: object) -> dict: ...

