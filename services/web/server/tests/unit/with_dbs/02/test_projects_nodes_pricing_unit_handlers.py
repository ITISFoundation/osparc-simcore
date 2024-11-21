# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


import re
from http import HTTPStatus
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingUnitGet,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_mock.plugin import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from servicelib.aiohttp import status
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.resource_usage.settings import get_plugin_settings

API_PREFIX = "/" + api_version_prefix


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_project_node_pricing_unit_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    user_role: UserRole,
    expected: HTTPStatus,
):
    node_id = next(iter(user_project["workbench"]))
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    assert (
        resp.status == status.HTTP_401_UNAUTHORIZED
        if user_role == UserRole.ANONYMOUS
        else status.HTTP_200_OK
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_project_node_pricing_unit_user_project_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    node_id = next(iter(user_project["workbench"]))
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    data, _ = await assert_status(resp, expected)
    assert data == None

    # Now we will log as a different user who doesnt have access to the project
    async with LoggedUser(client) as new_logged_user:
        base_url = client.app.router["get_project_node_pricing_unit"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        resp = await client.get(f"{base_url}")
        _, errors = await assert_status(resp, status.HTTP_403_FORBIDDEN)
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

    pricing_unit_get_base = PricingUnitGet.model_validate(
        PricingUnitGet.model_config["json_schema_extra"]["examples"][0]
    )
    pricing_unit_get_1 = pricing_unit_get_base.model_copy()
    pricing_unit_get_1.pricing_unit_id = _PRICING_UNIT_ID_1
    pricing_unit_get_2 = pricing_unit_get_base.model_copy()
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


@pytest.fixture
def mocked_clusters_keeper_service_get_instance_type_details(
    mocker: MockerFixture, faker: Faker
) -> mock.Mock:
    def _fake_instance_type_details(
        rabbitmq_client, instance_type_names: set[str]
    ) -> list[EC2InstanceTypeGet]:
        assert len(instance_type_names) > 0
        return [
            EC2InstanceTypeGet(
                name=next(iter(instance_type_names)),
                cpus=faker.pyfloat(min_value=0.1),
                ram=faker.pyint(min_value=1024),
            )
        ]

    return mocker.patch(
        "simcore_service_webserver.projects.projects_api.get_instance_type_details",
        side_effect=_fake_instance_type_details,
    )


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_project_wallets_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_rut_api_responses: AioResponsesMock,
    mocked_clusters_keeper_service_get_instance_type_details: mock.Mock,
):
    node_id = next(iter(user_project["workbench"]))
    assert client.app
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    data, _ = await assert_status(resp, expected)
    assert data is None

    # Now we will connect pricing unit to the project node
    base_url = client.app.router["connect_pricing_unit_to_project_node"].url_for(
        project_id=user_project["uuid"],
        node_id=node_id,
        pricing_plan_id=f"{_PRICING_PLAN_ID}",
        pricing_unit_id=f"{_PRICING_UNIT_ID_1}",
    )
    resp = await client.put(f"{base_url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)
    mocked_clusters_keeper_service_get_instance_type_details.assert_called_once()
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    data, _ = await assert_status(resp, expected)
    assert data["pricingUnitId"] == _PRICING_UNIT_ID_1

    # Now we will connect different pricing unit
    base_url = client.app.router["connect_pricing_unit_to_project_node"].url_for(
        project_id=user_project["uuid"],
        node_id=node_id,
        pricing_plan_id=f"{_PRICING_PLAN_ID}",
        pricing_unit_id=f"{_PRICING_UNIT_ID_2}",
    )
    resp = await client.put(f"{base_url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    data, _ = await assert_status(resp, expected)
    assert data["pricingUnitId"] == _PRICING_UNIT_ID_2
