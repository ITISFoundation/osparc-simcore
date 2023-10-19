import asyncio
import contextlib
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Final, TypeAlias

from pydantic import BaseModel
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
HealthCheckHandler: TypeAlias = Callable[..., Awaitable[None]]


class HealthCheckError(PydanticErrorMixin, RuntimeError):
    msg_template = "Registered handler '{handler_name}' failed!"


class _SupportedAppTypes(str, Enum):
    FASTAPI = "fastapi.applications.FastAPI"
    AIOHTTP = "aiohttp.web_app.Application"


class UnsupportedApplicationTypeError(PydanticErrorMixin, TypeError):
    msg_template = (
        "Provided application_class '{app_class}' is unsupported! "
        f"Expected an instance of { {x.value for x in _SupportedAppTypes} }"
    )


@dataclass
class HealthCheckInfo:
    handlers: list[Callable] = field(default_factory=list)


class HealthReport(BaseModel):
    is_healthy: bool
    ok_checks: list[str]
    failing_checks: list[str]


def _get_app_class_path(app: AppType) -> str:
    app_type = type(app)
    return f"{app_type.__module__}.{app_type.__name__}"


def _get_health_check_info(app: AppType) -> HealthCheckInfo:
    match _get_app_class_path(app):
        case _SupportedAppTypes.FASTAPI:
            return getattr(app.state, _HEALTH_CHECK_INFO_KEY)  # type: ignore
        case _SupportedAppTypes.AIOHTTP:
            return app[_HEALTH_CHECK_INFO_KEY]  # type: ignore
        case _:
            raise UnsupportedApplicationTypeError(app_class=app.__class__)


def setup_health_check(app: AppType) -> None:
    match _get_app_class_path(app):
        case _SupportedAppTypes.FASTAPI:
            setattr(app.state, _HEALTH_CHECK_INFO_KEY, HealthCheckInfo())  # type: ignore
        case _SupportedAppTypes.AIOHTTP:
            app[_HEALTH_CHECK_INFO_KEY] = HealthCheckInfo()  # type: ignore
        case _:
            raise UnsupportedApplicationTypeError(app_class=app.__class__)


def register_health_check(app: AppType, handler: HealthCheckHandler) -> None:
    """Register a handler that will handle the user defined health check.

    If the handler raises an error it means that the health check failed.
    """

    if not inspect.iscoroutinefunction(handler):
        msg = f"Expected coroutine, got {handler}"
        raise TypeError(msg)

    health_check_info = _get_health_check_info(app)
    health_check_info.handlers.append(handler)


async def is_healthy(app: AppType, timeout: float = 1) -> HealthReport:
    """Runs health checks for all registered handlers

    Keyword Arguments:
        timeout -- max execution time for each individual handler (default: {1})

    Raises:
        HealthCheckError: if any of the handlers fail
    """
    health_check_info = _get_health_check_info(app)

    async def _wrapper(handler: Awaitable, handler_name: str) -> str:
        try:
            await asyncio.wait_for(handler, timeout=timeout)
        except Exception as e:
            raise HealthCheckError(handler_name=handler_name) from e

        return handler_name

    _logger.debug(
        "Checking services: %s", [h.__name__ for h in health_check_info.handlers]
    )

    results = await logged_gather(
        *(
            _wrapper(handler(app), handler.__name__)
            for handler in health_check_info.handlers
        ),
        reraise=False,
    )

    ok_checks: list[str] = []
    failing_checks: list[str] = []
    for result in results:
        if isinstance(result, HealthCheckError):
            failing_checks.append(result.handler_name)  # type: ignore
        else:
            ok_checks.append(result)

    return HealthReport(
        is_healthy=len(failing_checks) == 0,
        ok_checks=ok_checks,
        failing_checks=failing_checks,
    )
