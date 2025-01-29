# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator

import httpx
import pytest
from asyncpg import PostgresError
from aws_library.s3._errors import S3AccessError, S3KeyNotFoundError
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
from simcore_service_storage.exceptions.errors import (
    FileAccessRightError,
    FileMetaDataNotFoundError,
    LinkAlreadyExistsError,
    ProjectAccessRightError,
    ProjectNotFoundError,
)
from simcore_service_storage.exceptions.handlers import set_exception_handlers
from simcore_service_storage.modules.datcore_adapter.datcore_adapter_exceptions import (
    DatcoreAdapterTimeoutError,
)
from simcore_service_storage.modules.db.db_access_layer import (
    InvalidFileIdentifierError,
)


@pytest.fixture
def initialized_app() -> FastAPI:
    app = FastAPI()
    set_exception_handlers(app)
    return app


@pytest.fixture
async def client(initialized_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=httpx.ASGITransport(app=initialized_app),
        base_url="http://test",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.mark.parametrize(
    "exception, status_code",
    [
        (
            InvalidFileIdentifierError(
                identifier="pytest file identifier", details="pytest details"
            ),
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (
            FileMetaDataNotFoundError(file_id="pytest file ID"),
            status.HTTP_404_NOT_FOUND,
        ),
        (
            S3KeyNotFoundError(key="pytest key", bucket="pytest bucket"),
            status.HTTP_404_NOT_FOUND,
        ),
        (
            ProjectNotFoundError(project_id="pytest project ID"),
            status.HTTP_404_NOT_FOUND,
        ),
        (
            FileAccessRightError(
                access_right="pytest access rights", file_id="pytest file ID"
            ),
            status.HTTP_403_FORBIDDEN,
        ),
        (
            ProjectAccessRightError(
                access_right="pytest access rights", project_id="pytest project ID"
            ),
            status.HTTP_403_FORBIDDEN,
        ),
        (
            LinkAlreadyExistsError(file_id="pytest file ID"),
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (
            PostgresError("pytest postgres error"),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            S3AccessError(),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            DatcoreAdapterTimeoutError(msg="pytest datcore adapter timeout"),
            status.HTTP_504_GATEWAY_TIMEOUT,
        ),
        (
            NotImplementedError("pytest not implemented error"),
            status.HTTP_501_NOT_IMPLEMENTED,
        ),
    ],
    ids=str,
)
async def test_exception_handlers(
    initialized_app: FastAPI,
    client: AsyncClient,
    exception: Exception,
    status_code: int,
):
    @initialized_app.get("/test")
    async def test_endpoint():
        raise exception

    response = await client.get("/test")
    assert response.status_code == status_code
    assert response.json() == {"errors": [f"{exception}"]}


async def test_generic_http_exception_handler(
    initialized_app: FastAPI, client: AsyncClient
):
    @initialized_app.get("/test")
    async def test_endpoint():
        raise HTTPException(status_code=status.HTTP_410_GONE)

    response = await client.get("/test")
    assert response.status_code == status.HTTP_410_GONE
    assert response.json() == {"errors": ["Gone"]}


async def test_request_validation_error_handler(
    initialized_app: FastAPI, client: AsyncClient
):
    @initialized_app.get("/test")
    async def test_endpoint():
        raise RequestValidationError(errors=["pytest request validation error"])

    response = await client.get("/test")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json() == {"errors": ["pytest request validation error"]}


@pytest.mark.xfail(
    reason="Generic exception handler is not working as expected as shown in https://github.com/ITISFoundation/osparc-simcore/blob/5732a12e07e63d5ce55010ede9b9ab543bb9b278/packages/service-library/tests/fastapi/test_exceptions_utils.py"
)
async def test_generic_exception_handler(initialized_app: FastAPI, client: AsyncClient):
    @initialized_app.get("/test")
    async def test_endpoint():
        msg = "Generic exception"
        raise Exception(msg)

    response = await client.get("/test")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "Generic exception"}
