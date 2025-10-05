# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import contextlib
import json
import logging
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

import pytest
import simcore_service_webserver
from aiohttp.test_utils import TestClient
from common_library.json_serialization import json_dumps
from faker import Faker
from models_library.api_schemas_webserver.projects import (
    ProjectGet,
    ProjectStateOutputSchema,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.faker_factories import random_phone_number
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_login import LoggedUser
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from pytest_simcore.simcore_webserver_projects_rest_api import NEW_PROJECT
from servicelib.aiohttp import status
from servicelib.common_headers import (
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
)
from servicelib.long_running_tasks.models import TaskStatus
from simcore_service_webserver.application_settings_utils import (
    AppConfigDict,
    convert_to_environ_vars,
)
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.models import PhoneNumberStr
from simcore_service_webserver.projects._crud_api_create import (
    OVERRIDABLE_DOCUMENT_KEYS,
)
from simcore_service_webserver.projects._groups_repository import (
    update_or_insert_project_group,
)
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.utils import to_datetime
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


# mute noisy loggers
logging.getLogger("openapi_spec_validator").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


# imports the fixtures for the integration tests
pytest_plugins = [
    "aiohttp.pytest_plugin",
    "pytest_simcore.asyncio_event_loops",
    "pytest_simcore.cli_runner",
    "pytest_simcore.db_entries_mocks",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.hypothesis_type_strategies",
    "pytest_simcore.logging",
    "pytest_simcore.openapi_specs",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.services_api_mocks_for_aiohttp_clients",
    "pytest_simcore.simcore_service_library_fixtures",
    "pytest_simcore.simcore_services",
    "pytest_simcore.simcore_webserver_groups_fixtures",
    "pytest_simcore.socketio_client",
]


@pytest.fixture(scope="session")
def service_name() -> str:
    # Overrides  service_name fixture needed in docker_compose_service_environment_dict fixture
    # NOTE: this can be used to setup configs for different webserver service variants e.g. wg-api-server, wg-garbage-collector, etc
    return "webserver"


@pytest.fixture
async def exit_stack() -> AsyncIterator[contextlib.AsyncExitStack]:
    """Provides an AsyncExitStack that gets cleaned up after each test"""
    async with contextlib.AsyncExitStack() as stack:
        yield stack


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """osparc-simcore installed directory"""
    dirpath = Path(simcore_service_webserver.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir) -> Path:
    service_dir = osparc_simcore_root_dir / "services" / "web" / "server"
    assert service_dir.exists()
    assert any(service_dir.glob("src/simcore_service_webserver"))
    return service_dir


@pytest.fixture(scope="session")
def api_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    specs_dir = osparc_simcore_root_dir / "api" / "specs" / "webserver"
    assert specs_dir.exists()
    return specs_dir


@pytest.fixture(scope="session")
def tests_data_dir(project_tests_dir: Path) -> Path:
    data_dir = project_tests_dir / "data"
    assert data_dir.exists()
    return data_dir


@pytest.fixture(scope="session")
def fake_data_dir(tests_data_dir: Path) -> Path:
    # legacy
    return tests_data_dir


@pytest.fixture
def fake_project(tests_data_dir: Path) -> ProjectDict:
    """fake data for a project in a response body of GET /project/{uuid} (see tests/data/fake-project.json)"""
    # TODO: rename as fake_project_data since it does not produce a BaseModel but its **data
    fpath = tests_data_dir / "fake-project.json"
    assert fpath.exists()
    return json.loads(fpath.read_text())


@pytest.fixture
def user_phone_number(faker: Faker) -> PhoneNumberStr:
    return TypeAdapter(PhoneNumberStr).validate_python(random_phone_number(faker))


@pytest.fixture
async def user(client: TestClient) -> AsyncIterator[UserInfoDict]:
    async with NewUser(
        user_data={
            "name": "test-user",
        },
        app=client.app,
    ) as user_info:
        yield user_info


@pytest.fixture
async def logged_user(
    client: TestClient,
    user_role: UserRole,
    faker: Faker,
    user_phone_number: PhoneNumberStr,
) -> AsyncIterator[UserInfoDict]:
    """adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {
            "role": user_role.name,
            "first_name": faker.first_name(),
            "last_name": faker.last_name(),
            "phone": user_phone_number,
        },
        check_if_succeeds=user_role != UserRole.ANONYMOUS,
    ) as user:
        print("-----> logged in user", user["name"], user_role)
        yield user
        print("<----- logged out user", user["name"], user_role)


@pytest.fixture
def monkeypatch_setenv_from_app_config(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[AppConfigDict], EnvVarsDict]:
    # TODO: Change signature to be analogous to
    # packages/pytest-simcore/src/pytest_simcore/helpers/utils_envs.py
    # That solution is more flexible e.g. for context manager with monkeypatch
    def _patch(app_config: dict) -> EnvVarsDict:
        assert isinstance(app_config, dict)

        print("  - app_config=\n", json_dumps(app_config, indent=1, sort_keys=True))
        envs: EnvVarsDict = {
            env_key: f"{env_value}"
            for env_key, env_value in convert_to_environ_vars(app_config).items()
        }

        print(
            "  - convert_to_environ_vars(app_cfg)=\n",
            json_dumps(envs, indent=1, sort_keys=True),
        )
        return setenvs_from_dict(monkeypatch, envs)

    return _patch


@pytest.fixture
async def request_create_project() -> (  # noqa: C901, PLR0915
    AsyncIterator[Callable[..., Awaitable[ProjectDict]]]
):
    """this fixture allows to create projects through the webserver interface

    Returns:
        Callable[..., Awaitable[ProjectDict]]: _description_
    """
    # pylint: disable=too-many-statements

    created_project_uuids = []
    used_clients = []

    async def _setup(  # noqa: C901
        client: TestClient,
        *,
        project: dict | None = None,
        from_study: dict | None = None,
        as_template: bool | None = None,
        copy_data: bool | None = None,
        parent_project_uuid: ProjectID | None,
        parent_node_id: NodeID | None,
    ):
        # Pre-defined fields imposed by required properties in schema
        project_data: ProjectDict = {}
        expected_data: ProjectDict = {
            "classifiers": [],
            "accessRights": {},
            "tags": [],
            "lastChangeDate": None,
            "creationDate": None,
            "quality": {},
            "dev": {},
            "ui": {},
            "workbench": None,
            "description": None,
            "uuid": None,
            "state": None,
            "thumbnail": None,
            "name": None,
            "prjOwner": None,
            "workspaceId": None,
            "folderId": None,
            "trashedAt": None,
            "trashedBy": None,
            "type": None,
            "templateType": None,
        }
        if from_study:
            from_study_wo_access_rights = deepcopy(from_study)
            from_study_wo_access_rights.pop("accessRights")
            expected_data = {
                **expected_data,
                "trashedByPrimaryGid": None,
                **from_study_wo_access_rights,
            }
            if not as_template:
                expected_data["name"] = f"{from_study['name']} (Copy)"

            expected_data = ProjectGet.from_domain_model(expected_data).model_dump(
                mode="json", by_alias=True
            )

        if not from_study or project:
            assert NEW_PROJECT.request_payload
            project_data = deepcopy(NEW_PROJECT.request_payload)

            if project:
                project_data.update(project)

            for key in project_data:
                expected_data[key] = project_data[key]
                if (
                    key in OVERRIDABLE_DOCUMENT_KEYS
                    and not project_data[key]
                    and from_study
                ):
                    expected_data[key] = from_study[key]

        # POST /v0/projects -> returns 202 or denied access
        assert client.app
        url: URL = client.app.router["create_project"].url_for()

        if from_study:
            url = url.update_query(from_study=from_study["uuid"])
        if as_template:
            url = url.update_query(as_template=f"{as_template}")
        if copy_data is not None:
            url = url.update_query(copy_data=f"{copy_data}")
        headers = {}
        if parent_project_uuid is not None:
            headers |= {
                X_SIMCORE_PARENT_PROJECT_UUID: f"{parent_project_uuid}",
            }
        if parent_node_id is not None:
            headers |= {
                X_SIMCORE_PARENT_NODE_ID: f"{parent_node_id}",
            }
        return url, project_data, expected_data, headers

    async def _creator(  # noqa: PLR0915
        client: TestClient,
        expected_accepted_response: HTTPStatus,
        expected_creation_response: HTTPStatus,
        logged_user: dict[str, str],
        primary_group: dict[str, str],
        *,
        project: dict | None = None,
        from_study: dict | None = None,
        as_template: bool | None = None,
        copy_data: bool | None = None,
        parent_project_uuid: ProjectID | None = None,
        parent_node_id: NodeID | None = None,
    ) -> ProjectDict:
        assert client.app

        url, project_data, expected_data, headers = await _setup(
            client,
            project=project,
            from_study=from_study,
            as_template=as_template,
            copy_data=copy_data,
            parent_project_uuid=parent_project_uuid,
            parent_node_id=parent_node_id,
        )
        # Create project here:
        resp = await client.post(
            f"{url}", json=project_data, headers=headers
        )  # NOTE: MD <-- here is project created!
        print(f"<-- created project response: {resp=}")
        data, error = await assert_status(resp, expected_accepted_response)
        if error:
            assert not data
            return {}
        assert data
        assert all(
            x in data for x in ["task_id", "status_href", "result_href", "abort_href"]
        )
        status_url = data["status_href"]
        result_url = data["result_href"]

        # get status GET /{task_id}
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1),
            stop=stop_after_delay(60),
            reraise=True,
            retry=retry_if_exception_type(AssertionError),
        ):
            with attempt:
                print(
                    f"--> waiting for creation {attempt.retry_state.attempt_number}..."
                )
                result = await client.get(urlparse(status_url).path)
                data, error = await assert_status(result, status.HTTP_200_OK)
                assert data
                assert not error
                task_status = TaskStatus.model_validate(data)
                assert task_status
                print(f"<-- status: {task_status.model_dump_json(indent=2)}")
                assert task_status.done, "task incomplete"
                print(
                    f"-- project creation completed: {json.dumps(attempt.retry_state.retry_object.statistics, indent=2)}"
                )

        # get result GET /{task_id}/result
        print("--> getting project creation result...")
        result = await client.get(urlparse(result_url).path)
        data, error = await assert_status(result, expected_creation_response)
        if error:
            assert not data
            return {}
        assert data
        assert not error
        print(f"<-- result: {data}")
        new_project = data

        # Setup access rights to the project
        if project_data and (
            project_data.get("access_rights") or project_data.get("accessRights")
        ):
            _access_rights = project_data.get("access_rights", {}) | project_data.get(
                "accessRights", {}
            )
            for group_id, permissions in _access_rights.items():
                await update_or_insert_project_group(
                    client.app,
                    project_id=data["uuid"],
                    group_id=int(group_id),
                    read=permissions["read"],
                    write=permissions["write"],
                    delete=permissions["delete"],
                )
        # Get project with already added access rights
        print("--> getting project groups after access rights change...")
        url = client.app.router["list_project_groups"].url_for(project_id=data["uuid"])
        resp = await client.get(url.path)
        data, error = await assert_status(resp, status.HTTP_200_OK)
        print(f"<-- result: {data}")
        new_project_access_rights = {}
        for item in data:
            new_project_access_rights.update(
                {
                    f"{item['gid']}": {
                        "read": item["read"],
                        "write": item["write"],
                        "delete": item["delete"],
                    }
                }
            )
        new_project["accessRights"] = new_project_access_rights

        # now check returned is as expected
        if new_project:
            # has project state
            assert not ProjectStateOutputSchema(
                **new_project.get("state", {})
            ).share_state.locked, "Newly created projects should be unlocked"

            # updated fields
            assert expected_data["uuid"] != new_project["uuid"]
            assert (
                new_project["prjOwner"] == logged_user["email"]
            )  # the project owner is assigned the user id e-mail
            assert to_datetime(expected_data["creationDate"]) < to_datetime(
                new_project["creationDate"]
            )
            assert to_datetime(expected_data["lastChangeDate"]) < to_datetime(
                new_project["lastChangeDate"]
            )
            # the access rights are set to use the logged user primary group + whatever was inside the project
            expected_data["accessRights"].update(
                {
                    f"{primary_group['gid']}": {
                        "read": True,
                        "write": True,
                        "delete": True,
                    }
                }
            )
            assert new_project_access_rights == expected_data["accessRights"]

            modified_fields = [
                # invariant fields
                "uuid",
                "prjOwner",
                "creationDate",
                "lastChangeDate",
                "accessRights",
                "workbench" if from_study else None,
                "ui" if from_study else None,
                # dynamic
                "state",
                "permalink",
                "folderId",
                "type",
                "templateType",
            ]

            for key in expected_data:
                if key not in modified_fields:
                    assert expected_data[key] == new_project[key]

        created_project_uuids.append(new_project["uuid"])
        used_clients.append(client)

        return new_project

    yield _creator

    # cleanup projects
    for client, project_uuid in zip(used_clients, created_project_uuids, strict=True):
        url = client.app.router["delete_project"].url_for(project_id=project_uuid)
        await client.delete(url.path)


@pytest.fixture
def mock_dynamic_scheduler(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler.api.stop_dynamic_services_in_project",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler.api.update_projects_networks",
        autospec=True,
    )


@pytest.fixture
def with_dev_features_enabled(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:
    setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
        },
    )
