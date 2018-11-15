import logging
import os
import socket
from typing import Dict

import docker
import pytest
import requests
import tenacity

from s3wrapper.s3_client import S3Client

log = logging.getLogger(__name__)

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
def external_minio()->Dict:
    client = docker.from_env()
    minio_config = {"host":_get_ip(), "port":9001, "s3access":"s3access", "s3secret":"s3secret"}
    container = client.containers.run("minio/minio:latest", command="server /data", 
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

@pytest.fixture(scope="session")
def s3_client(external_minio:Dict)->S3Client: # pylint:disable=redefined-outer-name
    s3_endpoint = "{}:{}".format(external_minio["host"], external_minio["port"])
    yield S3Client(s3_endpoint, external_minio["s3access"], external_minio["s3secret"], False)
    # tear down

@pytest.fixture(scope="session")
def bucket(s3_client:S3Client)->str: # pylint: disable=W0621
    bucket_name = "simcore-test"
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)
    # set env variables
    os.environ["S3_BUCKET_NAME"] = bucket_name
    yield bucket_name

    s3_client.remove_bucket(bucket_name, delete_contents=True)
