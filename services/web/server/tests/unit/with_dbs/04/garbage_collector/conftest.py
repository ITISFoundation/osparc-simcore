# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.projects import ProjectID
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from redis.asyncio import Redis
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.application_setup import is_setup_completed
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.director_v2.plugin import setup_director_v2
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.notifications.plugin import setup_notifications
from simcore_service_webserver.products.plugin import setup_products
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.rabbitmq import setup_rabbitmq
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session
from simcore_service_webserver.socketio.plugin import setup_socketio
from simcore_service_webserver.users.plugin import setup_users


@pytest.fixture(scope="session")
def service_name() -> str:
    # Overrides  service_name fixture needed in docker_compose_service_environment_dict fixture
    return "wb-garbage-collector"


@pytest.fixture(scope="session")
def fast_service_deletion_delay() -> int:
    """
    Returns the delay in seconds for fast service deletion.
    This is used to speed up tests that involve service deletion.
    """
    return 1


@pytest.fixture
def app_environment(
    fast_service_deletion_delay: int,
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_environment_dict: EnvVarsDict,
    env_devel_dict: EnvVarsDict,
) -> EnvVarsDict:

    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            "WEBSERVER_COMPUTATION": "1",
            "WEBSERVER_NOTIFICATIONS": "1",
            # sets TTL of a resource after logout
            "RESOURCE_MANAGER_RESOURCE_TTL_S": f"{fast_service_deletion_delay}",
            #  "WEBSERVER_PROJECTS must be enabled for close_project fixture"
            "WEBSERVER_PROJECTS": env_devel_dict["WEBSERVER_PROJECTS"],
        },
    )


@pytest.fixture
async def client(
    aiohttp_client: Callable,
    app_environment: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    mock_orphaned_services,
    redis_client: Redis,
    mock_dynamic_scheduler_rabbitmq: None,
) -> TestClient:
    app = create_safe_application()

    settings = setup_settings(app)
    assert settings.WEBSERVER_GARBAGE_COLLECTOR is not None

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)

    assert (
        settings.WEBSERVER_PROJECTS is not None
    ), "WEBSERVER_PROJECTS must be enabled for close_project fixture"
    assert setup_projects(app)

    setup_director_v2(app)
    assert setup_resource_manager(app)
    setup_rabbitmq(app)
    setup_notifications(app)
    setup_products(app)

    assert is_setup_completed("simcore_service_webserver.resource_manager", app)

    # NOTE: garbage_collector is disabled and instead explicitly called using
    # garbage_collectorgc_core.collect_garbage
    assert not is_setup_completed("simcore_service_webserver.garbage_collector", app)

    return await aiohttp_client(app)


@pytest.fixture
async def close_project() -> Callable[[TestClient, ProjectID, str], Awaitable[None]]:
    """Closes a project by sending a request to the close_project endpoint."""

    async def _close_project(
        client: TestClient, project_uuid: ProjectID, client_session_id: str
    ) -> None:
        url = client.app.router["close_project"].url_for(project_id=f"{project_uuid}")
        resp = await client.post(url, json=client_session_id)
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

    return _close_project


@pytest.fixture
async def open_project(
    close_project: Callable[[TestClient, ProjectID, str], Awaitable[None]],
) -> AsyncIterator[Callable[[TestClient, ProjectID, str], Awaitable[None]]]:
    _opened_projects: list[tuple[TestClient, ProjectID, str]] = []

    async def _open_project(
        client: TestClient, project_uuid: ProjectID, client_session_id: str
    ) -> None:
        url = client.app.router["open_project"].url_for(project_id=f"{project_uuid}")
        resp = await client.post(url, json=client_session_id)
        await assert_status(resp, status.HTTP_200_OK)
        _opened_projects.append((client, project_uuid, client_session_id))

    yield _open_project
    # cleanup, if we cannot close that is because the user_role might not allow it
    await asyncio.gather(
        *(
            close_project(client, project_uuid, client_session_id)
            for client, project_uuid, client_session_id in _opened_projects
        ),
        return_exceptions=True,
    )
