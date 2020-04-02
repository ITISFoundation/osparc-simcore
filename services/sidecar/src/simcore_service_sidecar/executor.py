import json
import logging
import shutil
import time
from pathlib import Path
from typing import Dict

import aiodocker
import aiopg
import attr
from celery.utils.log import get_task_logger

from servicelib.utils import fire_and_forget_task, logged_gather
from simcore_sdk import node_data, node_ports
from simcore_sdk.node_ports.dbmanager import DBManager

from . import config, exceptions
from .file_log_parser import LogType, monitor_logs_task
from .rabbitmq import RabbitMQ

log = get_task_logger(__name__)


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
        await self.post_messages(
            LogType.LOG, f"[sidecar]Downloading inputs...",
        )
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
            await self.post_messages(
                LogType.LOG,
                f"[sidecar]Pulling {self.task.image['name']}:{self.task.image['tag']}...",
            )
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
        await self.post_messages(
            LogType.LOG, f"[sidecar]Uploading outputs...",
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
        await self.post_messages(
            LogType.LOG, f"[sidecar]Uploading logs...",
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
        await self.post_messages(LogType.LOG, "[sidecar]Preprocessing...")
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
        await self.post_messages(LogType.LOG, "[sidecar]Processing...")
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
            await self.post_messages(
                LogType.LOG,
                f"[sidecar]Running {self.task.image['name']}:{self.task.image['tag']}...",
            )
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
        try:
            self.shared_folders = TaskSharedVolumes.from_task(self.task)
            await self.preprocess()
            await self.process()
            await self.postprocess()
            await self.post_messages(
                LogType.LOG, "[sidecar]...task completed successfully."
            )
        except exceptions.SidecarException:
            await self.post_messages(LogType.LOG, "[sidecar]...task failed.")
            raise

    async def postprocess(self):
        log.debug(
            "Post-Processing Pipeline %s:node %s:internal id %s from container",
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )
        await self.post_messages(LogType.LOG, "[sidecar]Postprocessing...")
        await self._process_task_output()
        await self._process_task_log()
