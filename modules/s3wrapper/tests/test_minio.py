import requests
import pytest

# pylint:disable=unused-import
from pytest_docker import docker_ip, docker_services

# pylint:disable=redefined-outer-name

def is_responsive(url, code=200):
    """Check if something responds to ``url``."""
    try:
        response = requests.get(url)
        if response.status_code == code:
            return True
    except requests.exceptions.RequestException as _e:
        pass
    
    return False

@pytest.mark.enable_travis
def test_minio(docker_ip, docker_services):
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

    