import httpx
import pytest

from app.integrations.wechat import WechatGateway, WechatLoginError


@pytest.mark.anyio
async def test_wechat_gateway_returns_openid_without_exposing_session_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["appid"] == "app-id"
        assert request.url.params["js_code"] == "wx-code"
        return httpx.Response(
            200, json={"openid": "openid-1", "session_key": "server-only"}
        )

    gateway = WechatGateway(
        "app-id", "app-secret", transport=httpx.MockTransport(handler)
    )
    assert await gateway.exchange_code("wx-code") == "openid-1"


@pytest.mark.anyio
async def test_wechat_gateway_converts_wechat_error_to_safe_message() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200, json={"errcode": 40029, "errmsg": "invalid code"}
        )
    )
    gateway = WechatGateway("app-id", "app-secret", transport=transport)

    with pytest.raises(WechatLoginError, match="凭证无效"):
        await gateway.exchange_code("bad-code")
