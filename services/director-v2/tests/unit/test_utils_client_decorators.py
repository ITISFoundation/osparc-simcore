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
                params=dict(kettle="boiling"),
                data=dict(kettle_number="royal_01"),
            )
        assert status.HTTP_503_SERVICE_UNAVAILABLE == exec_info.value.status_code
