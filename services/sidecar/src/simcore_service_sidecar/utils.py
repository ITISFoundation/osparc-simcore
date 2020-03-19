import asyncio
import logging
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import List, Tuple

import docker
import networkx as nx
import pika
import tenacity
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import sessionmaker

from s3wrapper.s3_client import S3Client
from simcore_sdk.config.db import Config as db_config
from simcore_sdk.config.docker import Config as docker_config
from simcore_sdk.config.rabbit import Config as rabbit_config
from simcore_sdk.config.s3 import Config as s3_config
from simcore_sdk.models.pipeline_models import SUCCESS, ComputationalTask


def wrap_async_call(fct: asyncio.coroutine):
    return asyncio.get_event_loop().run_until_complete(fct)


def delete_contents(folder: Path):
    for _fname in os.listdir(folder):
        file_path = os.path.join(folder, _fname)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except (OSError, IOError):
            logging.exception("Could not delete files")


def find_entry_point(g: nx.DiGraph) -> List:
    result = []
    for node in g.nodes:
        if len(list(g.predecessors(node))) == 0:
            result.append(node)
    return result


def is_node_ready(task, graph, _session, _logger):
    #pylint: disable=no-member
    tasks = _session.query(ComputationalTask).filter(and_(
        ComputationalTask.node_id.in_(list(graph.predecessors(task.node_id))),
        ComputationalTask.project_id == task.project_id)).all()

    _logger.debug("TASK %s ready? Checking ..", task.internal_id)
    for dep_task in tasks:
        job_id = dep_task.job_id
        if not job_id:
            return False
        _logger.debug("TASK %s DEPENDS ON %s with stat %s",
                      task.internal_id, dep_task.internal_id, dep_task.state)
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
                               access_key=self._config.access_key, secret_key=self._config.secret_key, secure=self._config.secure)
        self.bucket = self._config.bucket_name

        # self.__create_bucket()

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
        self.db = create_engine(
            self._db_config.endpoint +
            f"?application_name={__name__}_{id(self)}",
            client_encoding='utf8',
            pool_pre_ping=True)
        self.Session = sessionmaker(self.db, expire_on_commit=False)
        #self.session = self.Session()


class ExecutorSettings:
    def __init__(self):
        # shared folders
        self.in_dir: Path = ""
        self.out_dir: Path = ""
        self.log_dir: Path = ""


@contextmanager
def safe_channel(rabbit_settings: RabbitSettings) -> Tuple[pika.channel.Channel, pika.adapters.BlockingConnection]:
    try:
        connection = pika.BlockingConnection(rabbit_settings.parameters)
        channel = connection.channel()
        channel.exchange_declare(
            exchange=rabbit_settings.log_channel, exchange_type='fanout', auto_delete=True)
        channel.exchange_declare(
            exchange=rabbit_settings.progress_channel, exchange_type='fanout', auto_delete=True)
        yield channel, connection
    finally:
        connection.close()
