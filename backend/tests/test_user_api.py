from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.user import (
    QuizHistoryDetail,
    QuizHistoryItem,
    QuizHistoryPage,
    UserProfile,
)
from tests.test_api import ApiGateway
from tests.test_auth_api import FakeUserService


class FakeLearningRepository:
    def __init__(self) -> None:
        self.saved_quizzes: list[tuple[int, object]] = []
        self.saved_reports: list[tuple[int, object, object]] = []
        self.profile = UserProfile(
            id=7,
            nickname="学习者",
            avatar_url=None,
            total_xp=40,
            quiz_count=2,
            correct_count=3,
            average_accuracy=75,
        )

    async def save_quiz(self, user_id: int, quiz: object) -> None:
        self.saved_quizzes.append((user_id, quiz))

    async def save_report(self, user_id: int, payload: object, report: object) -> bool:
        self.saved_reports.append((user_id, payload, report))
        return True

    async def get_profile(self, user_id: int) -> UserProfile | None:
        return self.profile if user_id == 7 else None

    async def update_profile(self, user_id: int, update) -> UserProfile | None:
        if update.nickname is not None:
            self.profile.nickname = update.nickname
        if update.avatar_url is not None:
            self.profile.avatar_url = update.avatar_url
        return self.profile

    async def list_quizzes(self, user_id: int, page: int, page_size: int):
        return QuizHistoryPage(
            items=[
                QuizHistoryItem(
                    quiz_id="quiz_one",
                    title="RAG 入门",
                    accuracy=80,
                    question_count=5,
                    correct_count=4,
                    xp_earned=50,
                    status="completed",
                    created_at=datetime(2026, 9, 4, 10, 0, 0),
                )
            ],
            total=1,
            page=page,
            page_size=page_size,
        )

    async def get_quiz_detail(self, user_id: int, quiz_id: str):
        if quiz_id != "quiz_one":
            return None
        return QuizHistoryDetail(
            quiz={"quiz_id": quiz_id, "title": "RAG 入门"},
            answer_records=[],
            report=None,
        )


async def request(app, method: str, path: str, **kwargs):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, path, **kwargs)


def authenticated_app():
    user_service = FakeUserService()
    repository = FakeLearningRepository()
    app = create_app(
        gateway=ApiGateway(),
        user_service=user_service,
        learning_repository=repository,
    )
    token = user_service.tokens.create_access_token(user_service.user.id)
    return app, repository, {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_profile_requires_login() -> None:
    app, _, _ = authenticated_app()
    response = await request(app, "GET", "/api/v1/user/profile")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_get_and_update_profile() -> None:
    app, _, headers = authenticated_app()
    response = await request(app, "GET", "/api/v1/user/profile", headers=headers)
    assert response.json()["data"]["quiz_count"] == 2

    response = await request(
        app,
        "PUT",
        "/api/v1/user/profile",
        headers=headers,
        json={"nickname": "鱼仔同学"},
    )
    assert response.json()["data"]["nickname"] == "鱼仔同学"


@pytest.mark.anyio
async def test_history_list_and_owner_scoped_detail() -> None:
    app, _, headers = authenticated_app()
    listing = await request(
        app, "GET", "/api/v1/user/quizzes?page=1&page_size=10", headers=headers
    )
    assert listing.json()["data"]["items"][0]["quiz_id"] == "quiz_one"

    missing = await request(
        app, "GET", "/api/v1/user/quizzes/not-owned", headers=headers
    )
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_authenticated_core_flow_is_persisted() -> None:
    app, repository, headers = authenticated_app()
    quiz_response = await request(
        app,
        "POST",
        "/api/v1/quiz/generate",
        headers=headers,
        json={"user_input": "我想学习什么是 RAG", "question_count": 3},
    )
    quiz = quiz_response.json()["data"]
    assert len(repository.saved_quizzes) == 1

    report_response = await request(
        app,
        "POST",
        "/api/v1/report/generate",
        headers=headers,
        json={
            "quiz_id": quiz["quiz_id"],
            "topic": quiz["title"],
            "questions": quiz["questions"],
            "answer_records": [
                {"question_id": "q1", "selected_answers": ["B"]},
                {"question_id": "q2", "selected_answers": ["A", "C"]},
                {"question_id": "q3", "selected_answers": ["A"]},
            ],
        },
    )
    assert report_response.status_code == 200
    assert len(repository.saved_reports) == 1


@pytest.mark.anyio
async def test_anonymous_core_flow_does_not_write_database() -> None:
    app, repository, _ = authenticated_app()
    response = await request(
        app,
        "POST",
        "/api/v1/quiz/generate",
        json={"user_input": "我想学习什么是 RAG", "question_count": 3},
    )
    assert response.status_code == 200
    assert repository.saved_quizzes == []


@pytest.mark.anyio
async def test_avatar_upload_updates_profile(tmp_path) -> None:
    user_service = FakeUserService()
    repository = FakeLearningRepository()
    app = create_app(
        gateway=ApiGateway(),
        user_service=user_service,
        learning_repository=repository,
        upload_dir=tmp_path,
        upload_base_url="http://test",
    )
    token = user_service.tokens.create_access_token(user_service.user.id)
    response = await request(
        app,
        "POST",
        "/api/v1/user/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\nimage", "image/png")},
    )
    assert response.status_code == 200
    avatar_url = response.json()["data"]["avatar_url"]
    assert avatar_url.startswith("http://test/uploads/avatars/")
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.anyio
async def test_avatar_upload_rejects_non_image(tmp_path) -> None:
    user_service = FakeUserService()
    app = create_app(
        gateway=ApiGateway(),
        user_service=user_service,
        learning_repository=FakeLearningRepository(),
        upload_dir=tmp_path,
    )
    token = user_service.tokens.create_access_token(user_service.user.id)
    response = await request(
        app,
        "POST",
        "/api/v1/user/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("notes.txt", b"not-an-image", "text/plain")},
    )
    assert response.status_code == 400
