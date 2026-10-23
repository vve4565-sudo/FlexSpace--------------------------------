import hashlib
import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from ..config.config import settings
from ..redis_client import redis

logger = logging.getLogger(__name__)

_INCREMENT_WITH_EXPIRY = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        client_hash = hashlib.sha256(client_host.encode("utf-8")).hexdigest()
        try:
            request_count = await redis.eval(
                _INCREMENT_WITH_EXPIRY,
                1,
                f"api-rate:{client_hash}",
                60,
            )
        except RedisError:
            logger.exception("API rate limiter unavailable")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Request limiting is temporarily unavailable"},
            )

        if request_count > settings.API_RATE_LIMIT:
            logger.warning("API rate limit exceeded client_id=%s", client_hash[:12])
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests, try again later"},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
