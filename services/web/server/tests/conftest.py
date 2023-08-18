# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import logging
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from pathlib import Path

import pytest
import simcore_service_webserver
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.projects_state import ProjectState
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_dict import ConfigDict
from pytest_simcore.helpers.utils_login import LoggedUser, UserInfoDict
from pytest_simcore.simcore_webserver_projects_rest_api import NEW_PROJECT
from servicelib.aiohttp.long_running_tasks.server import TaskStatus
from servicelib.json_serialization import json_dumps
from simcore_service_webserver.application_settings_utils import convert_to_environ_vars
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects._crud_api_create import (
    OVERRIDABLE_DOCUMENT_KEYS,
)
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.utils import to_datetime
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


log = logging.getLogger(__name__)

# mute noisy loggers
logging.getLogger("openapi_spec_validator").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


# imports the fixtures for the integration tests
pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.db_entries_mocks",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.hypothesis_type_strategies",
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
    "pytest_simcore.tmp_path_extra",
    "pytest_simcore.websocket_client",
]


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
async def logged_user(
    client: TestClient, user_role: UserRole
) -> AsyncIterator[UserInfoDict]:
    """adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS,
    ) as user:
        print("-----> logged in user", user["name"], user_role)
        yield user
        print("<----- logged out user", user["name"], user_role)


@pytest.fixture
def monkeypatch_setenv_from_app_config(
    monkeypatch: MonkeyPatch,
) -> Callable[[ConfigDict], dict[str, str]]:
    # TODO: Change signature to be analogous to
    # packages/pytest-simcore/src/pytest_simcore/helpers/utils_envs.py
    # That solution is more flexible e.g. for context manager with monkeypatch
    def _patch(app_config: dict) -> dict[str, str]:
        assert isinstance(app_config, dict)

        print("  - app_config=\n", json_dumps(app_config, indent=1, sort_keys=True))
        envs = convert_to_environ_vars(app_config)

        print(
            "  - convert_to_environ_vars(app_cfg)=\n",
            json_dumps(envs, indent=1, sort_keys=True),
        )
        for env_key, env_value in envs.items():
            monkeypatch.setenv(env_key, f"{env_value}")

        return envs

    return _patch


@pytest.fixture
def request_create_project() -> Callable[..., Awaitable[ProjectDict]]:
    """this fixture allows to create projects through the webserver interface

        NOTE: a next iteration should take care of cleaning up created projects

    Returns:
        Callable[..., Awaitable[ProjectDict]]: _description_
    """
    # pylint: disable=too-many-statements

    async def _setup(
        client: TestClient,
        *,
        project: dict | None = None,
        from_study: dict | None = None,
        as_template: bool | None = None,
        copy_data: bool | None = None,
    ):
        # Pre-defined fields imposed by required properties in schema
        project_data: ProjectDict = {}
        expected_data: ProjectDict = {
            "classifiers": [],
            "accessRights": [],
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
        }
        if from_study:
            # access rights are replaced
            expected_data = deepcopy(from_study)
            expected_data["accessRights"] = {}
            if not as_template:
                expected_data["name"] = f"{from_study['name']} (Copy)"

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

        return url, project_data, expected_data

    async def _creator(
        client: TestClient,
        expected_accepted_response: type[web.HTTPException],
        expected_creation_response: type[web.HTTPException],
        logged_user: dict[str, str],
        primary_group: dict[str, str],
        *,
        project: dict | None = None,
        from_study: dict | None = None,
        as_template: bool | None = None,
        copy_data: bool | None = None,
    ) -> ProjectDict:
        url, project_data, expected_data = await _setup(
            client,
            project=project,
            from_study=from_study,
            as_template=as_template,
            copy_data=copy_data,
        )

        resp = await client.post(f"{url}", json=project_data)
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
                result = await client.get(f"{status_url}")
                data, error = await assert_status(result, web.HTTPOk)
                assert data
                assert not error
                task_status = TaskStatus.parse_obj(data)
                assert task_status
                print(f"<-- status: {task_status.json(indent=2)}")
                assert task_status.done, "task incomplete"
                print(
                    f"-- project creation completed: {json.dumps(attempt.retry_state.retry_object.statistics, indent=2)}"
                )

        # get result GET /{task_id}/result
        print("--> getting project creation result...")
        result = await client.get(f"{result_url}")
        data, error = await assert_status(result, expected_creation_response)
        if error:
            assert not data
            return {}
        assert data
        assert not error
        print(f"<-- result: {data}")
        new_project = data

        # now check returned is as expected
        if new_project:
            # has project state
            assert not ProjectState(
                **new_project.get("state", {})
            ).locked.value, "Newly created projects should be unlocked"

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
                    str(primary_group["gid"]): {
                        "read": True,
                        "write": True,
                        "delete": True,
                    }
                }
            )
            assert new_project["accessRights"] == expected_data["accessRights"]

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
            ]

            for key in new_project:
                if key not in modified_fields:
                    assert expected_data[key] == new_project[key]

        return new_project

    return _creator
