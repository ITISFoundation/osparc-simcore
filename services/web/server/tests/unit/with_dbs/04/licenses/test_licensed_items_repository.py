# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import copy

import pytest
from aiohttp.test_utils import TestClient
from models_library.licenses import (
    VIP_DETAILS_EXAMPLE,
    LicensedItemPatchDB,
    LicensedResourceType,
)
from models_library.rest_ordering import OrderBy
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_postgres_database.models.licensed_item_to_resource import (
    licensed_item_to_resource,
)
from simcore_postgres_database.utils_repos import transaction_context
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.licenses import (
    _licensed_items_repository,
    _licensed_resources_repository,
)
from simcore_service_webserver.licenses.errors import (
    LicensedItemNotFoundError,
    LicensedKeyVersionNotFoundError,
)
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


async def test_licensed_items_db_domain_crud(
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
        display_name="Renting A Display Name",
        key="Duke",
        version="1.0.0",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )
    licensed_item_id = got.licensed_item_id

    total_count, items = await _licensed_items_repository.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="display_name"),
    )
    assert total_count == 1
    assert items[0].licensed_item_id == licensed_item_id

    got = await _licensed_items_repository.get(
        client.app,
        licensed_item_id=licensed_item_id,
        product_name=osparc_product_name,
    )
    assert got.display_name == "Renting A Display Name"

    await _licensed_items_repository.update(
        client.app,
        licensed_item_id=licensed_item_id,
        product_name=osparc_product_name,
        updates=LicensedItemPatchDB(display_name="Renting B Display Name"),
    )

    got = await _licensed_items_repository.get(
        client.app,
        licensed_item_id=licensed_item_id,
        product_name=osparc_product_name,
    )
    assert got.display_name == "Renting B Display Name"

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


async def test_licensed_items_domain_listing(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    pricing_plan_id: int,
):
    assert client.app
    total_count, items = await _licensed_items_repository.list_licensed_items(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
    )
    assert total_count == 0
    assert not items

    got_duke1 = await _licensed_items_repository.create(
        client.app,
        product_name=osparc_product_name,
        display_name="Renting Duke 1.0.0 Display Name",
        key="Duke",
        version="1.0.0",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )

    got_duke2 = await _licensed_items_repository.create(
        client.app,
        product_name=osparc_product_name,
        display_name="Renting Duke 2.0.0 Display Name",
        key="Duke",
        version="2.0.0",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )

    # Create Licensed Resource with licensed key and version (Duke V1)
    example_duke1 = copy.deepcopy(VIP_DETAILS_EXAMPLE)
    example_duke1["license_key"] = "ABC"
    example_duke1["license_version"] = "1.0.0"
    example_duke1["id"] = 1

    got_licensed_resource_duke1 = (
        await _licensed_resources_repository.create_if_not_exists(
            client.app,
            display_name="Duke 1",
            licensed_resource_name="Duke 1",
            licensed_resource_type=LicensedResourceType.VIP_MODEL,
            licensed_resource_data=example_duke1,
        )
    )

    example_duke1_different_id = copy.deepcopy(VIP_DETAILS_EXAMPLE)
    example_duke1_different_id["license_key"] = "ABC"
    example_duke1_different_id["license_version"] = "1.0.0"
    example_duke1_different_id["id"] = 2

    # Create Licensed Resource with the same licensed key and version (Duke V1) but different external ID
    got_licensed_resource_duke1_different_id = (
        await _licensed_resources_repository.create_if_not_exists(
            client.app,
            display_name="Duke 1 (different external ID)",
            licensed_resource_name="Duke 1 different external ID",
            licensed_resource_type=LicensedResourceType.VIP_MODEL,
            licensed_resource_data=example_duke1_different_id,
        )
    )

    example_duke2 = copy.deepcopy(VIP_DETAILS_EXAMPLE)
    example_duke2["license_key"] = "ABC"
    example_duke2["license_version"] = "2.0.0"
    example_duke2["id"] = 3

    # Create Licensed Resource with the same licensed key but different version (Duke V2)
    got_licensed_resource_duke2 = (
        await _licensed_resources_repository.create_if_not_exists(
            client.app,
            display_name="Duke 2",
            licensed_resource_name="Duke 2",
            licensed_resource_type=LicensedResourceType.VIP_MODEL,
            licensed_resource_data=example_duke2,
        )
    )

    # Connect them via licensed_item_to_resorce DB table
    async with transaction_context(get_asyncpg_engine(client.app)) as conn:
        await conn.execute(
            licensed_item_to_resource.insert(),
            [
                {
                    "licensed_item_id": got_duke1.licensed_item_id,
                    "licensed_resource_id": got_licensed_resource_duke1.licensed_resource_id,
                    "product_name": osparc_product_name,
                },
                {
                    "licensed_item_id": got_duke1.licensed_item_id,
                    "licensed_resource_id": got_licensed_resource_duke1_different_id.licensed_resource_id,
                    "product_name": osparc_product_name,
                },
                {
                    "licensed_item_id": got_duke2.licensed_item_id,
                    "licensed_resource_id": got_licensed_resource_duke2.licensed_resource_id,
                    "product_name": osparc_product_name,
                },
            ],
        )

    total_count, items = await _licensed_items_repository.list_licensed_items(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="display_name"),
    )
    assert total_count == 2
    assert items[0].licensed_item_id == got_duke1.licensed_item_id
    assert len(items[0].licensed_resources) == 2
    assert items[1].licensed_item_id == got_duke2.licensed_item_id
    assert len(items[1].licensed_resources) == 1

    got = await _licensed_items_repository.get_licensed_item_by_key_version(
        client.app, key="Duke", version="1.0.0", product_name=osparc_product_name
    )
    assert got.display_name == "Renting Duke 1.0.0 Display Name"

    got = await _licensed_items_repository.get_licensed_item_by_key_version(
        client.app, key="Duke", version="2.0.0", product_name=osparc_product_name
    )
    assert got.display_name == "Renting Duke 2.0.0 Display Name"

    with pytest.raises(LicensedKeyVersionNotFoundError):
        await _licensed_items_repository.get_licensed_item_by_key_version(
            client.app,
            key="Non-Existing",
            version="2.0.0",
            product_name=osparc_product_name,
        )
