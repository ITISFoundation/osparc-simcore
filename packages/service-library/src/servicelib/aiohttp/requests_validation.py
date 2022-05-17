""" Parses and validation aiohttp requests against pydantic models

These functions are analogous to `pydantic.tools.parse_obj_as(model_class, obj)` for aiohttp's requests
"""

from contextlib import contextmanager
from typing import Iterator, Type, TypeVar

from aiohttp import web
from pydantic import BaseModel, ValidationError

from ..json_serialization import json_dumps
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON

M = TypeVar("M", bound=BaseModel)


@contextmanager
def handle_validation_as_http_error(*, error_msg_template: str) -> Iterator[None]:
    """
    Transforms ValidationError into HTTP error
    """
    try:

        yield

    except ValidationError as err:
        details = [
            {"loc": ".".join(map(str, e["loc"])), "msg": e["msg"]} for e in err.errors()
        ]
        msg = error_msg_template.format(failed=", ".join(d["loc"] for d in details))

        raise web.HTTPBadRequest(
            reason=msg,
            body=json_dumps({"error": {"msg": msg, "details": details}}),
            content_type=MIMETYPE_APPLICATION_JSON,
        )


# NOTE:
#
# - parameters in the path are part of the resource name and therefore are required
# - parameters in the query are typically extra options like flags or filter options
# - body holds the request data
#


def parse_request_path_parameters_as(
    parameters_schema: Type[M],
    request: web.Request,
) -> M:
    """Parses path parameters from 'request' and validates against 'parameters_schema'

    :raises HTTPBadRequest if validation of parameters  fail
    """
    with handle_validation_as_http_error(
        error_msg_template="Invalid parameter/s '{failed}' in request path"
    ):
        data = dict(request.match_info)
        return parameters_schema.parse_obj(data)


def parse_request_query_parameters_as(
    parameters_schema: Type[M],
    request: web.Request,
) -> M:
    """Parses query parameters from 'request' and validates against 'parameters_schema'

    :raises HTTPBadRequest if validation of queries fail
    """

    with handle_validation_as_http_error(
        error_msg_template="Invalid parameter/s '{failed}' in request query"
    ):
        data = dict(request.query)
        return parameters_schema.parse_obj(data)


async def parse_request_body_as(model_schema: Type[M], request: web.Request) -> M:
    """Parses and validates request body against schema

    :raises HTTPBadRequest
    """
    with handle_validation_as_http_error(
        error_msg_template="Invalid field/s '{failed}' in request body"
    ):
        body = await request.json()
        return model_schema.parse_obj(body)
