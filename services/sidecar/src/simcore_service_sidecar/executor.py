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
from packaging import version

from servicelib.utils import fire_and_forget_task, logged_gather
from simcore_sdk import node_data, node_ports
from simcore_sdk.node_ports.dbmanager import DBManager

from . import config, exceptions
from .log_parser import LogType, monitor_logs_task
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
class Executor:
    db_engine: aiopg.sa.Engine = None
    db_manager: DBManager = None
    rabbit_mq: RabbitMQ = None
    task: aiopg.sa.result.RowProxy = None
    user_id: str = None
    stack_name: str = config.SWARM_STACK_NAME
    shared_folders: TaskSharedVolumes = None
    integration_version: version.Version = version.parse("0.0.0")

    async def run(self):
        log.debug(
            "Running %s project:%s node:%s internal_id:%s from container",
            self.task.image["name"],
            self.task.project_id,
            self.task.node_id,
            self.task.internal_id,
        )
        try:
            await self.preprocess()
            await self.process()
            await self.postprocess()
            await self._post_messages(
                LogType.LOG, "[sidecar]...task completed successfully."
            )
        except exceptions.SidecarException:
            await self._post_messages(LogType.LOG, "[sidecar]...task failed.")
            raise

    async def preprocess(self):
        await self._post_messages(LogType.LOG, "[sidecar]Preprocessing...")
        log.debug("Pre-Processing...")
        self.shared_folders = TaskSharedVolumes.from_task(self.task)
        self.shared_folders.create()
        results = await logged_gather(self._process_task_inputs(), self._pull_image())
        await self._write_input_file(results[0])
        log.debug("Pre-Processing Pipeline DONE")

    async def process(self):
        log.debug("Processing...")
        await self._post_messages(LogType.LOG, "[sidecar]Processing...")
        await self._run_container()
        log.debug("Processing DONE")

    async def postprocess(self):
        log.debug("Post-Processing...")
        await self._post_messages(LogType.LOG, "[sidecar]Postprocessing...")
        await self._process_task_output()
        await self._process_task_log()
        log.debug("Post-Processing DONE")

    async def _get_node_ports(self):
        if self.db_manager is None:
            # Keeps single db engine: simcore_sdk.node_ports.dbmanager_{id}
            self.db_manager = DBManager(self.db_engine)
        return await node_ports.ports(self.db_manager)

    async def _process_task_input(self, port: node_ports.Port, input_ports: Dict):
        port_value = await port.get()
        log.debug("PROCESSING %s %s:%s", port.key, type(port_value), port_value)
        if str(port.type).startswith("data:"):
            path = port_value
            if path:
                # the filename is not necessarily the name of the port, might be mapped
                mapped_filename = Path(path).name
                input_ports[port.key] = str(port_value)
                final_path = Path(self.shared_folders.input_folder, mapped_filename)
                shutil.copy(str(path), str(final_path))
                log.debug(
                    "DOWNLOAD successfull from %s to %s via %s",
                    port.key,
                    final_path,
                    path,
                )
            else:
                input_ports[port.key] = port_value
        else:
            input_ports[port.key] = port_value

    async def _process_task_inputs(self) -> Dict:
        log.debug("Inputs parsing...")

        input_ports = dict()
        PORTS = await self._get_node_ports()
        await self._post_messages(
            LogType.LOG, "[sidecar]Downloading inputs...",
        )
        await logged_gather(
            *[
                self._process_task_input(port, input_ports)
                for port in (await PORTS.inputs)
            ]
        )
        log.debug("Inputs parsing DONE")
        return input_ports

    async def _write_input_file(self, inputs: Dict) -> None:
        if inputs:
            log.debug("Writing input file...")
            stem = (
                "input"
                if self.integration_version == version.parse("0.0.0")
                else "inputs"
            )
            file_name = self.shared_folders.input_folder / f"{stem}.json"
            file_name.write_text(json.dumps(inputs))
            log.debug("Writing input file DONE")

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
            await self._post_messages(
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

            # get integration version
            image_cfg = await docker_client.images.inspect(docker_image)
            # NOTE: old services did not have that label
            if "io.simcore.integration-version" in image_cfg["Config"]["Labels"]:
                self.integration_version = version.parse(
                    json.loads(
                        image_cfg["Config"]["Labels"]["io.simcore.integration-version"]
                    )["integration-version"]
                )

        except aiodocker.exceptions.DockerError:
            msg = f"Failed to pull image '{docker_image}'"
            log.exception(msg)
            raise

    async def _run_container(self):
        start_time = time.perf_counter()
        container = None
        docker_image = f"{config.DOCKER_REGISTRY}/{self.task.image['name']}:{self.task.image['tag']}"

        # NOTE: Env/Binds for log folder is only necessary for integraion "0"
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
        log.debug(
            "Running image %s with config %s", docker_image, docker_container_config
        )
        # volume paths for car container (w/o prefix)
        try:
            docker_client: aiodocker.Docker = aiodocker.Docker()
            await self._post_messages(
                LogType.LOG,
                f"[sidecar]Running {self.task.image['name']}:{self.task.image['tag']}...",
            )
            container = await docker_client.containers.create(
                config=docker_container_config
            )
            # start monitoring logs
            if self.integration_version == version.parse("0.0.0"):
                # touch output file, so it's ready for the container (v0)
                log_file = self.shared_folders.log_folder / "log.dat"
                log_file.touch()

                log_processor_task = fire_and_forget_task(
                    monitor_logs_task(log_file, self._post_messages)
                )
            else:
                log_processor_task = fire_and_forget_task(
                    monitor_logs_task(container, self._post_messages)
                )
            # start the container
            await container.start()
            # wait until the container finished, either success or fail or timeout
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
                        container.log(stdout=True, stderr=True),
                    )
                    await container.stop()
                    break

            # reload container data to check the error code with latest info
            container_data = await container.show()
            if container_data["State"]["ExitCode"] > 0:
                raise exceptions.SidecarException(
                    f"{docker_image} completed with error code {container_data['State']['ExitCode']}: {container_data['State']['Error']}"
                )
            # ensure progress 1.0 is sent
            await self._post_messages(LogType.PROGRESS, "1.0")
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
                # clean up the container
                await container.delete(force=True)
            # stop monitoring logs now
            log_processor_task.cancel()
            await log_processor_task

    async def _process_task_output(self):
        """ There will be some files in the /output

                - Maybe a output.json (should contain key value for simple things)
                - other files: should be named by the key in the output port

            Files will be pushed to S3 with reference in db. output.json will be parsed
            and the db updated
        """
        log.debug("Processing outputs...")
        await self._post_messages(
            LogType.LOG, "[sidecar]Uploading outputs...",
        )
        PORTS = await self._get_node_ports()
        stem = (
            "output"
            if self.integration_version == version.parse("0.0.0")
            else "outputs"
        )
        try:
            file_upload_tasks = []
            for file_path in self.shared_folders.output_folder.rglob("*"):
                if file_path.name == f"{stem}.json":
                    log.debug("POSTPRO found %s.json", stem)
                    # parse and compare/update with the tasks output ports from db
                    with file_path.open() as fp:
                        output_ports = json.load(fp)
                        task_outputs = await PORTS.outputs
                        for port in task_outputs:
                            if port.key in output_ports.keys():
                                await port.set(output_ports[port.key])
                else:
                    log.debug("POSTPRO found %s", file_path)
                    file_upload_tasks.append(PORTS.set_file_by_keymap(file_path))
            if file_upload_tasks:
                log.debug("POSTPRO uploading %d files...", len(file_upload_tasks))
                # WARNING: nodeports is NOT concurrent-safe, dont' use gather here
                for coro in file_upload_tasks:
                    await coro

        except json.JSONDecodeError:
            logging.exception("Error occured while decoding output.json")
        except node_ports.exceptions.NodeportsException:
            logging.exception("Error occured while setting port")
        except (OSError, IOError):
            logging.exception("Could not process output")
        log.debug("Processing outputs DONE")

    async def _process_task_log(self):
        log.debug("Processing Logs...")
        await self._post_messages(
            LogType.LOG, "[sidecar]Uploading logs...",
        )
        if self.shared_folders.log_folder.exists():
            await node_data.data_manager.push(
                self.shared_folders.log_folder, rename_to="logs"
            )
        log.debug("Processing Logs DONE")

    async def _post_messages(self, log_type: LogType, message: str):
        if log_type == LogType.LOG:
            await self.rabbit_mq.post_log_message(
                self.user_id, self.task.project_id, self.task.node_id, message,
            )
        elif log_type == LogType.PROGRESS:
            await self.rabbit_mq.post_progress_message(
                self.user_id, self.task.project_id, self.task.node_id, message,
            )
