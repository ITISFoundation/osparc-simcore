# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.resource_tracker import PricingPlanClassification
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole


@pytest.fixture
def mock_catalog_client(mocker: MockerFixture, faker: Faker) -> dict[str, MagicMock]:
    return {
        "get_service": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_service.catalog_service.get_service",
            autospec=True,
        )
    }


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
        (UserRole.PRODUCT_OWNER, status.HTTP_403_FORBIDDEN),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_get_admin_pricing_endpoints_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_rpc_resource_usage_tracker_service_api: dict,
    mock_catalog_client: dict,
    user_role: UserRole,
    expected: HTTPStatus,
):
    ## Pricing plans

    url = client.app.router["list_pricing_plans_for_admin_user"].url_for()
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)

    url = client.app.router["get_pricing_plan_for_admin_user"].url_for(
        pricing_plan_id="1"
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)

    url = client.app.router["create_pricing_plan"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "productName": "osparc",
            "displayName": "My pricing plan",
            "description": "This is general pricing plan",
            "classification": PricingPlanClassification.TIER,
            "pricingPlanKey": "my-unique-pricing-plan",
        },
    )
    await assert_status(resp, expected)

    url = client.app.router["update_pricing_plan"].url_for(pricing_plan_id="1")
    resp = await client.put(
        f"{url}",
        json={
            "pricingPlanId": 1,
            "displayName": "My pricing plan",
            "description": "This is general pricing plan",
            "isActive": True,
        },
    )
    await assert_status(resp, expected)

    ## Pricing Units

    url = client.app.router["get_pricing_unit"].url_for(
        pricing_plan_id="1", pricing_unit_id="1"
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)

    url = client.app.router["create_pricing_unit"].url_for(pricing_plan_id="1")
    resp = await client.post(
        f"{url}",
        json={
            "pricingPlanId": 1,
            "unitName": "My pricing plan",
            "unitExtraInfo": {"CPU": 4, "RAM": 32, "VRAM": 0},
            "default": True,
            "specificInfo": {"aws_ec2_instances": ["t3.medium"]},
            "costPerUnit": 10,
            "comment": "This pricing unit was create by Foo",
        },
    )
    await assert_status(resp, expected)

    url = client.app.router["update_pricing_unit"].url_for(
        pricing_plan_id="1", pricing_unit_id="1"
    )
    resp = await client.put(
        f"{url}",
        json={
            "pricingPlanId": 1,
            "unitName": "My pricing plan",
            "unitExtraInfo": {"CPU": 4, "RAM": 10, "VRAM": 0, "SSD": "800GB"},
            "default": True,
            "specificInfo": {"aws_ec2_instances": ["t3.medium"]},
            "costPerUnit": 10,
            "comment": "This pricing unit was create by Foo",
        },
    )
    await assert_status(resp, expected)

    ## Pricing Plan to Service

    url = client.app.router["list_connected_services_to_pricing_plan"].url_for(
        pricing_plan_id="1"
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)

    url = client.app.router["connect_service_to_pricing_plan"].url_for(
        pricing_plan_id="1"
    )
    resp = await client.post(
        f"{url}",
        json={
            "serviceKey": "simcore/services/comp/sleeper",
            "serviceVersion": "2.0.2",
        },
    )
    await assert_status(resp, expected)
