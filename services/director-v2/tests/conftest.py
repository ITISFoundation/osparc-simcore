# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint:disable=no-value-for-parameter

import asyncio
import json
import logging
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from pprint import pformat
from random import randint
from typing import Any, AsyncIterable, Callable, Dict, Iterable, List
from uuid import uuid4

import dotenv
import httpx
import nest_asyncio
import pytest
import simcore_service_director_v2
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from aiohttp.test_utils import loop_context
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from models_library.projects import Node, ProjectAtDB, Workbench
from pydantic.main import BaseModel
from pydantic.types import PositiveInt
from simcore_postgres_database.models.comp_pipeline import StateType, comp_pipeline
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB, Image
from simcore_service_director_v2.utils.computations import to_node_class
from sqlalchemy import literal_column
from starlette.testclient import TestClient

nest_asyncio.apply()


pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.minio_service",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.simcore_dask_service",
    "pytest_simcore.simcore_services",
    "pytest_simcore.simcore_storage_service",
    "pytest_simcore.tmp_path_extra",
]

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def project_slug_dir(services_dir: Path) -> Path:
    # uses pytest_simcore.environs.osparc_simcore_root_dir
    service_folder = services_dir / "director-v2"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_director_v2"))
    return service_folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    dirpath = Path(simcore_service_director_v2.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def project_env_devel_dict(project_slug_dir: Path) -> Dict[str, Any]:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv.dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture(scope="function")
def project_env_devel_environment(
    project_env_devel_dict: Dict[str, Any], monkeypatch
) -> Dict[str, Any]:
    for key, value in project_env_devel_dict.items():
        monkeypatch.setenv(key, value)
    return deepcopy(project_env_devel_dict)


@pytest.fixture(scope="module")
def loop() -> Iterable[asyncio.AbstractEventLoop]:
    with loop_context() as loop:
        yield loop


@pytest.fixture(scope="function")
def mock_env(monkeypatch: MonkeyPatch) -> None:
    # Works as below line in docker.compose.yml
    # ${DOCKER_REGISTRY:-itisfoundation}/dynamic-sidecar:${DOCKER_IMAGE_TAG:-latest}

    registry = os.environ.get("DOCKER_REGISTRY", "local")
    image_tag = os.environ.get("DOCKER_IMAGE_TAG", "production")

    monkeypatch.setenv(
        "DYNAMIC_SIDECAR_IMAGE", f"{registry}/dynamic-sidecar:{image_tag}"
    )
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_network_name")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")

    monkeypatch.setenv("POSTGRES_HOST", "mocked_host")
    monkeypatch.setenv("POSTGRES_USER", "mocked_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mocked_password")
    monkeypatch.setenv("POSTGRES_DB", "mocked_db")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "false")

    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # disable tracing as together with LifespanManager, it does not remove itself nicely
    monkeypatch.setenv("DIRECTOR_V2_TRACING", "null")


@pytest.fixture(scope="function")
def client(loop: asyncio.AbstractEventLoop, mock_env: None) -> Iterable[TestClient]:
    settings = AppSettings.create_from_envs()
    app = init_app(settings)
    print("Application settings\n", pformat(settings))
    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture(scope="function")
async def initialized_app(monkeypatch: MonkeyPatch) -> AsyncIterable[FastAPI]:
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", "itisfoundation/dynamic-sidecar:MOCK")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_network_name")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    settings = AppSettings.create_from_envs()
    app = init_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture(scope="function")
async def async_client(initialized_app: FastAPI) -> AsyncIterable[httpx.AsyncClient]:

    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://director-v2.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture(scope="function")
def minimal_app(client: TestClient) -> FastAPI:
    # NOTICE that this app triggers events
    # SEE: https://fastapi.tiangolo.com/advanced/testing-events/
    return client.app


@pytest.fixture(scope="session")
def tests_dir(project_slug_dir: Path) -> Path:
    testsdir = project_slug_dir / "tests"
    assert testsdir.exists()
    return testsdir


@pytest.fixture(scope="session")
def mocks_dir(tests_dir: Path) -> Path:
    mocksdir = tests_dir / "mocks"
    assert mocksdir.exists()
    return mocksdir


@pytest.fixture(scope="session")
def fake_workbench_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "fake_workbench.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def fake_workbench(fake_workbench_file: Path) -> Workbench:
    workbench_dict = json.loads(fake_workbench_file.read_text())
    workbench = {}
    for node_id, node_data in workbench_dict.items():
        workbench[node_id] = Node.parse_obj(node_data)
    return workbench


@pytest.fixture(scope="session")
def fake_workbench_as_dict(fake_workbench_file: Path) -> Dict[str, Any]:
    workbench_dict = json.loads(fake_workbench_file.read_text())
    return workbench_dict


@pytest.fixture
def fake_workbench_without_outputs(
    fake_workbench_as_dict: Dict[str, Any]
) -> Dict[str, Any]:
    workbench = deepcopy(fake_workbench_as_dict)
    # remove all the outputs from the workbench
    for _, data in workbench.items():
        data["outputs"] = {}

    return workbench


@pytest.fixture(scope="session")
def fake_workbench_computational_adjacency_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "fake_workbench_computational_adjacency_list.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def fake_workbench_adjacency(
    fake_workbench_computational_adjacency_file: Path,
) -> Dict[str, Any]:
    return json.loads(fake_workbench_computational_adjacency_file.read_text())


@pytest.fixture(scope="session")
def fake_workbench_complete_adjacency_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "fake_workbench_complete_adj_list.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def fake_workbench_complete_adjacency(
    fake_workbench_complete_adjacency_file: Path,
) -> Dict[str, Any]:
    return json.loads(fake_workbench_complete_adjacency_file.read_text())


@pytest.fixture(scope="session")
def user_id() -> PositiveInt:
    return randint(0, 10000)


@pytest.fixture(scope="module")
def user_db(postgres_db: sa.engine.Engine, user_id: PositiveInt) -> Dict:
    with postgres_db.connect() as con:
        # removes all users before continuing
        con.execute(users.delete())
        result = con.execute(
            users.insert()
            .values(
                id=user_id,
                name="test user",
                email="test@user.com",
                password_hash="testhash",
                status=UserStatus.ACTIVE,
                role=UserRole.USER,
            )
            .returning(literal_column("*"))
        )

        user = result.first()

        yield dict(user)

        con.execute(users.delete().where(users.c.id == user_id))


@pytest.fixture
def project(
    postgres_db: sa.engine.Engine, user_db: Dict
) -> Iterable[Callable[..., ProjectAtDB]]:
    created_project_ids: List[str] = []

    def creator(**overrides) -> ProjectAtDB:
        project_config = {
            "uuid": f"{uuid4()}",
            "name": "my test project",
            "type": ProjectType.STANDARD.name,
            "description": "my test description",
            "prj_owner": user_db["id"],
            "access_rights": {"1": {"read": True, "write": True, "delete": True}},
            "thumbnail": "",
            "workbench": {},
        }
        project_config.update(**overrides)
        with postgres_db.connect() as con:
            result = con.execute(
                projects.insert()
                .values(**project_config)
                .returning(literal_column("*"))
            )

            project = ProjectAtDB.parse_obj(result.first())
            created_project_ids.append(f"{project.uuid}")
            return project

    yield creator

    # cleanup
    with postgres_db.connect() as con:
        con.execute(projects.delete().where(projects.c.uuid.in_(created_project_ids)))


@pytest.fixture
def pipeline(
    postgres_db: sa.engine.Engine,
) -> Iterable[Callable[..., CompPipelineAtDB]]:
    created_pipeline_ids: List[str] = []

    def creator(**overrides) -> CompPipelineAtDB:
        pipeline_config = {
            "project_id": f"{uuid4()}",
            "dag_adjacency_list": {},
            "state": StateType.NOT_STARTED,
        }
        pipeline_config.update(**overrides)
        with postgres_db.connect() as conn:
            result = conn.execute(
                comp_pipeline.insert()
                .values(**pipeline_config)
                .returning(literal_column("*"))
            )
            new_pipeline = CompPipelineAtDB.parse_obj(result.first())
            created_pipeline_ids.append(f"{new_pipeline.project_id}")
            return new_pipeline

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            comp_pipeline.delete().where(
                comp_pipeline.c.project_id.in_(created_pipeline_ids)
            )
        )


@pytest.fixture
def tasks(postgres_db: sa.engine.Engine) -> Iterable[Callable[..., List[CompTaskAtDB]]]:
    created_task_ids: List[int] = []

    def creator(project: ProjectAtDB, **overrides) -> List[CompTaskAtDB]:
        created_tasks: List[CompTaskAtDB] = []
        for internal_id, (node_id, node_data) in enumerate(project.workbench.items()):
            task_config = {
                "project_id": f"{project.uuid}",
                "node_id": f"{node_id}",
                "schema": {"inputs": {}, "outputs": {}},
                "inputs": {
                    key: json.loads(value.json(by_alias=True, exclude_unset=True))
                    if isinstance(value, BaseModel)
                    else value
                    for key, value in node_data.inputs.items()
                }
                if node_data.inputs
                else {},
                "outputs": {
                    key: json.loads(value.json(by_alias=True, exclude_unset=True))
                    if isinstance(value, BaseModel)
                    else value
                    for key, value in node_data.outputs.items()
                }
                if node_data.outputs
                else {},
                "image": Image(
                    name=node_data.key,
                    tag=node_data.version,
                ).dict(by_alias=True, exclude_unset=True),
                "node_class": to_node_class(node_data.key),
                "internal_id": internal_id + 1,
                "submit": datetime.utcnow(),
            }
            task_config.update(**overrides)
            with postgres_db.connect() as conn:
                result = conn.execute(
                    comp_tasks.insert()
                    .values(**task_config)
                    .returning(literal_column("*"))
                )
                new_task = CompTaskAtDB.parse_obj(result.first())
                created_tasks.append(new_task)
            created_task_ids.extend([t.task_id for t in created_tasks if t.task_id])
        return created_tasks

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            comp_tasks.delete().where(comp_tasks.c.task_id.in_(created_task_ids))
        )
