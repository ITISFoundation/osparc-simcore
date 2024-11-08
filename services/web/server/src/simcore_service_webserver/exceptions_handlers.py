import functools
import logging
from collections.abc import Iterable
from typing import NamedTuple, TypeAlias

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from servicelib.aiohttp.web_exceptions_extension import get_http_error_class_or_none
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.status_codes_utils import is_5xx_server_error

_logger = logging.getLogger(__name__)


class HttpErrorInfo(NamedTuple):
    status_code: int
    msg_template: str


ExceptionToHttpErrorMap: TypeAlias = dict[type[BaseException], HttpErrorInfo]


class _DefaultDict(dict):
    def __missing__(self, key):
        return f"'{key}=?'"


def _sort_exceptions_by_specificity(
    exceptions: Iterable[type[BaseException]], *, concrete_first: bool = True
) -> list[type[BaseException]]:
    return sorted(
        exceptions,
        key=lambda exc: sum(issubclass(e, exc) for e in exceptions if e is not exc),
        reverse=not concrete_first,
    )


def create_exception_handlers_decorator(
    exceptions_catch: type[BaseException] | tuple[type[BaseException], ...],
    exc_to_status_map: ExceptionToHttpErrorMap,
):
    mapped_classes: tuple[type[BaseException], ...] = tuple(
        _sort_exceptions_by_specificity(exc_to_status_map.keys())
    )

    assert all(  # nosec
        issubclass(cls, exceptions_catch) for cls in mapped_classes
    ), f"Every {mapped_classes=} must inherit by one or more of {exceptions_catch=}"

    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request) -> web.StreamResponse:
            try:
                return await handler(request)

            except exceptions_catch as exc:
                if exc_cls := next(
                    (cls for cls in mapped_classes if isinstance(exc, cls)), None
                ):
                    http_error_info = exc_to_status_map[exc_cls]

                    # safe formatting, i.e. does not raise
                    user_msg = http_error_info.msg_template.format_map(
                        _DefaultDict(getattr(exc, "__dict__", {}))
                    )

                    http_error_cls = get_http_error_class_or_none(
                        http_error_info.status_code
                    )
                    assert http_error_cls  # nosec

                    if is_5xx_server_error(http_error_info.status_code):
                        _logger.exception(
                            **create_troubleshotting_log_kwargs(
                                user_msg,
                                error=exc,
                                error_context={
                                    "request": request,
                                    "request.remote": f"{request.remote}",
                                    "request.method": f"{request.method}",
                                    "request.path": f"{request.path}",
                                },
                            )
                        )
                    raise http_error_cls(reason=user_msg) from exc
                raise  # reraise

        return _wrapper

    return _decorator
