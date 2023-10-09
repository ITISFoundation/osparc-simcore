# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


import re

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import parse_obj_as
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, UserInfoDict
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.resource_usage.settings import get_plugin_settings

API_PREFIX = "/" + api_version_prefix


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_project_node_pricing_unit_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    user_role: UserRole,
    expected: type[web.HTTPException],
):
    node_id = next(iter(user_project["workbench"]))
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(base_url)
    assert resp.status == 401 if user_role == UserRole.ANONYMOUS else 200


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, web.HTTPOk)])
async def test_project_node_pricing_unit_user_project_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: type[web.HTTPException],
):
    node_id = next(iter(user_project["workbench"]))
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, expected)
    assert data == None

    # Now we will log as a different user who doesnt have access to the project
    async with LoggedUser(client) as new_logged_user:
        base_url = client.app.router["get_project_node_pricing_unit"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        resp = await client.get(base_url)
        _, errors = await assert_status(resp, web.HTTPNotFound)
        assert errors


_PRICING_PLAN_ID = 1
_PRICING_UNIT_ID_1 = 1
_PRICING_UNIT_ID_2 = 2


@pytest.fixture
def mock_rut_api_responses(
    client: TestClient, aioresponses_mocker: AioResponsesMock
) -> AioResponsesMock:
    assert client.app
    settings: ResourceUsageTrackerSettings = get_plugin_settings(client.app)

    pricing_unit_get_base = parse_obj_as(
        PricingUnitGet, PricingUnitGet.Config.schema_extra["examples"][0]
    )
    pricing_unit_get_1 = pricing_unit_get_base.copy()
    pricing_unit_get_1.pricing_unit_id = _PRICING_UNIT_ID_1
    pricing_unit_get_2 = pricing_unit_get_base.copy()
    pricing_unit_get_2.pricing_unit_id = _PRICING_UNIT_ID_2

    aioresponses_mocker.get(
        re.compile(f"^{settings.api_base_url}/pricing-plans/1/pricing-units/1+.+$"),
        payload=jsonable_encoder(pricing_unit_get_1),
        repeat=True,
    )
    aioresponses_mocker.get(
        re.compile(f"^{settings.api_base_url}/pricing-plans/1/pricing-units/2+.+$"),
        payload=jsonable_encoder(pricing_unit_get_2),
        repeat=True,
    )

    return aioresponses_mocker


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, web.HTTPOk)])
async def test_project_wallets_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: type[web.HTTPException],
    mock_rut_api_responses: AioResponsesMock,
):

    node_id = next(iter(user_project["workbench"]))

    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, expected)
    assert data == None

    # Now we will connect pricing unit to the project node
    base_url = client.app.router["connect_pricing_unit_to_project_node"].url_for(
        project_id=user_project["uuid"],
        node_id=node_id,
        pricing_plan_id=f"{_PRICING_PLAN_ID}",
        pricing_unit_id=f"{_PRICING_UNIT_ID_1}",
    )
    resp = await client.put(base_url)
    await assert_status(resp, web.HTTPNoContent)

    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, expected)
    assert data["pricingUnitId"] == _PRICING_UNIT_ID_1

    # Now we will connect different pricing unit
    base_url = client.app.router["connect_pricing_unit_to_project_node"].url_for(
        project_id=user_project["uuid"],
        node_id=node_id,
        pricing_plan_id=f"{_PRICING_PLAN_ID}",
        pricing_unit_id=f"{_PRICING_UNIT_ID_2}",
    )
    resp = await client.put(base_url)
    await assert_status(resp, web.HTTPNoContent)

    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(base_url)
    data, _ = await assert_status(resp, expected)
    assert data["pricingUnitId"] == _PRICING_UNIT_ID_2
