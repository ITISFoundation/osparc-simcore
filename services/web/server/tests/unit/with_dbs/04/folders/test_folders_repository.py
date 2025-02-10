# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import arrow
import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.products import ProductName
from simcore_service_webserver.folders import _folders_repository


@pytest.fixture
def user_role():
    return UserRole.USER


@pytest.fixture
def product_name():
    return "osparc"


async def test_batch_get_trashed_by_primary_gid(
    client: TestClient,
    logged_user: dict[str, Any],
    product_name: ProductName,
):
    assert client.app

    # Create two folders
    folder_1 = await _folders_repository.create(
        client.app,
        created_by_gid=logged_user["primary_gid"],
        folder_name="Folder 1",
        product_name=product_name,
        parent_folder_id=None,
        user_id=logged_user["id"],
        workspace_id=None,
    )
    folder_2 = await _folders_repository.create(
        client.app,
        created_by_gid=logged_user["primary_gid"],
        folder_name="Folder 2",
        product_name=product_name,
        parent_folder_id=None,
        user_id=logged_user["id"],
        workspace_id=None,
    )

    # Update the trashed flag for folder_1
    await _folders_repository.update(
        client.app,
        folders_id_or_ids=folder_1.folder_id,
        product_name=product_name,
        trashed=arrow.now().datetime,
        trashed_explicitly=True,
        trashed_by=logged_user["id"],
    )

    # Test batch_get_trashed_by_primary_gid
    trashed_by_primary_gid = await _folders_repository.batch_get_trashed_by_primary_gid(
        client.app,
        folders_ids=[folder_1.folder_id, folder_2.folder_id],
    )
    assert trashed_by_primary_gid == [logged_user["primary_gid"], None]

    # flipped
    trashed_by_primary_gid = await _folders_repository.batch_get_trashed_by_primary_gid(
        client.app,
        folders_ids=[folder_2.folder_id, folder_1.folder_id],
    )
    assert trashed_by_primary_gid == [None, logged_user["primary_gid"]]

    # repeated
    trashed_by_primary_gid = await _folders_repository.batch_get_trashed_by_primary_gid(
        client.app,
        folders_ids=[folder_1.folder_id] * 3,
    )
    assert trashed_by_primary_gid == [logged_user["primary_gid"]] * 3
