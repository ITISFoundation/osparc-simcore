import subprocess
from pathlib import Path

import docker
import pytest
import yaml


@pytest.fixture(scope='session')
def docker_client():
    client = docker.from_env()
    yield client

@pytest.fixture(scope='module')
def docker_swarm(docker_client):
    docker_client.swarm.init()
    yield
    # teardown
    assert docker_client.swarm.leave(force=True) == True

@pytest.fixture(scope='module')
def docker_stack(docker_swarm, docker_client, docker_compose_file: Path, tools_docker_compose_file: Path):
    docker_compose_ignore_file = docker_compose_file.parent / "docker-compose.ignore.yml"
    assert subprocess.run(
            "docker-compose -f {} -f {} config > {}".format(docker_compose_file.name, tools_docker_compose_file.name, docker_compose_ignore_file.name),
            shell=True,
            cwd=docker_compose_file.parent
        ).returncode == 0
    assert subprocess.run(
            "docker stack deploy -c {} services".format(docker_compose_ignore_file.name),
            shell=True,
            cwd=docker_compose_file.parent
        ).returncode == 0

    with docker_compose_ignore_file.open() as fp:
        docker_stack_cfg = yaml.safe_load(fp)
        yield docker_stack_cfg

    # clean up
    assert subprocess.run("docker stack rm services", shell=True).returncode == 0
    docker_compose_ignore_file.unlink()
