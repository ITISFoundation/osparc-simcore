import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Dict

import docker
import pika
from celery.states import SUCCESS as CSUCCESS
from celery.utils.log import get_task_logger
from sqlalchemy import and_, exc

from simcore_sdk.models.pipeline_models import (RUNNING, SUCCESS,
                                                ComputationalPipeline,
                                                ComputationalTask)

from simcore_sdk import node_ports


from .utils import (DbSettings, DockerSettings, ExecutorSettings,
                    RabbitSettings, S3Settings, delete_contents,
                    find_entry_point, is_node_ready, wrap_async_call)

log = get_task_logger(__name__)
log.setLevel(logging.DEBUG) # FIXME: set level via config


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

    def _process_task_input(self, port:node_ports.Port, input_ports:Dict):
        # pylint: disable=too-many-branches
        port_name = port.key
        port_value = wrap_async_call(port.get())
        log.debug("PROCESSING %s %s", port_name, port_value)
        log.debug(type(port_value))
        if str(port.type).startswith("data:"):
            path = port_value
            if not path is None:
                input_ports[port_name] = str(port_value)
                final_path = Path(self._executor.in_dir, port_name)
                shutil.move(str(path), str(final_path))
                log.debug("DONWLOAD successfull %s", port_name)
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
        PORTS = node_ports.ports()
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
            self._docker.client.login(registry=self._docker.registry,
                username=self._docker.registry_user, password=self._docker.registry_pwd)
            log.debug('img %s tag %s', self._docker.image_name, self._docker.image_tag)
            self._docker.client.images.pull(self._docker.image_name, tag=self._docker.image_tag)
        except docker.errors.APIError:
            log.exception("Pulling image failed")
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
                        log.debug('PROGRESS %s', progress)
                    elif "percent done" in clean_line.lower():
                        progress = clean_line.lower().rstrip("percent done")
                        try:
                            float_progress = float(progress) / 100.0
                            progress = str(float_progress)
                            self._progress(channel, progress)
                            log.debug('PROGRESS %s', progress)
                        except ValueError:
                            log.exception("Could not extract progress from solver")
                            self._log(channel, clean_line)
                    else:
                        self._log(channel, clean_line)
                        log.debug('LOG %s', clean_line)

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
        PORTS = node_ports.ports()
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
                        port_key = name
                        wrap_async_call(PORTS.outputs[port_key].set(Path(filepath)))

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
                    object_name = str(self._task.project_id) + "/" + self._task.node_id + "/log/" + name
                    if not self._s3.client.upload_file(self._s3.bucket, object_name, filepath):
                        log.error("Error uploading file to S3")

    def initialize(self, task, user_id):
        self._task = task

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

        # config nodeports
        node_ports.node_config.USER_ID = user_id
        node_ports.node_config.NODE_UUID = task.node_id        

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

        try:
            docker_image = self._docker.image_name + ":" + self._docker.image_tag
            self._docker.client.containers.run(docker_image, "run",
                 detach=False, remove=True,
                 volumes = {'services_input'  : {'bind' : '/input'},
                            'services_output' : {'bind' : '/output'},
                            'services_log'    : {'bind'  : '/log'}},
                 environment=self._docker.env)
        except docker.errors.ContainerError as _e:
            log.error("Run container returned non zero exit code")
        except docker.errors.ImageNotFound as _e:
            log.error("Run container: Image not found")
        except docker.errors.APIError as _e:
            log.error("Run Container: Server returns error")


        time.sleep(1)
        self._executor.run_pool = False
        while not fut.done():
            time.sleep(0.1)

        log.debug('DONE Processing Pipeline %s and node %s from container', self._task.project_id, self._task.internal_id)

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
        # import pdb; pdb.set_trace()
        next_task_nodes = []
        do_run = False

        try:
            _session = self._db.Session()
            _pipeline =_session.query(ComputationalPipeline).filter_by(project_id=project_id).one()

            graph = _pipeline.execution_graph
            if node_id:
                do_process = True
                # find the for the current node_id, skip if there is already a job_id around
                # pylint: disable=assignment-from-no-return
                query =_session.query(ComputationalTask).filter(and_(ComputationalTask.node_id==node_id,
                    ComputationalTask.project_id==project_id, ComputationalTask.job_id==None))
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

        except exc.SQLAlchemyError:
            log.exception("DB error")
            _session.rollback()

        finally:
            _session.close()

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
