""" Utils to check, convert and compose server responses for the RESTApi

"""

import inspect
import json
from collections.abc import Mapping
from typing import Any

from aiohttp import web, web_exceptions
from aiohttp.web_exceptions import HTTPError, HTTPException
from common_library.json_serialization import json_dumps
from models_library.rest_error import ErrorGet, ErrorItemType
from servicelib.aiohttp.status import HTTP_200_OK

from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from ..status_codes_utils import get_code_description

_ENVELOPE_KEYS = ("data", "error")


def is_enveloped_from_map(payload: Mapping) -> bool:
    return all(k in _ENVELOPE_KEYS for k in payload if not f"{k}".startswith("_"))


def is_enveloped_from_text(text: str) -> bool:
    try:
        payload = json.loads(text)
    except json.decoder.JSONDecodeError:
        return False
    return is_enveloped_from_map(payload)


def is_enveloped(payload: Mapping | str) -> bool:
    # pylint: disable=isinstance-second-argument-not-valid-type
    if isinstance(payload, Mapping):
        return is_enveloped_from_map(payload)
    if isinstance(payload, str):
        return is_enveloped_from_text(text=payload)
    return False


def wrap_as_envelope(
    data: Any = None,
    error: Any = None,
) -> dict[str, Any]:
    return {"data": data, "error": error}


def unwrap_envelope(payload: dict[str, Any]) -> tuple:
    """
    Safe returns (data, error) tuple from a response payload
    """
    return tuple(payload.get(k) for k in _ENVELOPE_KEYS) if payload else (None, None)


# RESPONSES FACTORIES -------------------------------


def create_data_response(
    data: Any, *, skip_internal_error_details=False, status=HTTP_200_OK
) -> web.Response:
    response = None
    try:
        payload = wrap_as_envelope(data) if not is_enveloped(data) else data

        response = web.json_response(payload, dumps=json_dumps, status=status)
    except (TypeError, ValueError) as err:
        response = exception_to_response(
            create_http_error(
                [
                    err,
                ],
                str(err),
                web.HTTPInternalServerError,
                skip_internal_error_details=skip_internal_error_details,
            )
        )
    return response


def create_http_error(
    errors: list[Exception] | Exception,
    reason: str | None = None,
    http_error_cls: type[HTTPError] = web.HTTPInternalServerError,
    *,
    skip_internal_error_details: bool = False,
) -> HTTPError:
    """
    - Response body conforms OAS schema model
    - Can skip internal details when 500 status e.g. to avoid transmitting server
    exceptions to the client in production
    """
    if not isinstance(errors, list):
        errors = [errors]

    # TODO: guarantee no throw!

    is_internal_error: bool = http_error_cls == web.HTTPInternalServerError
    default_message = reason or get_code_description(http_error_cls.status_code)

    if is_internal_error and skip_internal_error_details:
        error = ErrorGet(
            errors=[],
            logs=[],
            status=http_error_cls.status_code,
            message=default_message,
        )
    else:
        items = [ErrorItemType.from_error(err) for err in errors]
        error = ErrorGet(
            errors=items,
            logs=[],
            status=http_error_cls.status_code,
            message=default_message,
        )

    assert not http_error_cls.empty_body  # nosec
    payload = wrap_as_envelope(error=error)

    return http_error_cls(
        reason=reason,
        text=json_dumps(payload),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


def exception_to_response(exc: HTTPError) -> web.Response:
    # Returning web.HTTPException is deprecated so here we have a converter to a response
    # so it can be used as
    # SEE https://github.com/aio-libs/aiohttp/issues/2415
    return web.Response(
        status=exc.status,
        headers=exc.headers,
        reason=exc.reason,
        text=exc.text,
    )


# Inverse map from code to HTTPException classes
def _collect_http_exceptions(exception_cls: type[HTTPException] = HTTPException):
    def _pred(obj) -> bool:
        return (
            inspect.isclass(obj)
            and issubclass(obj, exception_cls)
            and getattr(obj, "status_code", 0) > 0
        )

    found: list[tuple[str, Any]] = inspect.getmembers(web_exceptions, _pred)
    assert found  # nosec

    http_statuses = {cls.status_code: cls for _, cls in found}
    assert len(http_statuses) == len(found), "No duplicates"  # nosec

    return http_statuses
