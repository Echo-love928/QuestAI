from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router
from app.core.config import get_settings
from app.core.exceptions import (
    EvidenceInsufficient,
    ExtractUnavailable,
    ModelGenerationError,
    ResearchBudgetExceeded,
    ResearchUnavailable,
    SearchUnavailable,
    TopicAmbiguous,
)
from app.core.security import TokenManager
from app.core.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from app.db.database import Database
from app.db.knowledge_repository import KnowledgeQuotaExceeded, KnowledgeRepository
from app.db.repositories import MySQLRepository
from app.integrations.wechat import WechatGateway
from app.llm.base import LearningModelGateway, ResearchGateway
from app.llm.deepseek_gateway import DeepSeekGateway
from app.research.agent import ResearchAgent
from app.research.safety import UnsafeUrlError
from app.services.user_service import UserService
from app.services.knowledge_service import KnowledgeNotFound, KnowledgeService
from app.knowledge.chunking import DocumentChunker
from app.knowledge.embeddings import BailianEmbeddingGateway
from app.knowledge.files import KnowledgeFileStore
from app.knowledge.ingestion import IngestionService
from app.knowledge.parsers import DocumentParser, LegacyDocParser
from app.knowledge.vector_store import ChromaKnowledgeStore
from app.knowledge.retriever import KnowledgeRetriever


def error_payload(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}


def create_app(
    gateway: LearningModelGateway | None = None,
    researcher: ResearchGateway | None = None,
    user_service: UserService | None = None,
    learning_repository: MySQLRepository | None = None,
    upload_dir: Path | None = None,
    upload_base_url: str | None = None,
    knowledge_service: KnowledgeService | None = None,
    knowledge_retriever: KnowledgeRetriever | None = None,
) -> FastAPI:
    settings = get_settings()
    database: Database | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.gateway = gateway or DeepSeekGateway(settings)
        nonlocal database
        if app.state.user_service is None or app.state.learning_repository is None:
            database = Database(settings)
            await database.connect()
            repository = MySQLRepository(database)
            app.state.learning_repository = repository
            if app.state.user_service is None:
                app.state.user_service = UserService(
                    repository,
                    WechatGateway(settings.wechat_app_id, settings.wechat_app_secret),
                    TokenManager(
                        settings.jwt_secret,
                        expires_delta=timedelta(hours=settings.jwt_expires_hours),
                    ),
                )
            if app.state.knowledge_service is None and settings.dashscope_api_key:
                knowledge_repository = KnowledgeRepository(database)
                file_store = KnowledgeFileStore(settings.knowledge_upload_dir, max_bytes=settings.knowledge_file_max_bytes)
                vector_store = ChromaKnowledgeStore(settings.chroma_persist_dir)
                embedding = BailianEmbeddingGateway(
                    api_key=settings.dashscope_api_key,
                    base_url=settings.dashscope_base_url,
                    model=settings.embedding_model,
                    dimensions=settings.embedding_dimensions,
                    batch_size=settings.embedding_batch_size,
                )
                ingestion = IngestionService(
                    repository=knowledge_repository,
                    files=file_store,
                    parser=DocumentParser(
                        max_chars=settings.knowledge_max_chars,
                        legacy_parser=LegacyDocParser(settings.tika_server_endpoint),
                    ),
                    chunker=DocumentChunker(
                        chunk_size=settings.knowledge_chunk_size,
                        chunk_overlap=settings.knowledge_chunk_overlap,
                        max_chunks=settings.knowledge_max_chunks,
                    ),
                    embedding=embedding,
                    store=vector_store,
                    embedding_model=settings.embedding_model,
                    embedding_dimensions=settings.embedding_dimensions,
                )
                app.state.knowledge_service = KnowledgeService(
                    repository=knowledge_repository,
                    file_store=file_store,
                    vector_store=vector_store,
                    ingestion=ingestion,
                    knowledge_base_limit=settings.knowledge_base_limit,
                    document_limit=settings.knowledge_document_limit,
                )
                app.state.knowledge_retriever = KnowledgeRetriever(
                    embedding,
                    vector_store,
                    top_k=settings.knowledge_retrieval_top_k,
                    min_score=settings.knowledge_retrieval_min_score,
                    max_per_document=settings.knowledge_max_chunks_per_document,
                    min_total_chars=settings.knowledge_retrieval_min_total_chars,
                )
                await ingestion.recover()
        try:
            yield
        finally:
            if database is not None:
                await database.close()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.gateway = gateway or DeepSeekGateway(settings)
    app.state.researcher = researcher or (
        ResearchAgent(settings)
        if gateway is None and settings.web_research_enabled
        else None
    )
    app.state.user_service = user_service
    app.state.learning_repository = learning_repository
    app.state.knowledge_service = knowledge_service
    app.state.knowledge_retriever = knowledge_retriever
    avatar_dir = upload_dir or (Path(__file__).resolve().parents[1] / "uploads" / "avatars")
    avatar_dir.mkdir(parents=True, exist_ok=True)
    app.state.avatar_dir = avatar_dir
    app.state.upload_base_url = (upload_base_url or settings.upload_base_url).rstrip("/")
    app.state.login_rate_limiter = SlidingWindowRateLimiter(
        limit=10, window=timedelta(minutes=1)
    )
    app.state.quiz_rate_limiter = SlidingWindowRateLimiter(
        limit=10,
        window=timedelta(minutes=1),
        message="题目生成请求过于频繁，请稍后重试",
    )
    app.mount("/uploads/avatars", StaticFiles(directory=avatar_dir), name="avatars")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.include_router(router, prefix=settings.api_prefix)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(4000, "请求参数不正确，请检查后重试"),
        )

    @app.exception_handler(ModelGenerationError)
    async def model_error_handler(
        _request: Request, _exc: ModelGenerationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=error_payload(5001, "AI 生成失败，请稍后重试"),
        )

    @app.exception_handler(KnowledgeNotFound)
    async def knowledge_not_found(_: Request, exc: KnowledgeNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content=error_payload(4404, str(exc)))

    @app.exception_handler(KnowledgeQuotaExceeded)
    async def knowledge_quota_exceeded(_: Request, exc: KnowledgeQuotaExceeded) -> JSONResponse:
        return JSONResponse(status_code=409, content=error_payload(4409, str(exc)))

    async def research_error_response(
        status_code: int, code: int, message: str
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content=error_payload(code, message),
        )

    @app.exception_handler(SearchUnavailable)
    async def search_error_handler(
        _request: Request, _exc: SearchUnavailable
    ) -> JSONResponse:
        return await research_error_response(503, 5101, "暂时无法获取最新资料，请稍后重试")

    @app.exception_handler(ExtractUnavailable)
    async def extract_error_handler(
        _request: Request, _exc: ExtractUnavailable
    ) -> JSONResponse:
        return await research_error_response(503, 5102, "暂时无法读取网页，请检查网址或稍后重试")

    @app.exception_handler(EvidenceInsufficient)
    async def evidence_error_handler(
        _request: Request, _exc: EvidenceInsufficient
    ) -> JSONResponse:
        return await research_error_response(422, 4102, "资料不足，请补充更明确的主题或原始内容")

    @app.exception_handler(TopicAmbiguous)
    async def ambiguous_error_handler(
        _request: Request, _exc: TopicAmbiguous
    ) -> JSONResponse:
        return await research_error_response(409, 4103, "主题存在多种含义，请补充所属领域")

    @app.exception_handler(ResearchBudgetExceeded)
    async def budget_error_handler(
        _request: Request, _exc: ResearchBudgetExceeded
    ) -> JSONResponse:
        return await research_error_response(503, 4104, "本次资料获取已达上限，请缩小主题后重试")

    @app.exception_handler(ResearchUnavailable)
    async def research_unavailable_handler(
        _request: Request, _exc: ResearchUnavailable
    ) -> JSONResponse:
        return await research_error_response(503, 5100, "联网研究暂时不可用，请稍后重试")

    @app.exception_handler(UnsafeUrlError)
    async def unsafe_url_handler(
        _request: Request, _exc: UnsafeUrlError
    ) -> JSONResponse:
        return await research_error_response(400, 4101, "网址不可访问，请使用公开的 HTTP(S) 网页")

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(
        _request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return await research_error_response(429, 4290, str(exc))

    @app.exception_handler(ValueError)
    async def value_error_handler(
        _request: Request, exc: ValueError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_payload(4001, str(exc)),
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        code = 4003 if exc.status_code == 401 else 4004
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, str(exc.detail)),
        )

    return app


app = create_app()
