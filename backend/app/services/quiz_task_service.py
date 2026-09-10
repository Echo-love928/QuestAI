import logging
from uuid import uuid4

from app.core.exceptions import (
    EvidenceInsufficient,
    ExtractUnavailable,
    ModelGenerationError,
    ResearchBudgetExceeded,
    ResearchUnavailable,
    SearchUnavailable,
    TopicAmbiguous,
)
from app.llm.base import LearningModelGateway, ResearchGateway
from app.models.quiz import QuizGenerateRequest
from app.models.quiz_task import QuizTaskStatus
from app.research.safety import UnsafeUrlError
from app.services.quiz_service import QuizService


logger = logging.getLogger(__name__)

SAFE_TASK_ERRORS = (
    (UnsafeUrlError, 4101, "网址不可访问，请使用公开的 HTTP(S) 网页"),
    (EvidenceInsufficient, 4102, "资料不足，请补充更明确的主题或原始内容"),
    (TopicAmbiguous, 4103, "主题存在多种含义，请补充所属领域"),
    (ResearchBudgetExceeded, 4104, "本次资料获取已达上限，请缩小主题后重试"),
    (SearchUnavailable, 5101, "暂时无法获取最新资料，请稍后重试"),
    (ExtractUnavailable, 5102, "暂时无法读取网页，请检查网址或稍后重试"),
    (ResearchUnavailable, 5100, "联网研究暂时不可用，请稍后重试"),
    (ModelGenerationError, 5001, "AI 生成失败，请稍后重试"),
)


class QuizTaskService:
    def __init__(
        self,
        gateway: LearningModelGateway,
        repository,
        researcher: ResearchGateway | None = None,
        private_retriever=None,
    ) -> None:
        self.repository = repository
        self.quiz_service = QuizService(
            gateway, researcher=researcher, private_retriever=private_retriever
        )

    async def create(
        self, request: QuizGenerateRequest, user_id: int | None
    ) -> QuizTaskStatus:
        task_id = f"task_{uuid4().hex}"
        return await self.repository.create_quiz_task(task_id, user_id, request)

    async def get(
        self, task_id: str, user_id: int | None
    ) -> QuizTaskStatus | None:
        result = await self.repository.get_quiz_task(task_id)
        if result is None:
            return None
        task, owner_id = result
        if owner_id is not None and owner_id != user_id:
            return None
        return task

    async def run(
        self,
        task_id: str,
        request: QuizGenerateRequest,
        user_id: int | None,
    ) -> None:
        await self.repository.mark_quiz_task_processing(task_id)
        try:
            quiz = await self.quiz_service.generate(request, user_id=user_id)
            if user_id is not None:
                await self.repository.save_quiz(user_id, quiz)
            await self.repository.complete_quiz_task(task_id, quiz)
        except Exception as exc:
            error_code, error_message = self._safe_error(exc)
            logger.error(
                "异步题目生成失败",
                extra={"task_id": task_id, "error_type": type(exc).__name__},
            )
            await self.repository.fail_quiz_task(
                task_id, error_code, error_message
            )

    @staticmethod
    def _safe_error(exc: Exception) -> tuple[int, str]:
        for error_type, code, message in SAFE_TASK_ERRORS:
            if isinstance(exc, error_type):
                return code, message
        return 5000, "题目生成任务失败，请稍后重试"
