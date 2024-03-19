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
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingUnitGet,
)
from models_library.resource_tracker import (
    PricingPlanCreate,
    PricingPlanUpdate,
    PricingUnitWithCostCreate,
    PricingUnitWithCostUpdate,
)
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole


@pytest.fixture
def mock_rpc_resource_usage_tracker_service_api(
    mocker: MockerFixture, faker: Faker
) -> dict[str, MagicMock]:
    return {
        ## Pricing plans
        "list_pricing_plans": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_api.pricing_plans.list_pricing_plans",
            autospec=True,
            return_value=[
                parse_obj_as(
                    PricingPlanGet, PricingPlanGet.Config.schema_extra["examples"][0]
                )
            ],
        ),
        "get_pricing_plan": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_api.pricing_plans.get_pricing_plan",
            autospec=True,
            return_value=parse_obj_as(
                PricingPlanGet, PricingPlanGet.Config.schema_extra["examples"][0]
            ),
        ),
        "create_pricing_plan": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_api.pricing_plans.create_pricing_plan",
            autospec=True,
            return_value=parse_obj_as(
                PricingPlanGet, PricingPlanGet.Config.schema_extra["examples"][0]
            ),
        ),
        "update_pricing_plan": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_api.pricing_plans.update_pricing_plan",
            autospec=True,
            return_value=parse_obj_as(
                PricingPlanGet, PricingPlanGet.Config.schema_extra["examples"][0]
            ),
        ),
        ## Pricing units
        "get_pricing_unit": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_api.pricing_units.get_pricing_unit",
            autospec=True,
            return_value=parse_obj_as(
                PricingUnitGet, PricingUnitGet.Config.schema_extra["examples"][0]
            ),
        ),
        "create_pricing_unit": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_api.pricing_units.create_pricing_unit",
            autospec=True,
            return_value=parse_obj_as(
                PricingUnitGet, PricingUnitGet.Config.schema_extra["examples"][0]
            ),
        ),
        "update_pricing_unit": mocker.patch(
            "simcore_service_webserver.resource_usage._pricing_plans_admin_api.pricing_units.update_pricing_unit",
            autospec=True,
            return_value=parse_obj_as(
                PricingUnitGet, PricingUnitGet.Config.schema_extra["examples"][0]
            ),
        ),
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
    user_role: UserRole,
    expected: HTTPStatus,
):
    ## Pricing plans

    url = client.app.router["list_pricing_plans"].url_for()
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)

    url = client.app.router["get_pricing_plan"].url_for(pricing_plan_id="1")
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)

    url = client.app.router["create_pricing_plan"].url_for()
    resp = await client.post(
        f"{url}", json=PricingPlanCreate.Config.schema_extra["examples"][0]
    )
    await assert_status(resp, expected)

    url = client.app.router["update_pricing_plan"].url_for(pricing_plan_id="1")
    resp = await client.put(
        f"{url}", json=PricingPlanUpdate.Config.schema_extra["examples"][0]
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
        f"{url}", json=PricingUnitWithCostCreate.Config.schema_extra["examples"][0]
    )
    await assert_status(resp, expected)

    url = client.app.router["update_pricing_unit"].url_for(
        pricing_plan_id="1", pricing_unit_id="1"
    )
    resp = await client.put(
        f"{url}", json=PricingUnitWithCostUpdate.Config.schema_extra["examples"][0]
    )
    await assert_status(resp, expected)
