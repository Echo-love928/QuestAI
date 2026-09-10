import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.knowledge.research import private_research_result
from app.models.knowledge import RetrievedChunk
from app.models.quiz import QuizGenerateRequest
from app.services.quiz_service import QuizService
from tests.factories import make_questions
from tests.test_auth_api import FakeUserService
from tests.test_quiz_task_service import MemoryTaskRepository


def chunks():
    return [
        RetrievedChunk(
            chunk_id="chunk-1", knowledge_base_id=3, document_id="doc-safe",
            filename="内部规范.pdf", content="客户投诉时应先安抚情绪并确认核心诉求。" * 4,
            score=.91, chunk_index=0, page=12,
        )
    ]


class FakeRetriever:
    def __init__(self): self.calls = []
    async def retrieve(self, **kwargs): self.calls.append(kwargs); return chunks()


class PrivateGateway:
    def __init__(self): self.context = ""
    async def generate_quiz(self, **kwargs):
        self.context = kwargs["grounding_context"]
        source_id = "private_doc-safe_0"
        return {
            "title": "内部规范闯关", "summary": "按内部资料生成",
            "questions": [q.model_copy(update={"source_ids": [source_id]}).model_dump() for q in make_questions()],
        }


class PublicResearcher:
    def __init__(self): self.inputs = []
    async def research(self, request):
        self.inputs.append(request.user_input)
        from app.research.models import EvidenceSource, ResearchBrief, ResearchFact, ResearchResult
        source = EvidenceSource(source_id="web-1", title="公开背景", url="https://example.com", site_name="example.com", acquisition_method="search_snippet", content="公开背景资料")
        return ResearchResult(
            grounding_mode="web_search", sources=[source],
            brief=ResearchBrief(resolved_topic="投诉", domain="客服", is_ambiguous=False, is_sufficient=True, summary="公开背景", key_facts=[ResearchFact(text="背景", source_ids=["web-1"])])
        )


class ReadyKnowledgeService:
    def __init__(self): self.calls = []
    async def validate_selection(self, user_id, knowledge_base_ids):
        self.calls.append((user_id, knowledge_base_ids))


def test_private_source_is_safe_and_traceable() -> None:
    result = private_research_result(chunks())
    public = result.sources[0].to_public().model_dump()
    assert public["source_type"] == "private_document"
    assert public["document_id"] == "doc-safe"
    assert public["location"] == "第 12 页"
    assert "path" not in public and "storage" not in public


@pytest.mark.anyio
async def test_private_mode_never_calls_public_researcher() -> None:
    gateway, retriever, public = PrivateGateway(), FakeRetriever(), PublicResearcher()
    quiz = await QuizService(gateway, researcher=public, private_retriever=retriever).generate(
        QuizGenerateRequest(user_input="学习内部制度", question_count=3, source_scope="private", knowledge_base_ids=[3]), user_id=7
    )
    assert quiz.grounding_mode == "private"
    assert public.inputs == []
    assert retriever.calls[0]["user_id"] == 7
    assert "客户投诉" in gateway.context


@pytest.mark.anyio
async def test_mixed_mode_researcher_receives_only_original_user_topic() -> None:
    gateway, retriever, public = PrivateGateway(), FakeRetriever(), PublicResearcher()
    await QuizService(gateway, researcher=public, private_retriever=retriever).generate(
        QuizGenerateRequest(user_input="学习内部制度", question_count=3, source_scope="mixed", knowledge_base_ids=[3]), user_id=7
    )
    assert public.inputs == ["学习内部制度"]
    assert "客户投诉" not in public.inputs[0]


@pytest.mark.anyio
async def test_private_quiz_endpoint_requires_login_before_retrieval() -> None:
    app = create_app(
        gateway=PrivateGateway(), learning_repository=object(),
        knowledge_service=ReadyKnowledgeService(), knowledge_retriever=FakeRetriever(),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/quiz/generate", json={
            "user_input": "学习内部制度", "question_count": 3,
            "source_scope": "private", "knowledge_base_ids": [3],
        })
    assert response.status_code == 401


@pytest.mark.anyio
async def test_private_quiz_endpoint_validates_owner_and_generates() -> None:
    users, knowledge, retriever = FakeUserService(), ReadyKnowledgeService(), FakeRetriever()
    app = create_app(
        gateway=PrivateGateway(), user_service=users, learning_repository=object(),
        knowledge_service=knowledge, knowledge_retriever=retriever,
    )
    token = users.tokens.create_access_token(users.user.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/quiz/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={"user_input": "学习内部制度", "question_count": 3,
                  "source_scope": "private", "knowledge_base_ids": [3]},
        )
    assert response.status_code == 200
    assert knowledge.calls == [(7, [3])]
    assert response.json()["data"]["grounding_mode"] == "private"


@pytest.mark.anyio
async def test_private_async_task_completes_and_can_be_polled_by_owner() -> None:
    users, knowledge, retriever = FakeUserService(), ReadyKnowledgeService(), FakeRetriever()
    repository = MemoryTaskRepository()
    app = create_app(
        gateway=PrivateGateway(), user_service=users, learning_repository=repository,
        knowledge_service=knowledge, knowledge_retriever=retriever,
    )
    headers = {"Authorization": f"Bearer {users.tokens.create_access_token(users.user.id)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/quiz/tasks", headers=headers, json={
            "user_input": "学习内部制度", "question_count": 3,
            "source_scope": "private", "knowledge_base_ids": [3],
        })
        task_id = created.json()["data"]["task_id"]
        polled = await client.get(f"/api/v1/quiz/tasks/{task_id}", headers=headers)
    assert created.status_code == 202
    assert polled.json()["data"]["status"] == "completed"
    assert polled.json()["data"]["quiz"]["grounding_mode"] == "private"
