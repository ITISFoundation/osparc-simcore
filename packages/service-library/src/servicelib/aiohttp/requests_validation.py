"""Parses and validation aiohttp requests against pydantic models

Rationale: These functions follow an interface analogous to ``pydantic.tools``'s

   parse_obj_as(model_class, obj)

but adapted to parse&validate path, query and body of an aiohttp's request
"""

import json.decoder
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypeVar

from aiohttp import web
from common_library.user_messages import user_message
from models_library.rest_error import EnvelopedError
from pydantic import BaseModel, TypeAdapter, ValidationError

from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from . import status

ModelClass = TypeVar("ModelClass", bound=BaseModel)
ModelOrListOrDictType = TypeVar("ModelOrListOrDictType", bound=BaseModel | list | dict)


@contextmanager
def handle_validation_as_http_error(
    *, error_msg_template: str, resource_name: str
) -> Iterator[None]:
    """Context manager to handle ValidationError and reraise them as HTTPUnprocessableEntity error

    Arguments:
        error_msg_template -- _description_
        resource_name --

    Raises:
        web.HTTPUnprocessableEntity: (422) raised from a ValidationError

    """

    try:
        yield

    except ValidationError as err:
        # SEE https://github.com/ITISFoundation/osparc-simcore/issues/443
        _details = [
            {
                "loc": ".".join(map(str, e["loc"])),  # e.g. "body.name"
                "msg": e["msg"],
                "type": e["type"],
            }
            for e in err.errors()
        ]

        errors_details = [
            {
                "code": e["type"],
                "message": e["msg"],
                "resource": resource_name,
                "field": e["loc"],
            }
            for e in _details
        ]

        error_json_str = EnvelopedError.model_validate(
            {
                "error": {
                    "message": error_msg_template.format(
                        failed=", ".join(e["field"] for e in errors_details)
                    ),
                    "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "errors": errors_details,
                }
            }
        ).model_dump_json(exclude_unset=True, exclude_none=True)

        raise web.HTTPUnprocessableEntity(  # 422
            text=error_json_str,
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from err


# NOTE:
#
# - parameters in the path are part of the resource name and therefore are required
# - parameters in the query are typically extra options like flags or filter options
# - body holds the request data
#


def parse_request_path_parameters_as(
    parameters_schema_cls: type[ModelClass],
    request: web.Request,
) -> ModelClass:
    """Parses path parameters from 'request' and validates against 'parameters_schema'


    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of parameters  fail

    Returns:
        Validated model of path parameters
    """

    with handle_validation_as_http_error(
        error_msg_template=user_message(
            "Invalid parameter/s '{failed}' in request path"
        ),
        resource_name=request.rel_url.path,
    ):
        data = dict(request.match_info)
        return parameters_schema_cls.model_validate(data)


def parse_request_query_parameters_as(
    parameters_schema_cls: type[ModelClass],
    request: web.Request,
) -> ModelClass:
    """Parses query parameters from 'request' and validates against 'parameters_schema'


    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of parameters  fail

    Returns:
        Validated model of query parameters
    """

    with handle_validation_as_http_error(
        error_msg_template=user_message(
            "Invalid parameter/s '{failed}' in request query"
        ),
        resource_name=request.rel_url.path,
    ):
        # NOTE: Currently, this does not take into consideration cases where there are multiple
        # query parameters with the same key. However, we are not using such cases anywhere at the moment.
        data = dict(request.query)

        if hasattr(parameters_schema_cls, "model_validate"):
            return parameters_schema_cls.model_validate(data)
        model: ModelClass = TypeAdapter(parameters_schema_cls).validate_python(data)
        return model


def parse_request_headers_as(
    parameters_schema_cls: type[ModelClass],
    request: web.Request,
) -> ModelClass:
    with handle_validation_as_http_error(
        error_msg_template=user_message(
            "Invalid parameter/s '{failed}' in request headers"
        ),
        resource_name=request.rel_url.path,
    ):
        data = dict(request.headers)
        return parameters_schema_cls.model_validate(data)


async def parse_request_body_as(
    model_schema_cls: type[ModelOrListOrDictType],
    request: web.Request,
) -> ModelOrListOrDictType:
    """Parses and validates request body against schema

    Keyword Arguments:
        use_enveloped_error_v1 -- new enveloped error model (default: {True})

    Raises:
        web.HTTPBadRequest: (400) if invalid json body
        web.HTTPUnprocessableEntity: (422) if does not validates against schema

    Returns:
        Validated model of request body
    """
    with handle_validation_as_http_error(
        error_msg_template=user_message("Invalid field/s '{failed}' in request body"),
        resource_name=request.rel_url.path,
    ):
        if not request.can_read_body:
            # requests w/o body e.g. when model-schema is fully optional
            body = {}
        else:
            try:
                body = await request.json()
            except json.decoder.JSONDecodeError as err:
                raise web.HTTPBadRequest(text=f"Invalid json in body: {err}") from err

        if hasattr(model_schema_cls, "model_validate"):
            # NOTE: model_schema can be 'list[T]' or 'dict[T]' which raise TypeError
            # with issubclass(model_schema, BaseModel)
            assert issubclass(model_schema_cls, BaseModel)  # nosec
            return model_schema_cls.model_validate(body)  # type: ignore [return-value]

        # used for model_schema like 'list[T]' or 'dict[T]'
        return TypeAdapter(model_schema_cls).validate_python(body)  # type: ignore[no-any-return]
