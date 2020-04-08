"""OpenAPI core contrib aiohttp responses module

SEE https://github.com/p1c2u/openapi-core/blob/master/openapi_core/contrib/requests/responses.py
"""
import asyncio
from typing import Coroutine, Union

from aiohttp import ClientResponse
from aiohttp.web import Response as ServerResponse
from openapi_core.validation.response.datatypes import OpenAPIResponse

from .utils import assert_type


class AiohttpOpenAPIResponseFactory:
    @classmethod
    def create(cls, response: Union[ServerResponse, ClientResponse]) -> OpenAPIResponse:
        # server response
        if isinstance(response, ServerResponse):
            return cls.create_from_server_response(response)

        # client response
        coro: Coroutine = cls.create_from_client_response(response)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    @classmethod
    def create_from_server_response(cls, response: ServerResponse) -> OpenAPIResponse:
        assert_type(response, ServerResponse)
        raw: str = response.text
        return OpenAPIResponse(
            data=raw, status_code=response.status, mimetype=response.content_type,
        )

    @classmethod
    async def create_from_client_response(
        cls, response: ClientResponse
    ) -> OpenAPIResponse:
        assert_type(response, ClientResponse)
        raw: str = await response.text()
        return OpenAPIResponse(
            data=raw, status_code=response.status, mimetype=response.content_type,
        )
