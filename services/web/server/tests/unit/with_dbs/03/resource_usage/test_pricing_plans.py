# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import re
from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingUnitGet,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.resource_usage.settings import get_plugin_settings


@pytest.fixture
def mock_rut_api_responses(
    client: TestClient, aioresponses_mocker: AioResponsesMock
) -> AioResponsesMock:
    assert client.app
    settings: ResourceUsageTrackerSettings = get_plugin_settings(client.app)

    pricing_unit_get = PricingUnitGet.model_validate(
        PricingUnitGet.model_config["json_schema_extra"]["examples"][0]
    )

    service_pricing_plan_get = PricingPlanGet.model_validate(
        PricingPlanGet.model_config["json_schema_extra"]["examples"][0],
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


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_get_pricing_plan_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_rut_api_responses: AioResponsesMock,
    user_role: UserRole,
    expected: HTTPStatus,
):
    url = client.app.router["get_pricing_plan_unit"].url_for(
        pricing_plan_id="1", pricing_unit_id="1"
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, expected)


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_get_pricing_plan(
    client: TestClient,
    logged_user: UserInfoDict,
    mock_rut_api_responses: AioResponsesMock,
):
    # Get specific pricing plan unit
    url = client.app.router["get_pricing_plan_unit"].url_for(
        pricing_plan_id="1", pricing_unit_id="1"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert mock_rut_api_responses
    assert len(data.keys()) == 5
    assert data["unitName"] == "SMALL"

    # Get default pricing plan for service
    url = client.app.router["get_service_pricing_plan"].url_for(
        service_key="simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper",
        service_version="1.0.16",
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["pricingPlanKey"] == "pricing-plan-sleeper"
    assert len(data["pricingUnits"]) == 1
