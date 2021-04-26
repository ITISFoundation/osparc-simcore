# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from distutils.util import strtobool
from typing import Dict, Iterator

import pytest
import tenacity
from minio import Minio

from .helpers.utils_docker import get_ip, get_service_published_port

log = logging.getLogger(__name__)


def _remove_bucket(client: Minio, bucket_name: str):
    if client.bucket_exists(bucket_name):
        # remove content
        objs = client.list_objects(bucket_name, prefix=None, recursive=True)
        errors = client.remove_objects(bucket_name, [o.object_name for o in objs])
        assert not list(errors)
        # remove bucket
        client.remove_bucket(bucket_name)
    assert not client.bucket_exists(bucket_name)


@pytest.fixture(scope="module")
def minio_config(
    docker_stack: Dict, devel_environ: Dict, monkeypatch_module
) -> Dict[str, str]:
    assert "ops_minio" in docker_stack["services"]

    config = {
        "client": {
            "endpoint": f"{get_ip()}:{get_service_published_port('minio')}",
            "access_key": devel_environ["S3_ACCESS_KEY"],
            "secret_key": devel_environ["S3_SECRET_KEY"],
            "secure": strtobool(devel_environ["S3_SECURE"]) != 0,
        },
        "bucket_name": devel_environ["S3_BUCKET_NAME"],
    }

    # nodeports takes its configuration from env variables
    for key, value in config["client"].items():
        monkeypatch_module.setenv(f"S3_{key.upper()}", str(value))

    monkeypatch_module.setenv("S3_SECURE", devel_environ["S3_SECURE"])
    monkeypatch_module.setenv("S3_BUCKET_NAME", config["bucket_name"])

    return config


@pytest.fixture(scope="module")
def minio_service(minio_config: Dict[str, str]) -> Iterator[Minio]:
    assert wait_till_minio_responsive(minio_config)

    client = Minio(**minio_config["client"])

    bucket_name = minio_config["bucket_name"]

    assert not client.bucket_exists(bucket_name)
    client.make_bucket(bucket_name)
    assert client.bucket_exists(bucket_name)

    yield client

    assert client.bucket_exists(bucket_name)
    _remove_bucket(client, bucket_name)


@tenacity.retry(
    wait=tenacity.wait_fixed(5),
    stop=tenacity.stop_after_attempt(60),
    before_sleep=tenacity.before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def wait_till_minio_responsive(minio_config: Dict[str, str]) -> bool:
    client = Minio(**minio_config["client"])
    # TODO: improve as https://docs.min.io/docs/minio-monitoring-guide.html
    if not client.bucket_exists("pytest"):
        client.make_bucket("pytest")
    client.remove_bucket("pytest")
    return True


@pytest.fixture(scope="module")
def bucket(minio_config: Dict[str, str], minio_service: Minio) -> str:
    bucket_name = minio_config["bucket_name"]

    _remove_bucket(minio_service, bucket_name)
    minio_service.make_bucket(bucket_name)

    yield bucket_name

    _remove_bucket(minio_service, bucket_name)
