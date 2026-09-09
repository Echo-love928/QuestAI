from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone


class RateLimitExceeded(ValueError):
    pass


class SlidingWindowRateLimiter:
    def __init__(
        self,
        limit: int,
        window: timedelta,
        message: str = "登录请求过于频繁，请稍后重试",
    ) -> None:
        self.limit = limit
        self.window = window
        self.message = message
        self.attempts: dict[str, deque[datetime]] = defaultdict(deque)

    def check(self, key: str, *, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        cutoff = current - self.window
        events = self.attempts[key]
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= self.limit:
            raise RateLimitExceeded(self.message)
        events.append(current)
