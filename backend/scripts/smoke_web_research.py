"""Controlled live smoke test for Tavily + DeepSeek grounded quiz generation."""

import argparse
import asyncio
import json
import logging
from time import monotonic

from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import ResearchError
from app.llm.deepseek_gateway import DeepSeekGateway
from app.models.quiz import QuizGenerateRequest
from app.research.agent import ResearchAgent
from app.services.quiz_service import QuizService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def error_types(exc: BaseException) -> list[str]:
    names = []
    current: BaseException | None = exc
    while current is not None and len(names) < 6:
        names.append(type(current).__name__)
        current = current.__cause__
    return names


def validation_errors(exc: BaseException) -> list[dict]:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, ValidationError):
            return [
                {"loc": list(item["loc"]), "type": item["type"], "msg": item["msg"]}
                for item in current.errors(include_input=False)[:10]
            ]
        current = current.__cause__
    return []


SCENARIOS = {
    "harness": ("Harness Engineering 在 AI Agent 软件工程中是什么？", "text", True),
    "latest": ("LangChain 1.4.0 create_agent 的最新用法", "text", True),
    "simple": ("勾股定理是什么？", "text", True),
    "bilingual": ("模型上下文协议 Model Context Protocol MCP 是什么？", "text", True),
    "global": ("全球 AI Agent 安全最佳实践", "text", True),
    "city": ("2026 年北京市人工智能教育政策", "text", True),
    "url": ("https://docs.langchain.com/oss/python/langchain/agents", "url", True),
    # A failed direct extraction may safely recover through fresh search evidence;
    # the assertion is that it never falls back to unsupported model memory.
    "unextractable": ("https://httpstat.us/404", "url", True),
    "ambiguous": ("Mercury 是什么？", "text", False),
}


async def run_one(name: str, settings: Settings) -> dict:
    value, source_type, expect_success = SCENARIOS[name]
    started = monotonic()
    try:
        quiz = await QuizService(
            DeepSeekGateway(settings),
            researcher=ResearchAgent(settings),
        ).generate(QuizGenerateRequest(user_input=value, source_type=source_type, question_count=3))
        source_ids = {source.source_id for source in quiz.sources}
        citations_valid = all(set(question.source_ids).issubset(source_ids) and question.source_ids for question in quiz.questions)
        return {
            "scenario": name,
            "outcome": "success",
            "expected": expect_success,
            "grounding_mode": quiz.grounding_mode,
            "source_count": len(quiz.sources),
            "sites": sorted({source.site_name for source in quiz.sources}),
            "methods": sorted({source.acquisition_method for source in quiz.sources}),
            "citations_valid": citations_valid,
            "title": quiz.title,
            "questions": [question.stem for question in quiz.questions],
            "duration_ms": int((monotonic() - started) * 1000),
        }
    except ResearchError as exc:
        return {
            "scenario": name,
            "outcome": "research_error",
            "expected": not expect_success,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:300],
            "duration_ms": int((monotonic() - started) * 1000),
        }
    except Exception as exc:
        return {
            "scenario": name,
            "outcome": "unexpected_error",
            "expected": False,
            "error_type": type(exc).__name__,
            "error_chain": error_types(exc),
            "validation_errors": validation_errors(exc),
            "error_message": str(exc)[:500],
            "duration_ms": int((monotonic() - started) * 1000),
        }


async def main(selected: list[str]) -> int:
    settings = Settings()
    if not settings.web_research_enabled or not settings.tavily_api_key or not settings.deepseek_api_key:
        print(json.dumps({"error": "live smoke configuration is incomplete"}))
        return 2
    results = []
    for name in selected:
        result = await run_one(name, settings)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    passed = all(item["expected"] and item["outcome"] != "unexpected_error" for item in results)
    print(json.dumps({"summary": {"passed": passed, "total": len(results)}}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("scenarios", nargs="*", choices=sorted(SCENARIOS), default=["harness"])
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.scenarios)))
