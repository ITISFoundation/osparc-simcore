# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import httpx
import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import HTTPStatusError, Request, Response
from simcore_service_api_server.exceptions import setup_exception_handlers
from simcore_service_api_server.exceptions.service_errors_utils import (
    service_exception_mapper,
)
from simcore_service_api_server.models.schemas.errors import ErrorGet


async def test_backend_service_exception_mapper():
    @service_exception_mapper(
        "DummyService",
        {
            status.HTTP_400_BAD_REQUEST: (
                status.HTTP_200_OK,
                lambda kwargs: "error message",
            )
        },
    )
    async def my_endpoint(status_code: int):
        raise HTTPStatusError(
            message="hello",
            request=Request("PUT", "https://asoubkjbasd.asjdbnsakjb"),
            response=Response(status_code),
        )

    with pytest.raises(HTTPException) as exc_info:
        await my_endpoint(status.HTTP_400_BAD_REQUEST)
    assert exc_info.value.status_code == status.HTTP_200_OK

    with pytest.raises(HTTPException) as exc_info:
        await my_endpoint(status.HTTP_500_INTERNAL_SERVER_ERROR)
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.fixture
def app() -> FastAPI:
    """Overrides app to avoid real app and builds instead a simple app to tests exception handlers"""
    app = FastAPI()
    setup_exception_handlers(app)

    @app.post("/raise-http-exception")
    def _raise_http_exception():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="fail message"
        )

    return app


async def test_http_exception_handlers(client: httpx.AsyncClient):
    response = await client.post("/raise-http-exception")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    got = ErrorGet.parse_raw(response.text)
    assert got.errors == ["fail message"]
