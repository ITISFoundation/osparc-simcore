"""Shared healthcheck utilities for FastAPI services.

Provides a canonical HealthCheckError exception and a handler that maps it
to a 503 PlainTextResponse.

Usage pattern — register the handler once during app setup::

    from servicelib.fastapi.health import HealthCheckError, health_check_error_handler

    app.add_exception_handler(HealthCheckError, health_check_error_handler)

Then raise ``HealthCheckError`` from any health endpoint when a critical
dependency is unreachable::

    @router.get("/", response_class=PlainTextResponse)
    async def health_check(app: Annotated[FastAPI, Depends(get_app)]):
        if not get_rabbitmq_client(app).healthy:
            raise HealthCheckError("RabbitMQ is unreachable")
        return f"{__name__}@{datetime.datetime.now(datetime.UTC).isoformat()}"

The handler converts the exception into a ``503 Service Unavailable``
plain-text response containing the exception message.

Note: ``set_app_default_http_error_handlers`` (from ``servicelib.fastapi.http_error``)
registers this handler automatically. Services that do not call that helper
must register it explicitly via ``app.add_exception_handler``.
"""

from fastapi import status
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse


class HealthCheckError(RuntimeError):
    """Raised when a health check fails.

    Services raise this from their health endpoint when a critical dependency
    (RabbitMQ, Redis, Postgres, etc.) is unreachable. It is mapped to a
    503 Service Unavailable plain-text response.
    """


async def health_check_error_handler(_: Request, exc: Exception) -> PlainTextResponse:  # NOSONAR
    assert isinstance(exc, HealthCheckError)  # nosec
    return PlainTextResponse(
        f"{exc}",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
