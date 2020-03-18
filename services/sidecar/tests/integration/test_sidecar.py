# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments

import os
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4
import json
import aio_pika
import pytest
import sqlalchemy as sa
from yarl import URL

from sidecar import config
from simcore_sdk.models.pipeline_models import ComputationalPipeline, ComputationalTask

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
def create_pipeline(postgres_session: sa.orm.session.Session, project_id: str):
    def create(tasks: Dict[str, Any], dag: Dict) -> ComputationalPipeline:
        # set the pipeline
        pipeline = ComputationalPipeline(project_id=project_id, dag_adjacency_list=dag)
        postgres_session.add(pipeline)
        postgres_session.commit()
        # now create the tasks
        for node_uuid, service in tasks.items():
            comp_task = ComputationalTask(
                project_id=project_id,
                node_id=node_uuid,
                schema=service["schema"],
                image=service["image"],
                inputs={},
                outputs={},
            )
            postgres_session.add(comp_task)
            postgres_session.commit()
        return pipeline

    yield create


@pytest.fixture
def sidecar_config() -> None:
    # NOTE: in integration tests the sidecar runs bare-metal which means docker volume cannot be used.
    config.SIDECAR_DOCKER_VOLUME_INPUT = Path.home() / f"input"
    config.SIDECAR_DOCKER_VOLUME_OUTPUT = Path.home() / f"output"
    config.SIDECAR_DOCKER_VOLUME_LOG = Path.home() / f"log"


async def test_run_sleepers(
    loop,
    postgres_session: sa.orm.session.Session,
    rabbit_queue,
    storage_service: URL,
    sleeper_service: Dict[str, str],
    sidecar_config: None,
    create_pipeline,
    user_id: int,
    mocker,
):
    # NOTE: import is done here as this triggers already DB calls and setting up some settings
    from sidecar.core import SIDECAR


    async def rabbit_message_handler(message: aio_pika.IncomingMessage):
        data = json.loads(message.body)
    await rabbit_queue.consume(rabbit_message_handler, exclusive=True, no_ack=True)

    celery_task = mocker.MagicMock()
    celery_task.request.id = 1

    pipeline = create_pipeline(
        tasks={
            "node_1": sleeper_service,
            "node_2": sleeper_service,
            "node_3": sleeper_service,
            "node_4": sleeper_service,
        },
        dag={
            "node_1": ["node_2", "node_3"],
            "node_2": ["node_4"],
            "node_3": ["node_4"],
            "node_4": [],
        },
    )

    next_task_nodes = await SIDECAR.inspect(
        celery_task, user_id, pipeline.project_id, node_id=None
    )
    assert len(next_task_nodes) == 1
    assert next_task_nodes[0] == "node_1"

    for node_id in next_task_nodes:
        celery_task.request.id += 1
        next_tasks = await SIDECAR.inspect(
            celery_task, user_id, pipeline.project_id, node_id=node_id
        )
        if next_tasks:
            next_task_nodes.extend(next_tasks)
    assert next_task_nodes == ["node_1", "node_2", "node_3", "node_4", "node_4"]
