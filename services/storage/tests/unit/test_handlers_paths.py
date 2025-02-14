# pylint:disable=no-name-in-module
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-positional-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable


from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi_pagination import LimitOffsetPage
from models_library.api_schemas_storage import FileMetaDataGet, PathMetaDataGet
from models_library.projects_nodes_io import LocationID, NodeID, SimcoreS3FileID
from models_library.users import UserID
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from servicelib.aiohttp import status

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_list_paths_root_folder_of_empty_returns_nothing(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
):
    url = url_from_operation_id(
        client, initialized_app, "list_paths", location_id=f"{location_id}"
    ).with_query(
        user_id=user_id
    )  # file_filter=None
    response = await client.get(f"{url}")

    page_of_files, _ = assert_status(
        response,
        status.HTTP_200_OK,
        LimitOffsetPage[FileMetaDataGet],
        expect_envelope=False,
    )
    assert page_of_files
    assert page_of_files.items == []
    assert page_of_files.total == 0


async def test_list_paths_root_folder(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    location_id: LocationID,
    user_id: UserID,
    with_random_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, dict[str, Path | str]]],
    ],
):
    project_in_db, list_of_files = with_random_project_with_files

    # listing root shall return only the project folder (i.e. the project ID)
    url = url_from_operation_id(
        client, initialized_app, "list_paths", location_id=f"{location_id}"
    ).with_query(
        user_id=user_id
    )  # file_filter=None
    response = await client.get(f"{url}")

    page_of_files, _ = assert_status(
        response,
        status.HTTP_200_OK,
        LimitOffsetPage[PathMetaDataGet],
        expect_envelope=False,
    )
    assert page_of_files
    assert len(page_of_files.items) == 1
    assert page_of_files.items == []
    assert page_of_files.total == 0
