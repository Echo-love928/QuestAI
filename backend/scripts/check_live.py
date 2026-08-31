"""手动验证真实 DeepSeek 链路；不会输出密钥或完整题目内容。"""

import asyncio

from app.core.config import get_settings
from app.llm.deepseek_gateway import DeepSeekGateway
from app.models.quiz import QuizGenerateRequest
from app.models.report import AnswerRecord, ReportGenerateRequest
from app.services.quiz_service import QuizService
from app.services.report_service import ReportService


async def main() -> None:
    gateway = DeepSeekGateway(get_settings())
    try:
        quiz = await QuizService(gateway).generate(
            QuizGenerateRequest(
                user_input="我想学习 RAG 的基本概念、应用场景和能力边界",
                question_count=3,
                difficulty="mixed",
            )
        )
        records = [
            AnswerRecord(
                question_id=question.id,
                selected_answers=question.answer,
                duration_ms=1000,
            )
            for question in quiz.questions
        ]
        report = await ReportService(gateway).generate(
            ReportGenerateRequest(
                quiz_id=quiz.quiz_id,
                topic=quiz.title,
                questions=quiz.questions,
                answer_records=records,
            )
        )
    except Exception as exc:
        cause = exc.__cause__
        print(
            {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "cause_type": type(cause).__name__ if cause else None,
                "cause": str(cause)[:1000] if cause else None,
            }
        )
        raise SystemExit(1) from None

    print(
        {
            "ok": True,
            "question_count": len(quiz.questions),
            "report_accuracy": report.accuracy,
            "summary_lines": len(report.three_line_summary),
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
