""" Parses and validation aiohttp requests against pydantic models

An analogous to pydantic.tools.parse_obj_as(...) for aiohttp's requests
"""

from typing import Type, TypeVar

from aiohttp import web
from pydantic import BaseModel, ValidationError
from servicelib.json_serialization import json_dumps

M = TypeVar("M", bound=BaseModel)


def _convert_to_http_error_kwargs(
    error: ValidationError,
    reason: str,
):
    details = [
        {"loc": ".".join(map(str, e["loc"])), "msg": e["msg"]} for e in error.errors()
    ]

    return dict(
        reason=reason.format(failed=", ".join(d["loc"] for d in details)),
        body=json_dumps({"error": details}),
        content_type="application/json",
    )


def parse_request_parameters_as(
    parameters_schema: Type[M],
    request: web.Request,
) -> M:
    """Parses path and query parameters from 'request' and validates against 'parameters_schema'

    :raises HTTPBadRequest if validation of parameters or queries fail
    """
    try:
        params = {
            **request.match_info,
            **request.query,
        }
        return parameters_schema.parse_obj(params)

    except ValidationError as err:
        raise web.HTTPBadRequest(
            **_convert_to_http_error_kwargs(
                err,
                reason="Invalid parameters {failed} in request",
            )
        )


async def parse_request_body_as(model_schema: Type[M], request: web.Request) -> M:
    """Parses and validates request body against schema

    :raises HTTPBadRequest
    """
    try:
        body = await request.json()
        return model_schema.parse_obj(body)

    except ValidationError as err:
        raise web.HTTPBadRequest(
            **_convert_to_http_error_kwargs(
                err,
                reason="Invalid {failed} in request body",
            )
        )


def parse_request_context_as(
    context_model_cls: Type[M],
    request: web.Request,
) -> M:
    """Parses and validate request context

    :raises ValidationError
    """
    app_ctx = dict(request.app)
    req_ctx = dict(request)

    assert set(app_ctx.keys()).intersection(req_ctx.keys()) == set()  # nosec
    context = {**app_ctx, **req_ctx}
    return context_model_cls.parse_obj(context)
