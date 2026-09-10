import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.knowledge.embeddings import BailianEmbeddingGateway
from app.llm.deepseek_gateway import DeepSeekGateway
from app.models.knowledge import RetrievedChunk
from app.models.quiz import QuizGenerateRequest
from app.research.agent import ResearchAgent
from app.services.quiz_service import QuizService


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_RAG_TESTS") != "1",
    reason="设置 RUN_LIVE_RAG_TESTS=1 后运行真实外部 API 烟雾测试",
)


def private_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="live-smoke", knowledge_base_id=1, document_id="doc_live_smoke",
        filename="无敏感测试规范.md", section="基本定义", chunk_index=0, score=.96,
        content="RAG 先检索授权资料，再把相关片段作为依据交给生成模型；题目必须引用检索来源。",
    )


@pytest.mark.anyio
async def test_live_bailian_embedding_dimensions() -> None:
    settings = Settings()
    gateway = BailianEmbeddingGateway(
        api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url,
        model=settings.embedding_model, dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
    )
    vectors = await gateway.embed_documents(["无敏感的知识库烟雾测试内容"])
    assert len(vectors) == 1
    assert len(vectors[0]) == settings.embedding_dimensions


@pytest.mark.anyio
async def test_live_private_and_mixed_quiz_have_private_citations() -> None:
    settings = Settings()
    retriever = SimpleNamespace(retrieve=AsyncMock(return_value=[private_chunk()]))
    service = QuizService(
        DeepSeekGateway(settings), researcher=ResearchAgent(settings), private_retriever=retriever
    )
    for scope in ("private", "mixed"):
        quiz = await service.generate(
            QuizGenerateRequest(
                user_input="学习 RAG 的基本原理和公开背景", question_count=3,
                source_scope=scope, knowledge_base_ids=[1],
            ),
            user_id=1,
        )
        private_ids = {source.source_id for source in quiz.sources if source.source_type == "private_document"}
        assert private_ids
        assert all(set(question.source_ids) & private_ids for question in quiz.questions)
