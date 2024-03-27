""" Utils to check, convert and compose server responses for the RESTApi

"""
from collections.abc import Mapping
from dataclasses import asdict
from http import HTTPStatus
from typing import Any, Final

from aiohttp import web
from aiohttp.web_exceptions import HTTPError
from servicelib.aiohttp.status import HTTP_200_OK

from ..json_serialization import json_dumps, safe_json_loads
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from .rest_models import ErrorDetail, ResponseErrorBody

_ENVELOPE_KEYS: Final = ("data", "error")


def is_enveloped_from_map(payload: Mapping) -> bool:
    # NOTE: keys starting with _ are metadata (e.g. pagination metadata)
    return all(key in _ENVELOPE_KEYS for key in payload if not f"{key}".startswith("_"))


def is_enveloped_from_text(text: str) -> bool:
    if payload := safe_json_loads(text):
        return is_enveloped_from_map(payload)
    return False


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


def create_enveloped_response(data: Any, *, status: int = HTTP_200_OK) -> web.Response:
    response = None
    try:
        enveloped_payload = wrap_as_envelope(data) if not is_enveloped(data) else data
        response = web.json_response(enveloped_payload, dumps=json_dumps, status=status)
    except (TypeError, ValueError) as err:
        # FIXME: this should never happen!
        response = create_error_response(
            errors=[
                err,
            ],
            message=str(err),
            http_error_cls=web.HTTPInternalServerError,
        )
    return response


def create_error_response(
    errors: Exception | list[Exception] | None,
    message: str | None = None,
    http_error_cls: type[HTTPError] = web.HTTPInternalServerError,
) -> HTTPError:
    """
    - Response body conforms OAS schema model
    - Can skip internal details when 500 status e.g. to avoid transmitting server
    exceptions to the client in production
    """
    if isinstance(errors, Exception):
        errors = [errors]

    errors = errors or []

    text: str | None = None
    if not http_error_cls.empty_body:
        error = ResponseErrorBody(
            status=http_error_cls.status_code,
            message=message or HTTPStatus(http_error_cls.status_code).description,
            errors=[ErrorDetail.from_exception(e) for e in errors],
        )
        text = json_dumps(wrap_as_envelope(error=asdict(error)))

    return http_error_cls(
        reason=message,
        text=text,
        content_type=MIMETYPE_APPLICATION_JSON,
    )
