# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments

import json
import os
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import aio_pika
import pytest
import sqlalchemy as sa
from yarl import URL

from simcore_sdk.models.pipeline_models import ComputationalPipeline, ComputationalTask
from simcore_service_sidecar import config

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
def sidecar_config(postgres_dsn: Dict[str, str], docker_registry: str) -> None:
    # NOTE: in integration tests the sidecar runs bare-metal which means docker volume cannot be used.
    config.SIDECAR_DOCKER_VOLUME_INPUT = Path.home() / f"input"
    config.SIDECAR_DOCKER_VOLUME_OUTPUT = Path.home() / f"output"
    config.SIDECAR_DOCKER_VOLUME_LOG = Path.home() / f"log"

    config.DOCKER_REGISTRY = docker_registry
    config.DOCKER_USER = "simcore"
    config.DOCKER_PASSWORD = ""

    config.POSTGRES_DB = postgres_dsn["database"]
    config.POSTGRES_ENDPOINT = f"{postgres_dsn['host']}:{postgres_dsn['port']}"
    config.POSTGRES_USER = postgres_dsn["user"]
    config.POSTGRES_PW = postgres_dsn["password"]


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
    from simcore_service_sidecar import cli

    incoming_data = []

    async def rabbit_message_handler(message: aio_pika.IncomingMessage):
        data = json.loads(message.body)
        incoming_data.append(data)

    await rabbit_queue.consume(rabbit_message_handler, exclusive=True, no_ack=True)

    job_id = 1

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

    import asyncio

    next_task_nodes = await cli.run_sidecar(job_id, user_id, pipeline.project_id, None)
    await asyncio.sleep(5)
    assert not incoming_data
    # async with rabbit_queue.iterator() as queue_iter:
    #     async for message in queue_iter:
    #         async with message.process():

    #             incoming_data.append(json.loads(message.body))

    assert len(next_task_nodes) == 1
    assert next_task_nodes[0] == "node_1"

    for node_id in next_task_nodes:
        job_id += 1
        next_tasks = await cli.run_sidecar(
            job_id, user_id, pipeline.project_id, node_id
        )
        if next_tasks:
            next_task_nodes.extend(next_tasks)
    assert next_task_nodes == ["node_1", "node_2", "node_3", "node_4", "node_4"]
