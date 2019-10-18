# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import subprocess
import time
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


@pytest.fixture(scope='module')
def docker_stack(docker_swarm, docker_client, docker_compose_file: Path, ops_docker_compose_file: Path):
    stacks = ['simcore', 'tools' ]

    # make up-version
    subprocess.run( f"docker stack deploy -c {docker_compose_file.name} {stacks[0]}",
        shell=True, check=True,
        cwd=docker_compose_file.parent)
    subprocess.run( f"docker stack deploy -c {ops_docker_compose_file.name} {stacks[1]}",
        shell=True, check=True,
        cwd=ops_docker_compose_file.parent)

    def _print_services(msg):
        from pprint import pprint
        print("{:*^100}".format("docker services running " + msg))
        for service in docker_client.services.list():
            pprint(service.attrs)
        print("-"*100)

    _print_services("[BEFORE TEST]")

    yield {
        'stacks':stacks,
        'services': [service.name for service in docker_client.services.list()]
    }

    _print_services("[AFTER TEST]")

    # clean up. Guarantees that all services are down before creating a new stack!
    #
    # WORKAROUND https://github.com/moby/moby/issues/30942#issue-207070098
    #
    # docker stack rm services

    # until [ -z "$(docker service ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ]; do
    # sleep 1;
    # done

    # until [ -z "$(docker network ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ]; do
    # sleep 1;
    # done

    # make down
    for stack in stacks:
        subprocess.run(f"docker stack rm {stack}", shell=True, check=True)

        while docker_client.services.list(filters={"label":f"com.docker.stack.namespace={stack}"}):
            time.sleep(1)

        while docker_client.networks.list(filters={"label":f"com.docker.stack.namespace={stack}"}):
            time.sleep(1)

    _print_services("[AFTER REMOVED]")
