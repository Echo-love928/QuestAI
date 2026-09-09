import logging
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile

from app.api.dependencies import optional_user, required_user
from app.core.rate_limit import RateLimitExceeded
from app.models.common import ApiResponse, HealthData
from app.models.quiz import Quiz, QuizGenerateRequest
from app.models.quiz_task import QuizTaskStatus
from app.models.report import LearningReport, ReportGenerateRequest
from app.services.quiz_service import QuizService
from app.services.quiz_task_service import QuizTaskService
from app.services.report_service import ReportService
from app.models.user import (
    LoginRequest,
    LoginResult,
    QuizHistoryDetail,
    QuizHistoryPage,
    User,
    UserProfile,
    UserProfileUpdate,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=ApiResponse[HealthData])
async def health() -> ApiResponse[HealthData]:
    return ApiResponse(data=HealthData())


@router.post("/quiz/generate", response_model=ApiResponse[Quiz])
async def generate_quiz(
    payload: QuizGenerateRequest,
    request: Request,
    user: Annotated[User | None, Depends(optional_user)],
) -> ApiResponse[Quiz]:
    client_key = f"user:{user.id}" if user is not None else (
        request.client.host if request.client else "anonymous"
    )
    request.app.state.quiz_rate_limiter.check(client_key)
    quiz = await QuizService(
        request.app.state.gateway,
        researcher=request.app.state.researcher,
    ).generate(payload)
    repository = request.app.state.learning_repository
    if user is not None and repository is not None:
        try:
            await repository.save_quiz(user.id, quiz)
        except Exception:
            logger.exception("保存闯关题目失败", extra={"quiz_id": quiz.quiz_id})
    return ApiResponse(data=quiz)


@router.post(
    "/quiz/tasks",
    response_model=ApiResponse[QuizTaskStatus],
    status_code=202,
)
async def create_quiz_task(
    payload: QuizGenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: Annotated[User | None, Depends(optional_user)],
) -> ApiResponse[QuizTaskStatus]:
    client_key = f"user:{user.id}" if user is not None else (
        request.client.host if request.client else "anonymous"
    )
    request.app.state.quiz_rate_limiter.check(client_key)
    repository = request.app.state.learning_repository
    if repository is None:
        raise HTTPException(status_code=503, detail="任务服务暂时不可用")
    service = QuizTaskService(
        request.app.state.gateway,
        repository,
        researcher=request.app.state.researcher,
    )
    task = await service.create(payload, user.id if user is not None else None)
    background_tasks.add_task(
        service.run, task.task_id, payload, user.id if user is not None else None
    )
    return ApiResponse(data=task)


@router.get(
    "/quiz/tasks/{task_id}",
    response_model=ApiResponse[QuizTaskStatus],
)
async def get_quiz_task(
    task_id: str,
    request: Request,
    user: Annotated[User | None, Depends(optional_user)],
) -> ApiResponse[QuizTaskStatus]:
    repository = request.app.state.learning_repository
    if repository is None:
        raise HTTPException(status_code=503, detail="任务服务暂时不可用")
    task = await QuizTaskService(
        request.app.state.gateway,
        repository,
        researcher=request.app.state.researcher,
    ).get(task_id, user.id if user is not None else None)
    if task is None:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    return ApiResponse(data=task)


@router.post("/report/generate", response_model=ApiResponse[LearningReport])
async def generate_report(
    payload: ReportGenerateRequest,
    request: Request,
    user: Annotated[User | None, Depends(optional_user)],
) -> ApiResponse[LearningReport]:
    report = await ReportService(request.app.state.gateway).generate(payload)
    repository = request.app.state.learning_repository
    if user is not None and repository is not None:
        try:
            await repository.save_report(user.id, payload, report)
        except Exception:
            logger.exception("保存闯关报告失败", extra={"quiz_id": payload.quiz_id})
    return ApiResponse(data=report)


@router.post("/user/login", response_model=ApiResponse[LoginResult])
async def login(payload: LoginRequest, request: Request) -> ApiResponse[LoginResult]:
    client_key = request.client.host if request.client else "unknown"
    try:
        request.app.state.login_rate_limiter.check(client_key)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from None
    service = request.app.state.user_service
    if service is None:
        raise HTTPException(status_code=503, detail="用户服务暂时不可用")
    return ApiResponse(data=await service.login(payload.code))


@router.get("/user/profile", response_model=ApiResponse[UserProfile])
async def get_profile(
    request: Request,
    user: Annotated[User, Depends(required_user)],
) -> ApiResponse[UserProfile]:
    profile = await request.app.state.learning_repository.get_profile(user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ApiResponse(data=profile)


@router.put("/user/profile", response_model=ApiResponse[UserProfile])
async def update_profile(
    payload: UserProfileUpdate,
    request: Request,
    user: Annotated[User, Depends(required_user)],
) -> ApiResponse[UserProfile]:
    profile = await request.app.state.learning_repository.update_profile(user.id, payload)
    if profile is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ApiResponse(data=profile)


@router.post("/user/avatar", response_model=ApiResponse[UserProfile])
async def upload_avatar(
    request: Request,
    user: Annotated[User, Depends(required_user)],
    file: Annotated[UploadFile, File()],
) -> ApiResponse[UserProfile]:
    content_types = {
        "image/jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
        "image/png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
        "image/webp": (
            ".webp",
            lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
        ),
    }
    media_type = file.content_type or ""
    if media_type not in content_types:
        raise HTTPException(status_code=400, detail="头像仅支持 JPG、PNG 或 WebP")
    content = await file.read(2 * 1024 * 1024 + 1)
    suffix, is_valid = content_types[media_type]
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像不能超过 2MB")
    if not is_valid(content):
        raise HTTPException(status_code=400, detail="头像文件格式不正确")
    filename = f"user-{user.id}-{uuid4().hex}{suffix}"
    (request.app.state.avatar_dir / filename).write_bytes(content)
    avatar_url = f"{request.app.state.upload_base_url}/uploads/avatars/{filename}"
    profile = await request.app.state.learning_repository.update_profile(
        user.id, UserProfileUpdate(avatar_url=avatar_url)
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ApiResponse(data=profile)


@router.get("/user/quizzes", response_model=ApiResponse[QuizHistoryPage])
async def list_quizzes(
    request: Request,
    user: Annotated[User, Depends(required_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ApiResponse[QuizHistoryPage]:
    return ApiResponse(
        data=await request.app.state.learning_repository.list_quizzes(
            user.id, page, page_size
        )
    )


@router.get(
    "/user/quizzes/{quiz_id}", response_model=ApiResponse[QuizHistoryDetail]
)
async def get_quiz_detail(
    quiz_id: str,
    request: Request,
    user: Annotated[User, Depends(required_user)],
) -> ApiResponse[QuizHistoryDetail]:
    detail = await request.app.state.learning_repository.get_quiz_detail(
        user.id, quiz_id
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="闯关记录不存在")
    return ApiResponse(data=detail)
