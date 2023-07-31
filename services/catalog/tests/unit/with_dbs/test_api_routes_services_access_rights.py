# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# type: ignore

import random
from typing import Any, Callable

from models_library.api_schemas_catalog.service_access_rights import (
    ServiceAccessRightsGet,
)
from pydantic import parse_obj_as
from respx.router import MockRouter
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_get_service_access_rights(
    mock_catalog_background_task: None,
    director_mockup: MockRouter,
    client: TestClient,
    user_db: Callable,
    products_names: list[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
):
    target_product = products_names[0]  # osparc
    user_id = user_db["id"]
    user_primary_gid = user_db["primary_gid"]

    # create some fake services
    NUM_SERVICES = 3
    fake_services = [
        service_catalog_faker(
            "simcore/services/dynamic/jupyterlab",
            f"1.0.{s}",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
        for s in range(NUM_SERVICES)
    ]
    # injects fake data in db
    await services_db_tables_injector(fake_services)

    service_to_check = fake_services[random.choice(range(NUM_SERVICES))][
        0
    ]  # --> service_meta_data table format
    url = URL(
        f"/v0/services/{service_to_check['key']}/{service_to_check['version']}/accessRights"
    ).with_query({"user_id": user_id})
    response = client.get(
        f"{url}",
        headers={"x-simcore-products-name": target_product},
    )
    assert response.status_code == 200
    data = parse_obj_as(ServiceAccessRightsGet, response.json())
    assert data.service_key == service_to_check["key"]
    assert data.service_version == service_to_check["version"]
    assert data.gids_with_access_rights == {
        user_primary_gid: {"execute_access": True, "write_access": True}
    }


async def test_get_service_access_rights_with_more_gids(
    mock_catalog_background_task: None,
    director_mockup: MockRouter,
    client: TestClient,
    user_db: dict[str, Any],
    products_names: list[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
    user_groups_ids: list[int],
):
    target_product = products_names[1]  # s4l
    user_id = user_db["id"]
    user_primary_gid = user_db["primary_gid"]
    everyone_gid, user_gid, team_gid = user_groups_ids

    fake_service = service_catalog_faker(
        "simcore/services/dynamic/jupyterlab",
        "1.0.1",
        team_access="x",
        everyone_access="x",
        product=target_product,
    )
    # injects fake data in db
    await services_db_tables_injector([fake_service])

    service_to_check = fake_service[0]  # --> service_meta_data table format
    url = URL(
        f"/v0/services/{service_to_check['key']}/{service_to_check['version']}/accessRights"
    ).with_query({"user_id": user_id})
    response = client.get(
        f"{url}",
        headers={"x-simcore-products-name": target_product},
    )
    assert response.status_code == 200
    data = parse_obj_as(ServiceAccessRightsGet, response.json())
    assert data.service_key == service_to_check["key"]
    assert data.service_version == service_to_check["version"]
    assert data.gids_with_access_rights == {
        1: {"execute_access": True, "write_access": False},
        user_primary_gid: {"execute_access": True, "write_access": True},
        team_gid: {"execute_access": True, "write_access": False},
    }
