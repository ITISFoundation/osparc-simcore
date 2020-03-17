# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from typing import Dict

import pytest
import sqlalchemy as sa
import tenacity
from sqlalchemy.orm import sessionmaker

from s3wrapper import s3_client
from servicelib.minio_utils import MinioRetryPolicyUponInitialization
from simcore_postgres_database.models.base import metadata
from utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def minio_config(docker_stack: Dict, devel_environ: Dict) -> Dict[str, str]:
    assert "ops_minio" in docker_stack["ops"]

    config = {
        "endpoint": f"127.0.0.1:{get_service_published_port('minio', devel_environ['S3_ENDPOINT'].split(':')[1])}",
        "access_key": devel_environ["S3_ACCESS_KEY"],
        "secret_key": devel_environ["S3_SECRET_KEY"],
        "bucket_name": devel_environ["S3_BUCKET_NAME"],
        "secure": devel_environ["S3_SECURE"],
    }
    # nodeports takes its configuration from env variables
    for key, value in config.items():
        os.environ[f"S3_{key.upper()}"] = value

    return config


@pytest.fixture(scope="module")
def minio_service(minio_config: Dict[str, str], docker_stack: Dict) -> s3_client:
    assert wait_till_minio_responsive(minio_config)

    client = s3_client(**minio_config)

    yield client


@tenacity.retry(**MinioRetryPolicyUponInitialization().kwargs)
def wait_till_minio_responsive(minio_config: Dict[str, str]) -> bool:
    """Check if something responds to ``url`` """
    s3_client(**minio_config)
    if s3_client.create_bucket("pytest"):
        s3_client.remove_bucket("pytest")
        return True
    return False
