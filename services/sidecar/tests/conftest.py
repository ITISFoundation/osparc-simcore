# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=W0621
import asyncio
import os
import subprocess
import sys
import uuid
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from random import randrange

import pytest
from aiopg.sa import create_engine

import sidecar
# from simcore_service_storage.datcore_wrapper import DatcoreWrapper
# from simcore_service_storage.dsm import DataStorageManager
# from simcore_service_storage.models import FileMetaData

import utils
from utils import (ACCESS_KEY, BUCKET_NAME, DATABASE, PASS, RABBIT_PWD,
                    RABBIT_USER, SECRET_KEY, USER)

# fixtures -------------------------------------------------------

@pytest.fixture(scope='session')
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope='session')
def docker_compose_file(here):
    """ Overrides pytest-docker fixture
    """
    old = os.environ.copy()

    # docker-compose reads these environs
    os.environ['POSTGRES_DB']=DATABASE
    os.environ['POSTGRES_USER']=USER
    os.environ['POSTGRES_PASSWORD']=PASS
    os.environ['POSTGRES_ENDPOINT']="FOO" # TODO: update config schema!!
    os.environ['MINIO_ACCESS_KEY']=ACCESS_KEY
    os.environ['MINIO_SECRET_KEY']=SECRET_KEY
    os.environ['RABBITMQ_USER']=RABBIT_USER
    os.environ['RABBITMQ_PASSWORD']=RABBIT_PWD


    dc_path = here / 'docker-compose.yml'

    assert dc_path.exists()
    yield str(dc_path)

    os.environ = old

@pytest.fixture(scope='session')
def postgres_service(docker_services, docker_ip):
    url = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
        user = USER,
        password = PASS,
        database = DATABASE,
        host=docker_ip,
        port=docker_services.port_for('postgres', 5432),
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: utils.is_postgres_responsive(url),
        timeout=30.0,
        pause=0.1,
    )

    postgres_service = {
        'user' : USER,
        'password' : PASS,
        'database' : DATABASE,
        'host' : docker_ip,
        'port' : docker_services.port_for('postgres', 5432)
    }
    # set env var here that is explicitly used from sidecar
    os.environ['POSTGRES_ENDPOINT'] = "{host}:{port}".format(host=docker_ip, port=docker_services.port_for('postgres', 5432))
    return postgres_service

@pytest.fixture(scope='session')
def rabbit_service(docker_services, docker_ip):
    # set env var here that is explicitly used from sidecar
    os.environ['RABBITMQ_HOST'] = "{host}".format(host=docker_ip)
    os.environ['RABBITMQ_PORT'] = "{port}".format(port=docker_services.port_for('rabbit', 15672))

    rabbit_service = "dummy"
    return rabbit_service

@pytest.fixture(scope='session')
def postgres_service_url(postgres_service, docker_services, docker_ip):
    postgres_service_url = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
        user = USER,
        password = PASS,
        database = DATABASE,
        host=docker_ip,
        port=docker_services.port_for('postgres', 5432),
    )

    return postgres_service_url

@pytest.fixture(scope='function')
async def postgres_engine(loop, postgres_service_url):
    postgres_engine = await create_engine(postgres_service_url)

    yield postgres_engine

    if postgres_engine:
        postgres_engine.close()
        await postgres_engine.wait_closed()


@pytest.fixture(scope='session')
def minio_service(docker_services, docker_ip):

   # Build URL to service listening on random port.
    url = 'http://%s:%d/' % (
        docker_ip,
        docker_services.port_for('minio', 9000),
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: utils.is_responsive(url, 403),
        timeout=30.0,
        pause=0.1,
    )

    os.environ['S3_BUCKET_NAME'] = "simcore-testing"
    os.environ['S3_ENDPOINT'] = '{ip}:{port}'.format(ip=docker_ip, port=docker_services.port_for('minio', 9000))
    os.environ['S3_ACCESS_KEY'] = ACCESS_KEY
    os.environ['S3_SECRET_KEY'] = SECRET_KEY

    return {
        'endpoint': '{ip}:{port}'.format(ip=docker_ip, port=docker_services.port_for('minio', 9000)),
        'access_key': ACCESS_KEY,
        'secret_key' : SECRET_KEY,
        }

@pytest.fixture(scope="module")
def s3_client(minio_service):
    from s3wrapper.s3_client import S3Client

    s3_client = S3Client(**minio_service)
    return s3_client


@pytest.fixture(scope="module")
def sidecar_platform_fixture(s3_client, postgres_service_url, rabbit_service):
    sidecar_platform_fixture = 1

    return sidecar_platform_fixture
