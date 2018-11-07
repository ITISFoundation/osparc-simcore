import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor

import docker
import tenacity
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import sessionmaker

from s3wrapper.s3_client import S3Client
from simcore_sdk.config.db import Config as db_config
from simcore_sdk.config.docker import Config as docker_config
from simcore_sdk.config.rabbit import Config as rabbit_config
from simcore_sdk.config.s3 import Config as s3_config
from simcore_sdk.models.pipeline_models import (
    SUCCESS,
    ComputationalTask
)


def delete_contents(folder):
    for _fname in os.listdir(folder):
        file_path = os.path.join(folder, _fname)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except (OSError, IOError):
            logging.exception("Could not delete files")

def find_entry_point(g):
    result = []
    for node in g.nodes:
        if len(list(g.predecessors(node))) == 0:
            result.append(node)
    return result

def is_node_ready(task, graph, _session, _logger):
    tasks = _session.query(ComputationalTask).filter(and_(
        ComputationalTask.node_id.in_(list(graph.predecessors(task.node_id))),
        ComputationalTask.project_id==task.project_id)).all()
    _logger.debug("TASK %s ready? Checking ..", task.internal_id)
    for dep_task in tasks:
        job_id = dep_task.job_id
        if not job_id:
            return False
        _logger.debug("TASK %s DEPENDS ON %s with stat %s", task.internal_id, dep_task.internal_id,dep_task.state)
        if not dep_task.state == SUCCESS:
            return False
    _logger.debug("TASK %s is ready", task.internal_id)
    return True

class DockerSettings:
    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self._config = docker_config()
        self.client = docker.from_env()
        self.registry = self._config.registry
        self.registry_name = self._config.registry_name
        self.registry_user = self._config.user
        self.registry_pwd = self._config.pwd
        self.image_name = ""
        self.image_tag = ""
        self.env = []


class S3Settings:
    def __init__(self):
        self._config = s3_config()
        self.client = S3Client(endpoint=self._config.endpoint,
            access_key=self._config.access_key, secret_key=self._config.secret_key)
        self.bucket = self._config.bucket_name

        self.__create_bucket()

    @tenacity.retry(wait=tenacity.wait_fixed(2), stop=tenacity.stop_after_attempt(15))
    def __create_bucket(self):
        self.client.create_bucket(self.bucket)


class RabbitSettings:
    def __init__(self):
        self._pika = rabbit_config()
        self.parameters = self._pika.parameters
        self.log_channel = self._pika.log_channel
        self.progress_channel = self._pika.progress_channel

class DbSettings:
    def __init__(self):
        self._db_config = db_config()
        self.db = create_engine(self._db_config.endpoint, client_encoding='utf8', pool_pre_ping=True)
        self.Session = sessionmaker(self.db, expire_on_commit=False)
        #self.session = self.Session()

class ExecutorSettings:
    def __init__(self):
        # Pool
        self.pool = ThreadPoolExecutor(1)
        self.run_pool = False

        # shared folders
        self.in_dir = ""
        self.out_dir = ""
        self.log_dir = ""
