"""Locale-aware request validation for the web-server.

Re-exports servicelib's parse_request_*_as functions with error messages
pre-translated to the request locale (via translate_message) before they
are formatted by the validation context manager.

Usage: import from here instead of servicelib.aiohttp.requests_validation
in any webserver controller that needs translated validation errors.
"""

import json.decoder
from typing import TypeVar

from aiohttp import web
from common_library.user_messages import user_message
from pydantic import BaseModel, TypeAdapter
from servicelib.aiohttp.requests_validation import handle_validation_as_http_error

from .locale import translate_message

ModelClass = TypeVar("ModelClass", bound=BaseModel)
ModelOrListOrDictType = TypeVar("ModelOrListOrDictType", bound=BaseModel | list | dict)

_MSG_INVALID_PATH = user_message("Invalid parameter/s '{failed}' in request path")
_MSG_INVALID_QUERY = user_message("Invalid parameter/s '{failed}' in request query")
_MSG_INVALID_HEADERS = user_message("Invalid parameter/s '{failed}' in request headers")
_MSG_INVALID_BODY = user_message("Invalid field/s '{failed}' in request body")


def parse_request_path_parameters_as(  # noqa: UP047
    parameters_schema_cls: type[ModelClass],
    request: web.Request,
) -> ModelClass:
    with handle_validation_as_http_error(
        error_msg_template=translate_message(_MSG_INVALID_PATH, request),
        resource_name=request.rel_url.path,
    ):
        return parameters_schema_cls.model_validate(dict(request.match_info))


def parse_request_query_parameters_as(  # noqa: UP047
    parameters_schema_cls: type[ModelClass],
    request: web.Request,
) -> ModelClass:
    with handle_validation_as_http_error(
        error_msg_template=translate_message(_MSG_INVALID_QUERY, request),
        resource_name=request.rel_url.path,
    ):
        data = dict(request.query)
        if hasattr(parameters_schema_cls, "model_validate"):
            return parameters_schema_cls.model_validate(data)
        model: ModelClass = TypeAdapter(parameters_schema_cls).validate_python(data)
        return model


def parse_request_headers_as(  # noqa: UP047
    parameters_schema_cls: type[ModelClass],
    request: web.Request,
) -> ModelClass:
    with handle_validation_as_http_error(
        error_msg_template=translate_message(_MSG_INVALID_HEADERS, request),
        resource_name=request.rel_url.path,
    ):
        return parameters_schema_cls.model_validate(dict(request.headers))


async def parse_request_body_as(  # noqa: UP047
    model_schema_cls: type[ModelOrListOrDictType],
    request: web.Request,
) -> ModelOrListOrDictType:
    with handle_validation_as_http_error(
        error_msg_template=translate_message(_MSG_INVALID_BODY, request),
        resource_name=request.rel_url.path,
    ):
        if not request.can_read_body:
            body = {}
        else:
            try:
                body = await request.json()
            except json.decoder.JSONDecodeError as err:
                raise web.HTTPBadRequest(text=f"Invalid json in body: {err}") from err

        if hasattr(model_schema_cls, "model_validate"):
            assert issubclass(model_schema_cls, BaseModel)  # nosec
            return model_schema_cls.model_validate(body)

        return TypeAdapter(model_schema_cls).validate_python(body)  # type: ignore[no-any-return]
