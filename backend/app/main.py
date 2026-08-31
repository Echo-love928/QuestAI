from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router
from app.core.config import get_settings
from app.core.exceptions import ModelGenerationError
from app.llm.base import LearningModelGateway
from app.llm.deepseek_gateway import DeepSeekGateway


def error_payload(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}


def create_app(gateway: LearningModelGateway | None = None) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.gateway = gateway or DeepSeekGateway(settings)
        yield

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.gateway = gateway or DeepSeekGateway(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
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

    return app


app = create_app()

