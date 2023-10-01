# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from datetime import datetime, timezone
from decimal import Decimal

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
    ServicePricingPlanGet,
)
from models_library.resource_tracker import PricingPlanClassification
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_service_webserver.db.models import UserRole

_PRICING_UNIT_GET: PricingUnitGet = PricingUnitGet(
    pricing_unit_id=1,
    unit_name="SMALL",
    current_cost_per_unit=Decimal(5),
    current_cost_per_unit_id=1,
    default=True,
    specific_info={},
)

_PRICING_PLAN_GET: ServicePricingPlanGet = ServicePricingPlanGet(
    pricing_plan_id=1,
    display_name="Sleeper pricing plan",
    description="",
    classification=PricingPlanClassification.TIER,
    created_at=datetime.now(tz=timezone.utc),
    pricing_plan_key="sleeper-pricing-plan",
    pricing_units=[_PRICING_UNIT_GET],
)


@pytest.fixture
def mock_resource_tracker_client(mocker: MockerFixture) -> tuple:
    mock_get_pricing_plan_unit = mocker.patch(
        "simcore_service_webserver.resource_usage._service_runs_api.resource_tracker_client.get_pricing_plan_unit",
        spec=True,
        return_value=_PRICING_UNIT_GET,
    )
    mock_get_default_service_pricing_plan = mocker.patch(
        "simcore_service_webserver.resource_usage._service_runs_api.resource_tracker_client.get_default_service_pricing_plan",
        spec=True,
        return_value=_PRICING_PLAN_GET,
    )
    return mock_get_pricing_plan_unit, mock_get_default_service_pricing_plan


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_list_service_usage(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_resource_tracker_client,
):
    # Get specific pricing plan unit
    url = client.app.router["get_pricing_plan_unit"].url_for(
        pricing_plan_id="1", pricing_unit_id="1"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert mock_resource_tracker_client[0].called
    assert len(data.keys()) == 4
    assert data["unitName"] == "SMALL"

    # Get default pricing plan for service
    url = client.app.router["get_service_pricing_plan"].url_for(
        service_key="simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper",
        service_version="1.0.16",
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert data["pricingPlanKey"] == "sleeper-pricing-plan"
    assert len(data["pricingUnits"]) == 1
