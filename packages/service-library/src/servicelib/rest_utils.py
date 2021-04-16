""" rest - misc utils

UNDER DEVELOPMENT

TODO: deprecate. Too general
"""
import json
from math import ceil
from typing import Any, Dict, List

import attr
from aiohttp import web
from openapi_core.extensions.models.factories import Model as BodyModel
from pydantic.types import PositiveInt
from yarl import URL

from .openapi_validation import (
    COOKIE_KEY,
    HEADER_KEY,
    PATH_KEY,
    QUERY_KEY,
    validate_request,
)
from .rest_models import ErrorItemType, ErrorType
from .rest_oas import get_specs


def body_to_dict(body: BodyModel) -> Dict:
    # openapi_core.extensions.models.factories.Model -> dict
    dikt = {}
    for k, v in body.__dict__.items():
        if hasattr(v, "__dict__"):
            v = body_to_dict(v)
        dikt[k] = v
    return dikt


class EnvelopeFactory:
    """
    Creates a { 'data': , 'error': } envelop for response payload

    as suggested in https://medium.com/studioarmix/learn-restful-api-design-ideals-c5ec915a430f
    """

    def __init__(self, data=None, error=None):
        enveloped = {"data": data, "error": error}
        for key, value in enveloped.items():
            if value is not None and not isinstance(value, dict):
                enveloped[key] = attr.asdict(value)
        self._envelope = enveloped

    def as_dict(self) -> Dict:
        return self._envelope

    def as_text(self) -> str:
        return json.dumps(self.as_dict())

    as_data = as_dict


async def extract_and_validate(request: web.Request):
    """
        Extracts validated parameters in path, query and body

    Can raise '400 Bad Request': indicates that the server could not understand the request due to invalid syntax
    See https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400
    """
    spec = get_specs(request.app)
    params, body, errors = await validate_request(request, spec)

    if errors:
        error = ErrorType(
            errors=[ErrorItemType.from_error(err) for err in errors],
            status=web.HTTPBadRequest.status_code,
        )
        raise web.HTTPBadRequest(
            reason="Failed request validation against API specs",
            text=EnvelopeFactory(error=error).as_text(),
            content_type="application/json",
        )

    return params[PATH_KEY], params[QUERY_KEY], body


def paginate_limit_offset(
    request_url: URL, *, data: List[Any], limit: PositiveInt, offset: int, total: int
) -> Dict[str, Any]:
    assert limit > 0  # nosec
    assert len(data) <= limit  # nosec
    last_page = ceil(total / limit) - 1
    return {
        "data": data,
        "_meta": {
            "total": total,
            "limit": limit,
            "count": len(data),
        },
        "_links": {
            "self": {"href": str(request_url)},
            "first": {"href": str(request_url.update_query({"offset": 0}))},
            "prev": {
                "href": str(request_url.update_query({"offset": offset - 1}))
                if offset > 0
                else None
            },
            "next": {
                "href": str(request_url.update_query({"offset": offset + 1}))
                if offset < last_page
                else None
            },
            "last": {"href": str(request_url.update_query({"offset": last_page}))},
        },
    }


__all__ = ("COOKIE_KEY", "HEADER_KEY", "PATH_KEY", "QUERY_KEY")
