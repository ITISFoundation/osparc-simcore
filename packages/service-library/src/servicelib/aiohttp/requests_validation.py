""" Parses and validation aiohttp requests against pydantic models

These functions are analogous to `pydantic.tools.parse_obj_as(model_class, obj)` for aiohttp's requests
"""

import json.decoder
from contextlib import contextmanager
from typing import Iterator, TypeVar, Union

from aiohttp import web
from pydantic import BaseModel, ValidationError, parse_obj_as

from ..json_serialization import json_dumps
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON

ModelType = TypeVar("ModelType", bound=BaseModel)
ModelOrListType = TypeVar("ModelOrListType", bound=Union[BaseModel, list])


@contextmanager
def handle_validation_as_http_error(
    *, error_msg_template: str, resource_name: str, use_error_v1: bool
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
                    "resource": resource_name,
                    "field": e["loc"],
                }
                for e in details
            ]
            error_str = json_dumps(
                {
                    "error": {
                        "status": web.HTTPUnprocessableEntity.status_code,
                        "errors": errors,
                    }
                }
            )
        else:
            # NEW proposed error for https://github.com/ITISFoundation/osparc-simcore/issues/443
            error_str = json_dumps(
                {
                    "error": {
                        "msg": reason_msg,
                        "resource": resource_name,  # optional
                        "details": details,  # optional
                    }
                }
            )

        raise web.HTTPUnprocessableEntity(  # 422
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
    parameters_schema: type[ModelType],
    request: web.Request,
    *,
    use_enveloped_error_v1: bool = True,
) -> ModelType:
    """Parses path parameters from 'request' and validates against 'parameters_schema'

    :raises HTTPUnprocessableEntity (422) if validation of parameters  fail
    """
    with handle_validation_as_http_error(
        error_msg_template="Invalid parameter/s '{failed}' in request path",
        resource_name=request.rel_url.path,
        use_error_v1=use_enveloped_error_v1,
    ):
        data = dict(request.match_info)
        return parameters_schema.parse_obj(data)


def parse_request_query_parameters_as(
    parameters_schema: type[ModelType],
    request: web.Request,
    *,
    use_enveloped_error_v1: bool = True,
) -> ModelType:
    """Parses query parameters from 'request' and validates against 'parameters_schema'

    :raises HTTPUnprocessableEntity (422) if validation of queries fail
    """

    with handle_validation_as_http_error(
        error_msg_template="Invalid parameter/s '{failed}' in request query",
        resource_name=request.rel_url.path,
        use_error_v1=use_enveloped_error_v1,
    ):
        data = dict(request.query)
        return parameters_schema.parse_obj(data)


async def parse_request_body_as(
    model_schema: type[ModelOrListType],
    request: web.Request,
    *,
    use_enveloped_error_v1: bool = True,
) -> ModelOrListType:
    """Parses and validates request body against schema

    :raises HTTPUnprocessableEntity (422), HTTPBadRequest(400)
    """
    with handle_validation_as_http_error(
        error_msg_template="Invalid field/s '{failed}' in request body",
        resource_name=request.rel_url.path,
        use_error_v1=use_enveloped_error_v1,
    ):
        if not request.can_read_body:
            # requests w/o body e.g. when model-schema is fully optional
            body = {}
        else:
            try:
                body = await request.json()
            except json.decoder.JSONDecodeError as err:
                raise web.HTTPBadRequest(reason=f"Invalid json in body: {err}")

        if hasattr(model_schema, "parse_obj"):
            # NOTE: model_schema can be 'list[T]' or 'dict[T]' which raise TypeError
            # with issubclass(model_schema, BaseModel)
            assert issubclass(model_schema, BaseModel)  # nosec
            return model_schema.parse_obj(body)

        # used for model_schema like 'list[T]' or 'dict[T]'
        return parse_obj_as(model_schema, body)
