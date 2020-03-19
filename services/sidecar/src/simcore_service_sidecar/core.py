import asyncio
import json
import logging
import shutil
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# import aiofiles
import docker
from celery.utils.log import get_task_logger
from pydantic import BaseModel
from sqlalchemy import and_, exc

from servicelib.utils import logged_gather
from simcore_sdk import node_data, node_ports
from simcore_sdk.models.pipeline_models import (RUNNING, SUCCESS,
                                                ComputationalPipeline,
                                                ComputationalTask)
from simcore_sdk.node_ports import log as node_port_log
from simcore_sdk.node_ports.dbmanager import DBManager

from . import config
from .rabbitmq import RabbitMQ
from .utils import (DbSettings, DockerSettings, ExecutorSettings, S3Settings,
                    find_entry_point, is_node_ready)

log = get_task_logger(__name__)
log.setLevel(config.SIDECAR_LOGLEVEL)

node_port_log.setLevel(config.SIDECAR_LOGLEVEL)


@contextmanager
def session_scope(session_factory):
    """Provide a transactional scope around a series of operations

    """
    session = session_factory()
    try:
        yield session
    except:  # pylint: disable=W0702
        log.exception("DB access error, rolling back")
        session.rollback()
    finally:
        session.close()

class Sidecar(BaseModel):
    _rabbit_mq: RabbitMQ
    _docker: DockerSettings = DockerSettings()
    _s3: S3Settings = S3Settings()
    _db: DbSettings = DbSettings() # keeps single db engine: sidecar.utils_{id}
    _db_manager: Any = None # lazy init because still not configured. SEE _get_node_ports
    _task: ComputationalTask = None # current task
    _user_id: str = None # current user id
    _stack_name: str = None # stack name
    _executor: ExecutorSettings = ExecutorSettings() # executor options

    async def _get_node_ports(self):
        if self._db_manager is None:
            # Keeps single db engine: simcore_sdk.node_ports.dbmanager_{id}
            self._db_manager = DBManager()
        return node_ports.ports(self._db_manager)

    async def _create_shared_folders(self):
        for folder in [
            self._executor.in_dir,
            self._executor.log_dir,
            self._executor.out_dir,
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
                final_path = Path(self._executor.in_dir, mapped_filename)
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
            self._task.project_id,
            self._task.internal_id,
        )

        input_ports = dict()
        PORTS = await self._get_node_ports()
        await logged_gather(
            *[self._process_task_input(port, input_ports) for port in PORTS.inputs]
        )

        log.debug("DUMPING json")
        if input_ports:
            file_name = self._executor.in_dir / "input.json"
            with file_name.open("w") as fp:
                json.dump(input_ports, fp)
        log.debug("DUMPING DONE")

    async def _pull_image(self):
        log.debug("PULLING IMAGE")
        log.debug(
            "reg %s user %s pwd %s",
            self._docker.registry,
            self._docker.registry_user,
            self._docker.registry_pwd,
        )

        try:
            self._docker.client.login(
                registry=self._docker.registry,
                username=self._docker.registry_user,
                password=self._docker.registry_pwd,
            )
            log.debug("img %s tag %s", self._docker.image_name, self._docker.image_tag)

            self._docker.client.images.pull(
                self._docker.image_name, tag=self._docker.image_tag
            )
        except docker.errors.APIError:
            msg = f"Failed to pull image '{self._docker.image_name}:{self._docker.image_tag}' from {self._docker.registry,}"
            log.exception(msg)
            raise docker.errors.APIError(msg)

    async def log_file_processor(self, log_file: Path) -> None:
        """checks both container logs and the log_file if any
        """
        # async def parse_line(line: str) -> None:
        #     # TODO: This should be 'settings', a regex for every service
        #     if line.lower().startswith("[progress]"):
        #         progress = line.lower().lstrip(
        #             "[progress]").rstrip("%").strip()
        #         await self._post_progress(channel, progress)
        #         log.debug('PROGRESS %s', progress)
        #     elif "percent done" in line.lower():
        #         progress = line.lower().rstrip("percent done")
        #         try:
        #             float_progress = float(progress) / 100.0
        #             progress = str(float_progress)
        #             await self._post_progress(channel, progress)
        #             log.debug('PROGRESS %s', progress)
        #         except ValueError:
        #             log.exception("Could not extract progress from solver")
        #     else:
        #         # just send as log
        #         await self._post_log(channel, msg=line)

        


        # try:
        #     TIME_BETWEEN_LOGS_S: int = 2
        #     time_logs_sent = time.monotonic()
        #     accumulated_logs = []
        #     async with aiofiles.open(log_file, mode="r") as fp:
        #         async for line in fp:
        #             now = time.monotonic()
        #             accumulated_logs.append(line)
        #             if (now - time_logs_sent) < TIME_BETWEEN_LOGS_S:
        #                 continue
        #             # send logs to rabbitMQ
        #             # TODO: NEEDS to shield??
        #             with safe_channel(self._pika) as (channel, _):
        #                 await self._post_log(channel, msg=accumulated_logs)
        #                 time_logs_sent = now
        #                 accumulated_logs = []
        # except asyncio.CancelledError:
        #     # the task is complete let's send the last logs
        #     if accumulated_logs:
        #         with safe_channel(self._pika) as (channel, _):
        #             await self._post_log(channel, msg=accumulated_logs)

    # async def _bg_job(self, log_file):
    #     log.debug('Bck job started %s:node %s:internal id %s from container',
    #               self._task.project_id, self._task.node_id, self._task.internal_id)
    #     with safe_channel(self._pika) as (channel, blocking_connection):

    #         async def _follow(thefile):
    #             thefile.seek(0, 2)
    #             while self._executor.run_pool:
    #                 line = thefile.readline()
    #                 if not line:
    #                     time.sleep(1)
    #                     blocking_connection.process_data_events()
    #                     continue
    #                 yield line

    #         async def _parse_progress(line: str):
    #             # TODO: This should be 'settings', a regex for every service
    #             if line.lower().startswith("[progress]"):
    #                 progress = line.lower().lstrip(
    #                     "[progress]").rstrip("%").strip()
    #                 await self._post_progress(channel, progress)
    #                 log.debug('PROGRESS %s', progress)
    #             elif "percent done" in line.lower():
    #                 progress = line.lower().rstrip("percent done")
    #                 try:
    #                     float_progress = float(progress) / 100.0
    #                     progress = str(float_progress)
    #                     await self._post_progress(channel, progress)
    #                     log.debug('PROGRESS %s', progress)
    #                 except ValueError:
    #                     log.exception("Could not extract progress from solver")
    #                     await self._post_log(channel, line)

    #         async def _log_accumulated_logs(new_log: str, acc_logs: List[str], time_logs_sent: float):
    #             # do not overload broker with messages, we log once every 1sec
    #             TIME_BETWEEN_LOGS_S = 2.0
    #             acc_logs.append(new_log)
    #             now = time.monotonic()
    #             if (now - time_logs_sent) > TIME_BETWEEN_LOGS_S:
    #                 await self._post_log(channel, acc_logs)
    #                 log.debug('LOG %s', acc_logs)
    #                 # empty the logs
    #                 acc_logs = []
    #                 time_logs_sent = now
    #             return acc_logs, time_logs_sent

    #         acc_logs = []
    #         time_logs_sent = time.monotonic()
    #         file_path = Path(log_file)
    #         with file_path.open() as fp:
    #             for line in await _follow(fp):
    #                 if not self._executor.run_pool:
    #                     break
    #                 await _parse_progress(line)
    #                 acc_logs, time_logs_sent = _log_accumulated_logs(
    #                     line, acc_logs, time_logs_sent)
    #         if acc_logs:
    #             # send the remaining logs
    #             await self._post_log(channel, acc_logs)
    #             log.debug('LOG %s', acc_logs)

    #         # set progress to 1.0 at the end, ignore failures
    #         progress = "1.0"
    #         await self._post_progress(channel, progress)
    #         log.debug('Bck job completed %s:node %s:internal id %s from container',
    #                   self._task.project_id, self._task.node_id, self._task.internal_id)

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
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )
        PORTS = await self._get_node_ports()
        directory = self._executor.out_dir
        if not directory.exists():
            return
        try:
            for file_path in directory.rglob("*.*"):
                if file_path.name == "output.json":
                    log.debug("POSTRO FOUND output.json")
                    # parse and compare/update with the tasks output ports from db
                    with file_path.open() as fp:
                        output_ports = json.load(fp)
                        task_outputs = PORTS.outputs
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
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )

    # pylint: disable=no-self-use

    async def _process_task_log(self):
        log.debug(
            "Processing Logs %s:node %s:internal id %s from container",
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )
        directory = self._executor.log_dir
        if directory.exists():
            await node_data.data_manager.push(directory, rename_to="logs")
        log.debug(
            "Processing Logs DONE %s:node %s:internal id %s from container",
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )

    async def initialize(self, task, user_id: str):
        log.debug(
            "TASK %s of user %s FOUND, initializing...", task.internal_id, user_id
        )
        self._task = task
        self._user_id = user_id
        self._docker.image_name = self._docker.registry_name + "/" + task.schema["key"]
        self._docker.image_tag = task.schema["version"]

        # volume paths for side-car container
        self._executor.in_dir = Path.home() / f"input/{task.job_id}"
        self._executor.out_dir = Path.home() / f"output/{task.job_id}"
        self._executor.log_dir = Path.home() / f"log/{task.job_id}"

        # volume paths for car container (w/o prefix)
        self._docker.env = [
            f"{name.upper()}_FOLDER=/{name}/{task.job_id}"
            for name in ["input", "output", "log"]
        ]

        # stack name, should throw if not set
        self._stack_name = config.SWARM_STACK_NAME

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
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )
        await self._create_shared_folders()
        await logged_gather(self._process_task_inputs(), self._pull_image())
        log.debug(
            "Pre-Processing Pipeline DONE %s:node %s:internal id %s from container",
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )

    async def process(self):
        log.debug(
            "Processing Pipeline %s:node %s:internal id %s from container",
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )

        # touch output file, so it's ready for the container (v0)
        log_file = self._executor.log_dir / "log.dat"
        log_file.touch()
        log_processor_task = asyncio.ensure_future(self.log_file_processor(log_file))

        start_time = time.perf_counter()
        container = None
        try:
            docker_image = f"{self._docker.image_name}:{self._docker.image_tag}"
            container = self._docker.client.containers.run(
                docker_image,
                "run",
                init=True,
                detach=True,
                remove=False,
                volumes={
                    f"{config.SIDECAR_DOCKER_VOLUME_INPUT}": {"bind": "/input"},
                    f"{config.SIDECAR_DOCKER_VOLUME_OUTPUT}": {"bind": "/output"},
                    f"{config.SIDECAR_DOCKER_VOLUME_LOG}": {"bind": "/log"},
                },
                environment=self._docker.env,
                nano_cpus=config.SERVICES_MAX_NANO_CPUS,
                mem_limit=config.SERVICES_MAX_MEMORY_BYTES,
                labels={
                    "user_id": str(self._user_id),
                    "study_id": str(self._task.project_id),
                    "node_id": str(self._task.node_id),
                    "nano_cpus_limit": str(config.SERVICES_MAX_NANO_CPUS),
                    "mem_limit": str(config.SERVICES_MAX_MEMORY_BYTES),
                },
            )
        except docker.errors.ImageNotFound:
            log.exception("Run container: Image not found")
        except docker.errors.APIError:
            log.exception("Run Container: Server returns error")

        if container:
            try:
                while not any(
                    n in container.status for n in ["not-running", "exited", "removed"]
                ):
                    # update status
                    container.reload()
                    if (
                        (time.perf_counter() - start_time)
                        > config.SERVICES_TIMEOUT_SECONDS
                        and config.SERVICES_TIMEOUT_SECONDS > 0
                    ):
                        log.error(
                            "Running container timed-out after %ss and will be stopped now\nlogs: %s",
                            config.SERVICES_TIMEOUT_SECONDS,
                            container.logs(),
                        )
                        container.stop()

                    await asyncio.sleep(2)
                # let's get the container response here
                response = container.wait()
                log.info(
                    "container completed with response %s\nlogs: %s",
                    response,
                    container.logs(),
                )
            except docker.errors.APIError:
                log.exception("Run Container: Server returns error")
            finally:
                stop_time = time.perf_counter()
                log.info(
                    "Running %s took %sseconds", docker_image, stop_time - start_time
                )
                container.remove(force=True)
                log_processor_task.cancel()
                await log_processor_task
        else:
            log.error("Container could not be created: %s", docker_image)

        log.debug(
            "DONE Processing Pipeline %s:node %s:internal id %s from container",
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )

    async def run(self):
        log.debug(
            "Running Pipeline %s:node %s:internal id %s from container",
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )
        await self._rabbit_mq.post_log_message("Preprocessing start...")
        await self.preprocess()
        await self._rabbit_mq.post_log_message("...preprocessing end")
        
        await self._rabbit_mq.post_log_message("Processing start...")
        await self.process()
        await self._rabbit_mq.post_log_message("...processing end")

        await self._rabbit_mq.post_log_message("Postprocessing start...")
        await self.postprocess()
        await self._rabbit_mq.post_log_message("...postprocessing end")

        log.debug(
            "Running Pipeline DONE %s:node %s:internal id %s from container",
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )

    async def postprocess(self):
        log.debug(
            "Post-Processing Pipeline %s:node %s:internal id %s from container",
            self._task.project_id,
            self._task.node_id,
            self._task.internal_id,
        )

        await self._process_task_output()
        await self._process_task_log()

        self._task.state = SUCCESS
        self._task.end = datetime.utcnow()
        _session = self._db.Session()
        try:
            _session.add(self._task)
            _session.commit()
            log.debug(
                "Post-Processing Pipeline DONE %s:node %s:internal id %s from container",
                self._task.project_id,
                self._task.node_id,
                self._task.internal_id,
            )

        except exc.SQLAlchemyError:
            log.exception("Could not update job from postprocessing")
            _session.rollback()
        finally:
            _session.close()

    async def inspect(self, job_request_id: int, user_id: str, project_id: str, node_id: str):
        log.debug(
            "ENTERING inspect with user %s pipeline:node %s: %s",
            user_id,
            project_id,
            node_id,
        )

        next_task_nodes = []
        with session_scope(self._db.Session) as _session:
            _pipeline = (
                _session.query(ComputationalPipeline)
                .filter_by(project_id=project_id)
                .one()
            )

            graph = _pipeline.execution_graph
            if not node_id:
                log.debug("NODE id was zero")
                log.debug("graph looks like this %s", graph)
                next_task_nodes = find_entry_point(graph)
                log.debug("Next task nodes %s", next_task_nodes)
                return next_task_nodes

            # find the for the current node_id, skip if there is already a job_id around
            query = _session.query(ComputationalTask).filter(
                and_(
                    ComputationalTask.node_id == node_id,  # pylint: disable=no-member
                    ComputationalTask.project_id # pylint: disable=no-member
                    == project_id,  # pylint: disable=no-member
                    ComputationalTask.job_id == None, # pylint: disable=no-member
                ) 
            )
            # Use SELECT FOR UPDATE TO lock the row
            query.with_for_update()
            task = query.one_or_none()

            if not task:
                log.debug("No task found")
                return next_task_nodes

            # already done or running and happy
            if task.job_id and (task.state == SUCCESS or task.state == RUNNING):
                log.debug("TASK %s ALREADY DONE OR RUNNING", task.internal_id)
                return next_task_nodes

            # Check if node's dependecies are there
            if not is_node_ready(task, graph, _session, log):
                log.debug("TASK %s NOT YET READY", task.internal_id)
                return next_task_nodes

            # the task is ready!
            task.job_id = job_request_id
            _session.add(task)
            _session.commit()

            task = (
                _session.query(ComputationalTask)
                .filter(
                    and_(
                        ComputationalTask.node_id == node_id, # pylint: disable=no-member
                        ComputationalTask.project_id == project_id, # pylint: disable=no-member
                    )
                )
                .one()
            )

            if task.job_id != job_request_id:
                # somebody else was faster
                return next_task_nodes
            task.state = RUNNING
            task.start = datetime.utcnow()
            _session.add(task)
            _session.commit()

            await self.initialize(task, user_id)

        # now proceed actually running the task (we do that after the db session has been closed)
        # try to run the task, return empyt list of next nodes if anything goes wrong
        await self.run()
        next_task_nodes = list(graph.successors(node_id))

        return next_task_nodes


# TODO: if a singleton, then use
SIDECAR = Sidecar()

__all__ = ["SIDECAR"]
