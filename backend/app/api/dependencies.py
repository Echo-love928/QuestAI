from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from app.core.security import TokenError
from app.models.user import User


async def optional_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    if authorization is None:
        return None
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="登录状态无效或已过期")
    service = getattr(request.app.state, "user_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="用户服务暂时不可用")
    try:
        return await service.authenticate(token)
    except (TokenError, ValueError):
        raise HTTPException(status_code=401, detail="登录状态无效或已过期") from None


async def required_user(
    user: Annotated[User | None, Depends(optional_user)],
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user
