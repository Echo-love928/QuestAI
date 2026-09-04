from dataclasses import dataclass

import pytest

from app.core.security import TokenManager
from app.models.user import User
from app.services.user_service import UserService


@dataclass
class FakeWechatGateway:
    openid: str = "openid-user-1"

    async def exchange_code(self, code: str) -> str:
        assert code == "wx-code"
        return self.openid


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    async def upsert_by_openid(self, openid: str) -> User:
        if openid not in self.users:
            self.users[openid] = User(
                id=len(self.users) + 1,
                nickname="学习者",
                avatar_url=None,
                total_xp=0,
                token_version=0,
            )
        return self.users[openid]

    async def get_by_id(self, user_id: int) -> User | None:
        return next((user for user in self.users.values() if user.id == user_id), None)


@pytest.mark.anyio
async def test_login_registers_user_and_returns_token() -> None:
    repository = FakeUserRepository()
    service = UserService(
        repository,
        FakeWechatGateway(),
        TokenManager("test-secret-with-at-least-32-characters"),
    )

    result = await service.login("wx-code")

    assert result.user.nickname == "学习者"
    assert (await service.authenticate(result.token)).id == result.user.id


@pytest.mark.anyio
async def test_repeated_login_reuses_same_user_without_revoking_old_token() -> None:
    repository = FakeUserRepository()
    service = UserService(
        repository,
        FakeWechatGateway(),
        TokenManager("test-secret-with-at-least-32-characters"),
    )

    first = await service.login("wx-code")
    second = await service.login("wx-code")

    assert first.user.id == second.user.id
    assert len(repository.users) == 1
    assert (await service.authenticate(first.token)).id == first.user.id


@pytest.mark.anyio
async def test_token_version_can_revoke_old_tokens() -> None:
    repository = FakeUserRepository()
    service = UserService(
        repository,
        FakeWechatGateway(),
        TokenManager("test-secret-with-at-least-32-characters"),
    )
    result = await service.login("wx-code")
    repository.users["openid-user-1"].token_version += 1

    with pytest.raises(ValueError, match="登录状态无效"):
        await service.authenticate(result.token)
