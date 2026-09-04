import os

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.db.repositories import MySQLRepository
from app.models.quiz import Quiz
from app.models.report import LearningReport, ReportGenerateRequest
from tests.factories import make_questions


@pytest.fixture
async def mysql_repository():
    if os.getenv("RUN_MYSQL_TESTS") != "1":
        pytest.skip("设置 RUN_MYSQL_TESTS=1 后运行 MySQL 集成测试")
    settings = Settings(
        _env_file=None,
        mysql_host=os.getenv("TEST_MYSQL_HOST", "localhost"),
        mysql_port=int(os.getenv("TEST_MYSQL_PORT", "3306")),
        mysql_user=os.getenv("TEST_MYSQL_USER", "root"),
        mysql_password=os.getenv("TEST_MYSQL_PASSWORD", ""),
        mysql_database="AI-learn-test",
    )
    database = Database(settings)
    await database.connect()
    async with database.require_pool().acquire() as connection:
        async with connection.cursor() as cursor:
            for table in ("reports", "answer_records", "quiz_sessions", "users"):
                await cursor.execute(f"DELETE FROM `{table}`")
        await connection.commit()
    try:
        yield MySQLRepository(database)
    finally:
        async with database.require_pool().acquire() as connection:
            async with connection.cursor() as cursor:
                for table in ("reports", "answer_records", "quiz_sessions", "users"):
                    await cursor.execute(f"DELETE FROM `{table}`")
            await connection.commit()
        await database.close()


def make_quiz() -> Quiz:
    return Quiz(
        quiz_id="quiz_mysql_test",
        title="RAG 入门闯关",
        summary="认识 RAG 的定义与边界",
        source_type="text",
        user_input="我想学习什么是 RAG",
        questions=make_questions(),
    )


def make_report_request(quiz: Quiz) -> ReportGenerateRequest:
    return ReportGenerateRequest(
        quiz_id=quiz.quiz_id,
        topic=quiz.title,
        questions=quiz.questions,
        answer_records=[
            {"question_id": "q1", "selected_answers": ["B"], "duration_ms": 1000},
            {
                "question_id": "q2",
                "selected_answers": ["A", "C"],
                "duration_ms": 2000,
            },
            {"question_id": "q3", "selected_answers": ["A"], "duration_ms": 1000},
        ],
    )


def make_report() -> LearningReport:
    return LearningReport(
        accuracy=67,
        correct_count=2,
        total_count=3,
        xp_earned=30,
        mastered_points=["RAG 定义"],
        weak_points=["RAG 能力边界"],
        answer_results=[
            {
                "question_id": "q1",
                "selected_answers": ["B"],
                "correct_answers": ["B"],
                "is_correct": True,
                "duration_ms": 1000,
            },
            {
                "question_id": "q2",
                "selected_answers": ["A", "C"],
                "correct_answers": ["A", "C"],
                "is_correct": True,
                "duration_ms": 2000,
            },
            {
                "question_id": "q3",
                "selected_answers": ["A"],
                "correct_answers": ["B"],
                "is_correct": False,
                "duration_ms": 1000,
            },
        ],
        three_line_summary=["第一句", "第二句", "第三句"],
        advice=["复习能力边界"],
        share_quote="把知识做成关卡，记得更牢。",
    )


@pytest.mark.anyio
async def test_mysql_login_profile_and_history_persistence(mysql_repository) -> None:
    repository = mysql_repository
    first = await repository.upsert_by_openid("openid-integration")
    second = await repository.upsert_by_openid("openid-integration")
    assert first.id == second.id

    quiz = make_quiz()
    await repository.save_quiz(first.id, quiz)
    persisted = await repository.save_report(
        first.id, make_report_request(quiz), make_report()
    )
    duplicate = await repository.save_report(
        first.id, make_report_request(quiz), make_report()
    )
    assert persisted is True
    assert duplicate is False

    profile = await repository.get_profile(first.id)
    assert profile is not None
    assert profile.total_xp == 30
    assert profile.quiz_count == 1
    assert profile.correct_count == 2

    history = await repository.list_quizzes(first.id, 1, 10)
    assert history.total == 1
    assert history.items[0].quiz_id == quiz.quiz_id

    detail = await repository.get_quiz_detail(first.id, quiz.quiz_id)
    assert detail is not None
    assert len(detail.answer_records) == 3
    assert detail.report is not None


@pytest.mark.anyio
async def test_history_is_scoped_to_current_user(mysql_repository) -> None:
    repository = mysql_repository
    owner = await repository.upsert_by_openid("owner")
    stranger = await repository.upsert_by_openid("stranger")
    quiz = make_quiz()
    await repository.save_quiz(owner.id, quiz)

    assert await repository.get_quiz_detail(stranger.id, quiz.quiz_id) is None
