""" Implements openapi specs validation

Based on openapi-core
"""

import logging

from aiohttp import web
from openapi_core import shortcuts
from openapi_core.schema.specs.models import Spec as OpenApiSpec
from openapi_core.validation.request.validators import RequestValidator
from openapi_core.validation.response.validators import ResponseValidator

from .openapi_wrappers import (PARAMETERS_KEYS, AiohttpOpenAPIRequest,
                               AiohttpOpenAPIResponse)

logger = logging.getLogger(__name__)

#from openapi_core.wrappers.mock import MockRequest

PATH_KEY, QUERY_KEY, HEADER_KEY, COOKIE_KEY = PARAMETERS_KEYS #pylint: disable=W0612


async def validate_request(request: web.Request, spec: OpenApiSpec):
    """ Validates aiohttp.web.Request against an opeapi specification

    Returns parameters dict, body object and list of errors (exceptions objects)
    """
    req = await AiohttpOpenAPIRequest.create(request)

    validator = RequestValidator(spec)
    result = validator.validate(req)

    return result.parameters, result.body, result.errors

async def validate_parameters(spec: OpenApiSpec, request: web.Request):
    req = await AiohttpOpenAPIRequest.create(request)
    return shortcuts.validate_parameters(spec, req)

async def validate_body(spec: OpenApiSpec, request: web.Request):
    req = await AiohttpOpenAPIRequest.create(request)
    return shortcuts.validate_body(spec, req)




async def validate_data(spec: OpenApiSpec, request, response: web.Response):

    if isinstance(request, web.Request):
        req = await AiohttpOpenAPIRequest.create(request)
    else:
        # TODO: alternative MockRequest
        #params = ['host_url', 'method', 'path']
        #opapi_request = MockRequest(*args)

        params = ['full_url_pattern', 'method']
        assert all(hasattr(request, attr) for attr in params)
        # TODO: if a dict with params, convert dict to dot operations! and reverse


        req = request

    res = await AiohttpOpenAPIResponse.create(response)

    validator = ResponseValidator(spec)
    result = validator.validate(req, res)

    result.raise_for_errors()

    return result.data

async def validate_response(spec: OpenApiSpec, request: web.Request, response: web.Response):
    """
      Validates server response against openapi specs

      Raises exceptions OpenAPIError, OpenAPIMappingError
    """
    validator = ResponseValidator(spec)

    req = await AiohttpOpenAPIRequest.create(request)
    res = AiohttpOpenAPIResponse(response, response.text) # FIXME:ONLY IN SERVER side. Async in client!
    result = validator.validate(req, res)
    result.raise_for_errors()


__all__ = (
    'validate_request',
    'validate_data'
)
