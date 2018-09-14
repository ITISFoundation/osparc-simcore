# TODO: PC->MaG, please check if something missing and delete

import json
import logging
import os
import time
from pathlib import Path

import docker
import pika
from celery import Celery
from celery.states import SUCCESS as CSUCCESS
from celery.utils.log import get_task_logger
from sqlalchemy import and_, exc
from sqlalchemy.orm.attributes import flag_modified

from simcore_sdk.config.rabbit import Config as rabbit_config
from simcore_sdk.models.pipeline_models import (RUNNING, SUCCESS,
                                                ComputationalPipeline,
                                                ComputationalTask)

from .utils import (DbSettings, DockerSettings, ExecutorSettings,
                    RabbitSettings, S3Settings, delete_contents,
                    find_entry_point, is_node_ready)

rabbit_config = rabbit_config()
celery= Celery(rabbit_config.name, broker=rabbit_config.broker, backend=rabbit_config.backend)

# TODO: configure via command line or config file
logging.basicConfig(level=logging.DEBUG)
#_LOGGER = logging.getLogger(__name__)
_LOGGER = get_task_logger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class Sidecar:
    def __init__(self):
        # publish subscribe config
        self._pika = RabbitSettings()

        # docker client config
        self._docker = DockerSettings()

        # object storage config
        self._s3 = S3Settings()

        # db config
        self._db = DbSettings()

        # current task
        self._task = None

        # executor options
        self._executor = ExecutorSettings()

    def _create_shared_folders(self):
        for folder in [self._executor.in_dir, self._executor.log_dir, self._executor.out_dir]:
            if not os.path.exists(folder):
                os.makedirs(folder)
            else:
                delete_contents(folder)

    def _process_task_input(self, port, input_ports):
        # pylint: disable=too-many-branches

        port_name = port['key']
        port_value = port['value']
        _LOGGER.debug("PROCESSING %s %s", port_name, port_value)
        _LOGGER.debug(type(port_value))
        if isinstance(port_value, str) and port_value.startswith("link."):
            if port['type'] == 'file-url':
                _LOGGER.debug('Fetch S3 %s', port_value)
                #parse the link assuming it is link.id.file.ending
                _parts = port_value.split(".")
                object_name = os.path.join(str(self._task.pipeline_id), _parts[1], ".".join(_parts[2:]))
                input_file = os.path.join(self._executor.in_dir, port_name)
                _LOGGER.debug('Downloading from  S3 %s/%s', self._s3.bucket, object_name)
                success = False
                ntry = 3
                trial = 0
                while not success and trial < ntry:
                    _LOGGER.debug('Downloading to %s trial %s from %s', input_file, trial, ntry)
                    success = self._s3.client.download_file(self._s3.bucket, object_name, input_file)
                    trial = trial + 1
                if success:
                    input_ports[port_name] = port_name
                    _LOGGER.debug("DONWLOAD successfull %s", port_name)
                else:
                    _LOGGER.debug("ERROR, input port %s not found in S3", object_name)
                    input_ports[port_name] = None
            else:
                _LOGGER.debug('Fetch DB %s', port_value)
                other_node_id = port_value.split(".")[1]
                other_output_port_id = port_value.split(".")[2]
                other_task = None
                _session = self._db.Session()
                try:
                    other_task =_session.query(ComputationalTask).filter(and_(ComputationalTask.node_id==other_node_id,
                                    ComputationalTask.pipeline_id==self._task.pipeline_id)).one()
                except exc.SQLAlchemyError:
                    _LOGGER.exception("Could not find other task")
                    _session.rollback()
                finally:
                    _session.close()

                if other_task is None:
                    _LOGGER.debug("ERROR, input port %s not found in db", port_value)
                else:
                    for oport in other_task.output:
                        if oport['key'] == other_output_port_id:
                            input_ports[port_name] = oport['value']
        else:
            _LOGGER.debug('Non link data %s : %s', port_name, port_value)
            input_ports[port_name] = port_value

    def _process_task_inputs(self):
        """ Writes input key-value pairs into a dictionary

            if the value of any port starts with 'link.' the corresponding
            output ports a fetched or files dowloaded --> @ jsonld

            The dictionary is dumped to input.json, files are dumped
            as port['key']. Both end up in /input/ of the container
        """
        _input = self._task.input
        _LOGGER.debug('Input parsing for %s and node %s from container', self._task.pipeline_id, self._task.internal_id)
        _LOGGER.debug(_input)

        input_ports = dict()
        for port in _input:
            _LOGGER.debug(port)
            self._process_task_input(port, input_ports)

        _LOGGER.debug('DUMPING json')
        #dump json file
        if input_ports:
            file_name = os.path.join(self._executor.in_dir, 'input.json')
            with open(file_name, 'w') as f:
                json.dump(input_ports, f)

        _LOGGER.debug('DUMPING DONE')

    def _pull_image(self):
        _LOGGER.debug('PULLING IMAGE')
        _LOGGER.debug('reg %s user %s pwd %s', self._docker.registry, self._docker.registry_user,self._docker.registry_pwd )

        try:
            self._docker.client.login(registry=self._docker.registry,
                username=self._docker.registry_user, password=self._docker.registry_pwd)
            _LOGGER.debug('img %s tag %s', self._docker.image_name, self._docker.image_tag)
            self._docker.client.images.pull(self._docker.image_name, tag=self._docker.image_tag)
        except docker.errors.APIError:
            _LOGGER.exception("Pulling image failed")
            raise docker.errors.APIError


    def _log(self, channel, msg):
        log_data = {"Channel" : "Log", "Node": self._task.node_id, "Message" : msg}
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

        with open(log_file) as file_:
            # Go to the end of file
            file_.seek(0,2)
            while self._executor.run_pool:
                curr_position = file_.tell()
                line = file_.readline()
                if not line:
                    file_.seek(curr_position)
                    time.sleep(1)
                else:
                    clean_line = line.strip()
                    # TODO: This should be 'settings', a regex for every service
                    if clean_line.lower().startswith("[progress]"):
                        progress = clean_line.lower().lstrip("[progress]").rstrip("%").strip()
                        self._progress(channel, progress)
                        _LOGGER.debug('PROGRESS %s', progress)
                    elif "percent done" in clean_line.lower():
                        progress = clean_line.lower().rstrip("percent done")
                        try:
                            float_progress = float(progress) / 100.0
                            progress = str(float_progress)
                            self._progress(channel, progress)
                            _LOGGER.debug('PROGRESS %s', progress)
                        except ValueError:
                            _LOGGER.exception("Could not extract progress from solver")
                            self._log(channel, clean_line)
                    else:
                        self._log(channel, clean_line)
                        _LOGGER.debug('LOG %s', clean_line)

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
        directory = self._executor.out_dir
        if not os.path.exists(directory):
            return
        try:
            for root, _dirs, files in os.walk(directory):
                for name in files:
                    filepath = os.path.join(root, name)
                    # the name should match what is in the db!

                    if name == 'output.json':
                        _LOGGER.debug("POSTRO FOUND output.json")
                        # parse and compare/update with the tasks output ports from db
                        output_ports = dict()
                        with open(filepath) as f:
                            output_ports = json.load(f)
                            task_outputs = self._task.output
                            for to in task_outputs:
                                if to['key'] in output_ports.keys():
                                    to['value'] = output_ports[to['key']]
                                    _LOGGER.debug("POSTRPO to['value]' becomes %s", output_ports[to['key']])
                                    flag_modified(self._task, "output")
                                    _session = self._db.Session()
                                    try:
                                        _session.commit()
                                    except exc.SQLAlchemyError as e:
                                        _LOGGER.debug(e)
                                        _session.rollback()
                                    finally:
                                        _session.close()
                    else:
                        # we want to keep the folder structure
                        if not root == directory:
                            rel_name = os.path.relpath(root, directory)
                            name = rel_name + "/" + name

                        object_name = str(self._task.pipeline_id) + "/" + self._task.node_id + "/" + name
                        success = False
                        ntry = 3
                        trial = 0
                        while not success and trial < ntry:
                            _LOGGER.debug("POSTRO pushes to S3 %s try %s from %s", object_name, trial, ntry)
                            success = self._s3.client.upload_file(self._s3.bucket, object_name, filepath)
                            trial = trial + 1

        except (OSError, IOError) as _e:
            logging.exception("Could not process output")

    def _process_task_log(self):
        """ There will be some files in the /log

                - put them all into S3 /log
        """
        directory = self._executor.log_dir
        if os.path.exists(directory):
            for root, _dirs, files in os.walk(directory):
                for name in files:
                    filepath = os.path.join(root, name)
                    object_name = str(self._task.pipeline_id) + "/" + self._task.node_id + "/log/" + name
                    if not self._s3.client.upload_file(self._s3.bucket, object_name, filepath):
                        _LOGGER.error("Error uploading file to S3")

    def initialize(self, task):
        self._task = task

        self._docker.image_name = self._docker.registry_name + "/" + task.image['name']
        self._docker.image_tag = task.image['tag']
        self._executor.in_dir = os.path.join("/", "input", task.job_id)
        self._executor.out_dir = os.path.join("/", "output", task.job_id)
        self._executor.log_dir = os.path.join("/", "log", task.job_id)

        self._docker.env = ["INPUT_FOLDER=" + self._executor.in_dir,
                            "OUTPUT_FOLDER=" + self._executor.out_dir,
                            "LOG_FOLDER=" + self._executor.log_dir]


    def preprocess(self):
        _LOGGER.debug('Pre-Processing Pipeline %s and node %s from container', self._task.pipeline_id, self._task.internal_id)
        self._create_shared_folders()
        self._process_task_inputs()
        self._pull_image()

    def process(self):
        _LOGGER.debug('Processing Pipeline %s and node %s from container', self._task.pipeline_id, self._task.internal_id)

        self._executor.run_pool = True

        # touch output file
        log_file = os.path.join(self._executor.log_dir, "log.dat")

        Path(log_file).touch()
        fut = self._executor.pool.submit(self._bg_job, log_file)

        try:
            docker_image = self._docker.image_name + ":" + self._docker.image_tag
            self._docker.client.containers.run(docker_image, "run",
                 detach=False, remove=True,
                 volumes = {'services_input'  : {'bind' : '/input'},
                            'services_output' : {'bind' : '/output'},
                            'services_log'    : {'bind'  : '/log'}},
                 environment=self._docker.env)
        except docker.errors.ContainerError as _e:
            _LOGGER.error("Run container returned non zero exit code")
        except docker.errors.ImageNotFound as _e:
            _LOGGER.error("Run container: Image not found")
        except docker.errors.APIError as _e:
            _LOGGER.error("Run Container: Server returns error")


        time.sleep(1)
        self._executor.run_pool = False
        while not fut.done():
            time.sleep(0.1)

        _LOGGER.debug('DONE Processing Pipeline %s and node %s from container', self._task.pipeline_id, self._task.internal_id)

    def run(self):
        connection = pika.BlockingConnection(self._pika.parameters)

        channel = connection.channel()
        channel.exchange_declare(exchange=self._pika.log_channel, exchange_type='fanout', auto_delete=True)

        msg = "Preprocessing start..."
        self._log(channel, msg)
        self.preprocess()
        msg = "...preprocessing end"
        self._log(channel, msg)

        msg = "Processing start..."
        self._log(channel, msg)
        self.process()
        msg = "...processing end"
        self._log(channel, msg)

        msg = "Postprocessing start..."
        self._log(channel, msg)
        self.postprocess()
        msg = "...postprocessing end"
        self._log(channel, msg)
        connection.close()


    def postprocess(self):
        #_LOGGER.debug('Post-Processing Pipeline %s and node %s from container', self._task.pipeline_id, self._task.internal_id)

        self._process_task_output()
        self._process_task_log()

        self._task.state = SUCCESS
        _session = self._db.Session()
        try:
            _session.add(self._task)
            _session.commit()
           # _LOGGER.debug('DONE Post-Processing Pipeline %s and node %s from container', self._task.pipeline_id, self._task.internal_id)

        except exc.SQLAlchemyError:
            _LOGGER.exception("Could not update job from postprocessing")
            _session.rollback()
        finally:
            _session.close()

    def inspect(self, celery_task, pipeline_id, node_id):
        _LOGGER.debug("ENTERING inspect pipeline:node %s: %s", pipeline_id, node_id)

        next_task_nodes = []
        do_run = False

        try:
            _session = self._db.Session()
            _pipeline =_session.query(ComputationalPipeline).filter_by(pipeline_id=pipeline_id).one()

            graph = _pipeline.execution_graph
            if node_id:
                do_process = True
                # find the for the current node_id, skip if there is already a job_id around
                # pylint: disable=assignment-from-no-return
                query =_session.query(ComputationalTask).filter(and_(ComputationalTask.node_id==node_id,
                    ComputationalTask.pipeline_id==pipeline_id, ComputationalTask.job_id==None))
                # Use SELECT FOR UPDATE TO lock the row
                query.with_for_update()
                task = query.one()

                if task == None:
                    return next_task_nodes

                # already done or running and happy
                if task.job_id and (task.state == SUCCESS or task.state == RUNNING):
                    _LOGGER.debug("TASK %s ALREADY DONE OR RUNNING", task.internal_id)
                    do_process = False

                # Check if node's dependecies are there
                if not is_node_ready(task, graph, _session, _LOGGER):
                    _LOGGER.debug("TASK %s NOT YET READY", task.internal_id)
                    do_process = False

                if do_process:
                    task.job_id = celery_task.request.id
                    _session.add(task)
                    _session.commit()

                    task =_session.query(ComputationalTask).filter(
                        and_(ComputationalTask.node_id==node_id,ComputationalTask.pipeline_id==pipeline_id)).one()

                    if task.job_id != celery_task.request.id:
                        # somebody else was faster
                        # return next_task_nodes
                        pass
                    else:
                        task.state = RUNNING
                        _session.add(task)
                        _session.commit()

                        self.initialize(task)

                        do_run = True
            else:
                _LOGGER.debug("NODE id was zero")
                _LOGGER.debug("graph looks like this %s", graph)

                next_task_nodes = find_entry_point(graph)
                _LOGGER.debug("Next task nodes %s", next_task_nodes)

            celery_task.update_state(state=CSUCCESS)

        except exc.SQLAlchemyError:
            _LOGGER.exception("DB error")
            _session.rollback()

        finally:
            _session.close()

        # now proceed actually running the task (we do that after the db session has been closed)
        if do_run:
            # try to run the task, return empyt list of next nodes if anything goes wrong
            self.run()
            next_task_nodes = list(graph.successors(node_id))

        return next_task_nodes


# FIXME: this should be moved into tasks.py and need a main.py as well!
SIDECAR = Sidecar()
@celery.task(name='comp.task', bind=True)
def pipeline(self, pipeline_id, node_id=None):
    _LOGGER.debug("ENTERING run")
    next_task_nodes = []
    try:
        next_task_nodes = SIDECAR.inspect(self, pipeline_id, node_id)
    #pylint:disable=broad-except
    except Exception:
        _LOGGER.exception("Uncaught exception")

    for _node_id in next_task_nodes:
        _task = celery.send_task('comp.task', args=(pipeline_id, _node_id), kwargs={})
