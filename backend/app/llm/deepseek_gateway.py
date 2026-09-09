import json
import logging
from typing import Any

from langchain_deepseek import ChatDeepSeek

from app.core.config import Settings
from app.core.exceptions import ConfigurationError, ModelGenerationError
from app.models.quiz import QuizDraft
from app.models.report import ReportNarrative
from app.prompts.templates import QUIZ_PROMPT, REPORT_PROMPT


logger = logging.getLogger(__name__)


class DeepSeekGateway:
    def __init__(self, settings: Settings, model: Any | None = None) -> None:
        if model is None:
            if not settings.deepseek_api_key:
                raise ConfigurationError("缺少 DEEPSEEK_API_KEY")
            model = ChatDeepSeek(
                model=settings.deepseek_model,
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                temperature=0.4,
                max_tokens=6000,
                timeout=45,
                max_retries=0,
                extra_body={"thinking": {"type": "disabled"}},
            )
        self._quiz_chain = QUIZ_PROMPT | model.with_structured_output(
            QuizDraft, method="json_mode"
        )
        self._report_chain = REPORT_PROMPT | model.with_structured_output(
            ReportNarrative, method="json_mode"
        )

    async def generate_quiz(self, **kwargs: object) -> dict:
        payload = dict(kwargs)
        payload.setdefault("grounding_mode", "user_content")
        payload.setdefault("grounding_context", "仅使用用户提供的学习内容。")
        payload["schema"] = json.dumps(
            QuizDraft.model_json_schema(), ensure_ascii=False
        )
        try:
            result = await self._quiz_chain.ainvoke(payload)
            if result is None:
                raise ValueError("模型返回空内容")
            return result.model_dump() if hasattr(result, "model_dump") else dict(result)
        except Exception as exc:
            logger.exception("quiz generation failed")
            raise ModelGenerationError("题库生成失败") from exc

    async def generate_report(self, **kwargs: object) -> dict:
        payload = dict(kwargs)
        payload["answer_context"] = json.dumps(
            payload.get("answer_context", {}), ensure_ascii=False
        )
        payload["score_context"] = json.dumps(
            payload.get("score_context", {}), ensure_ascii=False
        )
        payload["schema"] = json.dumps(
            ReportNarrative.model_json_schema(), ensure_ascii=False
        )
        try:
            result = await self._report_chain.ainvoke(payload)
            if result is None:
                raise ValueError("模型返回空内容")
            return result.model_dump() if hasattr(result, "model_dump") else dict(result)
        except Exception as exc:
            logger.exception("report generation failed")
            raise ModelGenerationError("复盘报告生成失败") from exc
