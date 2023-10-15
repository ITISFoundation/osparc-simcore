# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import re

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
    ServicePricingPlanGet,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import parse_obj_as
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.resource_usage.settings import get_plugin_settings


@pytest.fixture
def mock_rut_api_responses(
    client: TestClient, aioresponses_mocker: AioResponsesMock
) -> AioResponsesMock:
    assert client.app
    settings: ResourceUsageTrackerSettings = get_plugin_settings(client.app)

    pricing_unit_get = parse_obj_as(
        PricingUnitGet, PricingUnitGet.Config.schema_extra["examples"][0]
    )

    service_pricing_plan_get = parse_obj_as(
        ServicePricingPlanGet,
        ServicePricingPlanGet.Config.schema_extra["examples"][0],
    )

    aioresponses_mocker.get(
        re.compile(f"^{settings.api_base_url}/pricing-plans/+.+$"),
        payload=jsonable_encoder(pricing_unit_get),
    )
    aioresponses_mocker.get(
        re.compile(f"^{settings.api_base_url}/services/+.+$"),
        payload=jsonable_encoder(service_pricing_plan_get),
    )

    return aioresponses_mocker


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_list_service_usage(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_rut_api_responses,
):
    # Get specific pricing plan unit
    url = client.app.router["get_pricing_plan_unit"].url_for(
        pricing_plan_id="1", pricing_unit_id="1"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert mock_rut_api_responses
    assert len(data.keys()) == 5
    assert data["unitName"] == "SMALL"

    # Get default pricing plan for service
    url = client.app.router["get_service_pricing_plan"].url_for(
        service_key="simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper",
        service_version="1.0.16",
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert data["pricingPlanKey"] == "pricing-plan-sleeper"
    assert len(data["pricingUnits"]) == 1
