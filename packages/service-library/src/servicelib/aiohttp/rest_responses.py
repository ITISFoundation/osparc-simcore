"""Utils to check, convert and compose server responses for the RESTApi"""

import inspect
from typing import Any

from aiohttp import web, web_exceptions
from aiohttp.web_exceptions import HTTPError, HTTPException
from common_library.error_codes import ErrorCodeStr
from common_library.json_serialization import json_dumps
from models_library.rest_error import ErrorGet, ErrorItemType

from ..aiohttp.status import HTTP_200_OK
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from ..rest_constants import RESPONSE_MODEL_POLICY
from ..rest_responses import is_enveloped
from ..status_codes_utils import get_code_description


def wrap_as_envelope(
    data: Any = None,
    error: Any = None,
) -> dict[str, Any]:
    return {"data": data, "error": error}


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
    error_code: ErrorCodeStr | None = None,
) -> HTTPError:
    """
    - Response body conforms OAS schema model
    - Can skip internal details when 500 status e.g. to avoid transmitting server
    exceptions to the client in production
    """
    if not isinstance(errors, list):
        errors = [errors]

    is_internal_error: bool = http_error_cls == web.HTTPInternalServerError
    default_message = reason or get_code_description(http_error_cls.status_code)

    if is_internal_error and skip_internal_error_details:
        error = ErrorGet.model_validate(
            {
                "status": http_error_cls.status_code,
                "message": default_message,
                "support_id": error_code,
            }
        )
    else:
        items = [ErrorItemType.from_error(err) for err in errors]
        error = ErrorGet.model_validate(
            {
                "errors": items,  # NOTE: deprecated!
                "status": http_error_cls.status_code,
                "message": default_message,
                "support_id": error_code,
            }
        )

    assert not http_error_cls.empty_body  # nosec
    payload = wrap_as_envelope(
        error=error.model_dump(mode="json", **RESPONSE_MODEL_POLICY)
    )

    return http_error_cls(
        # Multiline not allowed in HTTP reason
        reason=reason.replace("\n", " ") if reason else None,
        text=json_dumps(
            payload,
        ),
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
