# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.licensed_items import LicensedItemGet
from models_library.licensed_items import LicensedResourceType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.catalog.licenses import _licensed_items_db
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

    # list
    url = client.app.router["list_licensed_items"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

    licensed_item_db = await _licensed_items_db.create(
        client.app,
        product_name=osparc_product_name,
        name="Model A",
        licensed_resource_type=LicensedResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )
    _licensed_item_id = licensed_item_db.licensed_item_id

    # list
    url = client.app.router["list_licensed_items"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert LicensedItemGet(**data[0])

    # get
    url = client.app.router["get_licensed_item"].url_for(
        licensed_item_id=f"{_licensed_item_id}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert LicensedItemGet(**data)

    # purchase
    url = client.app.router["purchase_licensed_item"].url_for(
        licensed_item_id=f"{_licensed_item_id}"
    )
    resp = await client.post(f"{url}", json={"wallet_id": 1, "num_of_seeds": 5})
    # NOTE: Not yet implemented
