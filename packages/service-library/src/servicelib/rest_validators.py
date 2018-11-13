
from aiohttp import web
from openapi_core.validation.request.validators import RequestValidator
from openapi_core.validation.response.validators import ResponseValidator

from .openapi_wrappers import (PATH_KEY, QUERY_KEY, AiohttpOpenAPIRequest,
                               AiohttpOpenAPIResponse)
from .rest_oas import OpenApiSpec, get_specs
from .rest_responses import create_error_response


class OpenApiValidator:
    """
        Used to validate data in the request->response cycle against openapi specs
    """
    @classmethod
    def create(cls, app: web.Application, _version=""):
        specs = get_specs(app)
        # TODO: one per version!
        return cls(specs)

    def __init__(self, spec: OpenApiSpec):
        self._reqvtor = RequestValidator(spec, custom_formatters=None)
        self._resvtor = ResponseValidator(spec, custom_formatters=None)

        # Current
        self.current_request = None # wrapper request

    async def check_request(self, request: web.Request):
        self.current_request = None

        rq = await AiohttpOpenAPIRequest.create(request)
        result = self._reqvtor.validate(rq)

        # keeps current request and reuses in response
        self.current_request = rq

        if result.errors:
            err = create_error_response(result.errors,
                        "Failed request validation against API specs",
                        web.HTTPBadRequest)
            raise err

        path, query = [ result.parameters[k] for k in (PATH_KEY, QUERY_KEY) ]

        return path, query, result.body

    def check_response(self, response: web.Response):
        req = self.current_request
        res = AiohttpOpenAPIResponse(response, response.text) # FIXME:ONLY IN SERVER side. Async in client!

        result = self._resvtor.validate(req, res)
        if result.errors:
            err = create_error_response(result.errors,
                        "Failed response validation against API specs",
                        web.HTTPServiceUnavailable)
            raise err
