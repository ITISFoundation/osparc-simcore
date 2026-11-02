# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import datetime
from collections.abc import Awaitable, Callable
from typing import Final

import httpx
import pytest
import sqlalchemy as sa
from fastapi import FastAPI, status
from models_library.api_schemas_storage.storage_schemas import FileUploadSchema
from models_library.products import ProductName
from models_library.projects_nodes_io import LocationID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize
from pytest_mock import MockerFixture
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from simcore_postgres_database.storage_models import file_meta_data as file_meta_data_table
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_plugins = [
    "pytest_simcore.xdist_docker_daemon",
]

# long enough that no clock skew between replicas can make it look unexpired
_EXPIRED_LEASE: Final[datetime.timedelta] = datetime.timedelta(hours=1)


@pytest.fixture
def disable_dsm_cleaner(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_storage.dsm_cleaner.clean_expired_uploads",
        autospec=True,
    )


@pytest.fixture
def disable_dsm_export_cleaner(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_storage.dsm_cleaner.clean_expired_exports",
        autospec=True,
    )


@pytest.fixture
def disable_all_dsm_cleaner_tasks(disable_dsm_cleaner: None, disable_dsm_export_cleaner: None) -> None:
    pass


@pytest.fixture
def start_upload_without_completing(
    client: httpx.AsyncClient,
    initialized_app: FastAPI,
) -> Callable[..., Awaitable[None]]:
    """Hand out upload links and stop there.

    Storage deletes the object and sets upload_expires_at when it creates those links, so this
    leaves a seeded file in the state readers find it in while an upload is under way.
    """

    async def _start(
        *,
        location_id: LocationID,
        file_id: SimcoreS3FileID,
        user_id: UserID,
        product_name: ProductName,
        file_size: ByteSize,
    ) -> None:
        url = url_from_operation_id(
            client,
            initialized_app,
            "upload_file",
            location_id=f"{location_id}",
            file_id=f"{file_id}",
        ).with_query(user_id=user_id, product_name=product_name, file_size=f"{int(file_size)}")
        response = await client.put(f"{url}")
        assert_status(response, status.HTTP_200_OK, FileUploadSchema)

    return _start


@pytest.fixture
def expire_upload_lease(sqlalchemy_async_engine: AsyncEngine) -> Callable[[SimcoreS3FileID], Awaitable[None]]:
    """Push upload_expires_at into the past, as in an upload whose links lapsed.

    The lease stays armed: only a resynchronization or the cleaner clears it, so the entry is
    still unsynchronized and its object still missing.
    """

    async def _expire(file_id: SimcoreS3FileID) -> None:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(
                sa.update(file_meta_data_table)
                .where(file_meta_data_table.c.file_id == file_id)
                .values(upload_expires_at=datetime.datetime.now(datetime.UTC) - _EXPIRED_LEASE)
            )

    return _expire
