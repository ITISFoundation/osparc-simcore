import json
import warnings
from dataclasses import asdict

from aiohttp import web

from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from .application_keys import APP_OPENAPI_SPECS_KEY
from .openapi_validation import PATH_KEY, QUERY_KEY, validate_request
from .rest_models import ErrorItemType, ErrorType


class EnvelopeFactory:
    """
    Creates a { 'data': , 'error': } envelop for response payload

    as suggested in https://medium.com/studioarmix/learn-restful-api-design-ideals-c5ec915a430f
    """

    def __init__(self, data=None, error=None):
        enveloped = {"data": data, "error": error}
        for key, value in enveloped.items():
            if value is not None and not isinstance(value, dict):
                enveloped[key] = asdict(value)
        self._envelope = enveloped

    def as_dict(self) -> dict:
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
    warnings.warn(
        "extract_and_validate is deprecated. Use instead servicelib.rest_utils.extract_and_validate",
        DeprecationWarning,
    )

    spec = request.app[APP_OPENAPI_SPECS_KEY]
    params, body, errors = await validate_request(request, spec)

    if errors:
        error = ErrorType(
            errors=[ErrorItemType.from_error(err) for err in errors],
            status=web.HTTPBadRequest.status_code,
        )
        raise web.HTTPBadRequest(
            reason="Failed request validation against API specs",
            text=EnvelopeFactory(error=error).as_text(),
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    return params[PATH_KEY], params[QUERY_KEY], body
