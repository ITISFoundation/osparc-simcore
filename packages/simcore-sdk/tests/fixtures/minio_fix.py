# pylint: disable=redefined-outer-name

import logging
import os
import socket
import sys
from pathlib import Path
from typing import Dict

import docker
import pytest
import requests
import tenacity
import yaml
from s3wrapper.s3_client import S3Client

log = logging.getLogger(__name__)
here = Path(sys.argv[0] if __name__=="__main__" else __file__ ).resolve().parent

@tenacity.retry(wait=tenacity.wait_fixed(2), stop=tenacity.stop_after_delay(10))
def _minio_is_responsive(url:str, code:int=403) ->bool:
    """Check if something responds to ``url`` syncronously"""
    try:
        response = requests.get(url)
        if response.status_code == code:
            log.info("minio is up and running")
            return True
    except requests.exceptions.RequestException as _e:
        pass

    return False

def _get_ip()->str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception: #pylint: disable=W0703
        IP = '127.0.0.1'
    finally:
        s.close()
    log.info("minio is set up to run on IP %s", IP)
    return IP


@pytest.fixture(scope="session")
def repo_folder_path():
    MAX_ITERATIONS = 7

    repo_path, n = here.parent, 0
    while not any(repo_path.glob(".git")) and n<MAX_ITERATIONS:
        repo_path = repo_path.parent
        n+=1
    assert n<MAX_ITERATIONS, f"Could not find repo_folder_path, got until '{repo_path}'"
    return repo_path


@pytest.fixture(scope="session")
def minio_image_name(repo_folder_path):
    """ Ensures it uses same image as defined in services/docker-compose.yml """
    DEFAULT_IMAGE = "minio/minio:latest"

    with open(repo_folder_path / "services" / "docker-compose-ops.yml") as fh:
        image_name = yaml.safe_load(fh) \
                .get('services', {})    \
                .get('minio', {})       \
                .get('image', DEFAULT_IMAGE)
    return image_name


@pytest.fixture(scope="module")
def external_minio(minio_image_name)->Dict:
    client = docker.from_env()
    minio_config = {"host":_get_ip(), "port":9001, "s3access":"s3access", "s3secret":"s3secret"}
    container = client.containers.run(minio_image_name, command="server /data",
                                        environment=["".join(["MINIO_ACCESS_KEY=", minio_config["s3access"]]),
                                                    "".join(["MINIO_SECRET_KEY=", minio_config["s3secret"]])],
                                        ports={'9000':minio_config["port"]},
                                        detach=True)
    url = "http://{}:{}".format(minio_config["host"], minio_config["port"])
    _minio_is_responsive(url)

    # set up env variables
    os.environ["S3_ENDPOINT"] = "{}:{}".format(minio_config["host"], minio_config["port"])
    os.environ["S3_ACCESS_KEY"] = minio_config["s3access"]
    os.environ["S3_SECRET_KEY"] = minio_config["s3secret"]
    log.info("env variables for accessing S3 set")

    # return the host, port to minio
    yield minio_config
    # tear down
    log.info("tearing down minio container")
    container.remove(force=True)

@pytest.fixture(scope="module")
def s3_client(external_minio:Dict)->S3Client: # pylint:disable=redefined-outer-name
    s3_endpoint = "{}:{}".format(external_minio["host"], external_minio["port"])
    yield S3Client(s3_endpoint, external_minio["s3access"], external_minio["s3secret"], False)
    # tear down

@pytest.fixture(scope="module")
def bucket(s3_client:S3Client)->str: # pylint: disable=W0621
    bucket_name = "simcore-test"
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)
    # set env variables
    os.environ["S3_BUCKET_NAME"] = bucket_name
    yield bucket_name

    s3_client.remove_bucket(bucket_name, delete_contents=True)
