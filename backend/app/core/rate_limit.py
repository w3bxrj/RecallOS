import time
from typing import Dict, List
from fastapi import Request, Depends, status
from app.core.errors import AppException
from app.models.user import User
from app.routers.deps import get_current_user


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter with automatic stale key pruning."""

    def __init__(self, rate: int, window_seconds: int = 60) -> None:
        self.rate = rate
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}
        self._last_prune_time = time.time()

    def _prune_all(self, now: float) -> None:
        """Periodically removes expired keys to prevent memory leaks."""
        expired_keys = []
        for key, timestamps in self._requests.items():
            valid = [ts for ts in timestamps if now - ts < self.window_seconds]
            if not valid:
                expired_keys.append(key)
            else:
                self._requests[key] = valid
        for key in expired_keys:
            self._requests.pop(key, None)
        self._last_prune_time = now

    def check(self, key: str) -> None:
        """Validates rate limit for a key. Raises AppException(429) if exceeded."""
        now = time.time()

        # Prune full map every 5 minutes or if tracking more than 5,000 keys
        if len(self._requests) > 5000 or now - self._last_prune_time > 300:
            self._prune_all(now)

        timestamps = self._requests.get(key, [])
        valid_timestamps = [ts for ts in timestamps if now - ts < self.window_seconds]

        if len(valid_timestamps) >= self.rate:
            raise AppException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="RATE_LIMIT_EXCEEDED",
                message=f"Rate limit exceeded. Maximum {self.rate} requests per {self.window_seconds}s.",
            )

        valid_timestamps.append(now)
        self._requests[key] = valid_timestamps

    def reset(self) -> None:
        """Clears all recorded requests (for testing)."""
        self._requests.clear()


class IPRateLimiter:
    """Dependency that limits requests per client IP (from request.client.host)."""

    def __init__(self, rate: int = 30, window_seconds: int = 60) -> None:
        self.limiter = InMemoryRateLimiter(rate=rate, window_seconds=window_seconds)

    async def __call__(self, request: Request) -> None:
        # Take IP from request.client.host (fixed by uvicorn --proxy-headers)
        client_ip = request.client.host if request.client else "unknown"
        self.limiter.check(f"ip:{client_ip}")


class UserRateLimiter:
    """Dependency that limits requests per authenticated user."""

    def __init__(self, rate: int = 10, window_seconds: int = 60) -> None:
        self.limiter = InMemoryRateLimiter(rate=rate, window_seconds=window_seconds)

    async def __call__(self, current_user: User = Depends(get_current_user)) -> None:
        self.limiter.check(f"user:{current_user.id}")


# Global limiters
auth_ip_limiter = IPRateLimiter(rate=30, window_seconds=60)
upload_user_limiter = UserRateLimiter(rate=10, window_seconds=60)
