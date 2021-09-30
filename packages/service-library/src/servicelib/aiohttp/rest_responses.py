""" Utils to check, convert and compose server responses for the RESTApi

"""
import inspect
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type, Union

import attr
from aiohttp import web, web_exceptions
from aiohttp.web_exceptions import HTTPError

from .rest_codecs import json, jsonify
from .rest_models import ErrorItemType, ErrorType, LogMessageType

ENVELOPE_KEYS = ("data", "error")
OFFSET_PAGINATION_KEYS = ("_meta", "_links")
JSON_CONTENT_TYPE = "application/json"

JsonLikeModel = Union[Dict[str, Any], List[Dict[str, Any]]]


def is_enveloped_from_map(payload: Mapping) -> bool:
    return all(k in ENVELOPE_KEYS for k in payload.keys() if not str(k).startswith("_"))


def is_enveloped_from_text(text: str) -> bool:
    try:
        payload = json.loads(text)
    except json.decoder.JSONDecodeError:
        return False
    return is_enveloped_from_map(payload)


def is_enveloped(payload: Union[Mapping, str]) -> bool:
    # pylint: disable=isinstance-second-argument-not-valid-type
    if isinstance(payload, Mapping):
        return is_enveloped_from_map(payload)
    if isinstance(payload, str):
        return is_enveloped_from_text(text=payload)
    return False


def wrap_as_envelope(
    data: Optional[JsonLikeModel] = None,
    error: Optional[JsonLikeModel] = None,
    as_null: bool = True,
) -> Dict[str, Any]:
    """
    as_null: if True, keys for null values are created and assigned to None
    """
    payload = {}
    if data or as_null:
        payload["data"] = data
    if error or as_null:
        payload["error"] = error
    return payload


def unwrap_envelope(payload: Dict[str, Any]) -> Tuple:
    """
    Safe returns (data, error) tuple from a response payload
    """
    return tuple(payload.get(k) for k in ENVELOPE_KEYS) if payload else (None, None)


# RESPONSES FACTORIES -------------------------------


def create_data_response(
    data: Union[Mapping, str], *, skip_internal_error_details=False
) -> web.Response:
    response = None
    try:
        if not is_enveloped(data):
            payload = wrap_as_envelope(data)
        else:
            payload = data

        response = web.json_response(payload, dumps=jsonify)
    except (TypeError, ValueError) as err:
        response = create_error_response(
            [
                err,
            ],
            str(err),
            web.HTTPInternalServerError,
            skip_internal_error_details=skip_internal_error_details,
        )
    return response


def create_error_response(
    errors: Union[List[Exception], Exception],
    reason: Optional[str] = None,
    http_error_cls: Type[HTTPError] = web.HTTPInternalServerError,
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

    if is_internal_error and skip_internal_error_details:
        error = ErrorType(
            errors=[],
            status=http_error_cls.status_code,
        )
    else:
        error = ErrorType(
            errors=[ErrorItemType.from_error(err) for err in errors],
            status=http_error_cls.status_code,
        )

    payload = wrap_as_envelope(error=attr.asdict(error))

    response = http_error_cls(
        reason=reason, text=jsonify(payload), content_type=JSON_CONTENT_TYPE
    )

    return response


def create_log_response(msg: str, level: str) -> web.Response:
    """Produces an enveloped response with a log message

    Analogous to  aiohttp's web.json_response
    """
    # TODO: DEPRECATE
    msg = LogMessageType(msg, level)
    response = web.json_response(data={"data": attr.asdict(msg), "error": None})
    return response


def get_http_error(status_code: int) -> Optional[Type[HTTPError]]:
    """Returns aiohttp exception class corresponding to a 4XX or 5XX status code

    NOTICE that any non-error code (i.e. 2XX, 3XX and 4XX) will return None
    """
    # SEE https://httpstatuses.com/
    # Errors are exceptions with status codes in the 400s and 500s.
    if status_code < 400 or 599 < status_code:
        return None

    def _pred(obj) -> bool:
        return (
            inspect.isclass(obj)
            and issubclass(obj, HTTPError)
            and getattr(obj, "status_code", None) == status_code
        )

    found: List[Tuple[str, Any]] = inspect.getmembers(web_exceptions, _pred)

    if found:
        assert len(found) == 1, f"Unexpected multiple matches {found}"  # nosec
        _, value = found[0]
        assert issubclass(value, HTTPError)  # nosec
        return value
    return None
