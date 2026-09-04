import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import TokenManager
from app.main import create_app
from app.models.user import LoginResult, User
from tests.test_api import ApiGateway


class FakeUserService:
    def __init__(self) -> None:
        self.user = User(
            id=7,
            nickname="学习者",
            avatar_url=None,
            total_xp=0,
            token_version=0,
        )
        self.tokens = TokenManager("test-secret-with-at-least-32-characters")

    async def login(self, code: str) -> LoginResult:
        assert code == "wx-code"
        return LoginResult(
            token=self.tokens.create_access_token(self.user.id),
            user=self.user,
        )

    async def authenticate(self, token: str) -> User:
        claims = self.tokens.decode_access_token(token)
        if claims.user_id != self.user.id:
            raise ValueError("用户不存在")
        return self.user


async def request(app, method: str, path: str, **kwargs):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.anyio
async def test_login_endpoint() -> None:
    app = create_app(gateway=ApiGateway(), user_service=FakeUserService())

    response = await request(
        app, "POST", "/api/v1/user/login", json={"code": "wx-code"}
    )

    assert response.status_code == 200
    assert response.json()["data"]["user"]["id"] == 7
    assert response.json()["data"]["token"]


@pytest.mark.anyio
async def test_core_endpoint_stays_anonymous_without_token() -> None:
    app = create_app(gateway=ApiGateway(), user_service=FakeUserService())

    response = await request(
        app,
        "POST",
        "/api/v1/quiz/generate",
        json={"user_input": "我想学习什么是 RAG", "question_count": 3},
    )

    assert response.status_code == 200


@pytest.mark.anyio
async def test_invalid_token_returns_401_even_for_core_endpoint() -> None:
    app = create_app(gateway=ApiGateway(), user_service=FakeUserService())

    response = await request(
        app,
        "POST",
        "/api/v1/quiz/generate",
        headers={"Authorization": "Bearer invalid-token"},
        json={"user_input": "我想学习什么是 RAG", "question_count": 3},
    )

    assert response.status_code == 401
    assert response.json()["code"] == 4003


@pytest.mark.anyio
async def test_login_endpoint_is_rate_limited() -> None:
    app = create_app(gateway=ApiGateway(), user_service=FakeUserService())
    for _ in range(10):
        response = await request(
            app, "POST", "/api/v1/user/login", json={"code": "wx-code"}
        )
        assert response.status_code == 200

    response = await request(
        app, "POST", "/api/v1/user/login", json={"code": "wx-code"}
    )
    assert response.status_code == 429
    assert "频繁" in response.json()["message"]
