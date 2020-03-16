# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import os
from typing import Dict
from uuid import uuid4

import pytest
import sqlalchemy as sa

from simcore_sdk.models.pipeline_models import (
    ComputationalPipeline,
    ComputationalTask,
    comp_pipeline,
    comp_tasks,
)

# Selection of core and tool services started in this swarm fixture (integration)
core_services = ["storage", "postgres", "rabbit"]

ops_services = ["minio", "adminer"]


@pytest.fixture
def project_id() -> str:
    return str(uuid4())


@pytest.fixture
def user_id() -> int:
    return 1


@pytest.fixture
def node_uuid() -> str:
    return str(uuid4())


@pytest.fixture
def pipeline_db(
    postgres_session: sa.orm.session.Session, project_id: str, node_uuid
) -> ComputationalPipeline:
    pipeline = ComputationalPipeline(project_id=project_id, dag_adjacency_list={node_uuid:[]})
    postgres_session.add(pipeline)
    postgres_session.commit()
    yield pipeline

@pytest.fixture
def task_db(
    postgres_session: sa.orm.session.Session,
    sleeper_service: Dict[str, str],
    pipeline_db: ComputationalPipeline,
    node_uuid: str,
) -> ComputationalTask:
    comp_task = ComputationalTask(
        project_id=pipeline_db.project_id,
        node_id=node_uuid,
        schema=sleeper_service["schema"],
        image=sleeper_service["image"],
        inputs={},
        outputs={},
    )
    postgres_session.add(comp_task)
    postgres_session.commit()

    yield comp_task

async def test_run_sleepers(
    loop,
    docker_stack: Dict,
    postgres_session: sa.orm.session.Session,
    sleeper_service: Dict[str, str],
    task_db: ComputationalTask,
    user_id: int,
    mocker,
):
    celery_task = mocker.MagicMock()
    celery_task.request.id = 1

    # Note this must happen here since DB is set already at that time
    from sidecar.core import SIDECAR
    next_task_nodes = await SIDECAR.inspect(
        celery_task, user_id, task_db.project_id, task_db.node_id
    )
