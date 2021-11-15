# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
import asyncio
import importlib
import inspect
import json
from collections import deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import aio_pika
import pytest
import sqlalchemy as sa
from models_library.settings.celery import CeleryConfig
from models_library.settings.rabbit import RabbitConfig
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from servicelib.resources import CPU_RESOURCE_LIMIT_KEY, MEM_RESOURCE_LIMIT_KEY
from simcore_postgres_database.models.comp_pipeline import comp_pipeline
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.storage_models import projects, users
from simcore_service_sidecar import config, utils
from simcore_service_sidecar.boot_mode import BootMode
from yarl import URL

SIMCORE_S3_ID = 0

# --------------------------------------------------------------------------------------
# Selection of core and tool services started in this swarm fixture (integration)
#
# SEE packages/pytest-simcore/src/pytest_simcore/docker_compose.py
#
pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "rabbit",
    "storage",
]

pytest_simcore_ops_services_selection = ["minio", "adminer"]

# --------------------------------------------------------------------------------------


@pytest.fixture
def user_id(postgres_engine: sa.engine.Engine) -> Iterable[int]:
    # inject user in db

    # NOTE: Ideally this (and next fixture) should be done via webserver API but at this point
    # in time, the webserver service would bring more dependencies to other services
    # which would turn this test too complex.

    # pylint: disable=no-value-for-parameter
    stmt = users.insert().values(**random_user(name="test")).returning(users.c.id)
    print(str(stmt))
    with postgres_engine.connect() as conn:
        result = conn.execute(stmt)
        [usr_id] = result.fetchone()

    yield usr_id

    with postgres_engine.connect() as conn:
        conn.execute(users.delete().where(users.c.id == usr_id))


@pytest.fixture
def project_id(user_id: int, postgres_engine: sa.engine.Engine) -> Iterable[str]:
    # inject project for user in db. This will give user_id, the full project's ownership

    # pylint: disable=no-value-for-parameter
    stmt = (
        projects.insert()
        .values(**random_project(prj_owner=user_id))
        .returning(projects.c.uuid)
    )
    print(str(stmt))
    with postgres_engine.connect() as conn:
        result = conn.execute(stmt)
        [prj_uuid] = result.fetchone()

    yield prj_uuid

    with postgres_engine.connect() as conn:
        conn.execute(projects.delete().where(projects.c.uuid == prj_uuid))


@pytest.fixture
async def mock_sidecar_get_volume_mount_point(monkeypatch):
    async def mock_get_volume_mount_point(volume_name: str) -> str:
        return volume_name

    monkeypatch.setattr(utils, "get_volume_mount_point", mock_get_volume_mount_point)

    # test the monkeypatching
    fake_name = "blahblah"
    x = await utils.get_volume_mount_point(fake_name)
    assert x == fake_name


@pytest.fixture
def sidecar_config(
    postgres_host_config: Dict[str, str],
    docker_registry: str,
    rabbit_service: RabbitConfig,
    mock_sidecar_get_volume_mount_point,
) -> None:
    # NOTE: in integration tests the sidecar runs bare-metal which means docker volume cannot be used.
    config.SIDECAR_DOCKER_VOLUME_INPUT = Path.home() / "input"
    config.SIDECAR_DOCKER_VOLUME_OUTPUT = Path.home() / "output"
    config.SIDECAR_DOCKER_VOLUME_LOG = Path.home() / "log"

    config.SIDECAR_HOST_HOSTNAME_PATH = Path("/etc/hostname")

    config.DOCKER_REGISTRY = docker_registry
    config.DOCKER_USER = "simcore"
    config.DOCKER_PASSWORD = ""

    config.POSTGRES_DB = postgres_host_config["database"]
    config.POSTGRES_ENDPOINT = (
        f"{postgres_host_config['host']}:{postgres_host_config['port']}"
    )
    config.POSTGRES_USER = postgres_host_config["user"]
    config.POSTGRES_PW = postgres_host_config["password"]

    config.CELERY_CONFIG = CeleryConfig.create_from_env()


class LockedCollector:
    __slots__ = ("_lock", "_list")

    def __init__(self):
        self._lock = asyncio.Lock()
        self._list = deque()

    async def is_empty(self):
        async with self._lock:
            return len(self._list) == 0

    async def append(self, item):
        async with self._lock:
            self._list.append(item)

    async def as_list(self) -> List:
        async with self._lock:
            return list(self._list)


async def _assert_incoming_data_logs(
    tasks: List[str],
    incoming_data: LockedCollector,
    user_id: int,
    project_id: str,
    service_repo: str,
    service_tag: str,
) -> Tuple[Dict[str, List[str]], Dict[str, List[float]], Dict[str, List[str]]]:
    # check message contents
    fields = ["channel", "node_id", "project_id", "user_id"]
    sidecar_logs = {task: [] for task in tasks}
    tasks_logs = {task: [] for task in tasks}
    progress_logs = {task: [] for task in tasks}
    instrumentation_messages = {task: [] for task in tasks}
    for message in await incoming_data.as_list():
        if "metrics" in message:
            # instrumentation message
            instrumentation_messages[message["service_uuid"]].append(message)
        else:
            assert all(field in message for field in fields)
            assert message["channel"] == "logger" or message["channel"] == "progress"
            assert message["user_id"] == user_id
            assert message["project_id"] == project_id
            if message["channel"] == "logger":
                assert "messages" in message
                for log in message["messages"]:
                    if log.startswith("[sidecar]"):
                        sidecar_logs[message["node_id"]].append(log)
                    else:
                        tasks_logs[message["node_id"]].append(log)
            elif message["channel"] == "progress":
                assert "progress" in message
                progress_logs[message["node_id"]].append(float(message["progress"]))

    for task in tasks:
        # the instrumentation should have 2 messages, start and stop
        assert instrumentation_messages[task], f"{instrumentation_messages}"
        assert len(instrumentation_messages[task]) == 2, f"{instrumentation_messages}"
        assert instrumentation_messages[task][0]["metrics"] == "service_started"
        assert instrumentation_messages[task][0]["user_id"] == user_id
        assert instrumentation_messages[task][0]["project_id"] == project_id
        assert instrumentation_messages[task][0]["service_uuid"] == task
        assert instrumentation_messages[task][0]["service_type"] == "COMPUTATIONAL"
        # the key is of type simcore/services/comp|dynamic/service_name
        assert (
            instrumentation_messages[task][0]["service_key"].split("/")[-1]
            == service_repo.split("/")[-1]
        )
        assert instrumentation_messages[task][0]["service_tag"] == service_tag

        assert instrumentation_messages[task][1]["metrics"] == "service_stopped"
        assert instrumentation_messages[task][1]["user_id"] == user_id
        assert instrumentation_messages[task][1]["project_id"] == project_id
        assert instrumentation_messages[task][1]["service_uuid"] == task
        assert instrumentation_messages[task][1]["service_type"] == "COMPUTATIONAL"
        # the key is of type simcore/services/comp|dynamic/service_name
        assert (
            instrumentation_messages[task][1]["service_key"].split("/")[-1]
            == service_repo.split("/")[-1]
        )
        assert instrumentation_messages[task][1]["service_tag"] == service_tag
        assert instrumentation_messages[task][1]["result"] == "SUCCESS"

        # the sidecar should have a fixed amount of logs
        assert sidecar_logs[task], f"No sidecar logs for {task}"
        # the tasks should have a variable amount of logs
        assert tasks_logs[task], f"No logs from {task}"
        # the progress should at least have the progress 1.0 log
        assert progress_logs[task], f"No progress of {task}"
        assert 1.0 in progress_logs[task]

    return (sidecar_logs, tasks_logs, progress_logs)


@pytest.fixture(
    params=[
        "node_ports",
        "node_ports_v2",
    ]
)
async def pipeline(
    sidecar_config: None,
    postgres_db: sa.engine.Engine,
    storage_service: URL,
    osparc_service: Dict[str, str],
    user_id: int,
    project_id: str,
    pipeline_cfg: Dict,
    mock_dir: Path,
    request,
) -> str:
    """creates a full pipeline.
    NOTE: 'pipeline', defined as parametrization
    """

    tasks = {key: osparc_service for key in pipeline_cfg}
    dag = {key: pipeline_cfg[key]["next"] for key in pipeline_cfg}
    inputs = {key: pipeline_cfg[key]["inputs"] for key in pipeline_cfg}

    np = importlib.import_module(f".{request.param}", package="simcore_sdk")

    async def _create(
        tasks: Dict[str, Any],
        dag: Dict[str, List[str]],
        inputs: Dict[str, Dict[str, Any]],
    ) -> str:

        # add a pipeline
        with postgres_db.connect() as conn:
            conn.execute(
                comp_pipeline.insert().values(  # pylint: disable=no-value-for-parameter
                    project_id=project_id, dag_adjacency_list=dag
                )
            )

            # create the tasks for each pipeline's node
            for node_uuid, service in tasks.items():
                node_inputs = inputs[node_uuid]
                conn.execute(
                    comp_tasks.insert().values(  # pylint: disable=no-value-for-parameter
                        project_id=project_id,
                        node_id=node_uuid,
                        schema=service["schema"],
                        image=service["image"],
                        inputs=node_inputs,
                        state="PENDING",
                        outputs={},
                    )
                )

        # check if file must be uploaded
        # create the tasks for each pipeline's node
        for node_uuid, service in tasks.items():
            node_inputs = inputs[node_uuid]
            for input_key in node_inputs:
                if (
                    isinstance(node_inputs[input_key], dict)
                    and "path" in node_inputs[input_key]
                ):
                    # update the files in mock_dir to S3
                    print("--" * 10)
                    print_module_variables(module=np.node_config)
                    print("--" * 10)

                    PORTS = await np.ports(user_id, project_id, node_uuid)
                    await (await PORTS.inputs)[input_key].set(
                        mock_dir / node_inputs[input_key]["path"]
                    )
        return project_id

    yield await _create(tasks, dag, inputs)

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(comp_tasks.delete().where(comp_tasks.c.project_id == project_id))
        conn.execute(
            comp_pipeline.delete().where(comp_pipeline.c.project_id == project_id)
        )


SLEEPERS_STUDY = (
    "itisfoundation/sleeper",
    "1.0.0",
    {
        "a13d197a-bf8c-4e11-8a15-44a9894cbbe8": {
            "next": [
                "28bf052a-5fb8-4935-9c97-2b15109632b9",
                "dfdc165b-a10d-4049-bf4e-555bf5e7d557",
            ],
            "inputs": {},
        },
        "28bf052a-5fb8-4935-9c97-2b15109632b9": {
            "next": ["54901e30-6cd2-417b-aaf9-b458022639d2"],
            "inputs": {
                "in_1": {
                    "nodeUuid": "a13d197a-bf8c-4e11-8a15-44a9894cbbe8",
                    "output": "out_1",
                },
                "in_2": {
                    "nodeUuid": "a13d197a-bf8c-4e11-8a15-44a9894cbbe8",
                    "output": "out_2",
                },
            },
        },
        "dfdc165b-a10d-4049-bf4e-555bf5e7d557": {
            "next": ["54901e30-6cd2-417b-aaf9-b458022639d2"],
            "inputs": {
                "in_1": {
                    "nodeUuid": "a13d197a-bf8c-4e11-8a15-44a9894cbbe8",
                    "output": "out_1",
                },
                "in_2": {
                    "nodeUuid": "a13d197a-bf8c-4e11-8a15-44a9894cbbe8",
                    "output": "out_2",
                },
            },
        },
        "54901e30-6cd2-417b-aaf9-b458022639d2": {
            "next": [],
            "inputs": {
                "in_1": {
                    "nodeUuid": "28bf052a-5fb8-4935-9c97-2b15109632b9",
                    "output": "out_1",
                },
                "in_2": {
                    "nodeUuid": "dfdc165b-a10d-4049-bf4e-555bf5e7d557",
                    "output": "out_2",
                },
            },
        },
    },
)

PYTHON_RUNNER_STUDY = (
    "itisfoundation/osparc-python-runner",
    "1.0.0",
    {
        "a13d197a-bf8c-4e11-8a15-44a9894cbbe8": {
            "next": [
                "28bf052a-5fb8-4935-9c97-2b15109632b9",
                "dfdc165b-a10d-4049-bf4e-555bf5e7d557",
            ],
            "inputs": {
                "input_1": {"store": SIMCORE_S3_ID, "path": "osparc_python_sample.py"}
            },
        },
        "28bf052a-5fb8-4935-9c97-2b15109632b9": {
            "next": ["54901e30-6cd2-417b-aaf9-b458022639d2"],
            "inputs": {
                "input_1": {"store": SIMCORE_S3_ID, "path": "osparc_python_sample.py"}
            },
        },
        "dfdc165b-a10d-4049-bf4e-555bf5e7d557": {
            "next": ["54901e30-6cd2-417b-aaf9-b458022639d2"],
            "inputs": {
                "input_1": {"store": SIMCORE_S3_ID, "path": "osparc_python_sample.py"}
            },
        },
        "54901e30-6cd2-417b-aaf9-b458022639d2": {
            "next": [],
            "inputs": {
                "input_1": {"store": SIMCORE_S3_ID, "path": "osparc_python_sample.py"}
            },
        },
    },
)

PYTHON_ENV_PRINTER = (
    "itisfoundation/osparc-python-runner",
    "1.0.0",
    {
        "a13d197a-bf8c-4e11-8a15-44a9894cbbe8": {
            "next": [],
            "inputs": {
                "input_1": {
                    "store": SIMCORE_S3_ID,
                    "path": "osparc_python_print_env.py",
                }
            },
        },
    },
)


# FIXME: input schema in osparc-python-executor service is wrong
PYTHON_RUNNER_FACTORY_STUDY = (
    "itisfoundation/osparc-python-runner",
    "1.0.0",
    {
        "a13d197a-bf8c-4e11-8a15-44a9894cbbe8": {
            "next": [
                "28bf052a-5fb8-4935-9c97-2b15109632b9",
            ],
            "inputs": {
                "input_1": {"store": SIMCORE_S3_ID, "path": "osparc_python_factory.py"}
            },
        },
        "28bf052a-5fb8-4935-9c97-2b15109632b9": {
            "next": [],
            "inputs": {
                "input_1": {
                    "nodeUuid": "a13d197a-bf8c-4e11-8a15-44a9894cbbe8",
                    "output": "output_1",
                },
            },
        },
    },
)


@pytest.mark.parametrize(
    "service_repo, service_tag, pipeline_cfg",
    [
        SLEEPERS_STUDY,
        PYTHON_RUNNER_STUDY,
        PYTHON_ENV_PRINTER,
    ],
    ids=["sleepers", "python-runner-study", "python-env-printer"],
)
async def test_run_services(
    loop,
    postgres_host_config: Dict[str, str],
    postgres_session: sa.orm.session.Session,
    rabbit_queue: aio_pika.Queue,
    storage_service: URL,
    osparc_service: Dict[str, str],
    sidecar_config: None,
    pipeline: str,
    service_repo: str,
    service_tag: str,
    pipeline_cfg: Dict,
    user_id: int,
    project_id: str,
    mocker,
):
    """

    :param osparc_service: Fixture defined in pytest-simcore.docker_registry. Uses parameters service_repo, service_tag
    :type osparc_service: Dict[str, str]
    """
    incoming_data = LockedCollector()

    async def rabbit_message_handler(message: aio_pika.IncomingMessage):
        async with message.process():
            data = json.loads(message.body)
            print("incoming message", data)
            await incoming_data.append(data)

    await rabbit_queue.consume(rabbit_message_handler, exclusive=True)

    job_id = 1

    from simcore_service_sidecar import cli

    # run nodes
    for node_id in pipeline_cfg:
        job_id += 1
        await cli.run_sidecar(
            job_id, user_id, project_id, node_id, sidecar_mode=BootMode.CPU
        )

    await asyncio.sleep(15)  # wait a little bit for logs to come in
    _sidecar_logs, tasks_logs, _progress_logs = await _assert_incoming_data_logs(
        list(pipeline_cfg.keys()),
        incoming_data,
        user_id,
        project_id,
        service_repo,
        service_tag,
    )

    # check input/output/log folder is empty
    assert not list(config.SIDECAR_INPUT_FOLDER.glob("**/*"))
    assert not list(config.SIDECAR_OUTPUT_FOLDER.glob("**/*"))
    assert not list(config.SIDECAR_LOG_FOLDER.glob("**/*"))

    # The python env printer should print what he sees in the environment
    if pipeline_cfg == PYTHON_ENV_PRINTER[2]:
        logs = json.dumps(tasks_logs)
        assert CPU_RESOURCE_LIMIT_KEY in logs
        assert MEM_RESOURCE_LIMIT_KEY in logs


def print_module_variables(module):
    print(module.__name__, ":")
    for attrname in dir(module):
        if not attrname.startswith("__"):
            attr = getattr(module, attrname)
            if not inspect.ismodule(attr):
                print(" ", attrname, "=", attr)
