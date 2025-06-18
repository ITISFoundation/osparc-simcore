from typing import Any, Final, TypedDict, TypeVar

from aiohttp import web
from aiohttp.web_exceptions import HTTPError
from common_library.error_codes import ErrorCodeStr
from common_library.json_serialization import json_dumps
from models_library.rest_error import ErrorGet, ErrorItemType

from ..aiohttp.status import HTTP_200_OK
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from ..rest_constants import RESPONSE_MODEL_POLICY
from ..rest_responses import is_enveloped
from ..status_codes_utils import get_code_description, get_code_display_name, is_error


class EnvelopeDict(TypedDict):
    data: Any
    error: Any


def wrap_as_envelope(
    data: Any | None = None,
    error: Any | None = None,
) -> EnvelopeDict:
    return {"data": data, "error": error}


def create_data_response(data: Any, *, status: int = HTTP_200_OK) -> web.Response:
    """Creates a JSON response with the given data and ensures it is wrapped in an envelope."""

    assert (  # nosec
        is_error(status) is False
    ), f"Expected a non-error status code, got {status=}"

    enveloped_payload = wrap_as_envelope(data) if not is_enveloped(data) else data
    return web.json_response(enveloped_payload, dumps=json_dumps, status=status)


MAX_STATUS_MESSAGE_LENGTH: Final[int] = 100


def safe_status_message(
    message: str | None, max_length: int = MAX_STATUS_MESSAGE_LENGTH
) -> str | None:
    """
    Truncates a status-message (i.e. `reason` in HTTP errors) to a maximum length, replacing newlines with spaces.

    If the message is longer than max_length, it will be truncated and "..." will be appended.

    This prevents issues such as:
        - `aiohttp.http_exceptions.LineTooLong`: 400, message: Got more than 8190 bytes when reading Status line is too long.
        - Multiline not allowed in HTTP reason attribute (aiohttp now raises ValueError).

    See:
        - When to use http status and/or text messages https://github.com/ITISFoundation/osparc-simcore/pull/7760
        - [RFC 9112, Section 4.1: HTTP/1.1 Message Syntax and Routing](https://datatracker.ietf.org/doc/html/rfc9112#section-4.1) (status line length limits)
        - [RFC 9110, Section 15.5: Reason Phrase](https://datatracker.ietf.org/doc/html/rfc9110#section-15.5) (reason phrase definition)
    """
    assert max_length > 0  # nosec

    if not message:
        return None

    flat_message = message.replace("\n", " ")
    if len(flat_message) <= max_length:
        return flat_message

    # Truncate and add ellipsis
    return flat_message[: max_length - 3] + "..."


T_HTTPError = TypeVar("T_HTTPError", bound=HTTPError)


def create_http_error(
    errors: list[Exception] | Exception,
    error_message: str | None = None,
    http_error_cls: type[
        T_HTTPError
    ] = web.HTTPInternalServerError,  # type: ignore[assignment]
    *,
    status_reason: str | None = None,
    skip_internal_error_details: bool = False,
    error_code: ErrorCodeStr | None = None,
) -> T_HTTPError:
    """
    - Response body conforms OAS schema model
    - Can skip internal details when 500 status e.g. to avoid transmitting server
    exceptions to the client in production
    """

    status_reason = status_reason or get_code_display_name(http_error_cls.status_code)
    error_message = error_message or get_code_description(http_error_cls.status_code)

    assert len(status_reason) < MAX_STATUS_MESSAGE_LENGTH  # nosec

    # WARNING: do not refactor too much this function withouth considering how
    # front-end handle errors. i.e. please sync with front-end developers before
    # changing the workflows in this function

    is_internal_error = bool(http_error_cls == web.HTTPInternalServerError)
    if is_internal_error and skip_internal_error_details:
        error_model = ErrorGet.model_validate(
            {
                "status": http_error_cls.status_code,
                "message": error_message,
                "support_id": error_code,
            }
        )
    else:
        if not isinstance(errors, list):
            errors = [errors]

        items = [ErrorItemType.from_error(err) for err in errors]
        error_model = ErrorGet.model_validate(
            {
                "errors": items,  # NOTE: deprecated!
                "status": http_error_cls.status_code,
                "message": error_message,
                "support_id": error_code,
            }
        )

    assert not http_error_cls.empty_body  # nosec

    payload = wrap_as_envelope(
        error=error_model.model_dump(mode="json", **RESPONSE_MODEL_POLICY)
    )

    return http_error_cls(
        reason=safe_status_message(status_reason),
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
