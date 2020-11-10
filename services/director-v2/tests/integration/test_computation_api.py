# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter

import json
from pathlib import Path
from random import randint
from time import sleep, time
from typing import Callable, Dict
from uuid import uuid4

import pytest
import sqlalchemy as sa
from models_library.projects import RunningState, Workbench
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from pydantic.types import PositiveInt
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_service_director_v2.models.domains.comp_tasks import ComputationTaskOut
from simcore_service_director_v2.models.domains.projects import ProjectAtDB
from sqlalchemy import literal_column
from starlette import status
from starlette.testclient import TestClient
from yarl import URL

core_services = ["director", "redis", "rabbit", "sidecar", "storage", "postgres"]
ops_services = ["minio"]


@pytest.fixture(autouse=True)
def minimal_configuration(
    sleeper_service: Dict[str, str],
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    simcore_services: Dict[str, URL],
    monkeypatch,
):
    pass


@pytest.fixture
def user_id() -> PositiveInt:
    return randint(0, 10000)


@pytest.fixture(scope="session")
def sleepers_workbench_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "4sleepers_workbench.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def sleepers_workbench(sleepers_workbench_file: Path) -> Dict:
    return json.loads(sleepers_workbench_file.read_text())


@pytest.fixture
def user_db(postgres_db: sa.engine.Engine, user_id: PositiveInt) -> Dict:
    with postgres_db.connect() as con:
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

        con.execute(users.delete().where(users.c.id == user["id"]))


@pytest.fixture
def project(postgres_db: sa.engine.Engine, user_db: Dict) -> Callable:
    created_project_ids = []

    def creator(**overrides):
        project_config = {
            "uuid": uuid4(),
            "name": "my test project",
            "type": ProjectType.STANDARD.name,
            "description": "my test description",
            "prj_owner": user_db["id"],
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
            created_project_ids.append(project.uuid)
            return project

    yield creator

    # cleanup
    with postgres_db.connect() as con:
        for pid in created_project_ids:
            con.execute(projects.delete().where(projects.c.uuid == str(pid)))


def test_invalid_computation(
    client: TestClient,
    user_id: PositiveInt,
):
    entrypoint = "v2/computations"

    # create a bunch of invalid stuff
    expected_resp = status.HTTP_422_UNPROCESSABLE_ENTITY
    response = client.post(
        entrypoint,
        json={"user_id": "some invalid id", "project_id": "not a uuid"},
    )
    assert (
        response.status_code == expected_resp
    ), f"response code is {response.status_code}, error: {response.text}"

    response = client.post(
        entrypoint,
        json={"user_id": user_id, "project_id": "not a uuid"},
    )
    assert (
        response.status_code == expected_resp
    ), f"response code is {response.status_code}, error: {response.text}"

    # send an invalid project to process
    expected_resp = status.HTTP_404_NOT_FOUND
    response = client.post(
        entrypoint,
        json={"user_id": user_id, "project_id": str(uuid4())},
    )
    assert (
        response.status_code == expected_resp
    ), f"response code is {response.status_code}, error: {response.text}"


def test_empty_computation(
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
):
    entrypoint = "v2/computations"
    # send an empty project to process
    expected_resp = status.HTTP_422_UNPROCESSABLE_ENTITY
    empty_project = project()
    response = client.post(
        entrypoint,
        json={"user_id": user_id, "project_id": str(empty_project.uuid)},
    )
    assert (
        response.status_code == expected_resp
    ), f"response code is {response.status_code}, error: {response.text}"


def test_run_computation(
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
    sleepers_workbench: Dict,
):
    entrypoint = "v2/computations"
    # send a valid project with a random number of sleepers
    sleepers_project = project(workbench=sleepers_workbench)
    expected_resp = status.HTTP_201_CREATED
    response = client.post(
        entrypoint,
        json={"user_id": user_id, "project_id": str(sleepers_project.uuid)},
    )
    assert (
        response.status_code == expected_resp
    ), f"response code is {response.status_code}, error: {response.text}"

    task_out = ComputationTaskOut.parse_obj(response.json())

    assert task_out.id == sleepers_project.uuid
    assert task_out.url == f"{client.base_url}/v2/computations/{sleepers_project.uuid}"

    # now wait for the computation to finish
    MAX_TIMEOUT_S = 60
    start_time = time()
    expected_resp = status.HTTP_202_ACCEPTED

    while (time() - start_time) < MAX_TIMEOUT_S:
        response = client.get(task_out.url, params={"user_id": user_id})
        assert (
            response.status_code == expected_resp
        ), f"response code is {response.status_code}, error: {response.text}"
        task_out = ComputationTaskOut.parse_obj(response.json())
        assert task_out.id == sleepers_project.uuid
        assert (
            task_out.url == f"{client.base_url}/v2/computations/{sleepers_project.uuid}"
        )
        print("Pipeline is in ", task_out.state)
        if task_out.state not in [
            RunningState.PENDING,
            RunningState.PUBLISHED,
            RunningState.STARTED,
            RunningState.RETRY,
        ]:
            break
        print("waiting...")
        sleep(1)

    assert task_out.state == RunningState.SUCCESS


def test_abort_computation():
    pass
