# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from typing import Any, Iterator

import pytest
from minio import Minio
from minio.datatypes import Object
from minio.deleteobjects import DeleteError, DeleteObject
from pydantic import parse_obj_as
from pytest import MonkeyPatch
from tenacity import Retrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from .helpers.utils_docker import get_localhost_ip, get_service_published_port

log = logging.getLogger(__name__)


def _ensure_remove_bucket(client: Minio, bucket_name: str):
    if client.bucket_exists(bucket_name):
        # remove content
        objs: Iterator[Object] = client.list_objects(
            bucket_name, prefix=None, recursive=True
        )

        # FIXME: minio 7.1.0 does NOT remove all objects!? Added in requirements/constraints.txt
        to_delete = [DeleteObject(o.object_name) for o in objs]
        errors: Iterator[DeleteError] = client.remove_objects(bucket_name, to_delete)

        list_of_errors = list(errors)
        assert not any(list_of_errors), list(list_of_errors)

        # remove bucket
        client.remove_bucket(bucket_name)

    assert not client.bucket_exists(bucket_name)


@pytest.fixture(scope="module")
def minio_config(
    docker_stack: dict, testing_environ_vars: dict, monkeypatch_module: MonkeyPatch
) -> dict[str, Any]:
    assert "pytest-ops_minio" in docker_stack["services"]

    config = {
        "client": {
            "endpoint": f"{get_localhost_ip()}:{get_service_published_port('minio')}",
            "access_key": testing_environ_vars["S3_ACCESS_KEY"],
            "secret_key": testing_environ_vars["S3_SECRET_KEY"],
            "secure": parse_obj_as(bool, testing_environ_vars["S3_SECURE"]),
        },
        "bucket_name": testing_environ_vars["S3_BUCKET_NAME"],
    }

    # nodeports takes its configuration from env variables
    for key, value in config["client"].items():
        monkeypatch_module.setenv(f"S3_{key.upper()}", str(value))

    monkeypatch_module.setenv("S3_SECURE", testing_environ_vars["S3_SECURE"])
    monkeypatch_module.setenv("S3_BUCKET_NAME", config["bucket_name"])

    return config


@pytest.fixture(scope="module")
def minio_service(minio_config: dict[str, str]) -> Iterator[Minio]:

    client = Minio(**minio_config["client"])

    for attempt in Retrying(
        wait=wait_fixed(5),
        stop=stop_after_attempt(60),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    ):
        with attempt:
            # TODO: improve as https://docs.min.io/docs/minio-monitoring-guide.html
            if not client.bucket_exists("pytest"):
                client.make_bucket("pytest")
            client.remove_bucket("pytest")

    bucket_name = minio_config["bucket_name"]

    # cleans up in case a failing tests left this bucket
    _ensure_remove_bucket(client, bucket_name)

    client.make_bucket(bucket_name)
    assert client.bucket_exists(bucket_name)

    yield client

    # cleanup upon tear-down
    _ensure_remove_bucket(client, bucket_name)


@pytest.fixture
def bucket(minio_config: dict[str, str], minio_service: Minio) -> Iterator[str]:
    bucket_name = minio_config["bucket_name"]

    _ensure_remove_bucket(minio_service, bucket_name)
    minio_service.make_bucket(bucket_name)

    yield bucket_name

    _ensure_remove_bucket(minio_service, bucket_name)
