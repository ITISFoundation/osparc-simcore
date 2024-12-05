# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.licensed_items import (
    LicensedItemDB,
    LicensedItemUpdateDB,
    LicensedResourceType,
)
from models_library.rest_ordering import OrderBy
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.catalog.licenses import _licensed_items_db
from simcore_service_webserver.catalog.licenses.errors import LicensedItemNotFoundError
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_licensed_items_db_crud(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    expected: HTTPStatus,
    pricing_plan_id: int,
):
    assert client.app

    output: tuple[int, list[LicensedItemDB]] = await _licensed_items_db.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
    )
    assert output[0] == 0

    licensed_item_db = await _licensed_items_db.create(
        client.app,
        product_name=osparc_product_name,
        name="Model A",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )
    _licensed_item_id = licensed_item_db.licensed_item_id

    output: tuple[int, list[LicensedItemDB]] = await _licensed_items_db.list_(
        client.app,
        product_name=osparc_product_name,
        offset=0,
        limit=10,
        order_by=OrderBy(field="modified"),
    )
    assert output[0] == 1

    licensed_item_db = await _licensed_items_db.get(
        client.app,
        licensed_item_id=_licensed_item_id,
        product_name=osparc_product_name,
    )
    assert licensed_item_db.name == "Model A"

    await _licensed_items_db.update(
        client.app,
        licensed_item_id=_licensed_item_id,
        product_name=osparc_product_name,
        updates=LicensedItemUpdateDB(name="Model B"),
    )

    licensed_item_db = await _licensed_items_db.get(
        client.app,
        licensed_item_id=_licensed_item_id,
        product_name=osparc_product_name,
    )
    assert licensed_item_db.name == "Model B"

    licensed_item_db = await _licensed_items_db.delete(
        client.app,
        licensed_item_id=_licensed_item_id,
        product_name=osparc_product_name,
    )

    with pytest.raises(LicensedItemNotFoundError):
        await _licensed_items_db.get(
            client.app,
            licensed_item_id=_licensed_item_id,
            product_name=osparc_product_name,
        )
