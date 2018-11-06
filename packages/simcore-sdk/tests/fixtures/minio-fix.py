import pytest
import requests
import os

from pytest_docker import docker_ip, docker_services # pylint:disable=unused-import

from s3wrapper.s3_client import S3Client


def is_responsive(url, code=200):
    """Check if something responds to ``url``."""
    try:
        response = requests.get(url)
        if response.status_code == code:
            return True
    except requests.exceptions.RequestException as _e:
        pass
    return False

@pytest.fixture(scope="module")
def s3_client(docker_ip, docker_services): # pylint:disable=redefined-outer-name
    """wait for minio to be up"""

    # Build URL to service listening on random port.
    url = 'http://%s:%d/' % (
        docker_ip,
        docker_services.port_for('minio', 9000),
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_responsive(url, 403),
        timeout=30.0,
        pause=0.1,
    )

    # Contact the service.
    response = requests.get(url)
    assert response.status_code == 403
    
    endpoint = '{ip}:{port}'.format(ip=docker_ip, port=docker_services.port_for('minio', 9000))
    access_key = "s3access"
    secret_key = "s3secret"
    os.environ["S3_ENDPOINT"] = endpoint
    os.environ["S3_ACCESS_KEY"] = "s3access"
    os.environ["S3_SECRET_KEY"] = "s3secret"
    secure = False
    yield S3Client(endpoint, access_key, secret_key, secure)

@pytest.fixture()
def bucket(s3_client): # pylint: disable=W0621
    os.environ["S3_BUCKET_NAME"] = "simcore-test"
    bucket_name = "simcore-test"
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)
    yield bucket_name

    s3_client.remove_bucket(bucket_name, delete_contents=True)