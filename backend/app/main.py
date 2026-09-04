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
from app.core.exceptions import ModelGenerationError
from app.core.security import TokenManager
from app.core.rate_limit import SlidingWindowRateLimiter
from app.db.database import Database
from app.db.repositories import MySQLRepository
from app.integrations.wechat import WechatGateway
from app.llm.base import LearningModelGateway
from app.llm.deepseek_gateway import DeepSeekGateway
from app.services.user_service import UserService


def error_payload(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}


def create_app(
    gateway: LearningModelGateway | None = None,
    user_service: UserService | None = None,
    learning_repository: MySQLRepository | None = None,
    upload_dir: Path | None = None,
    upload_base_url: str | None = None,
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
    app.state.user_service = user_service
    app.state.learning_repository = learning_repository
    avatar_dir = upload_dir or (Path(__file__).resolve().parents[1] / "uploads" / "avatars")
    avatar_dir.mkdir(parents=True, exist_ok=True)
    app.state.avatar_dir = avatar_dir
    app.state.upload_base_url = (upload_base_url or settings.upload_base_url).rstrip("/")
    app.state.login_rate_limiter = SlidingWindowRateLimiter(
        limit=10, window=timedelta(minutes=1)
    )
    app.mount("/uploads/avatars", StaticFiles(directory=avatar_dir), name="avatars")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
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
