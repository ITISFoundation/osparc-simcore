# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple
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
def sidecar_config(
    postgres_dsn: Dict[str, str],
    docker_registry: str,
    rabbit_config: config.RabbitConfig,
) -> None:
    # NOTE: in integration tests the sidecar runs bare-metal which means docker volume cannot be used.
    config.SIDECAR_DOCKER_VOLUME_INPUT = Path.home() / "input"
    config.SIDECAR_DOCKER_VOLUME_OUTPUT = Path.home() / "output"
    config.SIDECAR_DOCKER_VOLUME_LOG = Path.home() / "log"

    config.DOCKER_REGISTRY = docker_registry
    config.DOCKER_USER = "simcore"
    config.DOCKER_PASSWORD = ""

    config.POSTGRES_DB = postgres_dsn["database"]
    config.POSTGRES_ENDPOINT = f"{postgres_dsn['host']}:{postgres_dsn['port']}"
    config.POSTGRES_USER = postgres_dsn["user"]
    config.POSTGRES_PW = postgres_dsn["password"]

    config.RABBIT_CONFIG = rabbit_config


def _assert_incoming_data_logs(
    tasks: List[str], incoming_data: List[Dict[str, str]], user_id: int, project_id: str
) -> Tuple[Dict[str, List[str]], Dict[str, List[float]], Dict[str, List[str]]]:
    # check message contents
    fields = ["Channel", "Node", "project_id", "user_id"]
    sidecar_logs = {task: [] for task in tasks}
    tasks_logs = {task: [] for task in tasks}
    progress_logs = {task: [] for task in tasks}
    for message in incoming_data:
        assert all([field in message for field in fields])
        assert message["Channel"] == "Log" or message["Channel"] == "Progress"
        assert message["user_id"] == user_id
        assert message["project_id"] == project_id
        if message["Channel"] == "Log":
            assert "Messages" in message
            for log in message["Messages"]:
                if log.startswith("[sidecar]"):
                    sidecar_logs[message["Node"]].append(log)
                else:
                    tasks_logs[message["Node"]].append(log)
        elif message["Channel"] == "Progress":
            assert "Progress" in message
            progress_logs[message["Node"]].append(float(message["Progress"]))

    for task in tasks:
        # the sidecar should have a fixed amount of logs
        assert sidecar_logs[task]
        # the tasks should have a variable amount of logs
        assert tasks_logs[task]
        # the progress should at least have the progress 1.0 log
        assert progress_logs[task]
        assert 1.0 in progress_logs[task]

    return (sidecar_logs, tasks_logs, progress_logs)


@pytest.fixture
async def pipeline(
    postgres_session: sa.orm.session.Session,
    storage_service: URL,
    project_id: str,
    osparc_service: Dict[str, str],
    pipeline_cfg: Dict,
    mock_dir: Path,
) -> ComputationalPipeline:
    """creates a full pipeline.
        NOTE: 'pipeline', defined as parametrization
    """
    from simcore_sdk import node_ports

    tasks = {key: osparc_service for key in pipeline_cfg}
    dag = {key: pipeline_cfg[key]["next"] for key in pipeline_cfg}
    inputs = {key: pipeline_cfg[key]["inputs"] for key in pipeline_cfg}

    async def create(
        tasks: Dict[str, Any],
        dag: Dict[str, List[str]],
        inputs: Dict[str, Dict[str, Any]],
    ) -> ComputationalPipeline:
        # set the pipeline
        pipeline = ComputationalPipeline(project_id=project_id, dag_adjacency_list=dag)
        postgres_session.add(pipeline)
        postgres_session.commit()
        # now create the tasks
        for node_uuid, service in tasks.items():
            node_inputs = inputs[node_uuid]

            comp_task = ComputationalTask(
                project_id=project_id,
                node_id=node_uuid,
                schema=service["schema"],
                image=service["image"],
                inputs=node_inputs,
                outputs={},
            )
            postgres_session.add(comp_task)
            postgres_session.commit()

            # check if file must be uploaded
            for input_key in node_inputs:
                if (
                    isinstance(node_inputs[input_key], dict)
                    and "path" in node_inputs[input_key]
                ):
                    # update the file to S3
                    node_ports.node_config.PROJECT_ID = project_id
                    node_ports.node_config.NODE_UUID = node_uuid
                    PORTS = await node_ports.ports()
                    await (await PORTS.inputs)[input_key].set(
                        mock_dir / node_inputs[input_key]["path"]
                    )
        return pipeline

    yield await create(tasks, dag, inputs)


@pytest.mark.parametrize(
    "service_repo, service_tag, pipeline_cfg",
    [
        (
            "itisfoundation/sleeper",
            "1.0.0",
            {
                "node_1": {"next": ["node_2", "node_3"], "inputs": {},},
                "node_2": {
                    "next": ["node_4"],
                    "inputs": {
                        "in_1": {"nodeUuid": "node_1", "output": "out_1"},
                        "in_2": {"nodeUuid": "node_1", "output": "out_2"},
                    },
                },
                "node_3": {
                    "next": ["node_4"],
                    "inputs": {
                        "in_1": {"nodeUuid": "node_1", "output": "out_1"},
                        "in_2": {"nodeUuid": "node_1", "output": "out_2"},
                    },
                },
                "node_4": {
                    "next": [],
                    "inputs": {
                        "in_1": {"nodeUuid": "node_2", "output": "out_1"},
                        "in_2": {"nodeUuid": "node_3", "output": "out_2"},
                    },
                },
            },
        ),
        (
            "itisfoundation/osparc-python-runner",
            "1.0.0",
            {
                "node_1": {
                    "next": ["node_2", "node_3"],
                    "inputs": {
                        "input_1": {"store": 0, "path": "osparc_python_sample.py"}
                    },
                },
                "node_2": {
                    "next": ["node_4"],
                    "inputs": {
                        "input_1": {"store": 0, "path": "osparc_python_sample.py"}
                    },
                },
                "node_3": {
                    "next": ["node_4"],
                    "inputs": {
                        "input_1": {"store": 0, "path": "osparc_python_sample.py"}
                    },
                },
                "node_4": {
                    "next": [],
                    "inputs": {
                        "input_1": {"store": 0, "path": "osparc_python_sample.py"}
                    },
                },
            },
        ),
    ],
)
async def test_run_services(
    loop,
    postgres_session: sa.orm.session.Session,
    rabbit_queue: aio_pika.Queue,
    storage_service: URL,
    osparc_service: Dict[str, str],
    sidecar_config: None,
    pipeline: ComputationalPipeline,
    pipeline_cfg: Dict,
    user_id: int,
    mocker,
):
    incoming_data = []

    async def rabbit_message_handler(message: aio_pika.IncomingMessage):
        data = json.loads(message.body)
        incoming_data.append(data)

    await rabbit_queue.consume(rabbit_message_handler, exclusive=True, no_ack=True)

    job_id = 1

    from simcore_service_sidecar import cli

    next_task_nodes = await cli.run_sidecar(job_id, user_id, pipeline.project_id, None)
    await asyncio.sleep(5)
    assert not incoming_data

    assert len(next_task_nodes) == 1
    assert next_task_nodes[0] == next(iter(pipeline_cfg))

    for node_id in next_task_nodes:
        job_id += 1
        next_tasks = await cli.run_sidecar(
            job_id, user_id, pipeline.project_id, node_id
        )
        if next_tasks:
            next_task_nodes.extend(next_tasks)
    dag = [next_task_nodes[0]]
    for key in pipeline_cfg:
        dag.extend(pipeline_cfg[key]["next"])
    assert next_task_nodes == dag

    _assert_incoming_data_logs(
        list(pipeline_cfg.keys()), incoming_data, user_id, pipeline.project_id
    )
