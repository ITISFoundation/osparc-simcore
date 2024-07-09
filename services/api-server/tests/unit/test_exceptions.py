# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


from http import HTTPStatus

import httpx
import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import HTTPStatusError, Request, Response
from simcore_service_api_server.exceptions import setup_exception_handlers
from simcore_service_api_server.exceptions.backend_errors import ProfileNotFoundError
from simcore_service_api_server.exceptions.custom_errors import MissingWalletError
from simcore_service_api_server.exceptions.service_errors_utils import (
    service_exception_mapper,
)
from simcore_service_api_server.models.schemas.errors import ErrorGet


async def test_backend_service_exception_mapper():
    @service_exception_mapper(
        "DummyService",
        {status.HTTP_400_BAD_REQUEST: ProfileNotFoundError},
    )
    async def my_endpoint(status_code: int):
        raise HTTPStatusError(
            message="hello",
            request=Request("PUT", "https://asoubkjbasd.asjdbnsakjb"),
            response=Response(status_code),
        )

    with pytest.raises(ProfileNotFoundError):
        await my_endpoint(status.HTTP_400_BAD_REQUEST)

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

    @app.post("/raise-custom-error")
    def _raise_custom_exception():
        raise MissingWalletError(job_id=123)

    return app


async def test_raised_http_exception(client: httpx.AsyncClient):
    response = await client.post("/raise-http-exception")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    got = ErrorGet.parse_raw(response.text)
    assert got.errors == ["fail message"]


async def test_fastapi_http_exception_respond_with_error_model(
    client: httpx.AsyncClient,
):
    response = await client.get("/invalid")

    assert response.status_code == status.HTTP_404_NOT_FOUND

    got = ErrorGet.parse_raw(response.text)
    assert got.errors == [HTTPStatus(response.status_code).phrase]


async def test_custom_error_handlers(client: httpx.AsyncClient):
    response = await client.post("/raise-custom-error")

    assert response.status_code == status.HTTP_424_FAILED_DEPENDENCY

    got = ErrorGet.parse_raw(response.text)
    assert got.errors == [f"{MissingWalletError(job_id=123)}"]
