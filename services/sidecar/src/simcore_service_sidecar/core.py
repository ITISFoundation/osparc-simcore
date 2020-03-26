# pylint: disable=no-member
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiodocker
import aiopg
import attr
import networkx as nx
from celery.utils.log import get_task_logger
from sqlalchemy import and_, literal_column

from servicelib.utils import fire_and_forget_task, logged_gather
from simcore_postgres_database.sidecar_models import (  # PENDING,
    FAILED,
    RUNNING,
    SUCCESS,
    UNKNOWN,
    comp_pipeline,
    comp_tasks,
)
from simcore_sdk import node_data, node_ports
from simcore_sdk.node_ports import log as node_port_log
from simcore_sdk.node_ports.dbmanager import DBManager

from . import config, exceptions
from .log_parser import LogType, monitor_logs_task
from .rabbitmq import RabbitMQ
from .utils import execution_graph, find_entry_point, is_node_ready

log = get_task_logger(__name__)
log.setLevel(config.SIDECAR_LOGLEVEL)

node_port_log.setLevel(config.SIDECAR_LOGLEVEL)


@attr.s(auto_attribs=True)
class TaskSharedVolumes:
    input_folder: Path = None
    output_folder: Path = None
    log_folder: Path = None

    @classmethod
    def from_task(cls, task: aiopg.sa.result.RowProxy):
        return cls(
            Path.home() / f"input/{task.job_id}",
            Path.home() / f"output/{task.job_id}",
            Path.home() / f"log/{task.job_id}",
        )

    def create(self) -> None:
        for folder in [
            self.input_folder,
            self.output_folder,
            self.log_folder,
        ]:
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(parents=True, exist_ok=True)


@attr.s(auto_attribs=True)
class Sidecar:
    db_engine: aiopg.sa.Engine = None
    db_manager: DBManager = None
    rabbit_mq: RabbitMQ = None
    task: aiopg.sa.result.RowProxy = None
    user_id: str = None
    stack_name: str = config.SWARM_STACK_NAME
    shared_folders: TaskSharedVolumes = None

    async def _get_node_ports(self):
        if self.db_manager is None:
            # Keeps single db engine: simcore_sdk.node_ports.dbmanager_{id}
            self.db_manager = DBManager(self.db_engine)
        return await node_ports.ports(self.db_manager)

    async def _process_task_input(self, port: node_ports.Port, input_ports: Dict):
        # pylint: disable=too-many-branches
        port_name = port.key
        port_value = await port.get()
        log.debug("PROCESSING %s %s:%s", port_name, type(port_value), port_value)
        if str(port.type).startswith("data:"):
            path = port_value
            if not path is None:
                # the filename is not necessarily the name of the port, might be mapped
                mapped_filename = Path(path).name
                input_ports[port_name] = str(port_value)
                final_path = Path(self.shared_folders.input_folder, mapped_filename)
                shutil.copy(str(path), str(final_path))
                log.debug(
                    "DOWNLOAD successfull from %s to %s via %s",
                    str(port_name),
                    str(final_path),
                    str(path),
                )
            else:
                input_ports[port_name] = port_value
        else:
            input_ports[port_name] = port_value

    async def _process_task_inputs(self):
        """ Writes input key-value pairs into a dictionary

            if the value of any port starts with 'link.' the corresponding
            output ports a fetched or files dowloaded --> @ jsonld

            The dictionary is dumped to input.json, files are dumped
            as port['key']. Both end up in /input/ of the container
        """
        log.debug(
            "Input parsing for %s and node %s from container",
            self.task.project_id,
            self.task.internal_id,
        )

        input_ports = dict()
        PORTS = await self._get_node_ports()

        await logged_gather(
            *[
                self._process_task_input(port, input_ports)
                for port in (await PORTS.inputs)
            ]
        )

        log.debug("DUMPING json")
        if input_ports:
            file_name = self.shared_folders.input_folder / "input.json"
            with file_name.open("w") as fp:
                json.dump(input_ports, fp)
        log.debug("DUMPING DONE")

    async def _pull_image(self):
        docker_image = f"{config.DOCKER_REGISTRY}/{self.task.image['name']}:{self.task.image['tag']}"
        log.debug(
            "PULLING IMAGE %s as %s with pwd %s",
            docker_image,
            config.DOCKER_USER,
            config.DOCKER_PASSWORD,
        )
        try:
            docker_client: aiodocker.Docker = aiodocker.Docker()
            await docker_client.images.pull(
                docker_image,
                auth={
                    "username": config.DOCKER_USER,
                    "password": config.DOCKER_PASSWORD,
                },
            )
        except aiodocker.exceptions.DockerError:
            msg = f"Failed to pull image '{docker_image}'"
            log.exception(msg)
            raise

    async def _process_task_output(self):
        # pylint: disable=too-many-branches

        """ There will be some files in the /output

                - Maybe a output.json (should contain key value for simple things)
                - other files: should be named by the key in the output port

            Files will be pushed to S3 with reference in db. output.json will be parsed
            and the db updated
        """
        log.debug(
            "Processing task outputs %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )
        PORTS = await self._get_node_ports()
        directory = self.shared_folders.output_folder
        if not directory.exists():
            return
        try:
            for file_path in directory.rglob("*"):
                if file_path.name == "output.json":
                    log.debug("POSTRO FOUND output.json")
                    # parse and compare/update with the tasks output ports from db
                    with file_path.open() as fp:
                        output_ports = json.load(fp)
                        task_outputs = await PORTS.outputs
                        for port in task_outputs:
                            if port.key in output_ports.keys():
                                await port.set(output_ports[port.key])
                else:
                    log.debug("Uploading %s", file_path)
                    await PORTS.set_file_by_keymap(file_path)
        except json.JSONDecodeError:
            logging.exception("Error occured while decoding output.json")
        except node_ports.exceptions.NodeportsException:
            logging.exception("Error occured while setting port")
        except (OSError, IOError):
            logging.exception("Could not process output")
        log.debug(
            "Processing task outputs DONE %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

    async def _process_task_log(self):
        log.debug(
            "Processing Logs %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )
        directory = self.shared_folders.log_folder
        if directory.exists():
            await node_data.data_manager.push(directory, rename_to="logs")
        log.debug(
            "Processing Logs DONE %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

    async def preprocess(self):
        log.debug(
            "Pre-Processing Pipeline %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )
        self.shared_folders.create()
        await logged_gather(self._process_task_inputs(), self._pull_image())
        log.debug(
            "Pre-Processing Pipeline DONE %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

    async def post_messages(self, log_type: LogType, message: str):
        if log_type == LogType.LOG:
            await self.rabbit_mq.post_log_message(
                self.user_id, self.task.project_id, self.task.node_id, message,
            )
        elif log_type == LogType.PROGRESS:
            await self.rabbit_mq.post_progress_message(
                self.user_id, self.task.project_id, self.task.node_id, message,
            )

    async def process(self):
        log.debug(
            "Processing Pipeline %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

        # touch output file, so it's ready for the container (v0)
        log_file = self.shared_folders.log_folder / "log.dat"
        log_file.touch()

        log_processor_task = fire_and_forget_task(
            monitor_logs_task(log_file, self.post_messages)
        )

        start_time = time.perf_counter()
        container = None
        docker_image = f"{config.DOCKER_REGISTRY}/{self.task.image['name']}:{self.task.image['tag']}"

        docker_container_config = {
            "Env": [
                f"{name.upper()}_FOLDER=/{name}/{self.task.job_id}"
                for name in ["input", "output", "log"]
            ],
            "Cmd": "run",
            "Image": docker_image,
            "Labels": {
                "user_id": str(self.user_id),
                "study_id": str(self.task.project_id),
                "node_id": str(self.task.node_id),
                "nano_cpus_limit": str(config.SERVICES_MAX_NANO_CPUS),
                "mem_limit": str(config.SERVICES_MAX_MEMORY_BYTES),
            },
            "HostConfig": {
                "Memory": config.SERVICES_MAX_MEMORY_BYTES,
                "NanoCPUs": config.SERVICES_MAX_NANO_CPUS,
                "Init": True,
                "AutoRemove": False,
                "Binds": [
                    f"{config.SIDECAR_DOCKER_VOLUME_INPUT}:/input",
                    f"{config.SIDECAR_DOCKER_VOLUME_OUTPUT}:/output",
                    f"{config.SIDECAR_DOCKER_VOLUME_LOG}:/log",
                ],
            },
        }

        # volume paths for car container (w/o prefix)
        container = None
        try:
            docker_client: aiodocker.Docker = aiodocker.Docker()
            container = await docker_client.containers.run(
                config=docker_container_config
            )

            container_data = await container.show()
            while container_data["State"]["Running"]:
                # reload container data
                container_data = await container.show()
                if (
                    (time.perf_counter() - start_time) > config.SERVICES_TIMEOUT_SECONDS
                    and config.SERVICES_TIMEOUT_SECONDS > 0
                ):
                    log.error(
                        "Running container timed-out after %ss and will be stopped now\nlogs: %s",
                        config.SERVICES_TIMEOUT_SECONDS,
                        await container.logs(stdout=True, stderr=True),
                    )
                    await container.stop()
                    break

            # reload container data
            container_data = await container.show()
            if container_data["State"]["ExitCode"] > 0:
                log.error(
                    "%s completed with error code %s: %s",
                    docker_image,
                    container_data["State"]["ExitCode"],
                    container_data["State"]["Error"],
                )
            else:
                log.info("%s completed with successfully!", docker_image)
        except aiodocker.exceptions.DockerContainerError:
            log.exception(
                "Error while running %s with parameters %s",
                docker_image,
                docker_container_config,
            )
        except aiodocker.exceptions.DockerError:
            log.exception(
                "Unknown error while trying to run %s with parameters %s",
                docker_image,
                docker_container_config,
            )
        finally:
            stop_time = time.perf_counter()
            log.info("Running %s took %sseconds", docker_image, stop_time - start_time)
            if container:
                await container.delete(force=True)
            # stop monitoring logs now
            log_processor_task.cancel()
            await log_processor_task

        log.debug(
            "DONE Processing Pipeline %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

    async def run(self):
        log.debug(
            "Running Pipeline %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )
        await self.rabbit_mq.post_log_message(
            self.user_id,
            self.task.project_id,
            self.task.node_id,
            "Preprocessing start...",
        )
        await self.preprocess()
        await self.rabbit_mq.post_log_message(
            self.user_id,
            self.task.project_id,
            self.task.node_id,
            "...preprocessing end",
        )

        await self.rabbit_mq.post_log_message(
            self.user_id, self.task.project_id, self.task.node_id, "Processing start..."
        )
        await self.process()
        await self.rabbit_mq.post_log_message(
            self.user_id, self.task.project_id, self.task.node_id, "...processing end"
        )

        await self.rabbit_mq.post_log_message(
            self.user_id,
            self.task.project_id,
            self.task.node_id,
            "Postprocessing start...",
        )
        await self.postprocess()
        await self.rabbit_mq.post_log_message(
            self.user_id,
            self.task.project_id,
            self.task.node_id,
            "...postprocessing end",
        )

        log.debug(
            "Running Pipeline DONE %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

    async def postprocess(self):
        log.debug(
            "Post-Processing Pipeline %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

        await self._process_task_output()
        await self._process_task_log()


async def _try_get_task_from_db(
    db_connection: aiopg.sa.SAConnection,
    graph: nx.DiGraph,
    job_request_id: int,
    project_id: str,
    node_id: str,
) -> Optional[aiopg.sa.result.RowProxy]:
    task: aiopg.sa.result.RowProxy = None
    # Use SELECT FOR UPDATE TO lock the row
    result = await db_connection.execute(
        query=comp_tasks.select(for_update=True).where(
            and_(
                comp_tasks.c.node_id == node_id,
                comp_tasks.c.project_id == project_id,
                comp_tasks.c.job_id == None,
                comp_tasks.c.state == UNKNOWN,
            )
        )
    )
    task = await result.fetchone()

    if not task:
        log.debug("No task found")
        return

    # Check if node's dependecies are there
    if not await is_node_ready(task, graph, db_connection, log):
        log.debug("TASK %s NOT YET READY", task.internal_id)
        return

    # the task is ready!
    result = await db_connection.execute(
        # FIXME: E1120:No value for argument 'dml' in method call
        # pylint: disable=E1120
        comp_tasks.update()
        .where(
            and_(
                comp_tasks.c.node_id == node_id, comp_tasks.c.project_id == project_id,
            )
        )
        .values(job_id=job_request_id, state=RUNNING, start=datetime.utcnow())
        .returning(literal_column("*"))
    )
    task = await result.fetchone()
    log.debug(
        "Task %s taken for project:node %s:%s",
        task.job_id,
        task.project_id,
        task.node_id,
    )
    return task


async def _get_pipeline_from_db(
    db_connection: aiopg.sa.SAConnection, project_id: str,
) -> aiopg.sa.result.RowProxy:
    pipeline: aiopg.sa.result.RowProxy = None
    # get the pipeline
    result = await db_connection.execute(
        comp_pipeline.select().where(comp_pipeline.c.project_id == project_id)
    )
    if result.rowcount > 1:
        raise exceptions.DatabaseError(
            f"Pipeline {result.rowcount} found instead of only one for project_id {project_id}"
        )

    pipeline = await result.first()
    if not pipeline:
        raise exceptions.DatabaseError(f"Pipeline {project_id} not found")
    log.debug("found pipeline %s", pipeline)
    return pipeline


async def inspect(
    # pylint: disable=too-many-arguments
    db_engine: aiopg.sa.Engine,
    rabbit_mq: RabbitMQ,
    job_request_id: int,
    user_id: str,
    project_id: str,
    node_id: str,
) -> List[str]:
    log.debug(
        "ENTERING inspect with user %s pipeline:node %s: %s",
        user_id,
        project_id,
        node_id,
    )

    pipeline: aiopg.sa.result.RowProxy = None
    task: aiopg.sa.result.RowProxy = None
    graph: nx.DiGraph = None
    async with db_engine.acquire() as connection:
        pipeline = await _get_pipeline_from_db(connection, project_id)
        graph = execution_graph(pipeline)
        task = await _try_get_task_from_db(
            connection, graph, job_request_id, project_id, node_id
        )

    if not node_id:
        log.debug("NODE id was zero, this was the entry node id")
        return find_entry_point(graph)
    if not task:
        raise exceptions.SidecarException("Unknown error: No task found!")

    # config nodeports
    node_ports.node_config.USER_ID = user_id
    node_ports.node_config.NODE_UUID = task.node_id
    node_ports.node_config.PROJECT_ID = task.project_id

    # now proceed actually running the task (we do that after the db session has been closed)
    # try to run the task, return empyt list of next nodes if anything goes wrong
    run_result = UNKNOWN
    next_task_nodes = []
    try:
        sidecar = Sidecar(
            db_engine=db_engine,
            rabbit_mq=rabbit_mq,
            task=task,
            user_id=user_id,
            shared_folders=TaskSharedVolumes.from_task(task),
        )
        await sidecar.run()
        run_result = SUCCESS
        next_task_nodes = list(graph.successors(node_id))
    except exceptions.SidecarException:
        run_result = FAILED
    finally:
        async with db_engine.acquire() as connection:
            await connection.execute(
                # FIXME: E1120:No value for argument 'dml' in method call
                # pylint: disable=E1120
                comp_tasks.update()
                .where(
                    and_(
                        comp_tasks.c.node_id == node_id,
                        comp_tasks.c.project_id == project_id,
                    )
                )
                .values(state=run_result, end=datetime.utcnow())
            )

    return next_task_nodes
