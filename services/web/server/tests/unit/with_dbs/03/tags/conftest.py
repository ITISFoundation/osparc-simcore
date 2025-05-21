# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterator, Callable
from copy import deepcopy
from pathlib import Path

import pytest
from aioresponses import aioresponses
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_projects import NewProject, delete_all_projects
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.director_v2.plugin import setup_director_v2
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.products.plugin import setup_products
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session
from simcore_service_webserver.socketio.plugin import setup_socketio
from simcore_service_webserver.tags.plugin import setup_tags
from simcore_service_webserver.wallets.plugin import setup_wallets

API_VERSION = "v0"
RESOURCE_NAME = "projects"
API_PREFIX = "/" + API_VERSION


DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS: int = 3
DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS: int = 3


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    # NOTE: undos some app_environment settings
    monkeypatch.delenv("WEBSERVER_GARBAGE_COLLECTOR", raising=False)
    app_environment.pop("WEBSERVER_GARBAGE_COLLECTOR", None)

    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            # reduce deletion delay
            "RESOURCE_MANAGER_RESOURCE_TTL_S": f"{DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS}",
            # increase speed of garbage collection
            "GARBAGE_COLLECTOR_INTERVAL_S": f"{DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS}",
        },
    )


@pytest.fixture
async def client(
    aiohttp_client: Callable,
    app_environment: EnvVarsDict,
    postgres_db,
    mocked_dynamic_services_interface,
    mock_orphaned_services,
    redis_client,  # this ensure redis is properly cleaned
):
    app = create_safe_application()

    assert "WEBSERVER_GARBAGE_COLLECTOR" not in app_environment

    settings = setup_settings(app)
    assert settings.WEBSERVER_GARBAGE_COLLECTOR is not None
    assert settings.WEBSERVER_PROJECTS is not None
    assert settings.WEBSERVER_TAGS is not None

    # setup app
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)  # needed for login_utils fixtures
    setup_resource_manager(app)
    setup_socketio(app)
    setup_director_v2(app)
    assert setup_tags(app)
    setup_projects(app)
    setup_products(app)
    setup_wallets(app)

    # server and client
    return await aiohttp_client(app, server_kwargs={"host": "localhost"})

    # teardown here ...


@pytest.fixture
async def shared_project(
    client,
    fake_project,
    logged_user,
    all_group,
    tests_data_dir: Path,
    osparc_product_name: str,
):
    fake_project.update(
        {
            "accessRights": {
                f"{all_group['gid']}": {"read": True, "write": False, "delete": False}
            },
        },
    )
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        tests_data_dir=tests_data_dir,
        product_name=osparc_product_name,
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def template_project(
    client,
    fake_project,
    logged_user,
    all_group: dict[str, str],
    tests_data_dir: Path,
    osparc_product_name: str,
    user: UserInfoDict,
):
    project_data = deepcopy(fake_project)
    project_data["name"] = "Fake template"
    project_data["uuid"] = "d4d0eca3-d210-4db6-84f9-63670b07176b"
    project_data["accessRights"] = {
        str(all_group["gid"]): {"read": True, "write": False, "delete": False}
    }

    async with NewProject(
        project_data,
        client.app,
        user_id=user["id"],
        tests_data_dir=tests_data_dir,
        product_name=osparc_product_name,
    ) as template_project:
        print("-----> added template project", template_project["name"])
        yield template_project
        print("<----- removed template project", template_project["name"])


@pytest.fixture
async def project_db_cleaner(client):
    yield
    await delete_all_projects(client.app)


@pytest.fixture()
async def director_v2_automock(
    director_v2_service_mock: aioresponses,
) -> AsyncIterator[aioresponses]:
    return director_v2_service_mock
