# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.license_goods import LicenseGoodGet
from models_library.license_goods import LicenseResourceType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.licenses import _license_goods_db
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_license_goods_db_crud(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: str,
    expected: HTTPStatus,
    pricing_plan_id: int,
):
    assert client.app

    # list
    url = client.app.router["list_license_goods"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data == []

    license_good_db = await _license_goods_db.create(
        client.app,
        product_name=osparc_product_name,
        name="Model A",
        license_resource_type=LicenseResourceType.VIP_MODEL,
        pricing_plan_id=pricing_plan_id,
    )
    _license_good_id = license_good_db.license_good_id

    # list
    url = client.app.router["list_license_goods"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert LicenseGoodGet(**data[0])

    # get
    url = client.app.router["get_license_good"].url_for(
        license_good_id=_license_good_id
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert LicenseGoodGet(**data)

    # purchase
    url = client.app.router["purchase_license_good"].url_for(
        license_good_id=_license_good_id
    )
    resp = await client.post(f"{url}", json={"wallet_id": 1, "num_of_seeds": 5})
    # NOTE: Not yet implemented
