from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    token_version: int


class TokenManager:
    def __init__(
        self,
        secret: str,
        *,
        expires_delta: timedelta = timedelta(days=7),
        issuer: str = "ai-level-learning",
    ) -> None:
        if len(secret) < 32:
            raise ValueError("JWT_SECRET 至少需要 32 个字符")
        self.secret = secret
        self.expires_delta = expires_delta
        self.issuer = issuer

    def create_access_token(self, user_id: int, token_version: int = 0) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": str(user_id),
                "ver": token_version,
                "iat": now,
                "exp": now + self.expires_delta,
                "iss": self.issuer,
                "jti": uuid4().hex,
            },
            self.secret,
            algorithm="HS256",
        )

    def decode_access_token(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                issuer=self.issuer,
                options={"require": ["sub", "exp", "iat", "iss", "jti"]},
            )
            return TokenClaims(
                user_id=int(payload["sub"]),
                token_version=int(payload.get("ver", 0)),
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise TokenError("登录状态无效或已过期") from exc
