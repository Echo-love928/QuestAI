import asyncio
import json
from uuid import uuid4

from pydantic import ValidationError

from app.core.exceptions import ModelGenerationError
from app.llm.base import LearningModelGateway, ResearchGateway
from app.models.quiz import Quiz, QuizDraft, QuizGenerateRequest
from app.knowledge.research import combine_private_and_public, private_research_result
from app.knowledge.retriever import PrivateEvidenceInsufficient


class QuizService:
    def __init__(
        self,
        gateway: LearningModelGateway,
        researcher: ResearchGateway | None = None,
        private_retriever=None,
        max_attempts: int = 2,
    ) -> None:
        self.gateway = gateway
        self.researcher = researcher
        self.private_retriever = private_retriever
        self.max_attempts = max_attempts

    async def generate(self, request: QuizGenerateRequest, user_id: int | None = None) -> Quiz:
        if request.source_scope in {"private", "mixed"}:
            if user_id is None or self.private_retriever is None:
                raise PrivateEvidenceInsufficient("私有资料出题需要登录并选择可用知识库")
            chunks = await self.private_retriever.retrieve(
                user_id=user_id,
                knowledge_base_ids=request.knowledge_base_ids,
                query=request.user_input,
            )
            private = private_research_result(chunks)
            public = None
            if request.source_scope == "mixed" and self.researcher:
                public_request = request.model_copy(
                    update={"source_scope": "web", "knowledge_base_ids": []}
                )
                public = await self.researcher.research(public_request)
            research = combine_private_and_public(private, public)
        else:
            research = await self.researcher.research(request) if self.researcher else None
        grounding_mode = research.grounding_mode if research else "user_content"
        selected_sources = research.sources[:8] if research else []
        sources = [source.to_public() for source in selected_sources]
        if research and research.brief:
            selected_ids = {source.source_id for source in selected_sources}
            prompt_brief = research.brief.model_dump(mode="json")
            prompt_brief["key_facts"] = [
                {
                    **fact.model_dump(mode="json"),
                    "source_ids": [
                        source_id
                        for source_id in fact.source_ids
                        if source_id in selected_ids
                    ],
                }
                for fact in research.brief.key_facts
                if set(fact.source_ids) & selected_ids
            ]
            prompt_brief["first_party_source_ids"] = [
                source_id
                for source_id in research.brief.first_party_source_ids
                if source_id in selected_ids
            ]
            grounding_context = json.dumps(
                {
                    "research": prompt_brief,
                    "sources": [source.to_agent() for source in selected_sources],
                },
                ensure_ascii=False,
            )
        else:
            grounding_context = "仅使用用户提供的学习内容。"
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                raw = await self.gateway.generate_quiz(
                    user_input=request.user_input,
                    question_count=request.question_count,
                    difficulty=request.difficulty,
                    grounding_mode=grounding_mode,
                    grounding_context=grounding_context,
                )
                draft = QuizDraft.model_validate(raw)
                if len(draft.questions) != request.question_count:
                    raise ValueError("模型返回的题目数量不正确")
                return Quiz(
                    quiz_id=f"quiz_{uuid4().hex[:12]}",
                    source_type=request.source_type,
                    grounding_mode=grounding_mode,
                    sources=sources,
                    researched_at=research.researched_at if research else None,
                    user_input=request.user_input,
                    **draft.model_dump(),
                )
            except (ModelGenerationError, ValidationError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < self.max_attempts:
                    await asyncio.sleep(0)
        raise ModelGenerationError("题库生成失败，请重试") from last_error
