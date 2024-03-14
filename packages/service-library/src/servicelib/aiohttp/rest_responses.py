""" Utils to check, convert and compose server responses for the RESTApi

"""
import json
from collections.abc import Mapping
from dataclasses import asdict
from http import HTTPStatus
from typing import Any

from aiohttp import web
from aiohttp.web_exceptions import HTTPError
from servicelib.aiohttp.status import HTTP_200_OK

from ..json_serialization import json_dumps
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from .rest_models import ErrorItem, ResponseErrorBody

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


def create_data_response(data: Any, *, status=HTTP_200_OK) -> web.Response:
    response = None
    try:
        payload = wrap_as_envelope(data) if not is_enveloped(data) else data

        response = web.json_response(payload, dumps=json_dumps, status=status)
    except (TypeError, ValueError) as err:
        response = create_error_response(
            errors=[
                err,
            ],
            message=str(err),
            http_error_cls=web.HTTPInternalServerError,
        )
    return response


def create_error_response(
    errors: list[Exception] | Exception,
    message: str | None = None,
    http_error_cls: type[HTTPError] = web.HTTPInternalServerError,
) -> HTTPError:
    """
    - Response body conforms OAS schema model
    - Can skip internal details when 500 status e.g. to avoid transmitting server
    exceptions to the client in production
    """
    if not isinstance(errors, list):
        errors = [errors]

    if message is None:
        message = HTTPStatus(http_error_cls.status_code).description

    text: str | None = None
    if not http_error_cls.empty_body:
        error = ResponseErrorBody(
            status=http_error_cls.status_code,
            message=message,
            errors=[ErrorItem.from_error(e) for e in errors],
        )
        text = json_dumps(wrap_as_envelope(error=asdict(error)))

    return http_error_cls(
        reason=message,
        text=text,
        content_type=MIMETYPE_APPLICATION_JSON,
    )
