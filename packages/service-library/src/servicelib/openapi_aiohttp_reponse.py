"""OpenAPI core contrib aiohttp responses module"""
from aiohttp.web import Response

from openapi_core.validation.response.datatypes import OpenAPIResponse


class AiohttpOpenAPIResponseFactory(object):
    @classmethod
    async def create(cls, response: Response) -> OpenAPIResponse:
        body: str = await response.text()
        return OpenAPIResponse(
            data=body, status_code=response.status, mimetype=response.content_type,
        )
