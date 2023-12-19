# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from random import choice
from typing import Any, Final
from unittest import mock
from uuid import uuid4

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses as AioResponsesMock
from faker import Faker
from models_library.api_schemas_storage import FileMetaDataGet, PresignedLink
from models_library.generics import Envelope
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import NonNegativeFloat, NonNegativeInt, parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.helpers.utils_webserver_unit_with_db import (
    ExpectedResponse,
    MockedStorageSubsystem,
    standard_role_response,
)
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.projects import projects as projects_db_model
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects._nodes_handlers import _ProjectNodePreview
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_get_node_resources(
    client: TestClient,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
):
    assert client.app
    for node_id in user_project["workbench"]:
        url = client.app.router["get_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.get(f"{url}")
        data, error = await assert_status(response, expected)
        if data:
            assert not error
            node_resources = parse_obj_as(ServiceResourcesDict, data)
            assert node_resources
            assert DEFAULT_SINGLE_SERVICE_NAME in node_resources
            assert (
                node_resources
                == ServiceResourcesDictHelpers.Config.schema_extra["examples"][0]
            )
        else:
            assert not data
            assert error


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.TESTER, web.HTTPNotFound),
    ],
)
async def test_get_wrong_project_raises_not_found_error(
    client: TestClient,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
):
    assert client.app
    for node_id in user_project["workbench"]:
        url = client.app.router["get_node_resources"].url_for(
            project_id=f"{uuid4()}", node_id=node_id
        )
        response = await client.get(f"{url}")
        await assert_status(response, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.TESTER, web.HTTPNotFound),
    ],
)
async def test_get_wrong_node_raises_not_found_error(
    client: TestClient,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
):
    assert client.app
    url = client.app.router["get_node_resources"].url_for(
        project_id=user_project["uuid"], node_id=f"{uuid4()}"
    )
    response = await client.get(f"{url}")
    await assert_status(response, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPForbidden),
    ],
)
async def test_replace_node_resources_is_forbidden_by_default(
    client: TestClient,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
):
    assert client.app
    for node_id in user_project["workbench"]:
        url = client.app.router["replace_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.put(
            f"{url}",
            json=ServiceResourcesDictHelpers.create_jsonable(
                ServiceResourcesDictHelpers.Config.schema_extra["examples"][0]
            ),
        )
        data, error = await assert_status(response, expected)
        if data:
            assert not error
            node_resources = parse_obj_as(ServiceResourcesDict, data)
            assert node_resources
            assert DEFAULT_SINGLE_SERVICE_NAME in node_resources
            assert (
                node_resources
                == ServiceResourcesDictHelpers.Config.schema_extra["examples"][0]
            )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_replace_node_resources_is_ok_if_explicitly_authorized(
    client: TestClient,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
    with_permitted_override_services_specifications: None,
):
    assert client.app
    for node_id in user_project["workbench"]:
        url = client.app.router["replace_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.put(
            f"{url}",
            json=ServiceResourcesDictHelpers.create_jsonable(
                ServiceResourcesDictHelpers.Config.schema_extra["examples"][0]
            ),
        )
        data, error = await assert_status(response, expected)
        if data:
            assert not error
            node_resources = parse_obj_as(ServiceResourcesDict, data)
            assert node_resources
            assert DEFAULT_SINGLE_SERVICE_NAME in node_resources
            assert (
                node_resources
                == ServiceResourcesDictHelpers.Config.schema_extra["examples"][0]
            )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.TESTER, web.HTTPUnprocessableEntity),
    ],
)
async def test_replace_node_resources_raises_422_if_resource_does_not_validate(
    client: TestClient,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
):
    assert client.app
    for node_id in user_project["workbench"]:
        url = client.app.router["replace_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.put(
            f"{url}",
            json=ServiceResourcesDictHelpers.create_jsonable(
                # NOTE: we apply a different resource set
                ServiceResourcesDictHelpers.Config.schema_extra["examples"][1]
            ),
        )
        await assert_status(response, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.TESTER, web.HTTPNotFound),
    ],
)
async def test_replace_node_resources_raises_404_if_wrong_project_id_used(
    client: TestClient,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
    faker: Faker,
):
    assert client.app
    for node_id in user_project["workbench"]:
        url = client.app.router["replace_node_resources"].url_for(
            project_id=faker.uuid4(), node_id=node_id
        )
        response = await client.put(
            f"{url}",
            json={},
        )
        await assert_status(response, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.TESTER, web.HTTPNotFound),
    ],
)
async def test_replace_node_resources_raises_404_if_wrong_node_id_used(
    client: TestClient,
    user_project: dict[str, Any],
    expected: type[web.HTTPException],
    faker: Faker,
):
    assert client.app
    for node_id in user_project["workbench"]:
        assert node_id
        url = client.app.router["replace_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=faker.uuid4()
        )
        response = await client.put(
            f"{url}",
            json={},
        )
        await assert_status(response, expected)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_create_node_returns_422_if_body_is_missing(
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    faker: Faker,
    mocked_director_v2_api: dict[str, mock.MagicMock],
):
    assert client.app
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    for partial_body in [
        {},
        {"service_key": faker.pystr()},
        {
            "service_version": f"{faker.random_int()}.{faker.random_int()}.{faker.random_int()}"
        },
    ]:
        response = await client.post(url.path, json=partial_body)
        assert response.status == expected.unprocessable.status_code
    # this does not start anything in the backend
    mocked_director_v2_api["director_v2.api.run_dynamic_service"].assert_not_called()


@pytest.mark.parametrize(
    "node_class, expect_run_service_call",
    [("dynamic", True), ("comp", False), ("frontend", False)],
)
@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_create_node(
    node_class: str,
    expect_run_service_call: bool,
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    faker: Faker,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    postgres_db: sa.engine.Engine,
):
    assert client.app
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])

    body = {
        "service_key": f"simcore/services/{node_class}/{faker.pystr().lower()}",
        "service_version": faker.numerify("%.#.#"),
    }
    response = await client.post(url.path, json=body)
    data, error = await assert_status(response, expected.created)
    if data:
        assert not error
        mocked_director_v2_api[
            "director_v2.api.create_or_update_pipeline"
        ].assert_called_once()
        if expect_run_service_call:
            mocked_director_v2_api[
                "director_v2.api.run_dynamic_service"
            ].assert_called_once()
        else:
            mocked_director_v2_api[
                "director_v2.api.run_dynamic_service"
            ].assert_not_called()

        # check database is updated
        assert "node_id" in data
        create_node_id = data["node_id"]
        with postgres_db.connect() as conn:
            result = conn.execute(
                sa.select(projects_db_model.c.workbench).where(
                    projects_db_model.c.uuid == user_project["uuid"]
                )
            )
        assert result
        workbench = result.one()[projects_db_model.c.workbench]
        assert create_node_id in workbench
    else:
        assert error


def standard_user_role() -> tuple[str, tuple]:
    all_roles = standard_role_response()

    return (all_roles[0], (pytest.param(*all_roles[1][2], id="standard user role"),))


@pytest.mark.parametrize(*standard_user_role())
async def test_create_and_delete_many_nodes_in_parallel(
    disable_max_number_of_running_dynamic_nodes: dict[str, str],
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    faker: Faker,
    postgres_db: sa.engine.Engine,
    storage_subsystem_mock: MockedStorageSubsystem,
    mock_get_total_project_dynamic_nodes_creation_interval: None,
):
    assert client.app

    @dataclass
    class _RunninServices:
        running_services_uuids: list[str] = field(default_factory=list)

        def num_services(self, *args, **kwargs) -> list[dict[str, Any]]:
            return [
                {"service_uuid": service_uuid}
                for service_uuid in self.running_services_uuids
            ]

        def inc_running_services(self, *args, **kwargs):
            self.running_services_uuids.append(kwargs["service_uuid"])

    # let's count the started services
    running_services = _RunninServices()
    assert running_services.running_services_uuids == []
    mocked_director_v2_api[
        "director_v2.api.list_dynamic_services"
    ].side_effect = running_services.num_services
    mocked_director_v2_api[
        "director_v2.api.run_dynamic_service"
    ].side_effect = running_services.inc_running_services

    # let's create many nodes
    num_services_in_project = len(user_project["workbench"])
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    body = {
        "service_key": f"simcore/services/dynamic/{faker.pystr().lower()}",
        "service_version": faker.numerify("%.#.#"),
    }
    NUM_DY_SERVICES = 150
    responses = await asyncio.gather(
        *(client.post(f"{url}", json=body) for _ in range(NUM_DY_SERVICES))
    )
    # all shall have worked
    await asyncio.gather(*(assert_status(r, expected.created) for r in responses))

    # but only the allowed number of services should have started
    assert (
        mocked_director_v2_api["director_v2.api.run_dynamic_service"].call_count
        == NUM_DY_SERVICES
    )
    assert len(running_services.running_services_uuids) == NUM_DY_SERVICES
    # check that we do have NUM_DY_SERVICES nodes in the project
    with postgres_db.connect() as conn:
        result = conn.execute(
            sa.select(projects_db_model.c.workbench).where(
                projects_db_model.c.uuid == user_project["uuid"]
            )
        )
        assert result
        workbench = result.one()[projects_db_model.c.workbench]
    assert len(workbench) == NUM_DY_SERVICES + num_services_in_project
    print(f"--> {NUM_DY_SERVICES} nodes were created concurrently")
    #
    # delete now
    #
    delete_node_tasks = []
    for node_id in workbench:
        delete_url = client.app.router["delete_node"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        delete_node_tasks.append(client.delete(f"{delete_url}"))
    responses = await asyncio.gather(*delete_node_tasks)
    await asyncio.gather(*(assert_status(r, expected.no_content) for r in responses))
    print("--> deleted all nodes concurrently")


@pytest.mark.parametrize(*standard_user_role())
async def test_create_node_does_not_start_dynamic_node_if_there_are_already_too_many_running(
    client: TestClient,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    faker: Faker,
    max_amount_of_auto_started_dyn_services: int,
):
    assert client.app
    project = await user_project_with_num_dynamic_services(
        max_amount_of_auto_started_dyn_services
    )
    all_service_uuids = list(project["workbench"])
    mocked_director_v2_api["director_v2.api.list_dynamic_services"].return_value = [
        {"service_uuid": service_uuid} for service_uuid in all_service_uuids
    ]
    url = client.app.router["create_node"].url_for(project_id=project["uuid"])
    body = {
        "service_key": f"simcore/services/dynamic/{faker.pystr().lower()}",
        "service_version": faker.numerify("%.#.#"),
    }
    response = await client.post(f"{ url}", json=body)
    await assert_status(response, expected.created)
    mocked_director_v2_api["director_v2.api.run_dynamic_service"].assert_not_called()


@pytest.mark.parametrize(*standard_user_role())
async def test_create_many_nodes_in_parallel_still_is_limited_to_the_defined_maximum(
    client: TestClient,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    faker: Faker,
    max_amount_of_auto_started_dyn_services: int,
    postgres_db: sa.engine.Engine,
    mock_get_total_project_dynamic_nodes_creation_interval: None,
):
    assert client.app
    # create a starting project with no dy-services
    project = await user_project_with_num_dynamic_services(0)

    SERVICE_IS_RUNNING_AFTER_S: Final[NonNegativeFloat] = 0.1

    @dataclass
    class _RunninServices:
        running_services_uuids: list[str] = field(default_factory=list)

        async def num_services(self, *args, **kwargs) -> list[dict[str, Any]]:
            return [
                {"service_uuid": service_uuid}
                for service_uuid in self.running_services_uuids
            ]

        async def inc_running_services(self, *args, **kwargs):
            # simulate delay when service is starting
            # reproduces real world conditions and makes test to fail
            await asyncio.sleep(SERVICE_IS_RUNNING_AFTER_S)
            self.running_services_uuids.append(kwargs["service_uuid"])

    # let's count the started services
    running_services = _RunninServices()
    assert running_services.running_services_uuids == []
    mocked_director_v2_api[
        "director_v2.api.list_dynamic_services"
    ].side_effect = running_services.num_services
    mocked_director_v2_api[
        "director_v2.api.run_dynamic_service"
    ].side_effect = running_services.inc_running_services

    # let's create more than the allowed max amount in parallel
    url = client.app.router["create_node"].url_for(project_id=project["uuid"])
    body = {
        "service_key": f"simcore/services/dynamic/{faker.pystr().lower()}",
        "service_version": faker.numerify("%.#.#"),
    }
    NUM_DY_SERVICES: Final[NonNegativeInt] = 150
    responses = await asyncio.gather(
        *(client.post(f"{url}", json=body) for _ in range(NUM_DY_SERVICES))
    )
    # all shall have worked
    await asyncio.gather(*(assert_status(r, expected.created) for r in responses))

    # but only the allowed number of services should have started
    assert (
        mocked_director_v2_api["director_v2.api.run_dynamic_service"].call_count
        == max_amount_of_auto_started_dyn_services
    )
    assert (
        len(running_services.running_services_uuids)
        == max_amount_of_auto_started_dyn_services
    )
    # check that we do have NUM_DY_SERVICES nodes in the project
    with postgres_db.connect() as conn:
        result = conn.execute(
            sa.select(projects_db_model.c.workbench).where(
                projects_db_model.c.uuid == project["uuid"]
            )
        )
        assert result
        workbench = result.one()[projects_db_model.c.workbench]
    assert len(workbench) == NUM_DY_SERVICES


@pytest.mark.parametrize(*standard_user_role())
async def test_create_node_does_start_dynamic_node_if_max_num_set_to_0(
    disable_max_number_of_running_dynamic_nodes: dict[str, str],
    client: TestClient,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    faker: Faker,
):
    assert client.app
    project = await user_project_with_num_dynamic_services(faker.pyint(min_value=3))
    all_service_uuids = list(project["workbench"])
    mocked_director_v2_api["director_v2.api.list_dynamic_services"].return_value = [
        {"service_uuid": service_uuid} for service_uuid in all_service_uuids
    ]
    url = client.app.router["create_node"].url_for(project_id=project["uuid"])

    # Use-case 1.: not passing a service UUID will generate a new one on the fly
    body = {
        "service_key": f"simcore/services/dynamic/{faker.pystr().lower()}",
        "service_version": faker.numerify("%.#.#"),
    }
    response = await client.post(f"{ url}", json=body)
    await assert_status(response, expected.created)
    mocked_director_v2_api["director_v2.api.run_dynamic_service"].assert_called_once()


@pytest.mark.parametrize(
    "node_class",
    [("dynamic"), ("comp"), ("frontend")],
)
@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_creating_deprecated_node_returns_406_not_acceptable(
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    faker: Faker,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    node_class: str,
):
    mock_catalog_api["get_service"].return_value["deprecated"] = (
        datetime.utcnow() - timedelta(days=1)
    ).isoformat()
    assert client.app
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])

    # Use-case 1.: not passing a service UUID will generate a new one on the fly
    body = {
        "service_key": f"simcore/services/{node_class}/{faker.pystr().lower()}",
        "service_version": f"{faker.random_int()}.{faker.random_int()}.{faker.random_int()}",
    }
    response = await client.post(url.path, json=body)
    data, error = await assert_status(response, expected.not_acceptable)
    assert error
    assert not data
    # this does not start anything in the backend since this node is deprecated
    mocked_director_v2_api["director_v2.api.run_dynamic_service"].assert_not_called()


@pytest.mark.parametrize(
    "dy_service_running",
    [
        pytest.param(True, id="dy-service-running"),
        pytest.param(False, id="dy-service-NOT-running"),
    ],
)
@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_delete_node(
    client: TestClient,
    user_project: ProjectDict,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    storage_subsystem_mock: MockedStorageSubsystem,
    dy_service_running: bool,
    postgres_db: sa.engine.Engine,
):
    # first create a node
    assert client.app
    assert "workbench" in user_project
    assert isinstance(user_project["workbench"], dict)
    running_dy_services = [
        service_uuid
        for service_uuid, service_data in user_project["workbench"].items()
        if "/dynamic/" in service_data["key"] and dy_service_running
    ]
    mocked_director_v2_api["director_v2.api.list_dynamic_services"].return_value = [
        {"service_uuid": service_uuid} for service_uuid in running_dy_services
    ]
    for node_id in user_project["workbench"]:
        url = client.app.router["delete_node"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.delete(url.path)
        data, error = await assert_status(response, expected.no_content)
        assert not data
        if error:
            continue

        mocked_director_v2_api[
            "director_v2.api.list_dynamic_services"
        ].assert_called_once()
        mocked_director_v2_api["director_v2.api.list_dynamic_services"].reset_mock()

        if node_id in running_dy_services:
            mocked_director_v2_api[
                "director_v2.api.stop_dynamic_service"
            ].assert_called_once_with(
                mock.ANY,
                node_id,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=False,
            )
            mocked_director_v2_api["director_v2.api.stop_dynamic_service"].reset_mock()
        else:
            mocked_director_v2_api[
                "director_v2.api.stop_dynamic_service"
            ].assert_not_called()

        # ensure the node is gone
        with postgres_db.connect() as conn:
            result = conn.execute(
                sa.select(projects_db_model.c.workbench).where(
                    projects_db_model.c.uuid == user_project["uuid"]
                )
            )
            assert result
            workbench = result.one()[projects_db_model.c.workbench]
            assert node_id not in workbench


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_start_node(
    client: TestClient,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    faker: Faker,
    max_amount_of_auto_started_dyn_services: int,
):
    assert client.app
    project = await user_project_with_num_dynamic_services(
        max_amount_of_auto_started_dyn_services or faker.pyint(min_value=3)
    )
    all_service_uuids = list(project["workbench"])
    # start the node, shall work as expected
    url = client.app.router["start_node"].url_for(
        project_id=project["uuid"], node_id=choice(all_service_uuids)
    )
    response = await client.post(f"{url}")
    data, error = await assert_status(
        response,
        web.HTTPNoContent if user_role == UserRole.GUEST else expected.no_content,
    )
    if error is None:
        mocked_director_v2_api[
            "director_v2.api.run_dynamic_service"
        ].assert_called_once()
    else:
        mocked_director_v2_api[
            "director_v2.api.run_dynamic_service"
        ].assert_not_called()


@pytest.mark.parametrize(*standard_user_role())
async def test_start_node_raises_if_dynamic_services_limit_attained(
    client: TestClient,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    faker: Faker,
    max_amount_of_auto_started_dyn_services: int,
):
    assert client.app
    project = await user_project_with_num_dynamic_services(
        max_amount_of_auto_started_dyn_services
    )
    all_service_uuids = list(project["workbench"])
    mocked_director_v2_api["director_v2.api.list_dynamic_services"].return_value = [
        {"service_uuid": service_uuid} for service_uuid in all_service_uuids
    ]
    # start the node, shall work as expected
    url = client.app.router["start_node"].url_for(
        project_id=project["uuid"], node_id=choice(all_service_uuids)
    )
    response = await client.post(f"{url}")
    data, error = await assert_status(
        response,
        expected.conflict,
    )
    assert not data
    assert error
    mocked_director_v2_api["director_v2.api.run_dynamic_service"].assert_not_called()


@pytest.mark.parametrize(*standard_user_role())
async def test_start_node_starts_dynamic_service_if_max_number_of_services_set_to_0(
    disable_max_number_of_running_dynamic_nodes: dict[str, str],
    client: TestClient,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    faker: Faker,
):
    assert client.app
    project = await user_project_with_num_dynamic_services(faker.pyint(min_value=3))
    all_service_uuids = list(project["workbench"])
    mocked_director_v2_api["director_v2.api.list_dynamic_services"].return_value = [
        {"service_uuid": service_uuid} for service_uuid in all_service_uuids
    ]
    # start the node, shall work as expected
    url = client.app.router["start_node"].url_for(
        project_id=project["uuid"], node_id=choice(all_service_uuids)
    )
    response = await client.post(f"{url}")
    data, error = await assert_status(
        response,
        expected.no_content,
    )
    assert not data
    assert not error
    mocked_director_v2_api["director_v2.api.run_dynamic_service"].assert_called_once()


@pytest.mark.parametrize(*standard_user_role())
async def test_start_node_raises_if_called_with_wrong_data(
    client: TestClient,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    faker: Faker,
    max_amount_of_auto_started_dyn_services: int,
):
    assert client.app
    project = await user_project_with_num_dynamic_services(
        max_amount_of_auto_started_dyn_services
    )
    all_service_uuids = list(project["workbench"])

    # start the node, with wrong project
    url = client.app.router["start_node"].url_for(
        project_id=faker.uuid4(), node_id=choice(all_service_uuids)
    )
    response = await client.post(f"{url}")
    data, error = await assert_status(
        response,
        expected.not_found,
    )
    assert not data
    assert error
    mocked_director_v2_api["director_v2.api.run_dynamic_service"].assert_not_called()

    # start the node, with wrong node
    url = client.app.router["start_node"].url_for(
        project_id=project["uuid"], node_id=faker.uuid4()
    )
    response = await client.post(f"{url}")
    data, error = await assert_status(
        response,
        expected.not_found,
    )
    assert not data
    assert error
    mocked_director_v2_api["director_v2.api.run_dynamic_service"].assert_not_called()


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_stop_node(
    client: TestClient,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    faker: Faker,
    max_amount_of_auto_started_dyn_services: int,
):
    assert client.app
    project = await user_project_with_num_dynamic_services(
        max_amount_of_auto_started_dyn_services or faker.pyint(min_value=3)
    )
    all_service_uuids = list(project["workbench"])
    # start the node, shall work as expected
    url = client.app.router["stop_node"].url_for(
        project_id=project["uuid"], node_id=choice(all_service_uuids)  # noqa: S311
    )
    response = await client.post(f"{url}")
    data, error = await assert_status(
        response,
        web.HTTPAccepted if user_role == UserRole.GUEST else expected.accepted,
    )
    if error is None:
        mocked_director_v2_api[
            "director_v2.api.stop_dynamic_service"
        ].assert_called_once()
    else:
        mocked_director_v2_api[
            "director_v2.api.stop_dynamic_service"
        ].assert_not_called()


@pytest.fixture
def app_environment(
    app_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    # test_read_project_nodes_previews needs WEBSERVER_DEV_FEATURES_ENABLED=1
    new_envs = setenvs_from_dict(monkeypatch, {"WEBSERVER_DEV_FEATURES_ENABLED": "1"})
    return app_environment | new_envs


@pytest.fixture
def mock_storage_calls(aioresponses_mocker: AioResponsesMock, faker: Faker) -> None:
    _get_files_in_node_folder = re.compile(
        r"^http://[a-z\-_]*:[0-9]+/v[0-9]/locations/[0-9]+/files/metadata.+$"
    )

    _get_download_link = re.compile(
        r"^http://[a-z\-_]*:[0-9]+/v[0-9]/locations/[0-9]+/files.+$"
    )

    file_uuid = f"{uuid4()}/{uuid4()}/assets/some_file.png"
    aioresponses_mocker.get(
        _get_files_in_node_folder,
        payload=jsonable_encoder(
            Envelope[list[FileMetaDataGet]](
                data=[
                    parse_obj_as(
                        FileMetaDataGet,
                        {
                            "file_uuid": file_uuid,
                            "location_id": 0,
                            "file_name": Path(file_uuid).name,
                            "file_id": file_uuid,
                            "created_at": "2020-06-17 12:28:55.705340",
                            "last_modified": "2020-06-17 12:28:55.705340",
                        },
                    )
                ]
            )
        ),
        repeat=True,
    )

    aioresponses_mocker.get(
        _get_download_link,
        status=web.HTTPOk.status_code,
        payload=jsonable_encoder(
            Envelope[PresignedLink](data=PresignedLink(link=faker.image_url()))
        ),
        repeat=True,
    )


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_read_project_nodes_previews(
    mock_storage_calls: None,
    client: TestClient,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    user_role: UserRole,
):
    assert client.app
    project = await user_project_with_num_dynamic_services(3)

    # LIST all node previews
    url = client.app.router["list_project_nodes_previews"].url_for(
        project_id=project["uuid"]
    )
    response = await client.get(f"{url}")

    data, error = await assert_status(
        response,
        web.HTTPOk,
    )

    assert not error
    assert len(data) == 3

    nodes_previews = parse_obj_as(list[_ProjectNodePreview], data)

    # GET node's preview
    for node_preview in nodes_previews:
        assert f"{node_preview.project_id}" == project["uuid"]

        url = client.app.router["get_project_node_preview"].url_for(
            project_id=project["uuid"], node_id=f"{node_preview.node_id}"
        )

        response = await client.get(f"{url}")
        data, error = await assert_status(
            response,
            web.HTTPOk,
        )

        assert parse_obj_as(_ProjectNodePreview, data) == node_preview
