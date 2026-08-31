from fastapi import APIRouter, Request

from app.models.common import ApiResponse, HealthData
from app.models.quiz import Quiz, QuizGenerateRequest
from app.models.report import LearningReport, ReportGenerateRequest
from app.services.quiz_service import QuizService
from app.services.report_service import ReportService


router = APIRouter()


@router.get("/health", response_model=ApiResponse[HealthData])
async def health() -> ApiResponse[HealthData]:
    return ApiResponse(data=HealthData())


@router.post("/quiz/generate", response_model=ApiResponse[Quiz])
async def generate_quiz(
    payload: QuizGenerateRequest, request: Request
) -> ApiResponse[Quiz]:
    quiz = await QuizService(request.app.state.gateway).generate(payload)
    return ApiResponse(data=quiz)


@router.post("/report/generate", response_model=ApiResponse[LearningReport])
async def generate_report(
    payload: ReportGenerateRequest, request: Request
) -> ApiResponse[LearningReport]:
    report = await ReportService(request.app.state.gateway).generate(payload)
    return ApiResponse(data=report)

