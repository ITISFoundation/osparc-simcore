import functools
import logging
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


ExceptionToHttpErrorMap: TypeAlias = dict[type[Exception], HttpErrorInfo]


class _DefaultDict(dict):
    def __missing__(self, key):
        return f"'{key}=?'"


def create_http_error_from_map(
    request: web.Request, exc: BaseException, to_http_error_map: ExceptionToHttpErrorMap
) -> web.HTTPError | None:
    for exc_cls, http_error_info in to_http_error_map.items():
        # FIXME: there can be multiple matches if exc_cls is base class
        if isinstance(exc, exc_cls):

            # safe formatting, i.e. does not raise
            user_msg = http_error_info.msg_template.format_map(
                _DefaultDict(getattr(exc, "__dict__", {}))
            )

            http_error_cls = get_http_error_class_or_none(http_error_info.status_code)
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
            return http_error_cls(reason=user_msg)
    return None


def create_handle_request_exceptions_decorator(
    to_http_error_map: ExceptionToHttpErrorMap,
    exception_types: type[BaseException] | tuple[type[BaseException], ...] = Exception,
):
    """
    Creates a function to decorate routes handlers functions
    that can catch and handle exceptions raised in the decorated functions
    """
    assert all(issubclass(cls, exception_types) for cls in to_http_error_map)  # nosec

    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request) -> web.StreamResponse:
            """
            Raises:
                web.HTTPError: 4XX and 5XX http errors
            """
            try:
                return await handler(request)
            except exception_types as exc:
                if http_err := create_http_error_from_map(
                    request, exc, to_http_error_map
                ):
                    raise http_err from exc
                raise

        return _wrapper

    return _decorator
