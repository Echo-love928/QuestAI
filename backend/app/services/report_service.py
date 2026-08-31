from app.core.exceptions import ModelGenerationError
from app.llm.base import LearningModelGateway
from app.models.report import LearningReport, ReportGenerateRequest, ReportNarrative
from app.services.scoring_service import score_quiz


class ReportService:
    def __init__(
        self, gateway: LearningModelGateway, max_attempts: int = 2
    ) -> None:
        self.gateway = gateway
        self.max_attempts = max_attempts

    async def generate(self, request: ReportGenerateRequest) -> LearningReport:
        score = score_quiz(request.questions, request.answer_records)
        last_error: Exception | None = None
        for _ in range(self.max_attempts):
            try:
                raw = await self.gateway.generate_report(
                    topic=request.topic,
                    answer_context={
                        "questions": [item.model_dump() for item in request.questions],
                        "answer_records": [
                            item.model_dump() for item in request.answer_records
                        ],
                    },
                    score_context=score.model_dump(exclude={"answer_results"}),
                )
                narrative = ReportNarrative.model_validate(raw)
                return LearningReport(
                    **score.model_dump(),
                    **narrative.model_dump(),
                )
            except Exception as exc:
                last_error = exc
        raise ModelGenerationError("复盘报告生成失败，请重试") from last_error

