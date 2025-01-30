# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import arrow
import pytest
from aiohttp.test_utils import TestClient
from models_library.licensed_items import (
    VIP_DETAILS_EXAMPLE,
    LicensedItemUpdateDB,
    LicensedResourceType,
)
from models_library.rest_ordering import OrderBy
from pytest_simcore.helpers.webserver_login import UserInfoDict
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.licenses import _licensed_items_repository
from simcore_service_webserver.licenses.errors import LicensedItemNotFoundError
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


async def test_licensed_items_db_crud(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    pricing_plan_id: int,
):
    assert client.app
    total_count, items = await _licensed_items_repository.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
    )
    assert total_count == 0
    assert not items

    got = await _licensed_items_repository.create(
        client.app,
        product_name=osparc_product_name,
        licensed_resource_name="Model A",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        licensed_resource_data=VIP_DETAILS_EXAMPLE,
        pricing_plan_id=pricing_plan_id,
    )
    licensed_item_id = got.licensed_item_id

    total_count, items = await _licensed_items_repository.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
    )
    assert total_count == 1
    assert items[0].licensed_item_id == licensed_item_id

    got = await _licensed_items_repository.get(
        client.app,
        licensed_item_id=licensed_item_id,
        product_name=osparc_product_name,
    )
    assert got.licensed_resource_name == "Model A"

    await _licensed_items_repository.update(
        client.app,
        licensed_item_id=licensed_item_id,
        product_name=osparc_product_name,
        updates=LicensedItemUpdateDB(licensed_resource_name="Model B"),
    )

    got = await _licensed_items_repository.get(
        client.app,
        licensed_item_id=licensed_item_id,
        product_name=osparc_product_name,
    )
    assert got.licensed_resource_name == "Model B"

    got = await _licensed_items_repository.delete(
        client.app,
        licensed_item_id=licensed_item_id,
        product_name=osparc_product_name,
    )

    with pytest.raises(LicensedItemNotFoundError):
        await _licensed_items_repository.get(
            client.app,
            licensed_item_id=licensed_item_id,
            product_name=osparc_product_name,
        )


async def test_licensed_items_db_trash(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    pricing_plan_id: int,
):
    assert client.app

    # Create two licensed items
    licensed_item_ids = []
    for name in ["Model A", "Model B"]:
        licensed_item_db = await _licensed_items_repository.create(
            client.app,
            product_name=osparc_product_name,
            licensed_resource_name=name,
            licensed_resource_type=LicensedResourceType.VIP_MODEL,
            licensed_resource_data=VIP_DETAILS_EXAMPLE,
            pricing_plan_id=pricing_plan_id,
        )
        licensed_item_ids.append(licensed_item_db.licensed_item_id)

    # Trash one licensed item
    trashing_at = arrow.now().datetime
    trashed_item = await _licensed_items_repository.update(
        client.app,
        licensed_item_id=licensed_item_ids[0],
        product_name=osparc_product_name,
        updates=LicensedItemUpdateDB(trash=True),
    )

    assert trashed_item.licensed_item_id == licensed_item_ids[0]
    assert trashed_item.trashed
    assert trashing_at < trashed_item.trashed
    assert trashed_item.trashed < arrow.now().datetime

    # List with filter_trashed include
    total_count, items = await _licensed_items_repository.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
        trashed="include",
    )
    assert total_count == 2
    assert {i.licensed_item_id for i in items} == set(licensed_item_ids)

    # List with filter_trashed exclude
    total_count, items = await _licensed_items_repository.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
        trashed="exclude",
    )
    assert total_count == 1
    assert items[0].licensed_item_id == licensed_item_ids[1]
    assert items[0].trashed is None

    # List with filter_trashed all
    total_count, items = await _licensed_items_repository.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
        trashed="only",
    )
    assert total_count == 1
    assert items[0].licensed_item_id == trashed_item.licensed_item_id
    assert items[0].trashed

    # Get the trashed licensed item
    got = await _licensed_items_repository.get(
        client.app,
        licensed_item_id=trashed_item.licensed_item_id,
        product_name=osparc_product_name,
    )
    assert got == trashed_item
