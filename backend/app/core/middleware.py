import logging
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.middleware.request_logger")

SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "proxy-authorization",
}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log HTTP requests with method, path, response status,
    and execution latency in milliseconds without leaking sensitive headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
            process_time = (time.perf_counter() - start_time) * 1000
            status_code = response.status_code

            logger.info(
                f"{method} {path} - {status_code} - {process_time:.2f}ms [{client_host}]"
            )
            return response
        except Exception as exc:
            process_time = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"{method} {path} - FAILED after {process_time:.2f}ms [{client_host}]: {type(exc).__name__}"
            )
            raise exc
