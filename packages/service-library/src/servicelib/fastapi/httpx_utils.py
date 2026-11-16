import logging
from collections.abc import Callable, Coroutine
from typing import Any, Final

import httpx2
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from ..utils_secrets import mask_sensitive_data

_logger = logging.getLogger(__name__)

DROPPED_CONNECTION_ERRORS: Final[tuple[type[httpx2.RequestError], ...]] = (
    httpx2.RemoteProtocolError,
    httpx2.ReadError,
)


def retry_on_dropped_connection[**P, R](
    func: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Retries once, after a jitter of at most ~200 ms, if the server dropped the connection

    A server closing an idle pooled keep-alive connection surfaces as
    `RemoteProtocolError` or `ReadError` on the next request. The dead
    connection is evicted from the pool, so a single retry opens a new one.
    Timeouts are not retried.

    NOTE: only for idempotent (e.g. read-only) calls
    """
    return retry(
        retry=retry_if_exception_type(DROPPED_CONNECTION_ERRORS),
        stop=stop_after_attempt(2),
        wait=wait_random_exponential(multiplier=0.1, max=1),
        before_sleep=before_sleep_log(_logger, logging.WARNING),
        reraise=True,
    )(func)


def _get_headers_safely(request: httpx2.Request) -> dict[str, str]:
    return mask_sensitive_data(dict(request.headers))


def to_httpx_command(request: httpx2.Request, *, use_short_options: bool = True, multiline: bool = False) -> str:
    """Command with httpx2 CLI

    $ httpx2 --help

    NOTE: Particularly handy as an alternative to curl (e.g. when docker exec in osparc containers)
    SEE https://pydantic.dev/docs/httpx2/
    """
    cmd = [
        "httpx2",
    ]

    #  -m, --method METHOD
    cmd.append(f"{'-m' if use_short_options else '--method'} {request.method}")

    # -c, --content TEXT  Byte content to include in the request body.
    if content := request.read().decode():
        cmd.append(f"{'-c' if use_short_options else '--content'} '{content}'")

    # -h, --headers <NAME VALUE> ...  Include additional HTTP headers in the request.
    if headers := _get_headers_safely(request):
        cmd.extend(
            [f'{"-h" if use_short_options else "--headers"} "{name}" "{value}"' for name, value in headers.items()]
        )

    cmd.append(f"{request.url}")
    separator = " \\\n" if multiline else " "
    return separator.join(cmd)


def to_curl_command(request: httpx2.Request, *, use_short_options: bool = True, multiline: bool = False) -> str:
    """Composes a curl command from a given request

    $ curl --help

    NOTE: Handy reproduce a request in a separate terminal (e.g. debugging)
    """
    # Adapted from https://github.com/marcuxyz/curlify2/blob/master/curlify2/curlify.py
    cmd = [
        "curl",
    ]

    # https://curl.se/docs/manpage.html#-X
    # -X, --request {method}
    cmd.append(f"{'-X' if use_short_options else '--request'} {request.method}")

    # https://curl.se/docs/manpage.html#-H
    # H, --header <header/@file> Pass custom header(s) to server
    if headers := _get_headers_safely(request):
        cmd.extend([f'{"-H" if use_short_options else "--header"} "{k}: {v}"' for k, v in headers.items()])

    # https://curl.se/docs/manpage.html#-d
    # -d, --data <data>          HTTP POST data
    if body := request.read().decode():
        _d = "-d" if use_short_options else "--data"
        cmd.append(f"{_d} '{body}'")

    cmd.append(f"{request.url}")

    separator = " \\\n" if multiline else " "
    return separator.join(cmd)
