import asyncio
import contextlib
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, TypeAlias

from pydantic.errors import PydanticErrorMixin
from servicelib.utils import logged_gather

if TYPE_CHECKING:
    with contextlib.suppress(Exception):
        from fastapi import FastAPI

    with contextlib.suppress(Exception):
        from aiohttp.web import Application

_logger = logging.getLogger(__name__)

_HEALTH_CHECK_INFO_KEY: Final[str] = "_health_check_info"

AppType: TypeAlias = "FastAPI | Application"
HealthCheckHandler: TypeAlias = Callable[[AppType], Awaitable[None]]


class HealthCheckError(PydanticErrorMixin, RuntimeError):
    msg_template = "Registered handler '{handler_name}' failed!"


@dataclass
class HealthCheckInfo:
    handlers: list[Callable] = field(default_factory=list)


def _get_health_check_info(app: AppType) -> HealthCheckInfo:
    if hasattr(app, "state"):
        # fastapi.FastAPI
        return getattr(app.state, _HEALTH_CHECK_INFO_KEY)  # type: ignore

    # aiohttp.web.Application
    return app[_HEALTH_CHECK_INFO_KEY]  # type: ignore


def setup(app: AppType) -> None:
    if hasattr(app, "state"):
        # fastapi.FastAPI
        setattr(app.state, _HEALTH_CHECK_INFO_KEY, HealthCheckInfo())  # type: ignore
        return

    # aiohttp.web.Application
    app[_HEALTH_CHECK_INFO_KEY] = HealthCheckInfo()  # type: ignore


def register(app: AppType, handler: HealthCheckHandler) -> None:
    """Register a handler that will handle the user defined health check.

    If the handler raises an error it means that the health check failed.
    """

    if not inspect.iscoroutinefunction(handler):
        msg = f"Expected coroutine, got {handler}"
        raise TypeError(msg)

    health_check_info = _get_health_check_info(app)
    health_check_info.handlers.append(handler)


async def is_healthy(app: AppType, timeout: float = 1) -> bool:
    """Runs health checks for all registered handlers

    Keyword Arguments:
        timeout -- max execution time for each individual handler (default: {1})

    Raises:
        HealthCheckError: if any of the handlers fail
    """
    health_check_info = _get_health_check_info(app)

    async def _wrapper(handler: Awaitable, handler_name: str) -> None:
        try:
            await asyncio.wait_for(handler, timeout=timeout)
        except Exception as e:
            raise HealthCheckError(handler_name=handler_name) from e

    _logger.debug(
        "Checking services: %s", [h.__name__ for h in health_check_info.handlers]
    )

    try:
        await logged_gather(
            *(
                _wrapper(handler(app), handler.__name__)
                for handler in health_check_info.handlers
            )
        )
    except HealthCheckError:
        return False
    return True
