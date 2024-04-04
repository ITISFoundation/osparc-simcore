""" Utils to check, convert and compose server responses for the RESTApi

"""
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Final

from aiohttp import web
from aiohttp.web_exceptions import HTTPError, HTTPException
from models_library.generics import Envelope
from models_library.rest_enveloped import LogMessage, ManyErrors, OneError
from models_library.utils.fastapi_encoders import jsonable_encoder

from ..json_serialization import json_dumps, safe_json_loads
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from ..rest_constants import RESPONSE_MODEL_POLICY
from . import status

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


def create_enveloped_response(
    data: Any, *, status_code: int = status.HTTP_200_OK
) -> web.Response:
    response = None
    try:
        enveloped_payload = wrap_as_envelope(data) if not is_enveloped(data) else data
        response = web.json_response(
            enveloped_payload, dumps=json_dumps, status=status_code
        )
    except (TypeError, ValueError) as err:
        # FIXME: this should never happen!
        response = create_error_response(
            errors=[err],
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
        msg = message or HTTPStatus(http_error_cls.status_code).description
        if len(errors) > 1:
            error_model = ManyErrors(
                msg=msg, details=[OneError.from_exception(exc) for exc in errors]
            )
        else:
            error_model = OneError.from_exception(errors[0])
            if message:
                error_model.msg = message

        text = json_dumps(wrap_as_envelope(error=jsonable_encoder(error_model)))

    return http_error_cls(
        reason=message,
        text=text,
        content_type=MIMETYPE_APPLICATION_JSON,
    )


def envelope_response(
    data: Any, *, status_code: int = status.HTTP_200_OK
) -> web.Response:
    return web.json_response(
        jsonable_encoder({"data": data}, **RESPONSE_MODEL_POLICY),
        dumps=json_dumps,
        status=status_code,
    )


def envelope_json_response(
    obj: Any, status_cls: type[HTTPException] = web.HTTPOk
) -> web.Response:
    # NOTE: see https://github.com/ITISFoundation/osparc-simcore/issues/3646
    if issubclass(status_cls, HTTPError):
        enveloped = Envelope[Any](error=obj)
    else:
        enveloped = Envelope[Any](data=obj)

    return web.json_response(
        jsonable_encoder(enveloped, **RESPONSE_MODEL_POLICY),
        dumps=json_dumps,
        status=status_cls.status_code,
    )


def flash_response(
    message: str, level: str = "INFO", *, status_code: int = status.HTTP_200_OK
) -> web.Response:
    return envelope_response(
        data=LogMessage(message=message, level=level),
        status_code=status_code,
    )
