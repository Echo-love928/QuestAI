from datetime import datetime, timedelta, timezone

import pytest

from app.core.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter


def test_login_rate_limiter_blocks_excess_attempts() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window=timedelta(minutes=1))
    now = datetime.now(timezone.utc)
    limiter.check("127.0.0.1", now=now)
    limiter.check("127.0.0.1", now=now)

    with pytest.raises(RateLimitExceeded):
        limiter.check("127.0.0.1", now=now)


def test_login_rate_limiter_recovers_after_window() -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window=timedelta(seconds=30))
    now = datetime.now(timezone.utc)
    limiter.check("127.0.0.1", now=now)
    limiter.check("127.0.0.1", now=now + timedelta(seconds=31))


def test_rate_limiter_supports_endpoint_specific_safe_message() -> None:
    limiter = SlidingWindowRateLimiter(
        limit=1,
        window=timedelta(minutes=1),
        message="题目生成请求过于频繁，请稍后重试",
    )
    now = datetime.now(timezone.utc)
    limiter.check("client", now=now)

    with pytest.raises(RateLimitExceeded, match="题目生成请求过于频繁"):
        limiter.check("client", now=now)
