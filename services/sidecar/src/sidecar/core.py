import json
import logging
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Union

import docker
import pika
import requests
from celery.states import SUCCESS as CSUCCESS
from celery.utils.log import get_task_logger
from simcore_sdk import node_ports
from simcore_sdk.models.pipeline_models import (RUNNING, SUCCESS,
                                                ComputationalPipeline,
                                                ComputationalTask)
from simcore_sdk.node_ports import log as node_port_log
from simcore_sdk.node_ports.dbmanager import DBManager
from sqlalchemy import and_, exc

from . import config
from .utils import (DbSettings, DockerSettings, ExecutorSettings,
                    RabbitSettings, S3Settings, delete_contents,
                    find_entry_point, is_node_ready, wrap_async_call)

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
    except: # pylint: disable=W0702
        log.exception("DB access error, rolling back")
        session.rollback()
    finally:
        session.close()

class Sidecar: # pylint: disable=too-many-instance-attributes
    def __init__(self):
        # publish subscribe config
        self._pika = RabbitSettings()

        # docker client config
        self._docker = DockerSettings()

        # object storage config
        self._s3 = S3Settings()

        # db config
        self._db = DbSettings() # keeps single db engine: sidecar.utils_{id}
        self._db_manager = None # lazy init because still not configured. SEE _get_node_ports

        # current task
        self._task = None

        # current user id
        self._user_id = None

        # stack name
        self._stack_name = None

        # executor options
        self._executor = ExecutorSettings()

    def _get_node_ports(self):
        if self._db_manager is None:
            self._db_manager = DBManager() # Keeps single db engine: simcore_sdk.node_ports.dbmanager_{id}
        return node_ports.ports(self._db_manager)

    def _create_shared_folders(self):
        for folder in [self._executor.in_dir, self._executor.log_dir, self._executor.out_dir]:
            if not os.path.exists(folder):
                os.makedirs(folder)
            else:
                delete_contents(folder)

    def _process_task_input(self, port:node_ports.Port, input_ports:Dict):
        # pylint: disable=too-many-branches
        port_name = port.key
        port_value = wrap_async_call(port.get())
        log.debug("PROCESSING %s %s", port_name, port_value)
        log.debug(type(port_value))
        if str(port.type).startswith("data:"):
            path = port_value
            if not path is None:
                # the filename is not necessarily the name of the port, might be mapped
                mapped_filename = Path(path).name
                input_ports[port_name] = str(port_value)
                final_path = Path(self._executor.in_dir, mapped_filename)
                shutil.copy(str(path), str(final_path))
                log.debug("DOWNLOAD successfull from %s to %s via %s" , str(port_name), str(final_path), str(path))
            else:
                input_ports[port_name] = port_value
        else:
            input_ports[port_name] = port_value

    def _process_task_inputs(self):
        """ Writes input key-value pairs into a dictionary

            if the value of any port starts with 'link.' the corresponding
            output ports a fetched or files dowloaded --> @ jsonld

            The dictionary is dumped to input.json, files are dumped
            as port['key']. Both end up in /input/ of the container
        """
        log.debug('Input parsing for %s and node %s from container', self._task.project_id, self._task.internal_id)

        input_ports = dict()
        PORTS = self._get_node_ports()
        for port in PORTS.inputs:
            log.debug(port)
            self._process_task_input(port, input_ports)

        log.debug('DUMPING json')
        #dump json file
        if input_ports:
            file_name = os.path.join(self._executor.in_dir, 'input.json')
            with open(file_name, 'w') as f:
                json.dump(input_ports, f)

        log.debug('DUMPING DONE')

    def _pull_image(self):
        log.debug('PULLING IMAGE')
        log.debug('reg %s user %s pwd %s', self._docker.registry, self._docker.registry_user,self._docker.registry_pwd )

        try:
            self._docker.client.login(
                registry=self._docker.registry,
                username=self._docker.registry_user,
                password=self._docker.registry_pwd)
            log.debug('img %s tag %s', self._docker.image_name, self._docker.image_tag)

            self._docker.client.images.pull(self._docker.image_name, tag=self._docker.image_tag)
        except docker.errors.APIError:
            msg = f"Failed to pull image '{self._docker.image_name}:{self._docker.image_tag}' from {self._docker.registry,}"
            log.exception(msg)
            raise docker.errors.APIError(msg)

    def _log(self, channel: pika.channel.Channel, msg: Union[str, List[str]]):
        log_data = {"Channel" : "Log",
            "Node": self._task.node_id,
            "user_id": self._user_id,
            "project_id": self._task.project_id,
            "Messages" : msg if isinstance(msg, list) else [msg]
            }
        log_body = json.dumps(log_data)
        channel.basic_publish(exchange=self._pika.log_channel, routing_key='', body=log_body)

    def _progress(self, channel, progress):
        prog_data = {"Channel" : "Progress", "Node": self._task.node_id, "Progress" : progress}
        prog_body = json.dumps(prog_data)
        channel.basic_publish(exchange=self._pika.progress_channel, routing_key='', body=prog_body)

    def _bg_job(self, log_file):
        connection = pika.BlockingConnection(self._pika.parameters)

        channel = connection.channel()
        channel.exchange_declare(exchange=self._pika.log_channel, exchange_type='fanout', auto_delete=True)
        channel.exchange_declare(exchange=self._pika.progress_channel, exchange_type='fanout', auto_delete=True)

        def _follow(thefile):
            thefile.seek(0,2)
            while self._executor.run_pool:
                line = thefile.readline()
                if not line:
                    time.sleep(1)
                    continue
                yield line

        def _parse_progress(line: str):
            # TODO: This should be 'settings', a regex for every service
            if line.lower().startswith("[progress]"):
                progress = line.lower().lstrip("[progress]").rstrip("%").strip()
                self._progress(channel, progress)
                log.debug('PROGRESS %s', progress)
            elif "percent done" in line.lower():
                progress = line.lower().rstrip("percent done")
                try:
                    float_progress = float(progress) / 100.0
                    progress = str(float_progress)
                    self._progress(channel, progress)
                    log.debug('PROGRESS %s', progress)
                except ValueError:
                    log.exception("Could not extract progress from solver")
                    self._log(channel, line)

        def _log_accumulated_logs(new_log: str, acc_logs: List[str], time_logs_sent: float):
            # do not overload broker with messages, we log once every 1sec
            TIME_BETWEEN_LOGS_S = 2.0
            acc_logs.append(new_log)
            now = time.monotonic()
            if (now - time_logs_sent) > TIME_BETWEEN_LOGS_S:
                self._log(channel, acc_logs)
                log.debug('LOG %s', acc_logs)
                # empty the logs
                acc_logs = []
                time_logs_sent = now
            return acc_logs,time_logs_sent


        acc_logs = []
        time_logs_sent = time.monotonic()
        file_path = Path(log_file)
        with file_path.open() as fp:
            for line in _follow(fp):
                if not self._executor.run_pool:
                    break
                _parse_progress(line)
                acc_logs, time_logs_sent = _log_accumulated_logs(line, acc_logs, time_logs_sent)
        if acc_logs:
            # send the remaining logs
            self._log(channel, acc_logs)
            log.debug('LOG %s', acc_logs)

        # set progress to 1.0 at the end, ignore failures
        progress = "1.0"
        self._progress(channel, progress)
        connection.close()

    def _process_task_output(self):
        # pylint: disable=too-many-branches

        """ There will be some files in the /output

                - Maybe a output.json (should contain key value for simple things)
                - other files: should be named by the key in the output port

            Files will be pushed to S3 with reference in db. output.json will be parsed
            and the db updated
        """
        PORTS = self._get_node_ports()
        directory = self._executor.out_dir
        if not os.path.exists(directory):
            return
        try:
            for root, _dirs, files in os.walk(directory):
                for name in files:
                    filepath = os.path.join(root, name)
                    # the name should match what is in the db!
                    if name == 'output.json':
                        log.debug("POSTRO FOUND output.json")
                        # parse and compare/update with the tasks output ports from db
                        output_ports = dict()
                        with open(filepath) as f:
                            output_ports = json.load(f)
                            task_outputs = PORTS.outputs
                            for to in task_outputs:
                                if to.key in output_ports.keys():
                                    wrap_async_call(to.set(output_ports[to.key]))
                    else:
                        wrap_async_call(PORTS.set_file_by_keymap(Path(filepath)))

        except (OSError, IOError) as _e:
            logging.exception("Could not process output")


    # pylint: disable=no-self-use
    def _process_task_log(self):
        """ There will be some files in the /log

                - put them all into S3 /logg
        """
        return
        #directory = self._executor.log_dir
        #if os.path.exists(directory):
        #    for root, _dirs, files in os.walk(directory):
        #        for name in files:
        #            filepath = os.path.join(root, name)
        #            object_name = str(self._task.project_id) + "/" + self._task.node_id + "/log/" + name
        #            # if not self._s3.client.upload_file(self._s3.bucket, object_name, filepath):
        #            #     log.error("Error uploading file to S3")


    def initialize(self, task, user_id):
        self._task = task
        self._user_id = user_id

        HOMEDIR = str(Path.home())

        self._docker.image_name = self._docker.registry_name + "/" + task.image['name']
        self._docker.image_tag = task.image['tag']
        self._docker.env = []

        tails = dict( (name, Path(name, task.job_id).as_posix()) for name in ("input", "output", "log") )

        # volume paths for side-car container
        self._executor.in_dir = os.path.join(HOMEDIR, tails['input'])
        self._executor.out_dir = os.path.join(HOMEDIR, tails['output'])
        self._executor.log_dir = os.path.join(HOMEDIR, tails['log'])

        # volume paths for car container (w/o prefix)
        self._docker.env = ["{}_FOLDER=/{}".format(name.upper(), tail) for name, tail in tails.items()]

        # stack name, should throw if not set
        self._stack_name = config.SWARM_STACK_NAME

        # config nodeports
        node_ports.node_config.USER_ID = user_id
        node_ports.node_config.NODE_UUID = task.node_id
        node_ports.node_config.PROJECT_ID = task.project_id


    def preprocess(self):
        log.debug('Pre-Processing Pipeline %s and node %s from container', self._task.project_id, self._task.internal_id)
        self._create_shared_folders()
        self._process_task_inputs()
        self._pull_image()


    def process(self):
        log.debug('Processing Pipeline %s and node %s from container', self._task.project_id, self._task.internal_id)

        self._executor.run_pool = True

        # touch output file
        log_file = os.path.join(self._executor.log_dir, "log.dat")

        Path(log_file).touch()
        fut = self._executor.pool.submit(self._bg_job, log_file)

        start_time = time.perf_counter()
        container = None
        try:
            docker_image = self._docker.image_name + ":" + self._docker.image_tag
            container = self._docker.client.containers.run(docker_image, "run",
                                                            init=True,
                                                            detach=True, remove=False,
                                                            volumes = {'{}_input'.format(self._stack_name)  : {'bind' : '/input'},
                                                            '{}_output'.format(self._stack_name) : {'bind' : '/output'},
                                                            '{}_log'.format(self._stack_name)    : {'bind'  : '/log'}},
                                                            environment=self._docker.env,
                                                            nano_cpus=config.SERVICES_MAX_NANO_CPUS,
                                                            mem_limit=config.SERVICES_MAX_MEMORY_BYTES,
                                                            labels={
                                                                'user_id': str(self._user_id),
                                                                'study_id': str(self._task.project_id),
                                                                'node_id': str(self._task.node_id),
                                                                'nano_cpus_limit': str(config.SERVICES_MAX_NANO_CPUS),
                                                                'mem_limit': str(config.SERVICES_MAX_MEMORY_BYTES)
                                                            })
        except docker.errors.ImageNotFound:
            log.exception("Run container: Image not found")
        except docker.errors.APIError:
            log.exception("Run Container: Server returns error")

        if container:
            try:
                wait_arguments = {}
                if config.SERVICES_TIMEOUT_SECONDS > 0:
                    wait_arguments["timeout"] = int(config.SERVICES_TIMEOUT_SECONDS)
                response = container.wait(**wait_arguments)
                log.info("container completed with response %s\nlogs: %s", response, container.logs())
            except requests.exceptions.ConnectionError:
                log.exception("Running container timed-out after %ss and will be killed now\nlogs: %s", config.SERVICES_TIMEOUT_SECONDS, container.logs())
            except docker.errors.APIError:
                log.exception("Run Container: Server returns error")
            finally:
                stop_time = time.perf_counter()
                log.info("Running %s took %sseconds", docker_image, stop_time-start_time)
                container.remove(force=True)

        time.sleep(1)
        self._executor.run_pool = False
        while not fut.done():
            time.sleep(0.1)

        log.debug('DONE Processing Pipeline %s and node %s from container', self._task.project_id, self._task.internal_id)


    @contextmanager
    def safe_log_channel(self):
        connection = pika.BlockingConnection(self._pika.parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange=self._pika.log_channel, exchange_type='fanout', auto_delete=True)
        try:
            yield channel
        finally:
            connection.close()


    def run(self):
        with self.safe_log_channel() as channel:
            msg = "Preprocessing start..."
            self._log(channel, msg)

        self.preprocess()

        with self.safe_log_channel() as channel:
            msg = "...preprocessing end"
            self._log(channel, msg)
            msg = "Processing start..."
            self._log(channel, msg)

        self.process()

        with self.safe_log_channel() as channel:
            msg = "...processing end"
            self._log(channel, msg)
            msg = "Postprocessing start..."
            self._log(channel, msg)

        self.postprocess()

        with self.safe_log_channel() as channel:
            msg = "...postprocessing end"
            self._log(channel, msg)


    def postprocess(self):
        #log.debug('Post-Processing Pipeline %s and node %s from container', self._task.project_id, self._task.internal_id)

        self._process_task_output()
        self._process_task_log()

        self._task.state = SUCCESS
        _session = self._db.Session()
        try:
            _session.add(self._task)
            _session.commit()
           # log.debug('DONE Post-Processing Pipeline %s and node %s from container', self._task.project_id, self._task.internal_id)

        except exc.SQLAlchemyError:
            log.exception("Could not update job from postprocessing")
            _session.rollback()
        finally:
            _session.close()


    def inspect(self, celery_task, user_id, project_id, node_id):
        log.debug("ENTERING inspect pipeline:node %s: %s", project_id, node_id)

        next_task_nodes = []
        do_run = False

        with session_scope(self._db.Session) as _session:
            _pipeline =_session.query(ComputationalPipeline).filter_by(project_id=project_id).one()

            graph = _pipeline.execution_graph
            if node_id:
                do_process = True
                # find the for the current node_id, skip if there is already a job_id around
                # pylint: disable=assignment-from-no-return
                # pylint: disable=no-member
                query =_session.query(ComputationalTask).filter(
                    and_(   ComputationalTask.node_id==node_id,
                            ComputationalTask.project_id==project_id,
                            ComputationalTask.job_id==None )
                )
                # Use SELECT FOR UPDATE TO lock the row
                query.with_for_update()
                task = query.one()

                if task == None:
                    return next_task_nodes

                # already done or running and happy
                if task.job_id and (task.state == SUCCESS or task.state == RUNNING):
                    log.debug("TASK %s ALREADY DONE OR RUNNING", task.internal_id)
                    do_process = False

                # Check if node's dependecies are there
                if not is_node_ready(task, graph, _session, log):
                    log.debug("TASK %s NOT YET READY", task.internal_id)
                    do_process = False

                if do_process:
                    task.job_id = celery_task.request.id
                    _session.add(task)
                    _session.commit()

                    task =_session.query(ComputationalTask).filter(
                        and_(ComputationalTask.node_id==node_id,ComputationalTask.project_id==project_id)).one()

                    if task.job_id != celery_task.request.id:
                        # somebody else was faster
                        # return next_task_nodes
                        pass
                    else:
                        task.state = RUNNING
                        _session.add(task)
                        _session.commit()

                        self.initialize(task, user_id)

                        do_run = True
            else:
                log.debug("NODE id was zero")
                log.debug("graph looks like this %s", graph)

                next_task_nodes = find_entry_point(graph)
                log.debug("Next task nodes %s", next_task_nodes)

            celery_task.update_state(state=CSUCCESS)

        # now proceed actually running the task (we do that after the db session has been closed)
        if do_run:
            # try to run the task, return empyt list of next nodes if anything goes wrong
            self.run()
            next_task_nodes = list(graph.successors(node_id))

        return next_task_nodes


# TODO: if a singleton, then use
SIDECAR = Sidecar()

__all__ = [
    "SIDECAR"
]
