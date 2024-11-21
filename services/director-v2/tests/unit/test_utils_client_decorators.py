# pylint: disable=redefined-outer-name

import logging

import pytest
import respx
from fastapi import HTTPException, status
from httpx import AsyncClient, Response
from simcore_service_director_v2.utils.client_decorators import handle_errors

logger = logging.getLogger(__name__)


@pytest.fixture
async def httpx_async_client() -> AsyncClient:
    async with AsyncClient() as client:
        yield client


async def test_handle_errors(httpx_async_client: AsyncClient):
    @handle_errors("AService", logger)
    async def a_request(method: str, **kwargs) -> Response:
        return await httpx_async_client.request(method, **kwargs)

    url = "https://tea.org/"
    with respx.mock:
        respx.post(url).mock(
            return_value=Response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                text="this kettle is currently\nserving the empire",
            )
        )

        with pytest.raises(HTTPException) as exec_info:
            await a_request(
                "POST",
                url=url,
                params={"kettle": "boiling"},
                data={"kettle_number": "royal_01"},
            )
        assert exec_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        # ERROR    test_utils_client_decorators:client_decorators.py:76 AService service error:
        # |Request|
        # <Request('POST', 'https://tea.org/?kettle=boiling')>
        # host: tea.org
        # accept: */*
        # accept-encoding: gzip, deflate
        # connection: keep-alive
        # user-agent: python-httpx/0.23.0
        # content-length: 22
        # content-type: application/x-www-form-urlencoded
        # kettle_number=royal_01
        # |Response|
        # <Response [500 Internal Server Error]>
        # content-length: 43
        # content-type: text/plain; charset=utf-8
        # this kettle is currently
        # serving the empire
