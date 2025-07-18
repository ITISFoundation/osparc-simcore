# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import AsyncIterator
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_networks import NetworksWithAliases
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
    insert_and_get_row_lifespan,
)
from pytest_simcore.helpers.postgres_users import (
    insert_and_get_user_and_secrets_lifespan,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.projects import projects
from simcore_service_dynamic_scheduler.repository.events import (
    get_project_networks_repo,
)
from simcore_service_dynamic_scheduler.repository.project_networks import (
    ProjectNetworkNotFoundError,
    ProjectNetworksRepo,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: PostgresTestConfig,
    disable_rabbitmq_lifespan: None,
    disable_redis_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_CLIENT_NAME": "test_postgres_client",
        },
    )
    return app_environment


@pytest.fixture
def engine(app: FastAPI) -> AsyncEngine:
    assert isinstance(app.state.engine, AsyncEngine)
    return app.state.engine


@pytest.fixture
def user_id() -> UserID:
    return 1


@pytest.fixture
async def user_in_db(
    engine: AsyncEngine,
    user: dict[str, Any],
    user_id: UserID,
) -> AsyncIterator[dict[str, Any]]:
    """
    injects a user + secrets in db
    """
    assert user_id == user["id"]
    async with insert_and_get_user_and_secrets_lifespan(
        engine,
        **user,
    ) as user_row:
        yield user_row


@pytest.fixture
async def project_in_db(
    engine: AsyncEngine,
    project_id: ProjectID,
    project_data: dict[str, Any],
    user_in_db: UserID,
) -> AsyncIterator[dict[str, Any]]:
    assert f"{project_id}" == project_data["uuid"]
    async with insert_and_get_row_lifespan(
        engine,
        table=projects,
        values=project_data,
        pk_col=projects.c.uuid,
        pk_value=project_data["uuid"],
    ) as row:
        yield row


@pytest.fixture()
def project_networks_repo(app: FastAPI) -> ProjectNetworksRepo:
    return get_project_networks_repo(app)


@pytest.fixture
def networks_with_aliases() -> NetworksWithAliases:
    return TypeAdapter(NetworksWithAliases).validate_python(
        NetworksWithAliases.model_json_schema()["examples"][0]
    )


async def test_no_project_networks_for_project(
    project_networks_repo: ProjectNetworksRepo,
    project_in_db: dict[str, Any],
    project_id: ProjectID,
):
    with pytest.raises(ProjectNetworkNotFoundError):
        await project_networks_repo.get_projects_networks(project_id=project_id)


async def test_upsert_projects_networks(
    project_networks_repo: ProjectNetworksRepo,
    project_in_db: dict[str, Any],
    project_id: ProjectID,
    networks_with_aliases: NetworksWithAliases,
):

    # allows ot test the upsert capabilities
    for _ in range(2):
        await project_networks_repo.upsert_projects_networks(
            project_id=project_id, networks_with_aliases=networks_with_aliases
        )

    project_networks = await project_networks_repo.get_projects_networks(
        project_id=project_id
    )
    assert project_networks.project_uuid == project_id
    assert project_networks.networks_with_aliases == networks_with_aliases
