# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Awaitable, Callable

import httpx
import pytest
from fastapi import FastAPI, status
from models_library.api_schemas_storage.storage_schemas import FileUploadSchema
from models_library.products import ProductName
from models_library.projects_nodes_io import LocationID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize
from pytest_mock import MockerFixture
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status

pytest_plugins = [
    "pytest_simcore.xdist_docker_daemon",
]


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
