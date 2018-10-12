import docker
import pytest

@pytest.fixture(scope="session")
def docker_swarm(): #pylint: disable=W0613, W0621
    client = docker.from_env()
    assert client is not None
    client.swarm.init()

    yield client

    # teardown
    assert client.swarm.leave(force=True) == True
