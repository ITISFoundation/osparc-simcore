# pylint: disable=no-member
import asyncio
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union

import aiodocker
import aiofiles
import aiopg
import attr
from celery.utils.log import get_task_logger
from sqlalchemy import and_

from servicelib.utils import logged_gather
from simcore_postgres_database.sidecar_models import (
    FAILED,
    # PENDING,
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
from .rabbitmq import RabbitMQ
from .utils import ExecutorSettings, execution_graph, find_entry_point, is_node_ready

log = get_task_logger(__name__)
log.setLevel(config.SIDECAR_LOGLEVEL)

node_port_log.setLevel(config.SIDECAR_LOGLEVEL)


@attr.s
class Sidecar:
    db_engine: aiopg.sa.Engine = None
    db_manager: DBManager = None
    rabbit_mq: RabbitMQ = None
    task: comp_tasks = None  # current task
    user_id: str = None  # current user id
    stack_name: str = None  # stack name
    executor: ExecutorSettings = ExecutorSettings()  # executor options

    async def _get_node_ports(self):
        if self.db_manager is None:
            # Keeps single db engine: simcore_sdk.node_ports.dbmanager_{id}
            self.db_manager = DBManager(self.db_engine)
        return await node_ports.ports(self.db_manager)

    async def _create_shared_folders(self):
        for folder in [
            self.executor.in_dir,
            self.executor.log_dir,
            self.executor.out_dir,
        ]:
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(parents=True, exist_ok=True)

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
                final_path = Path(self.executor.in_dir, mapped_filename)
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
            file_name = self.executor.in_dir / "input.json"
            with file_name.open("w") as fp:
                json.dump(input_ports, fp)
        log.debug("DUMPING DONE")

    async def _pull_image(self):
        docker_image = f"{config.DOCKER_REGISTRY}/{self.task.schema['key']}:{self.task.schema['version']}"
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

    async def log_file_processor(self, log_file: Path) -> None:
        """checks both container logs and the log_file if any
        """

        async def parse_line(
            line: str, accumulated_messages: Dict[str, Union[str, List]]
        ) -> Dict[str, Union[str, List]]:
            # TODO: This should be 'settings', a regex for every service
            if line.lower().startswith("[progress]"):
                accumulated_messages["progress"] = (
                    line.lower().lstrip("[progress]").rstrip("%").strip()
                )
            elif "percent done" in line.lower():
                progress = line.lower().rstrip("percent done")
                try:
                    float_progress = float(progress) / 100.0
                    accumulated_messages["progress"] = str(float_progress)
                except ValueError:
                    log.exception("Could not extract progress from solver")
            else:
                accumulated_messages["log"].append(line)
            return accumulated_messages

        async def post_messages(
            accumulated_messages: Dict[str, Union[str, List]]
        ) -> None:
            await logged_gather(
                [
                    self.rabbit_mq.post_log_message(
                        self.user_id,
                        self.task.project_id,
                        self.task.node_id,
                        accumulated_messages["log"],
                    ),
                    self.rabbit_mq.post_progress_message(
                        self.user_id,
                        self.task.project_id,
                        self.task.node_id,
                        accumulated_messages["progress"],
                    ),
                ]
            )

        try:
            TIME_BETWEEN_LOGS_S: int = 2
            time_logs_sent = time.monotonic()
            accumulated_messages = {"log": [], "progress": ""}
            async with aiofiles.open(log_file, mode="r") as fp:
                async for line in fp:
                    now = time.monotonic()
                    accumulated_messages = await parse_line(line, accumulated_messages)
                    if (now - time_logs_sent) < TIME_BETWEEN_LOGS_S:
                        continue
                    # send logs to rabbitMQ (TODO: shield?)
                    await post_messages(accumulated_messages)
                    accumulated_messages = {"log": [], "progress": ""}

        except asyncio.CancelledError:
            # the task is complete let's send the last messages if any
            accumulated_messages["progress"] = "1.0"
            if accumulated_messages:
                await post_messages(accumulated_messages)

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
        directory = self.executor.out_dir
        if not directory.exists():
            return
        try:
            for file_path in directory.rglob("*.*"):
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
        directory = self.executor.log_dir
        if directory.exists():
            await node_data.data_manager.push(directory, rename_to="logs")
        log.debug(
            "Processing Logs DONE %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

    async def initialize(self, task, user_id: str):
        log.debug(
            "TASK %s of user %s FOUND, initializing...", task.internal_id, user_id
        )
        self.task = task
        self.user_id = user_id

        # volume paths for side-car container
        self.executor.in_dir = Path.home() / f"input/{task.job_id}"
        self.executor.out_dir = Path.home() / f"output/{task.job_id}"
        self.executor.log_dir = Path.home() / f"log/{task.job_id}"

        # stack name, should throw if not set
        self.stack_name = config.SWARM_STACK_NAME

        # config nodeports
        node_ports.node_config.USER_ID = user_id
        node_ports.node_config.NODE_UUID = task.node_id
        node_ports.node_config.PROJECT_ID = task.project_id
        log.debug(
            "TASK %s of user %s FOUND, initializing DONE", task.internal_id, user_id
        )

    async def preprocess(self):
        log.debug(
            "Pre-Processing Pipeline %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )
        await self._create_shared_folders()
        await logged_gather(self._process_task_inputs(), self._pull_image())
        log.debug(
            "Pre-Processing Pipeline DONE %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

    async def process(self):
        log.debug(
            "Processing Pipeline %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )

        # touch output file, so it's ready for the container (v0)
        log_file = self.executor.log_dir / "log.dat"
        log_file.touch()
        log_processor_task = asyncio.ensure_future(self.log_file_processor(log_file))

        start_time = time.perf_counter()
        container = None
        docker_image = f"{config.DOCKER_REGISTRY}/{self.task.schema['key']}:{self.task.schema['version']}"

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
                await asyncio.sleep(5)
            # reload container data
            container_data = await container.show()
            log.info(
                "%s completed with error code %s and Error %s",
                docker_image,
                container_data["State"]["ExitCode"],
                container_data["State"]["Error"],
            )
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
            await container.delete(force=True)
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

    async def inspect(
        self,
        db_engine: aiopg.sa.Engine,
        rabbit_mq: RabbitMQ,
        job_request_id: int,
        user_id: str,
        project_id: str,
        node_id: str,
    ):  # pylint: disable=too-many-arguments
        log.debug(
            "ENTERING inspect with user %s pipeline:node %s: %s",
            user_id,
            project_id,
            node_id,
        )
        self.db_engine = db_engine
        self.rabbit_mq = rabbit_mq
        next_task_nodes = []

        async with self.db_engine.acquire() as connection:

            query = comp_pipeline.select().where(
                comp_pipeline.c.project_id == project_id
            )
            result = await connection.execute(query)
            if result.rowcount > 1:
                raise exceptions.DatabaseError(
                    f"Pipeline {result.rowcount} found instead of only one for project_id {project_id}"
                )
            pipeline = await result.first()
            if not pipeline:
                raise exceptions.DatabaseError(f"Pipeline {project_id} not found")

            graph = execution_graph(pipeline)
            if not node_id:
                log.debug("NODE id was zero and graph looks like this %s", graph)
                next_task_nodes = find_entry_point(graph)
                log.debug("Next task nodes %s", next_task_nodes)
                return next_task_nodes

            # find the for the current node_id, skip if there is already a job_id around
            # Use SELECT FOR UPDATE TO lock the row
            result = await connection.execute(
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
                return next_task_nodes

            # Check if node's dependecies are there
            if not await is_node_ready(task, graph, connection, log):
                log.debug("TASK %s NOT YET READY", task.internal_id)
                return next_task_nodes

            # the task is ready!
            result = await connection.execute(
                # FIXME: E1120:No value for argument 'dml' in method call
                # pylint: disable=E1120
                comp_tasks.update()
                .where(
                    and_(
                        comp_tasks.c.node_id == node_id,
                        comp_tasks.c.project_id == project_id,
                    )
                )
                .values(job_id=job_request_id, state=RUNNING, start=datetime.utcnow())
            )

            await self.initialize(task, user_id)

        # now proceed actually running the task (we do that after the db session has been closed)
        # try to run the task, return empyt list of next nodes if anything goes wrong
        run_result = UNKNOWN
        try:
            await self.run()
            run_result = SUCCESS
            next_task_nodes = list(graph.successors(node_id))
        except exceptions.SidecarException:
            run_result = FAILED
        finally:
            async with self.db_engine.acquire() as connection:
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
