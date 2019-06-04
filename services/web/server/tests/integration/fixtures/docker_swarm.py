# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

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
    assert docker_client.swarm.leave(force=True)

import time

@pytest.fixture(scope='module')
def docker_stack(docker_swarm, docker_client, docker_compose_file: Path, tools_docker_compose_file: Path):
    docker_compose_ignore_file = docker_compose_file.parent / "docker-compose.ignore.yml"

    cmd = "docker-compose -f {} -f {} config > {}".format(docker_compose_file.name, tools_docker_compose_file.name, docker_compose_ignore_file.name)
    process = subprocess.run(
            cmd,
            shell=True,
            cwd=docker_compose_file.parent
        )
    assert process.returncode == 0, "Error in '{}'".format(cmd)

    cmd = "docker stack deploy -c {} services".format(docker_compose_ignore_file.name)
    process = subprocess.run(
            cmd,
            shell=True,
            cwd=docker_compose_file.parent
        )
    assert process.returncode == 0, "Error in '{}'".format(cmd)


    def _print_services():
        from pprint import pprint
        print("{:*^100}".format("docker services list"))
        for service in docker_client.services.list():
            pprint(service.attrs)
        print("-"*100)

    with docker_compose_ignore_file.open() as fp:
        docker_stack_cfg = yaml.safe_load(fp)

    _print_services()

    yield docker_stack_cfg

    _print_services()

    # clean up
    assert subprocess.run("docker stack rm services", shell=True).returncode == 0


    # """
    # docker stack rm services

    # until [ -z "$(docker service ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ]; do
    # sleep 1;
    # done

    # until [ -z "$(docker network ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ]; do
    # sleep 1;
    # done
    # """

    while docker_client.services.list(filters={"label":"com.docker.stack.namespace=services"}):
        time.sleep(1)

    while docker_client.networks.list(filters={"label":"com.docker.stack.namespace=services"}):
        time.sleep(1)

    docker_compose_ignore_file.unlink()

    _print_services()
