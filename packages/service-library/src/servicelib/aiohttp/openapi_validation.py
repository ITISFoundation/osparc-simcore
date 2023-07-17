""" Implements openapi specs validation

Based on openapi-core
"""
# mypy: ignore-errors

import logging

from aiohttp import web
from openapi_core.schema.specs.models import Spec as OpenApiSpec
from openapi_core.validation.request.validators import RequestValidator

from .openapi_wrappers import PARAMETERS_KEYS, AiohttpOpenAPIRequest

logger = logging.getLogger(__name__)


PATH_KEY, QUERY_KEY, HEADER_KEY, COOKIE_KEY = PARAMETERS_KEYS


async def validate_request(request: web.Request, spec: OpenApiSpec):
    """Validates aiohttp.web.Request against an opeapi specification

    Returns parameters dict, body object and list of errors (exceptions objects)
    """
    req = await AiohttpOpenAPIRequest.create(request)

    validator = RequestValidator(spec)
    result = validator.validate(req)

    return result.parameters, result.body, result.errors
