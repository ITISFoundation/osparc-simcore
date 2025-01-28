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
from fastapi import FastAPI, status
from httpx import AsyncClient
from simcore_service_storage.api.rest.utils import set_exception_handlers
from simcore_service_storage.exceptions.errors import (
    FileAccessRightError,
    FileMetaDataNotFoundError,
    LinkAlreadyExistsError,
    ProjectAccessRightError,
    ProjectNotFoundError,
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
