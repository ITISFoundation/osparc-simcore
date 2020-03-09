"""OpenAPI core contrib aiohttp responses module"""
from aiohttp.web import Response

from openapi_core.validation.response.datatypes import OpenAPIResponse


class AiohttpOpenAPIResponseFactory:
    @classmethod
    def create(cls, response: Response) -> OpenAPIResponse:
        return OpenAPIResponse(
            data=response.text,
            status_code=response.status,
            mimetype=response.content_type,
        )
