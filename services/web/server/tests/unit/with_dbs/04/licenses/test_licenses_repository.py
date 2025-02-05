# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import pytest
from aiohttp.test_utils import TestClient
from models_library.licensed_items import VIP_DETAILS_EXAMPLE, LicensedResourceType
from models_library.licenses import License, LicenseDB, LicenseUpdateDB
from models_library.rest_ordering import OrderBy
from pytest_simcore.helpers.webserver_login import UserInfoDict
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.licenses import (
    _licensed_items_repository,
    _licenses_repository,
)
from simcore_service_webserver.licenses.errors import LicenseNotFoundError
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


async def test_licenses_db_crud(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    pricing_plan_id: int,
):
    got = await _licensed_items_repository.create(
        client.app,
        product_name=osparc_product_name,
        display_name="Model A Display Name",
        licensed_resource_name="Model A",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        licensed_resource_data=VIP_DETAILS_EXAMPLE,
        pricing_plan_id=pricing_plan_id,
    )
    licensed_item_id = got.licensed_item_id

    ### NEW:

    got = await _licenses_repository.create(
        client.app,
        product_name=osparc_product_name,
        display_name="Model A",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )
    license_id = got.license_id

    total_count, items = await _licenses_repository.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="display_name"),
    )
    assert total_count == 1
    assert items[0].license_id == license_id

    got = await _licenses_repository.get(
        client.app,
        license_id=license_id,
        product_name=osparc_product_name,
    )
    assert isinstance(got, LicenseDB)
    assert got.display_name == "Model A"

    got = await _licenses_repository.update(
        client.app,
        license_id=license_id,
        product_name=osparc_product_name,
        updates=LicenseUpdateDB(display_name="Model B"),
    )
    assert isinstance(got, LicenseDB)

    got = await _licenses_repository.get(
        client.app,
        license_id=license_id,
        product_name=osparc_product_name,
    )
    assert isinstance(got, LicenseDB)
    assert got.display_name == "Model B"

    # CONNECT RESOURCE TO LICENSE

    await _licenses_repository.add_licensed_resource_to_license(
        client.app,
        license_id=license_id,
        licensed_item_id=licensed_item_id,
    )

    got = await _licenses_repository.list_licenses(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="display_name"),
    )
    assert got[0] == 1
    assert isinstance(got[1], list)
    assert isinstance(got[1][0], License)

    got = await _licenses_repository.get_license(
        client.app,
        product_name=osparc_product_name,
        license_id=license_id,
    )
    assert isinstance(got, License)

    # DELETE

    await _licenses_repository.delete_licensed_resource_from_license(
        client.app,
        license_id=license_id,
        licensed_item_id=licensed_item_id,
    )

    got = await _licenses_repository.delete(
        client.app,
        license_id=license_id,
        product_name=osparc_product_name,
    )

    with pytest.raises(LicenseNotFoundError):
        await _licenses_repository.get(
            client.app,
            license_id=license_id,
            product_name=osparc_product_name,
        )
