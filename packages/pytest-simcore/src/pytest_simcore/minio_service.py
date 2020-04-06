# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from distutils.util import strtobool
from typing import Dict

import pytest
import tenacity

from s3wrapper.s3_client import S3Client
from servicelib.minio_utils import MinioRetryPolicyUponInitialization

from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def minio_config(docker_stack: Dict, devel_environ: Dict) -> Dict[str, str]:
    assert "ops_minio" in docker_stack["services"]

    # NOTE: 172.17.0.1 is the docker0 interface, which redirect from inside a
    # container onto the host network interface.
    config = {
        "client": {
            "endpoint": f"172.17.0.1:{get_service_published_port('minio', devel_environ['S3_ENDPOINT'].split(':')[1])}",
            "access_key": devel_environ["S3_ACCESS_KEY"],
            "secret_key": devel_environ["S3_SECRET_KEY"],
            "secure": strtobool(devel_environ["S3_SECURE"]) != 0,
        },
        "bucket_name": devel_environ["S3_BUCKET_NAME"],
    }

    # nodeports takes its configuration from env variables
    for key, value in config["client"].items():
        os.environ[f"S3_{key.upper()}"] = str(value)
    os.environ[f"S3_SECURE"] = devel_environ["S3_SECURE"]
    os.environ[f"S3_BUCKET_NAME"] = devel_environ["S3_BUCKET_NAME"]

    return config


@pytest.fixture(scope="module")
def minio_service(minio_config: Dict[str, str], docker_stack: Dict) -> S3Client:
    assert wait_till_minio_responsive(minio_config)

    client = S3Client(**minio_config["client"])
    assert client.create_bucket(minio_config["bucket_name"])

    yield client

    assert client.remove_bucket(minio_config["bucket_name"], delete_contents=True)


@tenacity.retry(**MinioRetryPolicyUponInitialization().kwargs)
def wait_till_minio_responsive(minio_config: Dict[str, str]) -> bool:
    """Check if something responds to ``url`` """
    client = S3Client(**minio_config["client"])
    if client.create_bucket("pytest"):
        client.remove_bucket("pytest")
        return True
    raise Exception(f"Minio not responding to {minio_config}")


@pytest.fixture(scope="module")
def bucket(minio_config: Dict[str, str], minio_service: S3Client) -> str:
    bucket_name = minio_config["bucket_name"]
    minio_service.create_bucket(bucket_name, delete_contents_if_exists=True)
    yield bucket_name

    minio_service.remove_bucket(bucket_name, delete_contents=True)
