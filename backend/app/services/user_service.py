from typing import Protocol

from app.core.security import TokenError, TokenManager
from app.models.user import LoginResult, User


class UserRepository(Protocol):
    async def upsert_by_openid(self, openid: str) -> User: ...

    async def get_by_id(self, user_id: int) -> User | None: ...


class WechatCodeGateway(Protocol):
    async def exchange_code(self, code: str) -> str: ...


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        wechat_gateway: WechatCodeGateway,
        tokens: TokenManager,
    ) -> None:
        self.repository = repository
        self.wechat_gateway = wechat_gateway
        self.tokens = tokens

    async def login(self, code: str) -> LoginResult:
        openid = await self.wechat_gateway.exchange_code(code)
        user = await self.repository.upsert_by_openid(openid)
        return LoginResult(
            token=self.tokens.create_access_token(user.id, user.token_version),
            user=user,
        )

    async def authenticate(self, token: str) -> User:
        claims = self.tokens.decode_access_token(token)
        user = await self.repository.get_by_id(claims.user_id)
        if user is None or user.token_version != claims.token_version:
            raise TokenError("登录状态无效或已过期")
        return user
