""" Parses and validation aiohttp requests against pydantic models

Rationale: These functions follow an interface analogous to ``pydantic.tools``'s

   parse_obj_as(model_class, obj)

but adapted to parse&validate path, query and body of an aiohttp's request
"""

import json.decoder
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TypeAlias, TypeVar, Union

from aiohttp import web
from pydantic import BaseModel, Extra, ValidationError, parse_obj_as

from ..json_serialization import json_dumps
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from . import status
from .rest_models import ManyErrors, OneError

ModelClass = TypeVar("ModelClass", bound=BaseModel)
ModelOrListOrDictType = TypeVar("ModelOrListOrDictType", bound=BaseModel | list | dict)
UnionOfModelTypes: TypeAlias = Union[type[ModelClass], type[ModelClass]]  # noqa: UP007


class RequestParams(BaseModel):
    ...


class StrictRequestParams(BaseModel):
    """Use a base class for context, path and query parameters"""

    class Config:
        extra = Extra.forbid  # strict


@contextmanager
def handle_validation_as_http_error(
    *,
    error_msg_template: str,
    resource_name: str,
    user_deprecated_model: bool,
    loc_prefix: str | None = None,
) -> Iterator[None]:
    """Context manager to handle ValidationError and reraise them as HTTPUnprocessableEntity error

    Raises:
        web.HTTPUnprocessableEntity: (422) raised from a ValidationError

    """
    try:

        yield

    except ValidationError as err:
        details = [
            {
                "msg": e["msg"],
                "type": e["type"],
                "loc": ".".join(
                    map(str, (loc_prefix,) + e["loc"] if loc_prefix else e["loc"])
                ),  # e.g. ["body", "x",0,"y"] -> "body.x.0.y"
            }
            for e in err.errors()
        ]
        reason_msg = error_msg_template.format(
            failed=", ".join(_["loc"] for _ in details)
        )

        if user_deprecated_model:
            # NOTE: keeps backwards compatibility until ligher error response is implemented in the entire API
            # Implements servicelib.aiohttp.rest_responses.ErrorItem
            errors = [
                {
                    "code": e["type"],
                    "message": e["msg"],  # required
                    "resource": resource_name,
                    "field": e["loc"],
                }
                for e in details
            ]
            enveloped_error_json = json_dumps(
                # NOTE: this has to be like ResponseErrorBody
                {
                    "error": {
                        "message": reason_msg,
                        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                        "errors": errors,
                    }
                }
            )
        else:
            # NEW proposed error for https://github.com/ITISFoundation/osparc-simcore/issues/443
            errors = [
                {
                    "type": e["type"],  # optional
                    "msg": e["msg"],  # required
                    "loc": e["loc"],  # optional
                }
                for e in details
            ]
            envelope: dict[str, Any]
            if len(errors) == 1:
                # Error with a single occurrence
                envelope = {"error": errors[0]}
            else:
                # Error with multiple occurence
                envelope = {
                    "error": {
                        "msg": reason_msg,  # required
                        "details": errors,
                    }
                }

            assert parse_obj_as(OneError | ManyErrors, envelope["error"])  # type: ignore[arg-type] # nosec

            enveloped_error_json = json_dumps(envelope)
        raise web.HTTPUnprocessableEntity(  # 422
            reason=reason_msg,
            text=enveloped_error_json,
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
    *,
    use_enveloped_error_v1: bool = True,
) -> ModelClass:
    """Parses path parameters from 'request' and validates against 'parameters_schema'


    Keyword Arguments:
        use_enveloped_error_v1 -- new enveloped error model (default: {True})

    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of parameters  fail

    Returns:
        Validated model of path parameters
    """

    with handle_validation_as_http_error(
        error_msg_template="Invalid parameter/s '{failed}' in request",
        resource_name=request.rel_url.path,
        user_deprecated_model=use_enveloped_error_v1,
        loc_prefix="path",
    ):
        data = dict(request.match_info)
        return parameters_schema_cls.parse_obj(data)


def parse_request_query_parameters_as(
    parameters_schema_cls: type[ModelClass] | UnionOfModelTypes,
    request: web.Request,
    *,
    use_enveloped_error_v1: bool = True,
) -> ModelClass:
    """Parses query parameters from 'request' and validates against 'parameters_schema'


    Keyword Arguments:
        use_enveloped_error_v1 -- new enveloped error model (default: {True})

    Raises:
        web.HTTPUnprocessableEntity: (422) if validation of parameters  fail

    Returns:
        Validated model of query parameters
    """

    with handle_validation_as_http_error(
        error_msg_template="Invalid parameter/s '{failed}' in request",
        resource_name=request.rel_url.path,
        user_deprecated_model=use_enveloped_error_v1,
        loc_prefix="query",
    ):
        data = dict(request.query)
        if hasattr(parameters_schema_cls, "parse_obj"):
            return parameters_schema_cls.parse_obj(data)
        model: ModelClass = parse_obj_as(parameters_schema_cls, data)
        return model


async def parse_request_body_as(
    model_schema_cls: type[ModelOrListOrDictType],
    request: web.Request,
    *,
    use_enveloped_error_v1: bool = True,
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
        error_msg_template="Invalid field/s '{failed}' in request",
        resource_name=request.rel_url.path,
        user_deprecated_model=use_enveloped_error_v1,
        loc_prefix="body",
    ):
        if not request.can_read_body:
            # requests w/o body e.g. when model-schema is fully optional
            body = {}
        else:
            try:
                body = await request.json()
            except json.decoder.JSONDecodeError as err:
                raise web.HTTPBadRequest(reason=f"Invalid json in body: {err}") from err

        if hasattr(model_schema_cls, "parse_obj"):
            # NOTE: model_schema can be 'list[T]' or 'dict[T]' which raise TypeError
            # with issubclass(model_schema, BaseModel)
            assert issubclass(model_schema_cls, BaseModel)  # nosec
            return model_schema_cls.parse_obj(body)  # type: ignore [return-value]

        # used for model_schema like 'list[T]' or 'dict[T]'
        return parse_obj_as(model_schema_cls, body)
