import asyncio
import json
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Dict, Optional

import aiopg
import attr
from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerContainerError, DockerError
from celery.utils.log import get_task_logger
from packaging import version
from servicelib.utils import fire_and_forget_task, logged_gather
from simcore_sdk import node_data, node_ports
from simcore_sdk.node_ports.dbmanager import DBManager

from . import config, exceptions
from .boot_mode import get_boot_mode
from .log_parser import LogType, monitor_logs_task
from .rabbitmq import RabbitMQ
from .utils import get_volume_mount_point

log = get_task_logger(__name__)


@attr.s(auto_attribs=True)
class TaskSharedVolumes:
    input_folder: Optional[Path] = None
    output_folder: Optional[Path] = None
    log_folder: Optional[Path] = None

    @classmethod
    def from_task(cls, task: aiopg.sa.result.RowProxy):
        return cls(
            config.SIDECAR_INPUT_FOLDER / f"{task.job_id}",
            config.SIDECAR_OUTPUT_FOLDER / f"{task.job_id}",
            config.SIDECAR_LOG_FOLDER / f"{task.job_id}",
        )

    def create(self) -> None:
        for folder in [
            self.input_folder,
            self.output_folder,
            self.log_folder,
        ]:
            if folder.exists():
                shutil.rmtree(str(folder))
            folder.mkdir(parents=True, exist_ok=True)

    def delete(self) -> None:
        for folder in [
            self.input_folder,
            self.output_folder,
            self.log_folder,
        ]:
            if folder.exists():

                def log_error(_, path, excinfo):
                    log.warning(
                        "Failed to remove %s [reason: %s]. Should consider pruning files in host later",
                        path,
                        excinfo,
                    )

                shutil.rmtree(str(folder), onerror=log_error)


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
        except asyncio.CancelledError:
            await self._post_messages(LogType.LOG, "[sidecar]...task cancelled")
            raise
        except (DockerError, exceptions.SidecarException) as exc:
            await self._post_messages(
                LogType.LOG, f"[sidecar]...task failed: {str(exc)}"
            )
            raise exceptions.SidecarException(
                f"Error while executing task {self.task}"
            ) from exc
        finally:
            await self.cleanup()

    async def preprocess(self):
        await self._post_messages(LogType.LOG, "[sidecar]Preprocessing...")
        log.debug("Pre-Processing...")
        self.shared_folders = TaskSharedVolumes.from_task(self.task)
        self.shared_folders.create()
        host_name = config.SIDECAR_HOST_HOSTNAME_PATH.read_text()
        await self._post_messages(LogType.LOG, f"[sidecar]Running on {host_name}")
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

    async def cleanup(self):
        log.debug("Cleaning...")
        await self._post_messages(LogType.LOG, "[sidecar]Cleaning...")
        if self.shared_folders:
            self.shared_folders.delete()
        await self._post_messages(LogType.LOG, "[sidecar]Cleaning completed")
        log.debug("Cleaning DONE")

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
                final_path = self.shared_folders.input_folder / mapped_filename
                shutil.copy(str(path), str(final_path))
                log.debug(
                    "DOWNLOAD successfull from %s to %s via %s",
                    port.key,
                    final_path,
                    path,
                )
                # check if the file is a zip, in that case extract all if the service does not expect a zip file
                if zipfile.is_zipfile(final_path) and (
                    str(port.type) != "data:application/zip"
                ):
                    with zipfile.ZipFile(final_path, "r") as zip_obj:
                        zip_obj.extractall(final_path.parents[0])
                    # finally remove the zip archive
                    os.remove(final_path)
            else:
                input_ports[port.key] = port_value
        else:
            input_ports[port.key] = port_value

    async def _process_task_inputs(self) -> Dict:
        log.debug("Inputs parsing...")

        input_ports: Dict = {}
        try:
            PORTS = await self._get_node_ports()
        except node_ports.exceptions.NodeNotFound:
            await self._error_message_to_ui_and_logs(
                "Missing node information in the database"
            )
            return input_ports

        await self._post_messages(
            LogType.LOG,
            "[sidecar]Downloading inputs...",
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
        async with Docker() as docker_client:
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

    async def _create_container_config(self, docker_image: str) -> Dict:
        # NOTE: Env/Binds for log folder is only necessary for integraion "0"
        env_vars = [
            f"{name.upper()}_FOLDER=/{name}/{self.task.job_id}"
            for name in [
                "input",
                "output",
                "log",
            ]
        ]
        env_vars.append(f"SC_COMP_SERVICES_SCHEDULED_AS={get_boot_mode().value}")

        host_input_path = await get_volume_mount_point(
            config.SIDECAR_DOCKER_VOLUME_INPUT
        )
        host_output_path = await get_volume_mount_point(
            config.SIDECAR_DOCKER_VOLUME_OUTPUT
        )
        host_log_path = await get_volume_mount_point(config.SIDECAR_DOCKER_VOLUME_LOG)

        docker_container_config = {
            "Env": env_vars,
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
                    # NOTE: the docker engine is mounted, so only named volumes are usable. Therefore for a selective
                    # subfolder mount we need to get the path as seen from the host computer (see https://github.com/ITISFoundation/osparc-simcore/issues/1723)
                    f"{host_input_path}/{self.task.job_id}:/input/{self.task.job_id}",
                    f"{host_output_path}/{self.task.job_id}:/output/{self.task.job_id}",
                    f"{host_log_path}/{self.task.job_id}:/log/{self.task.job_id}",
                ],
            },
        }
        return docker_container_config

    async def _start_monitoring_container(
        self, container: DockerContainer
    ) -> asyncio.Future:
        log_file = self.shared_folders.log_folder / "log.dat"
        if self.integration_version == version.parse("0.0.0"):
            # touch output file, so it's ready for the container (v0)
            log_file.touch()

            log_processor_task = fire_and_forget_task(
                monitor_logs_task(log_file, self._post_messages)
            )
            return log_processor_task
        log_processor_task = fire_and_forget_task(
            monitor_logs_task(container, self._post_messages, log_file)
        )
        return log_processor_task

    async def _run_container(self):
        start_time = time.perf_counter()
        docker_image = f"{config.DOCKER_REGISTRY}/{self.task.image['name']}:{self.task.image['tag']}"
        container_config = await self._create_container_config(docker_image)

        # volume paths for car container (w/o prefix)
        result = "FAILURE"
        log_processor_task = None
        try:
            async with Docker() as docker_client:
                await self._post_messages(
                    LogType.LOG,
                    f"[sidecar]Running {self.task.image['name']}:{self.task.image['tag']}...",
                )
                container = await docker_client.containers.create(
                    config=container_config
                )
                log_processor_task = await self._start_monitoring_container(container)
                # start the container
                await container.start()
                # indicate container is started
                await self.rabbit_mq.post_instrumentation_message(
                    {
                        "metrics": "service_started",
                        "user_id": self.user_id,
                        "project_id": self.task.project_id,
                        "service_uuid": self.task.node_id,
                        "service_type": "COMPUTATIONAL",
                        "service_key": self.task.image["name"],
                        "service_tag": self.task.image["tag"],
                    }
                )

                # wait until the container finished, either success or fail or timeout
                container_data = await container.show()
                TIME_TO_NEXT_PERDIODIC_CHECK_SECS = 2
                while container_data["State"]["Running"]:
                    await asyncio.sleep(TIME_TO_NEXT_PERDIODIC_CHECK_SECS)
                    # reload container data
                    container_data = await container.show()
                    if (
                        (time.perf_counter() - start_time)
                        > config.SERVICES_TIMEOUT_SECONDS
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
                    logs = await container.log(stdout=True, stderr=True, tail=10)
                    exc = exceptions.SidecarException(
                        f"{docker_image} completed with error code {container_data['State']['ExitCode']}:\n {container_data['State']['Error']}\n:Last logs:\n{logs}"
                    )
                    # clean up the container
                    await container.delete(force=True)
                    raise exc
                # clean up the container
                await container.delete(force=True)
                # ensure progress 1.0 is sent
                await self._post_messages(LogType.PROGRESS, "1.0")
                result = "SUCCESS"
                log.info("%s completed with successfully!", docker_image)
        except DockerContainerError:
            log.exception(
                "Error while running %s with parameters %s",
                docker_image,
                container_config,
            )
            raise
        except DockerError:
            log.exception(
                "Unknown error while trying to run %s with parameters %s",
                docker_image,
                container_config,
            )
            raise
        except asyncio.CancelledError:
            log.warning("Container run was cancelled")
            raise

        finally:
            stop_time = time.perf_counter()
            log.info("Running %s took %sseconds", docker_image, stop_time - start_time)
            # stop monitoring logs now
            if log_processor_task:
                log_processor_task.cancel()
                await log_processor_task
            # instrumentation
            await self.rabbit_mq.post_instrumentation_message(
                {
                    "metrics": "service_stopped",
                    "user_id": self.user_id,
                    "project_id": self.task.project_id,
                    "service_uuid": self.task.node_id,
                    "service_type": "COMPUTATIONAL",
                    "service_key": self.task.image["name"],
                    "service_tag": self.task.image["tag"],
                    "result": result,
                }
            )

    async def _process_task_output(self):
        """There will be some files in the /output

            - Maybe a output.json (should contain key value for simple things)
            - other files: should be named by the key in the output port

        Files will be pushed to S3 with reference in db. output.json will be parsed
        and the db updated
        """
        log.debug("Processing outputs...")
        await self._post_messages(
            LogType.LOG,
            "[sidecar]Uploading outputs...",
        )
        try:
            PORTS = await self._get_node_ports()
            stem = (
                "output"
                if self.integration_version == version.parse("0.0.0")
                else "outputs"
            )
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
        except node_ports.exceptions.NodeNotFound:
            await self._error_message_to_ui_and_logs(
                "Error: no ports info found in the database."
            )
        except json.JSONDecodeError:
            await self._error_message_to_ui_and_logs(
                "Error occurred while decoding output.json"
            )
        except node_ports.exceptions.NodeportsException:
            await self._error_message_to_ui_and_logs(
                "Error occurred while setting port"
            )
        except (OSError, IOError):
            await self._error_message_to_ui_and_logs("Could not process output")
        log.debug("Processing outputs DONE")

    async def _process_task_log(self):
        log.debug("Processing Logs...")
        await self._post_messages(
            LogType.LOG,
            "[sidecar]Uploading logs...",
        )
        if self.shared_folders.log_folder and self.shared_folders.log_folder.exists():
            await node_data.data_manager.push(
                self.shared_folders.log_folder, rename_to="logs"
            )
        log.debug("Processing Logs DONE")

    async def _post_messages(self, log_type: LogType, message: str):
        if log_type == LogType.LOG:
            await self.rabbit_mq.post_log_message(
                self.user_id,
                self.task.project_id,
                self.task.node_id,
                message,
            )
        elif log_type == LogType.PROGRESS:
            await self.rabbit_mq.post_progress_message(
                self.user_id,
                self.task.project_id,
                self.task.node_id,
                message,
            )

    async def _error_message_to_ui_and_logs(self, error_message):
        logging.exception(error_message)
        await self._post_messages(LogType.LOG, f"[ERROR]: {error_message}")
