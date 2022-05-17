""" Parses and validation aiohttp requests against pydantic models

These functions are analogous to `pydantic.tools.parse_obj_as(model_class, obj)` for aiohttp's requests
"""

from contextlib import contextmanager
from typing import Iterator, Type, TypeVar

from aiohttp import web
from pydantic import BaseModel, ValidationError
from yarl import URL

from ..json_serialization import json_dumps
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON

ModelType = TypeVar("ModelType", bound=BaseModel)


@contextmanager
def handle_validation_as_http_error(
    *, error_msg_template: str, resource: URL, use_error_v1: bool
) -> Iterator[None]:
    """
    Transforms ValidationError into HTTP error
    """
    try:

        yield

    except ValidationError as err:
        details = [
            {
                "loc": ".".join(map(str, e["loc"])),
                "msg": e["msg"],
                "type": e["type"],
            }
            for e in err.errors()
        ]
        reason_msg = error_msg_template.format(
            failed=", ".join(d["loc"] for d in details)
        )

        if use_error_v1:
            # NOTE: keeps backwards compatibility until ligher error response is implemented in the entire API
            # Implements servicelib.aiohttp.rest_responses.ErrorItemType
            errors = [
                {
                    "code": e["type"],
                    "message": e["msg"],
                    "resource": f"{resource}",
                    "field": e["loc"],
                }
                for e in details
            ]
            error_str = json_dumps(
                {"error": {"status": web.HTTPBadRequest.status_code, "errors": errors}}
            )
        else:
            # NEW proposed error for https://github.com/ITISFoundation/osparc-simcore/issues/443
            error_str = json_dumps(
                {
                    "error": {
                        "msg": reason_msg,
                        "resource": f"{resource}",  # optional
                        "details": details,  # optional
                    }
                }
            )

        raise web.HTTPBadRequest(
            reason=reason_msg,
            text=error_str,
            content_type=MIMETYPE_APPLICATION_JSON,
        )


# NOTE:
#
# - parameters in the path are part of the resource name and therefore are required
# - parameters in the query are typically extra options like flags or filter options
# - body holds the request data
#


def parse_request_path_parameters_as(
    parameters_schema: Type[ModelType],
    request: web.Request,
    *,
    use_enveloped_error_v1: bool = True,
) -> ModelType:
    """Parses path parameters from 'request' and validates against 'parameters_schema'

    :raises HTTPBadRequest if validation of parameters  fail
    """
    with handle_validation_as_http_error(
        error_msg_template="Invalid parameter/s '{failed}' in request path",
        resource=request.rel_url,
        use_error_v1=use_enveloped_error_v1,
    ):
        data = dict(request.match_info)
        return parameters_schema.parse_obj(data)


def parse_request_query_parameters_as(
    parameters_schema: Type[ModelType],
    request: web.Request,
    *,
    use_enveloped_error_v1: bool = True,
) -> ModelType:
    """Parses query parameters from 'request' and validates against 'parameters_schema'

    :raises HTTPBadRequest if validation of queries fail
    """

    with handle_validation_as_http_error(
        error_msg_template="Invalid parameter/s '{failed}' in request query",
        resource=request.rel_url,
        use_error_v1=use_enveloped_error_v1,
    ):
        data = dict(request.query)
        return parameters_schema.parse_obj(data)


async def parse_request_body_as(
    model_schema: Type[ModelType],
    request: web.Request,
    *,
    use_enveloped_error_v1: bool = True,
) -> ModelType:
    """Parses and validates request body against schema

    :raises HTTPBadRequest
    """
    with handle_validation_as_http_error(
        error_msg_template="Invalid field/s '{failed}' in request body",
        resource=request.rel_url,
        use_error_v1=use_enveloped_error_v1,
    ):
        body = await request.json()
        return model_schema.parse_obj(body)
