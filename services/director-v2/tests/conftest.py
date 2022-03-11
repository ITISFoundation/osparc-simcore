# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint:disable=no-value-for-parameter

import json
import logging
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Any, AsyncIterable, Callable, Dict, Iterable, Iterator, List
from uuid import uuid4

import dotenv
import httpx
import pytest
import simcore_service_director_v2
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from models_library.clusters import Cluster
from models_library.projects import Node, ProjectAtDB, Workbench
from models_library.projects_access import GroupID
from models_library.projects_nodes_io import NodeID
from pydantic.main import BaseModel
from pydantic.types import PositiveInt
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from simcore_postgres_database.models.comp_pipeline import StateType, comp_pipeline
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB, Image
from simcore_service_director_v2.models.schemas.constants import UserID
from simcore_service_director_v2.utils.computations import to_node_class
from simcore_service_director_v2.utils.dask import generate_dask_job_id
from sqlalchemy import literal_column
from sqlalchemy.sql.expression import select
from starlette.testclient import TestClient

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
    "pytest_simcore.pytest_global_environs",
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


@pytest.fixture
def dynamic_sidecar_docker_image() -> str:
    # Works as below line in docker.compose.yml
    # ${DOCKER_REGISTRY:-itisfoundation}/dynamic-sidecar:${DOCKER_IMAGE_TAG:-latest}
    registry = os.environ.get("DOCKER_REGISTRY", "local")
    image_tag = os.environ.get("DOCKER_IMAGE_TAG", "production")
    return f"{registry}/dynamic-sidecar:{image_tag}"


@pytest.fixture(scope="function")
def mock_env(monkeypatch: MonkeyPatch, dynamic_sidecar_docker_image: str) -> None:
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", dynamic_sidecar_docker_image)
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_network_name")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")

    monkeypatch.setenv("REGISTRY_AUTH", "false")
    monkeypatch.setenv("REGISTRY_USER", "test")
    monkeypatch.setenv("REGISTRY_PW", "test")
    monkeypatch.setenv("REGISTRY_SSL", "false")

    monkeypatch.setenv("POSTGRES_HOST", "mocked_host")
    monkeypatch.setenv("POSTGRES_USER", "mocked_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mocked_password")
    monkeypatch.setenv("POSTGRES_DB", "mocked_db")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "false")

    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # disable tracing as together with LifespanManager, it does not remove itself nicely
    monkeypatch.setenv("DIRECTOR_V2_TRACING", "null")


@pytest.fixture(scope="function")
def client(mock_env: None) -> Iterable[TestClient]:
    settings = AppSettings.create_from_envs()
    app = init_app(settings)
    print("Application settings\n", pformat(settings))
    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture(scope="function")
async def initialized_app(mock_env: None) -> AsyncIterable[FastAPI]:
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


@pytest.fixture()
def user_db(
    postgres_db: sa.engine.Engine, faker: Faker
) -> Iterator[Callable[..., Dict]]:
    created_user_ids = []

    def creator(**user_kwargs) -> Dict[str, Any]:
        with postgres_db.connect() as con:
            # removes all users before continuing
            user_config = {
                "id": len(created_user_ids) + 1,
                "name": faker.name(),
                "email": faker.email(),
                "password_hash": faker.password(),
                "status": UserStatus.ACTIVE,
                "role": UserRole.USER,
            }
            user_config.update(user_kwargs)

            con.execute(
                users.insert().values(user_config).returning(literal_column("*"))
            )
            # this is needed to get the primary_gid correctly
            result = con.execute(select([users]).where(users.c.id == user_config["id"]))
            user = result.first()
            created_user_ids.append(user["id"])
        return dict(user)

    yield creator

    with postgres_db.connect() as con:
        con.execute(users.delete().where(users.c.id.in_(created_user_ids)))


@pytest.fixture
def project(postgres_db: sa.engine.Engine) -> Iterable[Callable[..., ProjectAtDB]]:
    created_project_ids: List[str] = []

    def creator(user_id: UserID, **overrides) -> ProjectAtDB:
        project_uuid = uuid4()
        print(f"Created new project with uuid={project_uuid}")
        project_config = {
            "uuid": f"{project_uuid}",
            "name": "my test project",
            "type": ProjectType.STANDARD.name,
            "description": "my test description",
            "prj_owner": user_id,
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

    def creator(**pipeline_kwargs) -> CompPipelineAtDB:
        pipeline_config = {
            "project_id": f"{uuid4()}",
            "dag_adjacency_list": {},
            "state": StateType.NOT_STARTED,
        }
        pipeline_config.update(**pipeline_kwargs)
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
def tasks(
    postgres_db: sa.engine.Engine, user_id: PositiveInt
) -> Iterable[Callable[..., List[CompTaskAtDB]]]:
    created_task_ids: List[int] = []

    def creator(project: ProjectAtDB, **overrides_kwargs) -> List[CompTaskAtDB]:
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
                "image": Image(name=node_data.key, tag=node_data.version).dict(  # type: ignore
                    by_alias=True, exclude_unset=True
                ),  # type: ignore
                "node_class": to_node_class(node_data.key),
                "internal_id": internal_id + 1,
                "submit": datetime.utcnow(),
                "job_id": generate_dask_job_id(
                    service_key=node_data.key,
                    service_version=node_data.version,
                    user_id=user_id,
                    project_id=project.uuid,
                    node_id=NodeID(node_id),
                ),
            }
            task_config.update(**overrides_kwargs)
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


@pytest.fixture
def runs(postgres_db: sa.engine.Engine) -> Iterable[Callable[..., CompRunsAtDB]]:
    created_run_ids: List[int] = []

    def creator(
        user: Dict[str, Any], project: ProjectAtDB, **run_kwargs
    ) -> CompRunsAtDB:
        run_config = {
            "project_uuid": f"{project.uuid}",
            "user_id": f"{user['id']}",
            "iteration": 1,
            "result": StateType.NOT_STARTED,
        }
        run_config.update(**run_kwargs)
        with postgres_db.connect() as conn:
            result = conn.execute(
                comp_runs.insert().values(**run_config).returning(literal_column("*"))
            )
            new_run = CompRunsAtDB.parse_obj(result.first())
            created_run_ids.append(new_run.run_id)
            return new_run

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(comp_runs.delete().where(comp_runs.c.run_id.in_(created_run_ids)))


@pytest.fixture
def cluster(
    postgres_db: sa.engine.Engine,
) -> Iterable[Callable[..., Cluster]]:
    created_cluster_ids: List[str] = []

    def creator(owner_gid: GroupID, **overrides) -> Cluster:
        cluster_config = Cluster.Config.schema_extra["examples"][0]
        cluster_config["owner"] = owner_gid
        cluster_config.update(**overrides)
        new_cluster = Cluster.parse_obj(cluster_config)
        assert new_cluster

        with postgres_db.connect() as conn:
            created_cluster_id = conn.scalar(
                # pylint: disable=no-value-for-parameter
                clusters.insert()
                .values(new_cluster.to_clusters_db(only_update=False))
                .returning(clusters.c.id)
            )
            created_cluster_ids.append(created_cluster_id)
            result = conn.execute(
                sa.select(
                    [
                        clusters,
                        cluster_to_groups.c.gid,
                        cluster_to_groups.c.read,
                        cluster_to_groups.c.write,
                        cluster_to_groups.c.delete,
                    ]
                )
                .select_from(
                    clusters.join(
                        cluster_to_groups,
                        clusters.c.id == cluster_to_groups.c.cluster_id,
                    )
                )
                .where(clusters.c.id == created_cluster_id)
            )

            row = result.fetchone()
            assert row
            return Cluster.construct(
                id=row[clusters.c.id],
                name=row[clusters.c.name],
                description=row[clusters.c.description],
                type=row[clusters.c.type],
                owner=row[clusters.c.owner],
                endpoint=row[clusters.c.endpoint],
                authentication=row[clusters.c.authentication],
                access_rights={
                    row[clusters.c.owner]: {
                        "read": row[cluster_to_groups.c.read],
                        "write": row[cluster_to_groups.c.write],
                        "delete": row[cluster_to_groups.c.delete],
                    }
                },
            )

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            # pylint: disable=no-value-for-parameter
            clusters.delete().where(clusters.c.id.in_(created_cluster_ids))
        )
