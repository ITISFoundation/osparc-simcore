# pylint: disable=redefined-outer-name

import logging

import pytest
import respx
from fastapi import HTTPException, status
from httpx import AsyncClient, Response
from pytest import LogCaptureFixture
from simcore_service_director_v2.utils.client_decorators import handle_errors

logger = logging.getLogger(__name__)


@pytest.fixture
async def httpx_async_client() -> AsyncClient:
    async with AsyncClient() as client:
        yield client


async def test_handle_errors(
    httpx_async_client: AsyncClient, caplog_debug_level: LogCaptureFixture
):
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
                params=dict(kettle="boiling"),
                data=dict(kettle_number="royal_01"),
            )
        assert status.HTTP_503_SERVICE_UNAVAILABLE == exec_info.value.status_code

        assert "ERROR" in caplog_debug_level.text
        assert "this kettle is currently\nserving the empire" in caplog_debug_level.text

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


@pytest.mark.testit
async def test_handle_legacy_errors(
    httpx_async_client: AsyncClient, caplog_debug_level: LogCaptureFixture
):
    @handle_errors("DynamicService", logger)
    async def a_request(method: str, **kwargs) -> Response:
        return await httpx_async_client.request(method, **kwargs)

    url = "http://raw-graphs_0a4ab690-f0c8-4104-b270-9e67239eca0d:4000/x/0a4ab690-f0c8-4104-b270-9e67239eca0d/retrieve"
    with respx.mock:
        respx.post(url).mock(
            return_value=Response(status.HTTP_500_INTERNAL_SERVER_ERROR)
        )

        await a_request("POST", url=url)

        assert "legacy service does not implement" in caplog_debug_level.text
