import httpx


class WechatLoginError(ValueError):
    pass


class WechatGateway:
    ENDPOINT = "https://api.weixin.qq.com/sns/jscode2session"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.transport = transport

    async def exchange_code(self, code: str) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=10, transport=self.transport
            ) as client:
                response = await client.get(
                    self.ENDPOINT,
                    params={
                        "appid": self.app_id,
                        "secret": self.app_secret,
                        "js_code": code,
                        "grant_type": "authorization_code",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WechatLoginError("微信登录服务暂时不可用") from exc
        openid = payload.get("openid")
        if not openid:
            raise WechatLoginError("微信登录凭证无效")
        return str(openid)
